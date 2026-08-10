"""Simulated IoT sensor network control."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import OverrideRequest, ScenarioRequest
from ..services import assessment
from ..services.mine import ZONES
from ..services.simulator import simulator

router = APIRouter(prefix="/sensors", tags=["sensors"])

# Channel display metadata for the Sensor Monitoring page.
CHANNELS = [
    {"key": "rainfall", "label": "Rainfall", "unit": "mm/24h", "min": 0, "max": 120, "warn": 40, "danger": 80},
    {"key": "humidity", "label": "Humidity", "unit": "%", "min": 15, "max": 100, "warn": 75, "danger": 90},
    {"key": "temperature", "label": "Temperature", "unit": "°C", "min": -5, "max": 48, "warn": 38, "danger": 44},
    {"key": "vibration", "label": "Vibration (PPV)", "unit": "mm/s", "min": 0, "max": 30, "warn": 5, "danger": 12},
    {"key": "slope_angle", "label": "Slope / Tilt", "unit": "°", "min": 20, "max": 80, "warn": 50, "danger": 60},
    {"key": "displacement", "label": "Displacement", "unit": "mm", "min": 0, "max": 40, "warn": 5, "danger": 12},
    {"key": "pore_pressure", "label": "Pore Pressure", "unit": "kPa", "min": 0, "max": 100, "warn": 50, "danger": 75},
    {"key": "crack_density", "label": "Crack Density", "unit": "%", "min": 0, "max": 45, "warn": 12, "danger": 22},
    {"key": "crack_severity", "label": "Crack Severity", "unit": "/100", "min": 0, "max": 100, "warn": 40, "danger": 70},
    {"key": "rock_condition", "label": "Rock Quality", "unit": "/100", "min": 5, "max": 98, "warn": 50, "danger": 35, "inverted": True},
]


@router.get("")
def get_sensors() -> dict:
    """Current readings for every zone, plus channel metadata."""
    snapshot = simulator.snapshot()
    return {
        "status": simulator.status(),
        "channels": CHANNELS,
        "zones": [
            {
                "zone_id": z["zone_id"],
                "name": z["name"],
                "wall": z["wall"],
                "personnel": z["personnel"],
                "readings": snapshot[z["zone_id"]],
            }
            for z in ZONES
        ],
    }


@router.post("/scenario")
def set_scenario(payload: ScenarioRequest, db: Session = Depends(get_db)) -> dict:
    """Switch the whole simulated network between NORMAL / WARNING / CRITICAL."""
    try:
        simulator.set_scenario(payload.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Score and persist immediately so the UI (and the alert list) reflect the
    # new scenario on the very next poll rather than after the next background tick.
    assessments = assessment.assess_all()
    raised = assessment.persist_tick(db, assessments, source="scenario")
    return {
        "status": simulator.status(),
        "overall": assessment.mine_wide_risk(assessments),
        "zones": assessments,
        "alerts_raised": raised,
    }


@router.post("/override")
def set_override(payload: OverrideRequest, db: Session = Depends(get_db)) -> dict:
    """Pin individual channels for one zone (manual sensor injection)."""
    try:
        applied = simulator.set_override(payload.zone_id, payload.values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = assessment.assess_zone(payload.zone_id)
    raised = assessment.persist_tick(db, [result], source="manual")
    return {"zone": result, "overrides": applied, "alerts_raised": raised}


@router.delete("/override/{zone_id}")
def clear_override(zone_id: str) -> dict:
    simulator.clear_overrides(zone_id)
    return {"cleared": zone_id, "status": simulator.status()}


@router.post("/tick")
def force_tick(db: Session = Depends(get_db)) -> dict:
    """Advance the simulation one step on demand (used by the manual-refresh button)."""
    simulator.tick()
    assessments = assessment.assess_all()
    raised = assessment.persist_tick(db, assessments)
    return {
        "status": simulator.status(),
        "overall": assessment.mine_wide_risk(assessments),
        "zones": assessments,
        "alerts_raised": raised,
    }


@router.post("/reset")
def reset() -> dict:
    """Return every zone to its NORMAL baseline and drop all overrides."""
    simulator.reset()
    return {"status": simulator.status(), "zones": assessment.assess_all()}
