"""Agent orchestration — ties together memory recall and LLM diagnosis.

Two public functions:
  - analyze_incident(): recall → LLM → return analysis
  - resolve_incident(): update Mongo → retain into memory
"""

from __future__ import annotations

import logging
import time
from typing import List

from app import db, llm, memory

logger = logging.getLogger(__name__)


def analyze_incident(incident_text: str, use_memory: bool) -> dict:
    """
    Run the full analysis pipeline for a new incident.

    Steps:
      1. If use_memory, call recall_similar to get past incidents.
      2. Call the LLM with the incident text and recalled memories.
      3. Return combined result dict including latency.
    """
    t0 = time.monotonic()

    recalled: List[dict] = []
    if use_memory:
        recalled = memory.recall_similar(incident_text, top_k=3)

    diagnosis = llm.diagnose(incident_text, recalled)
    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    return {
        **diagnosis,
        "recalled_incidents": recalled,
        "memory_used": use_memory,
        "latency_ms": latency_ms,
        "llm_backend": llm.llm_backend(),
        "memory_backend": memory.memory_backend(),
    }


def resolve_incident(
    incident_id: str,
    root_cause: str,
    fix_steps: List[str],
    resolution_minutes: int,
) -> dict:
    """
    Mark an incident as resolved in Mongo and retain it into memory.

    Raises:
        ValueError: If no incident with the given ID exists.
    """
    updated = db.resolve_incident(incident_id, root_cause, fix_steps, resolution_minutes)
    if not updated:
        raise ValueError(f"Incident {incident_id} not found")

    doc = db.get_incident(incident_id)
    if doc is None:
        raise ValueError(f"Incident {incident_id} disappeared after update")

    memory_retained = False
    try:
        memory.retain_incident(doc)
        memory_retained = True
    except memory.MemoryUnavailableError as exc:
        logger.error("Could not retain memory for %s: %s", incident_id, exc)

    return {
        "success": True,
        "memory_retained": memory_retained,
        "incident_id": incident_id,
    }
