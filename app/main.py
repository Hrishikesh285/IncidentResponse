"""FastAPI application — all routes and static file serving."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Path as FPath
from fastapi.staticfiles import StaticFiles

from app import agent, db, llm, memory, seed
from app.config import settings
from app.models import AnalyzeRequest, ResolveRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpsMemory",
    version="1.1.0",
    description="Incident Response Agent with Hindsight memory",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def on_startup():
    """Prepare indexes and auto-seed an empty database."""
    try:
        db.ensure_indexes()
    except Exception as exc:
        logger.warning("Index setup skipped: %s", exc)

    try:
        result = seed.ensure_seeded()
        if result:
            logger.info("Auto-seeded empty store: %s", result)
    except Exception as exc:
        logger.warning("Auto-seed skipped: %s", exc)

    logger.info(
        "OpsMemory ready | storage=%s | memory=%s | llm=%s | demo_mode=%s",
        "local" if db.using_local() else "mongodb",
        memory.memory_backend(),
        llm.llm_backend(),
        settings.demo_mode,
    )


@app.get("/", include_in_schema=False)
async def root():
    """Serve the single-page frontend."""
    from fastapi.responses import FileResponse

    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health", tags=["system"])
async def health():
    """Readiness probe with backend status."""
    storage = "local" if db.using_local() else "mongodb"
    mongo_ok = not db.using_local()
    try:
        # Touch the store
        db.get_stats()
        store_ok = True
    except Exception:
        store_ok = False

    return {
        "status": "ok" if store_ok else "degraded",
        "storage": storage,
        "mongodb": mongo_ok,
        "memory_backend": memory.memory_backend(),
        "llm_backend": llm.llm_backend(),
        "demo_mode": settings.demo_mode or memory.using_local() or llm.using_local(),
        "hindsight_configured": settings.use_hindsight,
        "groq_configured": settings.use_groq,
    }


@app.post("/api/incidents/analyze", tags=["incidents"])
async def analyze(req: AnalyzeRequest):
    """Create a new open incident, run the agent analysis, and return the diagnosis."""
    if not req.title or not req.service or not req.severity:
        raise HTTPException(status_code=400, detail="title, service, and severity are required")

    if req.service not in (
        "payments-api",
        "auth-service",
        "order-service",
        "inventory-service",
        "notification-service",
        "search-service",
    ):
        raise HTTPException(status_code=400, detail=f"Unknown service: {req.service}")

    if req.severity not in ("SEV1", "SEV2", "SEV3"):
        raise HTTPException(status_code=400, detail="severity must be SEV1, SEV2, or SEV3")

    incident_id = db.next_incident_id()
    doc = {
        "incident_id": incident_id,
        "title": req.title,
        "service": req.service,
        "severity": req.severity,
        "error_log": req.error_log,
        "symptoms": req.symptoms,
        "root_cause": "",
        "fix_steps": [],
        "resolution_minutes": 0,
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }
    db.insert_incident(doc)
    logger.info("Created incident %s", incident_id)

    incident_text = (
        f"Title: {req.title}\n"
        f"Service: {req.service}\n"
        f"Severity: {req.severity}\n"
        f"Symptoms: {req.symptoms}\n"
        f"Error Log:\n{req.error_log}"
    )

    try:
        result = agent.analyze_incident(incident_text, req.use_memory)
    except Exception as exc:
        logger.error("Agent analysis failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    return {"incident_id": incident_id, **result}


@app.post("/api/incidents/{incident_id}/resolve", tags=["incidents"])
async def resolve(
    incident_id: str = FPath(..., description="Incident ID, e.g. INC-0001"),
    req: ResolveRequest = ...,
):
    """Resolve an open incident: update store and retain the resolution into memory."""
    if not req.root_cause:
        raise HTTPException(status_code=400, detail="root_cause is required")
    if not req.fix_steps:
        raise HTTPException(status_code=400, detail="fix_steps must not be empty")
    if req.resolution_minutes <= 0:
        raise HTTPException(status_code=400, detail="resolution_minutes must be positive")

    try:
        result = agent.resolve_incident(
            incident_id, req.root_cause, req.fix_steps, req.resolution_minutes
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Resolve failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail=f"Resolve failed: {exc}")

    return result


@app.get("/api/incidents", tags=["incidents"])
async def list_incidents():
    """Return all incidents, newest first."""
    incidents = db.list_incidents()
    # JSON-serialize datetimes
    for inc in incidents:
        for key in ("created_at", "resolved_at"):
            val = inc.get(key)
            if hasattr(val, "isoformat"):
                inc[key] = val.isoformat()
    return {"incidents": incidents}


@app.get("/api/incidents/{incident_id}", tags=["incidents"])
async def get_incident(incident_id: str = FPath(..., description="Incident ID")):
    """Fetch a single incident by ID."""
    doc = db.get_incident(incident_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    for key in ("created_at", "resolved_at"):
        val = doc.get(key)
        if hasattr(val, "isoformat"):
            doc[key] = val.isoformat()
    return doc


@app.get("/api/stats", tags=["system"])
async def stats():
    """Return aggregate stats plus backend mode."""
    data = db.get_stats()
    data["memory_backend"] = memory.memory_backend()
    data["llm_backend"] = llm.llm_backend()
    return data


@app.post("/api/reset", tags=["system"])
async def reset(reseed: bool = True):
    """
    Clear all incidents and memories. By default re-seeds the 40 demo incidents
    so the UI is immediately demo-ready again.
    """
    deleted = db.clear_incidents()
    try:
        memory.reset_bank()
        mem_reset = True
    except Exception as exc:
        logger.warning("Hindsight bank reset failed: %s", exc)
        mem_reset = False

    seed_result = None
    if reseed:
        try:
            seed_result = seed.seed_all(clear_first=False, retain_remote=not memory.using_local())
        except Exception as exc:
            logger.warning("Reseed after reset failed: %s", exc)
            seed_result = {"error": str(exc)}

    return {
        "incidents_deleted": deleted,
        "memory_reset": mem_reset,
        "reseeded": seed_result,
    }


@app.post("/api/seed", tags=["system"])
async def seed_endpoint():
    """Manually (re)seed incidents and memory from data/incidents_seed.json."""
    try:
        result = seed.seed_all(clear_first=True, retain_remote=not memory.using_local())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Seed failed: {exc}")
    return result
