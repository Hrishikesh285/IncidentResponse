"""Pytest configuration — force live backend paths so mocks are exercised."""

from __future__ import annotations

import os

# Ensure memory/llm tests hit the Cloud client code paths (mocked),
# not the local fallbacks that activate when keys are empty.
os.environ.setdefault("HINDSIGHT_API_KEY", "test-hindsight-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("DEMO_MODE", "false")
