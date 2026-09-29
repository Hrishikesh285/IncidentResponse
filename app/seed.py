"""Shared seed / reseed helpers used by scripts and the API reset endpoint."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from app import db, memory

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "incidents_seed.json"


def load_seed_incidents() -> List[dict]:
    if not SEED_FILE.exists():
        raise FileNotFoundError(
            f"Seed file not found: {SEED_FILE}. Run: python data/generate_incidents.py"
        )
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def seed_all(clear_first: bool = True, retain_remote: bool = True) -> dict:
    """
    Load seed incidents into storage and memory.

    Args:
        clear_first: Wipe existing incidents/memories before seeding.
        retain_remote: Also retain into Hindsight when configured.
    """
    incidents = load_seed_incidents()

    if clear_first:
        deleted = db.clear_incidents()
        try:
            memory.reset_bank()
        except Exception as exc:
            logger.warning("Memory bank reset during seed: %s", exc)
        logger.info("Cleared %d incidents before seed", deleted)

    # Persist all seed docs
    db.replace_all(incidents)

    # Always seed local memory so offline recall works
    local_count = memory.seed_local_from_incidents(incidents)

    ok_memory = local_count
    fail_memory = 0

    if retain_remote and not memory.using_local():
        ok_memory = 0
        for inc in incidents:
            try:
                memory.retain_incident(inc)
                ok_memory += 1
            except memory.MemoryUnavailableError as exc:
                fail_memory += 1
                logger.warning("Retain failed for %s: %s", inc.get("incident_id"), exc)

    result = {
        "seeded": len(incidents),
        "local_memories": local_count,
        "remote_retained": ok_memory if not memory.using_local() else 0,
        "remote_failed": fail_memory,
        "storage": "local" if db.using_local() else "mongodb",
        "memory_backend": memory.memory_backend(),
    }
    logger.info("Seed complete: %s", result)
    return result


def ensure_seeded() -> Optional[dict]:
    """If the store is empty and seed file exists, seed automatically."""
    stats = db.get_stats()
    if stats.get("total_incidents", 0) > 0:
        # Still ensure local memory is warm from resolved docs
        resolved = [i for i in db.list_incidents() if i.get("status") == "resolved"]
        if resolved and memory.using_local():
            memory.seed_local_from_incidents(resolved)
        return None
    if not SEED_FILE.exists():
        logger.warning("No seed file and empty DB — starting blank")
        return None
    return seed_all(clear_first=False, retain_remote=False)
