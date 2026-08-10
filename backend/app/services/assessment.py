"""Ties the pieces together: sensors -> risk engine -> persistence -> alerts."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import Prediction, SensorReading
from . import alerts as alerts_service
from . import risk_engine
from .mine import ZONE_BY_ID, ZONES, mine_summary
from .simulator import simulator

# The 8 channels the model consumes. The simulator carries extra telemetry
# (displacement, pore pressure) that operators watch but the model does not use.
MODEL_FEATURES = (
    "rainfall", "humidity", "temperature", "slope_angle",
    "vibration", "crack_density", "crack_severity", "rock_condition",
)


def assess_zone(zone_id: str, sensors: dict[str, float] | None = None) -> dict:
    """Score a single zone from its current (or supplied) sensor state."""
    zone = ZONE_BY_ID[zone_id]
    state = sensors if sensors is not None else simulator.zone_state(zone_id)
    features = {k: state[k] for k in MODEL_FEATURES if k in state}
    result = risk_engine.predict(features)

    return {
        "zone_id": zone_id,
        "zone_name": zone["name"],
        "wall": zone["wall"],
        "bench": zone["bench"],
        "center": zone["center"],
        "polygon": zone["polygon"],
        "personnel": zone["personnel"],
        "equipment": zone["equipment"],
        "sensors": {k: round(float(v), 2) for k, v in state.items()},
        **result,
    }


def assess_all() -> list[dict]:
    return [assess_zone(z["zone_id"]) for z in ZONES]


def mine_wide_risk(assessments: list[dict]) -> dict:
    """Roll zone scores up into one mine-wide number.

    Deliberately not a plain average: a mine is only as safe as its most
    dangerous active bench, and averaging six zones would let one critical wall
    disappear behind five quiet ones. The worst zone therefore dominates, with a
    personnel-weighted mean mixed in so that risk concentrated where people are
    actually working reads higher than the same risk on an empty wall.
    """
    if not assessments:
        return {"risk_score": 0.0, "risk_level": "LOW", "worst_zone": None,
                "personnel_at_risk": 0, "zones_by_level": {}}

    worst = max(assessments, key=lambda a: a["risk_score"])
    total_people = sum(a["personnel"] for a in assessments) or 1
    weighted_mean = sum(a["risk_score"] * a["personnel"] for a in assessments) / total_people

    score = round(0.65 * worst["risk_score"] + 0.35 * weighted_mean, 1)
    level = risk_engine.classify(score)

    by_level: dict[str, int] = {}
    for a in assessments:
        by_level[a["risk_level"]] = by_level.get(a["risk_level"], 0) + 1

    return {
        "risk_score": score,
        "risk_level": level,
        "probability": round(sum(a["probability"] for a in assessments) / len(assessments), 4),
        "worst_zone": {
            "zone_id": worst["zone_id"],
            "zone_name": worst["zone_name"],
            "risk_score": worst["risk_score"],
            "risk_level": worst["risk_level"],
            "recommended_action": worst["recommended_action"],
        },
        "personnel_at_risk": sum(a["personnel"] for a in assessments if a["risk_level"] in ("HIGH", "CRITICAL")),
        "zones_by_level": by_level,
        "method": "0.65 x worst zone + 0.35 x personnel-weighted mean",
    }


def persist_tick(db: Session, assessments: list[dict], source: str = "simulation") -> list[dict]:
    """Write one round of readings + predictions, and raise any warranted alerts."""
    scenario = simulator.scenario
    raised: list[dict] = []

    for a in assessments:
        s = a["sensors"]
        db.add(
            SensorReading(
                zone_id=a["zone_id"],
                mode=scenario,
                rainfall=s.get("rainfall", 0.0),
                humidity=s.get("humidity", 0.0),
                temperature=s.get("temperature", 0.0),
                vibration=s.get("vibration", 0.0),
                slope_angle=s.get("slope_angle", 0.0),
                displacement=s.get("displacement", 0.0),
                pore_pressure=s.get("pore_pressure", 0.0),
            )
        )
        db.add(
            Prediction(
                zone_id=a["zone_id"],
                source=source,
                risk_score=a["risk_score"],
                risk_level=a["risk_level"],
                probability=a["probability"],
                recommended_action=a["recommended_action"],
                features_json=json.dumps(a["features"]),
                contributions_json=json.dumps(a["contributions"]),
            )
        )
    db.commit()

    for a in assessments:
        alert = alerts_service.maybe_raise(db, a)
        if alert is not None:
            raised.append(alerts_service.serialize(alert))

    return raised


def dashboard_payload(db: Session | None = None) -> dict:
    assessments = assess_all()
    return {
        "mine": mine_summary(),
        "overall": mine_wide_risk(assessments),
        "zones": assessments,
        "simulation": simulator.status(),
        "engine": risk_engine.model_info(),
    }
