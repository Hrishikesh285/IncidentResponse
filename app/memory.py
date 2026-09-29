"""Hindsight memory integration — ALL Hindsight calls live here only.

Uses hindsight-client when API keys are configured; otherwise falls back
to app.local_memory so Memory ON still works offline / in demo mode.
"""

from __future__ import annotations

import logging
from typing import List

from app import local_memory
from app.config import settings

logger = logging.getLogger(__name__)


class MemoryUnavailableError(RuntimeError):
    """Raised when a retain call fails and we cannot store the memory."""


_client = None


def using_local() -> bool:
    """True when Hindsight Cloud is not configured."""
    return not settings.use_hindsight


def _get_client():
    """Return the singleton Hindsight client, created on first call."""
    global _client
    if using_local():
        raise RuntimeError("Hindsight is not configured; local memory is active")
    if _client is None:
        from hindsight_client import Hindsight

        kwargs: dict = {}
        if settings.hindsight_base_url:
            kwargs["base_url"] = settings.hindsight_base_url
        if settings.hindsight_api_key:
            kwargs["api_key"] = settings.hindsight_api_key
        _client = Hindsight(**kwargs)
    return _client


def _build_content(incident: dict) -> str:
    """
    Construct the memory content string from a resolved incident document.

    Includes: title, service, severity, symptoms, error_log (first 15 lines),
    root_cause, fix_steps, resolution_minutes, incident_id.
    """
    error_lines = (incident.get("error_log") or "").split("\n")[:15]
    error_snippet = "\n".join(error_lines)

    steps = incident.get("fix_steps") or []
    steps_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps))

    return (
        f"Incident ID: {incident.get('incident_id', 'N/A')}\n"
        f"Title: {incident.get('title', '')}\n"
        f"Service: {incident.get('service', '')}\n"
        f"Severity: {incident.get('severity', '')}\n"
        f"Symptoms: {incident.get('symptoms', '')}\n"
        f"Error Log (first 15 lines):\n{error_snippet}\n"
        f"Root Cause: {incident.get('root_cause', '')}\n"
        f"Fix Steps:\n{steps_text}\n"
        f"Resolution Time: {incident.get('resolution_minutes', 0)} minutes"
    )


def retain_incident(incident: dict) -> None:
    """
    Store one resolved incident as a memory.

    Raises MemoryUnavailableError on failure so callers can surface a
    clear error rather than silently losing the memory.
    """
    incident_id = incident.get("incident_id", "unknown")
    content = _build_content(incident)

    if using_local():
        try:
            local_memory.retain(incident_id, content)
            return
        except Exception as exc:
            raise MemoryUnavailableError(
                f"Failed to retain local memory for {incident_id}: {exc}"
            ) from exc

    try:
        client = _get_client()
        client.retain(bank_id=settings.hindsight_bank_id, content=content)
        # Mirror into local bank so recall still works if Cloud flakes mid-demo
        local_memory.retain(incident_id, content)
        logger.info("MEMORY RETAIN | incident_id=%s | bank=%s", incident_id, settings.hindsight_bank_id)
    except Exception as exc:
        logger.error("MEMORY RETAIN FAILED | incident_id=%s | error=%s", incident_id, exc)
        raise MemoryUnavailableError(
            f"Failed to retain memory for {incident_id}: {exc}"
        ) from exc


def recall_similar(query: str, top_k: int = 3) -> List[dict]:
    """
    Recall the top-k most relevant past incidents for a given query.

    Returns a list of dicts with keys: incident_id, text, score.
    Returns an empty list on any Hindsight failure (the app must not crash).
    """
    if using_local():
        return local_memory.recall(query, top_k=top_k)

    try:
        client = _get_client()
        results = client.recall(bank_id=settings.hindsight_bank_id, query=query)

        memories: List[dict] = []
        items = results if isinstance(results, list) else []
        for item in items[:top_k]:
            if isinstance(item, dict):
                text = item.get("content") or item.get("text") or str(item)
                score = item.get("score") or item.get("relevance_score") or 0.0
            else:
                text = getattr(item, "content", None) or getattr(item, "text", None) or str(item)
                score = getattr(item, "score", None) or getattr(item, "relevance_score", 0.0)

            inc_id = "unknown"
            for line in (text or "").split("\n"):
                if line.startswith("Incident ID:"):
                    inc_id = line.split(":", 1)[1].strip()
                    break

            memories.append({"incident_id": inc_id, "text": text, "score": float(score)})

        logger.info(
            "MEMORY RECALL | query_len=%d | bank=%s | results=%d",
            len(query),
            settings.hindsight_bank_id,
            len(memories),
        )
        return memories

    except Exception as exc:
        logger.error("MEMORY RECALL FAILED | error=%s — falling back to local", exc)
        return local_memory.recall(query, top_k=top_k)


def reset_bank() -> None:
    """Clear all memories in the configured bank (Cloud and/or local)."""
    local_memory.clear()

    if using_local():
        return

    import httpx

    base = (settings.hindsight_base_url or "https://api.hindsight.vectorize.io").rstrip("/")
    headers: dict = {}
    if settings.hindsight_api_key:
        headers["Authorization"] = f"Bearer {settings.hindsight_api_key}"

    try:
        resp = httpx.delete(
            f"{base}/api/v1/banks/{settings.hindsight_bank_id}/memories",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("MEMORY RESET | bank=%s | status=%s", settings.hindsight_bank_id, resp.status_code)
    except Exception as exc:
        logger.error("MEMORY RESET FAILED | bank=%s | error=%s", settings.hindsight_bank_id, exc)
        raise


def seed_local_from_incidents(incidents: List[dict]) -> int:
    """Load resolved incidents into the local memory bank."""
    return local_memory.load_from_incidents(incidents, _build_content)


def memory_backend() -> str:
    return "local" if using_local() else "hindsight"
