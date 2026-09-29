# OpsMemory — API Reference

All endpoints return JSON. Errors return `{"detail": "..."}` (FastAPI default) or `{"error": "..."}`.

---

## GET /

Serves `index.html` (the single-page frontend).

---

## GET /api/health

Liveness probe.

**Response:**
```json
{"status": "ok"}
```

---

## POST /api/incidents/analyze

Create a new open incident, run memory recall + LLM diagnosis, and return the result.

**Request body:**
```json
{
  "title": "payments-api — HikariPool connection timeout causing 5xx flood",
  "service": "payments-api",
  "severity": "SEV1",
  "error_log": "2025-09-28T08:12:15.342Z ERROR HikariPool-1 — Connection is not available, request timed out after 30000ms\n...",
  "symptoms": "5xx error rate climbed to 40%. HikariPool-1 timeout errors in logs.",
  "use_memory": true
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title | string | yes | Short summary |
| service | string | yes | One of the 6 services |
| severity | string | yes | SEV1, SEV2, or SEV3 |
| error_log | string | no | Log lines or stack trace |
| symptoms | string | no | On-call observations |
| use_memory | boolean | no | Default: true |

**Response (200):**
```json
{
  "incident_id": "INC-0001",
  "diagnosis": "This matches the HikariPool connection pool exhaustion pattern seen in INC-0003...",
  "likely_root_cause": "DB connection pool exhausted after traffic spike",
  "recommended_steps": [
    "Increase pool size to 50 in application config",
    "Restart payments-api pods",
    "Add pool-timeout alert at 80% utilisation"
  ],
  "confidence": "high",
  "matched_incident_id": "INC-0003",
  "match_reason": "Identical HikariPool-1 timeout error pattern on payments-api",
  "recalled_incidents": [
    {
      "incident_id": "INC-0003",
      "text": "Incident ID: INC-0003\nTitle: payments-api — DB connection pool saturated...",
      "score": 0.94
    }
  ],
  "memory_used": true,
  "latency_ms": 1342.7
}
```

**Error responses:**
- `400` — missing required field or invalid service/severity
- `500` — LLM or internal error

---

## POST /api/incidents/{incident_id}/resolve

Resolve an open incident: update MongoDB and retain the resolution into Hindsight memory.

**Path parameter:** `incident_id` — e.g. `INC-0001`

**Request body:**
```json
{
  "root_cause": "DB connection pool exhausted after Black Friday traffic spike",
  "fix_steps": [
    "Increase pool size to 50; restart payments-api pods",
    "Add pool-timeout alert",
    "Add HPA metric for active DB connections"
  ],
  "resolution_minutes": 22
}
```

**Response (200):**
```json
{
  "success": true,
  "memory_retained": true,
  "incident_id": "INC-0001"
}
```

**Error responses:**
- `400` — missing root_cause, empty fix_steps, or non-positive resolution_minutes
- `404` — incident_id not found

---

## GET /api/incidents

Return all incidents, newest first.

**Response (200):**
```json
{
  "incidents": [
    {
      "incident_id": "INC-0001",
      "title": "payments-api — HikariPool connection timeout...",
      "service": "payments-api",
      "severity": "SEV1",
      "status": "resolved",
      "created_at": "2025-09-28T08:12:00Z",
      "resolved_at": "2025-09-28T08:34:00Z",
      "resolution_minutes": 22,
      ...
    }
  ]
}
```

---

## GET /api/stats

Return aggregate statistics.

**Response (200):**
```json
{
  "total_incidents": 41,
  "resolved": 41,
  "avg_resolution_minutes": 28.4,
  "memories_retained": 41
}
```

---

## POST /api/reset

Clear all incidents from MongoDB and all memories from the Hindsight bank.

> ⚠️ Destructive — intended for demo resets only.

**Response (200):**
```json
{
  "incidents_deleted": 41,
  "memory_reset": true
}
```
