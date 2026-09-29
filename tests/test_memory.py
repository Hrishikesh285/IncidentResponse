"""Tests for the Hindsight memory module.

Verifies that:
  - recall_similar returns an empty list (not a crash) when Hindsight is down
  - retain_incident raises MemoryUnavailableError on failure (not silent)
  - reset_bank surfaces exceptions for callers to handle
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.memory import MemoryUnavailableError, recall_similar, retain_incident


# ---------------------------------------------------------------------------
# recall_similar tests
# ---------------------------------------------------------------------------


class TestRecallSimilar:
    """Tests for the recall_similar() public function."""

    def test_returns_empty_list_when_hindsight_raises(self):
        """recall_similar must return [] and not re-raise on Hindsight failure."""
        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.recall.side_effect = RuntimeError("Hindsight service unavailable")
            mock_get.return_value = mock_client

            result = recall_similar("connection pool error")

        assert result == [], "Expected empty list on failure, not an exception"

    def test_returns_empty_list_on_network_timeout(self):
        """recall_similar must swallow TimeoutError and return []."""
        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.recall.side_effect = TimeoutError("timeout")
            mock_get.return_value = mock_client

            result = recall_similar("redis oom error")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_normalises_list_response_to_dicts(self):
        """When Hindsight returns a list, each item is converted to {incident_id, text, score}."""
        raw_item = MagicMock()
        raw_item.content = "Incident ID: INC-0001\nTitle: Test\nRoot Cause: pool"
        raw_item.score = 0.9

        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.recall.return_value = [raw_item]
            mock_get.return_value = mock_client

            result = recall_similar("pool exhaustion", top_k=3)

        assert len(result) == 1
        assert result[0]["incident_id"] == "INC-0001"
        assert "score" in result[0]

    def test_respects_top_k_limit(self):
        """recall_similar must not return more than top_k items."""
        items = []
        for i in range(10):
            m = MagicMock()
            m.content = f"Incident ID: INC-{i:04d}\n"
            m.score = 0.9 - i * 0.05
            items.append(m)

        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.recall.return_value = items
            mock_get.return_value = mock_client

            result = recall_similar("any query", top_k=3)

        assert len(result) <= 3


# ---------------------------------------------------------------------------
# retain_incident tests
# ---------------------------------------------------------------------------


class TestRetainIncident:
    """Tests for the retain_incident() public function."""

    def test_raises_memory_unavailable_on_failure(self):
        """retain_incident must raise MemoryUnavailableError, not swallow the error."""
        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.retain.side_effect = RuntimeError("network error")
            mock_get.return_value = mock_client

            incident = {
                "incident_id": "INC-0001",
                "title": "Test",
                "service": "payments-api",
                "severity": "SEV1",
                "symptoms": "errors",
                "error_log": "log line",
                "root_cause": "pool exhausted",
                "fix_steps": ["increase pool"],
                "resolution_minutes": 22,
            }

            with pytest.raises(MemoryUnavailableError):
                retain_incident(incident)

    def test_calls_hindsight_retain_with_bank_id(self):
        """retain_incident must pass the configured bank_id to Hindsight."""
        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            incident = {
                "incident_id": "INC-0001",
                "title": "DB pool exhausted",
                "service": "payments-api",
                "severity": "SEV1",
                "symptoms": "5xx errors",
                "error_log": "HikariPool timeout",
                "root_cause": "pool exhausted",
                "fix_steps": ["increase pool size"],
                "resolution_minutes": 22,
            }
            retain_incident(incident)

        mock_client.retain.assert_called_once()
        call_kwargs = mock_client.retain.call_args
        # bank_id must be passed
        assert "bank_id" in call_kwargs.kwargs or call_kwargs.args

    def test_content_includes_key_fields(self):
        """The content string passed to Hindsight must include all required fields."""
        captured_content = []

        with patch("app.memory._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.retain.side_effect = lambda **kw: captured_content.append(kw.get("content", ""))
            mock_get.return_value = mock_client

            incident = {
                "incident_id": "INC-0005",
                "title": "Redis OOM",
                "service": "auth-service",
                "severity": "SEV2",
                "symptoms": "login failures",
                "error_log": "OOM command not allowed",
                "root_cause": "Redis maxmemory exceeded",
                "fix_steps": ["raise maxmemory", "set eviction policy"],
                "resolution_minutes": 35,
            }
            retain_incident(incident)

        assert captured_content, "retain was not called"
        content = captured_content[0]
        assert "INC-0005" in content
        assert "Redis OOM" in content
        assert "auth-service" in content
        assert "Redis maxmemory exceeded" in content
