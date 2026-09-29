"""Groq LLM integration — ALL Groq calls live here only.

Exposes a single public function: diagnose().
Falls back to a heuristic local diagnosis when Groq is not configured.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


SYSTEM_PROMPT = (
    "You are OpsMemory, an on-call incident assistant. "
    "You will receive a NEW incident and, optionally, PAST INCIDENTS recalled from memory. "
    "If past incidents are provided, use them: name the most relevant one by its incident_id, "
    "explain why it matches, and base the fix on what worked before. "
    "If no past incidents are provided, give a generic diagnosis and say clearly that no "
    "historical context was available. "
    "Respond with ONLY valid JSON and no markdown, in this shape: "
    '{"diagnosis": string, "likely_root_cause": string, '
    '"recommended_steps": [string], "confidence": "low"|"medium"|"high", '
    '"matched_incident_id": string|null, "match_reason": string}'
)


# Pattern → (root_cause, steps) for offline heuristic diagnosis
_HEURISTICS = [
    (
        re.compile(r"hikari|connection.?pool|too many clients|queues?pool|jdbc|psycopg", re.I),
        "DB connection pool exhausted",
        [
            "Increase the connection pool size in the service config",
            "Restart affected pods to release stuck connections",
            "Check for connection leaks (connections not closed in finally/with)",
            "Add an alert when pool utilisation exceeds 80%",
        ],
    ),
    (
        re.compile(r"redis|oom|maxmemory|jedis|evict", re.I),
        "Redis memory pressure / OOM",
        [
            "Raise Redis maxmemory or scale the cache instance",
            "Switch eviction policy to allkeys-lru if appropriate",
            "Flush unused keys / review TTL settings",
            "Add memory utilisation alerts",
        ],
    ),
    (
        re.compile(r"timeout|timed?\s*out|deadline|latency", re.I),
        "Upstream timeout / elevated latency",
        [
            "Identify the slow dependency from traces/logs",
            "Increase timeout only as a temporary mitigation",
            "Scale the bottleneck service or add caching",
            "Add SLOs and latency alerts for the critical path",
        ],
    ),
    (
        re.compile(r"oom.?kill|out of memory|memory.?limit|heap", re.I),
        "Process or container out-of-memory",
        [
            "Increase memory limits for the workload",
            "Capture a heap dump before restarting",
            "Look for memory leaks or unbounded caches",
            "Tune GC / reduce batch sizes if applicable",
        ],
    ),
    (
        re.compile(r"kafka|consumer.?lag|broker|partition", re.I),
        "Messaging backlog / consumer lag",
        [
            "Scale consumers or increase partitions carefully",
            "Replay or skip poison messages",
            "Check broker disk and network health",
            "Add consumer-lag alerts",
        ],
    ),
]


def using_local() -> bool:
    return not settings.use_groq


def _get_client():
    global _client
    if using_local():
        raise RuntimeError("Groq is not configured; local heuristic is active")
    if _client is None:
        from groq import Groq

        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _build_user_message(incident_text: str, recalled: List[dict]) -> str:
    parts = [f"NEW INCIDENT:\n{incident_text}"]

    if recalled:
        parts.append("\nPAST INCIDENTS RECALLED FROM MEMORY:")
        for i, mem in enumerate(recalled, 1):
            score_str = f" (relevance: {mem.get('score', 0):.2f})" if mem.get("score") else ""
            parts.append(
                f"\n[{i}] {mem.get('incident_id', 'N/A')}{score_str}\n{mem.get('text', '')}"
            )
    else:
        parts.append("\nNo past incidents were retrieved from memory.")

    return "\n".join(parts)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _parse_json(raw: str) -> dict:
    cleaned = _strip_fences(raw)
    return json.loads(cleaned)


def _extract_field(text: str, label: str) -> str:
    for line in (text or "").split("\n"):
        if line.lower().startswith(label.lower()):
            return line.split(":", 1)[1].strip()
    return ""


def _extract_steps(text: str) -> List[str]:
    steps: List[str] = []
    in_steps = False
    for line in (text or "").split("\n"):
        if line.lower().startswith("fix steps"):
            in_steps = True
            continue
        if in_steps:
            cleaned = re.sub(r"^\s*\d+\.\s*", "", line).strip()
            if cleaned:
                steps.append(cleaned)
            elif steps:
                break
    return steps


def _local_diagnose(incident_text: str, recalled: List[dict]) -> dict:
    """Heuristic diagnosis grounded in recalled memories when available."""
    if recalled:
        best = recalled[0]
        text = best.get("text") or ""
        root = _extract_field(text, "Root Cause") or "Same class of failure as the matched past incident"
        steps = _extract_steps(text) or [
            "Apply the fix steps from the matched past incident",
            "Verify error rates and latency return to baseline",
            "Retain this resolution so future matches improve",
        ]
        matched = best.get("incident_id")
        return {
            "diagnosis": (
                f"Memory-informed diagnosis (local mode): this incident closely matches "
                f"{matched}. Reusing the resolution that worked before."
            ),
            "likely_root_cause": root,
            "recommended_steps": steps,
            "confidence": "high" if (best.get("score") or 0) >= 0.15 else "medium",
            "matched_incident_id": matched,
            "match_reason": (
                f"Highest local similarity score ({best.get('score', 0):.2f}) "
                f"against past incident {matched}."
            ),
        }

    blob = incident_text or ""
    for pattern, root, steps in _HEURISTICS:
        if pattern.search(blob):
            return {
                "diagnosis": (
                    "Generic diagnosis (local mode, no historical memory used): "
                    f"symptoms match the '{root}' pattern. "
                    "Enable Memory ON after seeding to ground fixes in past incidents."
                ),
                "likely_root_cause": root,
                "recommended_steps": steps,
                "confidence": "medium",
                "matched_incident_id": None,
                "match_reason": "No past incidents were provided; heuristic pattern match only.",
            }

    return {
        "diagnosis": (
            "Generic diagnosis (local mode): no strong pattern match and no historical "
            "context was available. Investigate recent deploys, dependency health, and error spikes."
        ),
        "likely_root_cause": "Unknown — please investigate manually.",
        "recommended_steps": [
            "Check service logs for recent errors",
            "Review recent deployments for changes",
            "Escalate to senior engineer if unresolved",
        ],
        "confidence": "low",
        "matched_incident_id": None,
        "match_reason": "No historical context was available.",
    }


def _call_model(model: str, user_message: str) -> dict:
    """Call the specified Groq model and parse the JSON response."""
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )
    raw = response.choices[0].message.content or ""

    try:
        return _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("JSON parse failed on first attempt; retrying once")

    retry_resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": "Your response was not valid JSON. Respond with ONLY the JSON object, no markdown.",
            },
        ],
        temperature=0.0,
    )
    raw2 = retry_resp.choices[0].message.content or ""
    return _parse_json(raw2)


def diagnose(incident_text: str, recalled: List[dict]) -> dict:
    """
    Send the incident + recalled memories to Groq and return a parsed diagnosis.

    Strategy:
      1. If Groq is not configured, use local heuristic diagnosis.
      2. Try primary model (GROQ_MODEL).
      3. On any error, retry once with primary model.
      4. If still failing, fall back to GROQ_FALLBACK_MODEL.
      5. If all fail, return a friendly error dict.
    """
    if using_local():
        result = _local_diagnose(incident_text, recalled)
        logger.info("LLM DIAGNOSE (local) | confidence=%s", result.get("confidence"))
        return result

    user_message = _build_user_message(incident_text, recalled)

    # Primary model with one retry (do NOT break after first failure)
    primary_ok = False
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = _call_model(settings.groq_model, user_message)
            logger.info(
                "LLM DIAGNOSE | model=%s | attempt=%d | confidence=%s",
                settings.groq_model,
                attempt + 1,
                result.get("confidence"),
            )
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "LLM call failed | model=%s | attempt=%d | error=%s",
                settings.groq_model,
                attempt + 1,
                exc,
            )

    # Fallback model
    try:
        result = _call_model(settings.groq_fallback_model, user_message)
        logger.info(
            "LLM DIAGNOSE (fallback) | model=%s | confidence=%s",
            settings.groq_fallback_model,
            result.get("confidence"),
        )
        return result
    except Exception as exc:
        logger.error("LLM fallback also failed | error=%s | primary_err=%s", exc, last_exc)

    # Last resort: local heuristic so the demo never hard-fails
    logger.warning("Falling back to local heuristic after Groq failures")
    return _local_diagnose(incident_text, recalled)


def llm_backend() -> str:
    return "local" if using_local() else "groq"
