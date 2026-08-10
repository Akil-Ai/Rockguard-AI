"""Historical time series and summary statistics."""
from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, ImageAnalysis, Prediction, SensorReading, iso_utc, utcnow

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/risk")
def risk_history(
    limit: int = Query(120, ge=1, le=2000),
    zone_id: str | None = None,
    hours: int | None = Query(None, ge=1, le=720),
    db: Session = Depends(get_db),
) -> dict:
    """Risk-score time series, oldest first (chart-ready)."""
    stmt = select(Prediction).order_by(Prediction.created_at.desc())
    if zone_id:
        stmt = stmt.where(Prediction.zone_id == zone_id)
    if hours:
        stmt = stmt.where(Prediction.created_at >= utcnow() - timedelta(hours=hours))

    rows = list(reversed(db.execute(stmt.limit(limit)).scalars().all()))
    return {
        "points": [
            {
                "id": r.id,
                "t": iso_utc(r.created_at),
                "zone_id": r.zone_id,
                "risk_score": round(r.risk_score, 1),
                "risk_level": r.risk_level,
                "probability": round(r.probability, 4),
                "source": r.source,
            }
            for r in rows
        ]
    }


@router.get("/risk/mine")
def mine_risk_history(
    buckets: int = Query(60, ge=5, le=400),
    db: Session = Depends(get_db),
) -> dict:
    """Mine-wide risk trend: the worst zone score per timestamp group.

    Predictions are written one row per zone per tick, so plotting them raw
    produces six interleaved sawtooths. Grouping by second and taking the peak
    gives the single "how bad is the mine right now" line the dashboard shows.
    """
    sub = (
        select(
            func.strftime("%Y-%m-%dT%H:%M:%S", Prediction.created_at).label("bucket"),
            func.max(Prediction.risk_score).label("peak"),
            func.avg(Prediction.risk_score).label("mean"),
        )
        .group_by("bucket")
        .order_by(func.max(Prediction.created_at).desc())
        .limit(buckets)
    )
    rows = list(reversed(db.execute(sub).all()))
    return {
        "points": [
            # strftime returns a bare naive-UTC string; tag it so clients do not
            # read the bucket as local time.
            {"t": f"{b}Z", "peak": round(float(p), 1), "mean": round(float(m), 1)}
            for b, p, m in rows
        ]
    }


@router.get("/sensors")
def sensor_history(
    zone_id: str | None = None,
    limit: int = Query(120, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(SensorReading).order_by(SensorReading.created_at.desc())
    if zone_id:
        stmt = stmt.where(SensorReading.zone_id == zone_id)
    rows = list(reversed(db.execute(stmt.limit(limit)).scalars().all()))
    return {
        "points": [
            {
                "t": iso_utc(r.created_at),
                "zone_id": r.zone_id,
                "mode": r.mode,
                "rainfall": round(r.rainfall, 2),
                "humidity": round(r.humidity, 2),
                "temperature": round(r.temperature, 2),
                "vibration": round(r.vibration, 2),
                "slope_angle": round(r.slope_angle, 2),
                "displacement": round(r.displacement, 2),
                "pore_pressure": round(r.pore_pressure, 2),
            }
            for r in rows
        ]
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    """Counts and distributions for the History page header."""
    level_counts = dict(
        db.execute(select(Prediction.risk_level, func.count(Prediction.id))
                   .group_by(Prediction.risk_level)).all()
    )
    zone_peaks = [
        {"zone_id": z, "peak": round(float(p), 1), "mean": round(float(m), 1), "samples": int(n)}
        for z, p, m, n in db.execute(
            select(Prediction.zone_id, func.max(Prediction.risk_score),
                   func.avg(Prediction.risk_score), func.count(Prediction.id))
            .group_by(Prediction.zone_id)
            .order_by(func.max(Prediction.risk_score).desc())
        ).all()
    ]

    return {
        "totals": {
            "predictions": db.execute(select(func.count(Prediction.id))).scalar_one(),
            "sensor_readings": db.execute(select(func.count(SensorReading.id))).scalar_one(),
            "alerts": db.execute(select(func.count(Alert.id))).scalar_one(),
            "image_analyses": db.execute(select(func.count(ImageAnalysis.id))).scalar_one(),
        },
        "predictions_by_level": level_counts,
        "zone_peaks": zone_peaks,
    }


@router.get("/predictions")
def prediction_log(
    limit: int = Query(60, ge=1, le=500),
    zone_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Full prediction records, newest first, including their explanations."""
    stmt = select(Prediction).order_by(Prediction.created_at.desc())
    if zone_id:
        stmt = stmt.where(Prediction.zone_id == zone_id)
    rows = db.execute(stmt.limit(limit)).scalars().all()

    return {
        "records": [
            {
                "id": r.id,
                "t": iso_utc(r.created_at),
                "zone_id": r.zone_id,
                "source": r.source,
                "risk_score": round(r.risk_score, 1),
                "risk_level": r.risk_level,
                "probability": round(r.probability, 4),
                "recommended_action": r.recommended_action,
                "features": json.loads(r.features_json or "{}"),
                "contributions": json.loads(r.contributions_json or "[]"),
            }
            for r in rows
        ]
    }
