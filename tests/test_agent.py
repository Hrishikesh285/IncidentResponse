"""Tests for the agent orchestration layer.

Hindsight and Groq are fully mocked so no external services are required.
Verifies that:
  - memory ON → recall_similar is called and results are passed to diagnose
  - memory OFF → recall_similar is NOT called and empty list reaches diagnose
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app import agent


# ---------------------------------------------------------------------------
# Shared mock diagnosis return value
# ---------------------------------------------------------------------------

MOCK_DIAGNOSIS = {
    "diagnosis": "Looks like a connection pool issue.",
    "likely_root_cause": "DB connection pool exhausted",
    "recommended_steps": ["Increase pool size", "Restart pods"],
    "confidence": "high",
    "matched_incident_id": "INC-0003",
    "match_reason": "Identical HikariPool error pattern",
}

MOCK_RECALLED = [
    {"incident_id": "INC-0003", "text": "DB pool exhausted on payments-api", "score": 0.95}
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeIncident:
    """Unit tests for agent.analyze_incident()."""

    def test_memory_on_calls_recall_and_passes_results(self):
        """When use_memory=True, recalled incidents must reach the LLM."""
        with (
            patch("app.agent.memory.recall_similar", return_value=MOCK_RECALLED) as mock_recall,
            patch("app.agent.llm.diagnose", return_value=MOCK_DIAGNOSIS) as mock_diagnose,
        ):
            result = agent.analyze_incident("connection pool timeout", use_memory=True)

        # recall_similar must have been called exactly once
        mock_recall.assert_called_once_with("connection pool timeout", top_k=3)

        # diagnose must receive the recalled incidents
        mock_diagnose.assert_called_once()
        _, call_kwargs = mock_diagnose.call_args
        passed_recalled = mock_diagnose.call_args[0][1]  # second positional arg
        assert passed_recalled == MOCK_RECALLED

        # Result should contain recalled_incidents and memory_used=True
        assert result["memory_used"] is True
        assert result["recalled_incidents"] == MOCK_RECALLED
        assert "latency_ms" in result

    def test_memory_off_passes_empty_list_to_llm(self):
        """When use_memory=False, recalled must be [] and recall_similar not called."""
        with (
            patch("app.agent.memory.recall_similar", return_value=MOCK_RECALLED) as mock_recall,
            patch("app.agent.llm.diagnose", return_value=MOCK_DIAGNOSIS) as mock_diagnose,
        ):
            result = agent.analyze_incident("connection pool timeout", use_memory=False)

        # recall_similar must NOT have been called
        mock_recall.assert_not_called()

        # diagnose must receive an empty list
        passed_recalled = mock_diagnose.call_args[0][1]
        assert passed_recalled == []

        # Result flags
        assert result["memory_used"] is False
        assert result["recalled_incidents"] == []

    def test_result_contains_diagnosis_fields(self):
        """Returned dict must include all LLM diagnosis fields."""
        with (
            patch("app.agent.memory.recall_similar", return_value=[]),
            patch("app.agent.llm.diagnose", return_value=MOCK_DIAGNOSIS),
        ):
            result = agent.analyze_incident("test incident", use_memory=False)

        for key in ("diagnosis", "likely_root_cause", "recommended_steps", "confidence"):
            assert key in result, f"Missing key: {key}"

    def test_memory_recall_failure_does_not_crash(self):
        """If recall_similar returns empty due to Hindsight being down, agent still works."""
        with (
            patch("app.agent.memory.recall_similar", return_value=[]),
            patch("app.agent.llm.diagnose", return_value=MOCK_DIAGNOSIS),
        ):
            result = agent.analyze_incident("test incident", use_memory=True)

        assert result["recalled_incidents"] == []
        assert result["memory_used"] is True


class TestResolveIncident:
    """Unit tests for agent.resolve_incident()."""

    def test_resolve_updates_db_and_retains_memory(self):
        """resolve_incident must update MongoDB and call retain_incident."""
        mock_doc = {
            "incident_id": "INC-0001",
            "title": "Test",
            "service": "payments-api",
            "severity": "SEV1",
            "root_cause": "pool exhausted",
            "fix_steps": ["increase pool"],
            "resolution_minutes": 20,
            "status": "resolved",
        }
        with (
            patch("app.agent.db.resolve_incident", return_value=True),
            patch("app.agent.db.get_incident", return_value=mock_doc),
            patch("app.agent.memory.retain_incident") as mock_retain,
        ):
            result = agent.resolve_incident("INC-0001", "pool exhausted", ["increase pool"], 20)

        mock_retain.assert_called_once_with(mock_doc)
        assert result["success"] is True
        assert result["memory_retained"] is True

    def test_resolve_not_found_raises_value_error(self):
        """resolve_incident should raise ValueError for unknown incident_id."""
        with patch("app.agent.db.resolve_incident", return_value=False):
            with pytest.raises(ValueError, match="INC-9999"):
                agent.resolve_incident("INC-9999", "cause", ["step"], 10)
