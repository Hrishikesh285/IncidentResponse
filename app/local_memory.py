"""Local in-process memory bank used when Hindsight Cloud is unavailable.

Stores retained incident texts and ranks them with simple token overlap
so Memory ON still works in demo / offline mode.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Dict, List

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
# incident_id -> content text
_BANK: Dict[str, str] = {}

_TOKEN_RE = re.compile(r"[a-z0-9_./-]{3,}", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def clear() -> None:
    with _LOCK:
        _BANK.clear()
    logger.info("LOCAL MEMORY RESET")


def retain(incident_id: str, content: str) -> None:
    with _LOCK:
        _BANK[incident_id] = content
    logger.info("LOCAL MEMORY RETAIN | incident_id=%s | bank_size=%d", incident_id, len(_BANK))


def recall(query: str, top_k: int = 3) -> List[dict]:
    q = _tokens(query)
    if not q:
        return []

    scored: List[tuple[float, str, str]] = []
    with _LOCK:
        items = list(_BANK.items())

    for incident_id, text in items:
        t = _tokens(text)
        if not t:
            continue
        overlap = len(q & t)
        if overlap == 0:
            continue
        # Jaccard-ish score biased toward query coverage
        score = overlap / (len(q) + 0.25 * len(t - q))
        scored.append((score, incident_id, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [
        {"incident_id": iid, "text": text, "score": round(score, 4)}
        for score, iid, text in scored[:top_k]
    ]
    logger.info("LOCAL MEMORY RECALL | results=%d", len(results))
    return results


def size() -> int:
    with _LOCK:
        return len(_BANK)


def load_from_incidents(incidents: List[dict], build_content) -> int:
    """Bulk-load resolved incidents into the local bank."""
    with _LOCK:
        _BANK.clear()
        for inc in incidents:
            if inc.get("status") != "resolved":
                continue
            iid = inc.get("incident_id") or "unknown"
            _BANK[iid] = build_content(inc)
        count = len(_BANK)
    logger.info("LOCAL MEMORY SEEDED | count=%d", count)
    return count
