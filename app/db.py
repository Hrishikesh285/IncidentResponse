"""MongoDB access layer with automatic fallback to a local JSON store.

All database operations live here. If MongoDB is unreachable at first use,
OpsMemory seamlessly switches to app.local_store so the demo still runs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app import local_store
from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_use_local: Optional[bool] = None


def _probe_mongo() -> bool:
    """Return True if MongoDB is reachable."""
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        global _client
        _client = client
        logger.info("MongoDB connected at %s", settings.mongo_uri)
        return True
    except Exception as exc:
        logger.warning("MongoDB unavailable (%s) — using local JSON store", exc)
        return False


def using_local() -> bool:
    """Whether the local JSON store is active."""
    global _use_local
    if _use_local is None:
        _use_local = not _probe_mongo()
    return _use_local


def get_client() -> MongoClient:
    """Return the singleton MongoClient, creating it on first call."""
    global _client
    if using_local():
        raise RuntimeError("MongoDB is unavailable; local store is active")
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    return _client


def get_collection() -> Collection:
    """Return the incidents collection."""
    return get_client()[settings.mongo_db]["incidents"]


def ensure_indexes() -> None:
    """Create useful indexes when using MongoDB."""
    if using_local():
        return
    try:
        col = get_collection()
        col.create_index("incident_id", unique=True)
        col.create_index([("created_at", -1)])
        col.create_index("status")
    except Exception as exc:
        logger.warning("Could not create indexes: %s", exc)


def list_incidents(limit: int = 500) -> List[dict]:
    """Return all incidents, newest first, with _id stripped."""
    if using_local():
        return local_store.list_incidents(limit)
    col = get_collection()
    docs = list(col.find({}, {"_id": 0}).sort("created_at", -1).limit(limit))
    return docs


def get_incident(incident_id: str) -> Optional[dict]:
    """Fetch a single incident by incident_id; return None if not found."""
    if using_local():
        return local_store.get_incident(incident_id)
    col = get_collection()
    return col.find_one({"incident_id": incident_id}, {"_id": 0})


def get_stats() -> dict:
    """Compute aggregate statistics over the incidents collection."""
    if using_local():
        stats = local_store.get_stats()
    else:
        col = get_collection()
        total = col.count_documents({})
        resolved = col.count_documents({"status": "resolved"})

        pipeline = [
            {"$match": {"status": "resolved", "resolution_minutes": {"$gt": 0}}},
            {"$group": {"_id": None, "avg": {"$avg": "$resolution_minutes"}}},
        ]
        agg = list(col.aggregate(pipeline))
        avg_min = round(agg[0]["avg"], 1) if agg else 0.0

        stats = {
            "total_incidents": total,
            "resolved": resolved,
            "avg_resolution_minutes": avg_min,
            "memories_retained": resolved,
        }

    # Enrich with storage backend so the UI/health can show mode
    stats["storage"] = "local" if using_local() else "mongodb"
    return stats


def next_incident_id() -> str:
    """Generate the next sequential incident ID (max existing + 1)."""
    if using_local():
        return local_store.next_incident_id()

    col = get_collection()
    # Prefer the highest INC-NNNN rather than count (safe after deletes)
    cursor = col.find({"incident_id": {"$regex": r"^INC-\d+$"}}, {"incident_id": 1, "_id": 0})
    max_n = 0
    for doc in cursor:
        try:
            max_n = max(max_n, int(doc["incident_id"].split("-", 1)[1]))
        except (KeyError, ValueError, IndexError):
            continue
    return f"INC-{max_n + 1:04d}"


def insert_incident(doc: dict) -> str:
    """Insert a new incident document and return its incident_id."""
    if using_local():
        return local_store.insert_incident(doc)
    col = get_collection()
    try:
        col.insert_one(doc)
    except PyMongoError as exc:
        logger.error("Mongo insert failed: %s", exc)
        raise
    return doc["incident_id"]


def resolve_incident(
    incident_id: str,
    root_cause: str,
    fix_steps: List[str],
    resolution_minutes: int,
) -> bool:
    """
    Mark an incident as resolved and populate resolution fields.

    Returns True if a document was updated, False if not found.
    """
    if using_local():
        return local_store.resolve_incident(
            incident_id, root_cause, fix_steps, resolution_minutes
        )
    col = get_collection()
    result = col.update_one(
        {"incident_id": incident_id},
        {
            "$set": {
                "status": "resolved",
                "root_cause": root_cause,
                "fix_steps": fix_steps,
                "resolution_minutes": resolution_minutes,
                "resolved_at": datetime.now(timezone.utc),
            }
        },
    )
    return result.matched_count > 0


def clear_incidents() -> int:
    """Delete all incident documents. Returns number deleted."""
    if using_local():
        return local_store.clear_incidents()
    col = get_collection()
    result = col.delete_many({})
    return result.deleted_count


def replace_all(docs: List[dict]) -> int:
    """Replace all incidents (seed helper)."""
    if using_local():
        return local_store.replace_all(docs)
    col = get_collection()
    col.delete_many({})
    if docs:
        col.insert_many(docs)
    return len(docs)
