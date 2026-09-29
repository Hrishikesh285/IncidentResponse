# OpsMemory — Architecture

## Components

| Component | Technology | Role |
|-----------|-----------|------|
| **Browser** | HTML + Vanilla JS | Single-page UI; three-panel layout |
| **FastAPI** | Python + Uvicorn | REST API; static file serving |
| **Agent** | `app/agent.py` | Orchestration: recall → LLM → respond |
| **Memory** | Hindsight Cloud | Vector memory store (retain / recall) |
| **LLM** | Groq (openai/gpt-oss-120b) | Diagnosis generation |
| **Database** | MongoDB (Docker) | Incident document store |

## ASCII Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │  Incident    │  │  Diagnosis    │  │  Recalled   │  │
│  │  Form        │  │  Panel        │  │  Memory     │  │
│  └──────┬───────┘  └───────▲───────┘  └──────▲──────┘  │
└─────────┼───────────────────┼──────────────────┼────────┘
          │ POST /analyze      │                  │
          ▼                   │ JSON response     │
┌─────────────────────────────────────────────────────────┐
│                     FastAPI (Uvicorn)                   │
│               app/main.py  — Routes                     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   app/agent.py                          │
│              analyze_incident()                         │
│         1. recall_similar()    2. diagnose()            │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────────┐  ┌───────────────────────────┐
│   app/memory.py        │  │      app/llm.py            │
│   Hindsight Client     │  │      Groq Client           │
│                        │  │                            │
│  retain_incident()     │  │  diagnose(text, recalled)  │
│  recall_similar()      │  │                            │
│  reset_bank()          │  │  Model: gpt-oss-120b       │
└────────┬───────────────┘  │  Fallback: qwen3-32b      │
         │                  └──────────────────────────┘
         ▼
┌────────────────────┐      ┌──────────────────────────┐
│  Hindsight Cloud   │      │      MongoDB              │
│                    │      │   (Docker — port 27017)   │
│  Memory Bank:      │      │   Collection: incidents   │
│  opsmemory-prod    │      │                           │
└────────────────────┘      └──────────────────────────┘
                                       ▲
                                       │
                            app/db.py ─┘
```

## Data Flow — Analyze

1. User fills in the incident form and clicks "Analyze Incident".
2. Browser POSTs `{title, service, severity, error_log, symptoms, use_memory}` to `/api/incidents/analyze`.
3. FastAPI creates an `open` incident in MongoDB and delegates to `agent.analyze_incident()`.
4. If `use_memory=True`, the agent calls `memory.recall_similar(query, top_k=3)` → Hindsight returns the top 3 matching memories.
5. The agent calls `llm.diagnose(incident_text, recalled)` → Groq returns structured JSON.
6. FastAPI returns `{incident_id, diagnosis, root_cause, steps, confidence, recalled_incidents, latency_ms}`.
7. The browser renders the diagnosis panel and the recall panel with matched cards.

## Data Flow — Resolve

1. User fills in the "Mark as Resolved" form and clicks "Resolve & Learn".
2. Browser POSTs `{root_cause, fix_steps, resolution_minutes}` to `/api/incidents/{id}/resolve`.
3. FastAPI calls `agent.resolve_incident()`.
4. The agent updates MongoDB (status → resolved, fills resolution fields).
5. The agent calls `memory.retain_incident(doc)` → Hindsight stores the resolved incident as a memory.
6. Future `recall_similar` queries can now find this incident.
