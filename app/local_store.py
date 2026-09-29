"""File-backed local store used when MongoDB is unavailable.

Persists incidents as JSON under data/local_db.json so the demo works
without Docker. Same document shape as the MongoDB collection.
"""

from __future__ import annotations

import json
import logging
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "local_db.json"


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


def _deserialize(value: Any) -> Any:
    if isinstance(value, str):
        # ISO timestamps used by this app
        if len(value) >= 19 and value[4] == "-" and "T" in value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value
    if isinstance(value, list):
        return [_deserialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _deserialize(v) for k, v in value.items()}
    return value


def _load() -> List[dict]:
    if not _DB_PATH.exists():
        return []
    try:
        raw = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [_deserialize(doc) for doc in raw]
    except Exception as exc:
        logger.warning("Failed to load local store: %s", exc)
        return []


def _save(docs: List[dict]) -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [_serialize(doc) for doc in docs]
    _DB_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_incidents(limit: int = 500) -> List[dict]:
    with _LOCK:
        docs = _load()
        docs.sort(
            key=lambda d: d.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return [deepcopy(d) for d in docs[:limit]]


def get_incident(incident_id: str) -> Optional[dict]:
    with _LOCK:
        for doc in _load():
            if doc.get("incident_id") == incident_id:
                return deepcopy(doc)
        return None


def get_stats() -> dict:
    with _LOCK:
        docs = _load()
        total = len(docs)
        resolved_docs = [d for d in docs if d.get("status") == "resolved"]
        resolved = len(resolved_docs)
        mins = [d.get("resolution_minutes", 0) for d in resolved_docs if d.get("resolution_minutes", 0) > 0]
        avg_min = round(sum(mins) / len(mins), 1) if mins else 0.0
        return {
            "total_incidents": total,
            "resolved": resolved,
            "avg_resolution_minutes": avg_min,
            "memories_retained": resolved,
        }


def next_incident_id() -> str:
    with _LOCK:
        docs = _load()
        max_n = 0
        for doc in docs:
            iid = doc.get("incident_id") or ""
            if iid.startswith("INC-"):
                try:
                    max_n = max(max_n, int(iid.split("-", 1)[1]))
                except ValueError:
                    continue
        return f"INC-{max_n + 1:04d}"


def insert_incident(doc: dict) -> str:
    with _LOCK:
        docs = _load()
        docs.append(deepcopy(doc))
        _save(docs)
        return doc["incident_id"]


def resolve_incident(
    incident_id: str,
    root_cause: str,
    fix_steps: List[str],
    resolution_minutes: int,
) -> bool:
    with _LOCK:
        docs = _load()
        for doc in docs:
            if doc.get("incident_id") == incident_id:
                doc["status"] = "resolved"
                doc["root_cause"] = root_cause
                doc["fix_steps"] = list(fix_steps)
                doc["resolution_minutes"] = resolution_minutes
                doc["resolved_at"] = datetime.now(timezone.utc)
                _save(docs)
                return True
        return False


def clear_incidents() -> int:
    with _LOCK:
        docs = _load()
        count = len(docs)
        _save([])
        return count


def replace_all(docs: List[dict]) -> int:
    """Replace the entire store (used by seed/reset)."""
    with _LOCK:
        _save([deepcopy(d) for d in docs])
        return len(docs)
