# OpsMemory — Hindsight Usage

## Where Hindsight Is Called

All Hindsight interactions are isolated to **`app/memory.py`**. No other file imports the Hindsight client.

| Function | Called from | When |
|----------|------------|------|
| `retain_incident(incident)` | `app/agent.py` → `resolve_incident()` | Every time an incident is marked resolved |
| `recall_similar(query, top_k)` | `app/agent.py` → `analyze_incident()` | Every time a new incident is analyzed (when `use_memory=True`) |
| `reset_bank()` | `app/main.py` → `/api/reset` | Demo reset only |
| `seed_memory.py` script | Manual seed run | Loads 40 seed incidents into memory |

## What Content Is Stored

Each memory is a plain text string built by `_build_content()` in `app/memory.py`:

```
Incident ID: INC-0001
Title: payments-api — HikariPool connection timeout
Service: payments-api
Severity: SEV1
Symptoms: 5xx error rate climbed to 40%. HikariPool-1 timeout errors.
Error Log (first 15 lines):
2025-09-28T08:12:15.342Z ERROR HikariPool-1 — Connection is not available...
...
Root Cause: DB connection pool exhausted after traffic spike
Fix Steps:
  1. Increase connection pool size to 50
  2. Restart payments-api pods
  3. Add pool-timeout alert at 80% utilisation
Resolution Time: 22 minutes
```

This rich content enables semantic search across all dimensions: error text, root cause vocabulary, fix terminology, and service context.

## Why Memory Is Central

Without memory, OpsMemory is just a generic LLM wrapper. The key differentiator is the **learning loop**:

```
Resolve incident → retain() → memory bank grows
New incident → recall() → LLM cites past fix → faster resolution
```

Over time, the system accumulates institutional knowledge that survives:
- Engineer turnover
- On-call rotation changes
- Postmortem document entropy

## Memory OFF vs. Memory ON

| Scenario | Memory OFF | Memory ON |
|---------|-----------|----------|
| **Demo A** (fresh, no history) | Generic diagnosis: "check connection pool settings" | After seeding: cites INC-0003 (db_pool_exhaustion family), recommends same pool increase that worked before |
| **Demo C** (after resolving A) | Generic diagnosis for different wording of pool exhaustion | Recalls both the seeded pool incidents AND the just-resolved Demo A, providing a fix with confirmed history |
| Confidence level | low → medium | medium → high |
| Mean time to action | ~20 min reading docs | ~3 min confirming familiar fix |

## Hindsight Client Initialisation

```python
from hindsight_client import Hindsight

client = Hindsight(
    base_url=settings.hindsight_base_url,  # e.g. https://api.hindsight.vectorize.io
    api_key=settings.hindsight_api_key,
)
```

The client is a lazy singleton created on first call via `_get_client()`. API key and base URL come from `.env`; never hardcoded.

## Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Hindsight down during `recall_similar` | Returns `[]`; LLM still runs with no context; app does not crash |
| Hindsight down during `retain_incident` | Raises `MemoryUnavailableError`; incident is still resolved in MongoDB |
| Invalid Hindsight credentials | Same as above; errors logged at ERROR level |
