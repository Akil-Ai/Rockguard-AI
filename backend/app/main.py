"""RockGuard AI — FastAPI application entry point.

Run from the backend directory:

    uvicorn app.main:app --reload --port 8000

Interactive API docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import SessionLocal, init_db
from .routers import alerts, dashboard, history, predict, sensors, vision
from .services import assessment
from .services.risk_engine import model_info
from .services.simulator import simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("rockguard")

DISCLAIMER = (
    "DEMO SYSTEM. All sensor data is simulated, the mine is fictional, and the "
    "risk model is trained on a synthetic dataset. Not validated against real "
    "rockfall events and not for operational safety use."
)


async def _simulation_loop() -> None:
    """Advance the simulated sensor network and score every zone on a timer.

    Runs as a background task for the life of the process so the trend charts,
    history table and alert list keep filling even when nobody is clicking.
    """
    interval = max(1, settings.sensor_tick_seconds)
    log.info("Simulation loop started (%.0fs interval).", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            # The simulator and SQLAlchemy calls are blocking, so push the whole
            # tick to a worker thread and keep the event loop responsive.
            await asyncio.to_thread(_tick_once)
        except asyncio.CancelledError:
            log.info("Simulation loop stopped.")
            raise
        except Exception:
            # One bad tick must never kill the loop mid-demo.
            log.exception("Simulation tick failed; continuing.")


def _tick_once() -> None:
    simulator.tick()
    db = SessionLocal()
    try:
        raised = assessment.persist_tick(db, assessment.assess_all())
        for alert in raised:
            log.warning("ALERT %s %s risk=%s", alert["risk_level"], alert["zone_id"], alert["risk_score"])
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    info = model_info()
    log.info("Risk engine: %s (%s)", info["engine"], "loaded" if info["loaded"] else "FALLBACK")
    if not info["loaded"]:
        log.warning("No trained model found. Run `python -m app.ml.train_model` for the full pipeline.")

    task = asyncio.create_task(_simulation_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="RockGuard AI",
    version="1.0.0",
    description=(
        "AI-based rockfall prediction and alert system for open-pit mines "
        f"(SIH25071).\n\n**{DISCLAIMER}**"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (dashboard.router, sensors.router, predict.router,
               vision.router, alerts.router, history.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "engine": model_info(),
        "simulation": simulator.status(),
        "disclaimer": DISCLAIMER,
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health", "disclaimer": DISCLAIMER}
