"""Alert list, acknowledgement and stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Alert, utcnow
from ..schemas import AcknowledgeRequest
from ..services import alerts as alerts_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    limit: int = Query(50, ge=1, le=500),
    level: str | None = Query(None, pattern="^(HIGH|CRITICAL)$"),
    zone_id: str | None = None,
    unacknowledged_only: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if level:
        stmt = stmt.where(Alert.risk_level == level)
    if zone_id:
        stmt = stmt.where(Alert.zone_id == zone_id)
    if unacknowledged_only:
        stmt = stmt.where(Alert.acknowledged == 0)

    rows = db.execute(stmt.limit(limit)).scalars().all()

    counts = dict(
        db.execute(select(Alert.risk_level, func.count(Alert.id)).group_by(Alert.risk_level)).all()
    )
    active = db.execute(
        select(func.count(Alert.id)).where(Alert.acknowledged == 0)
    ).scalar_one()

    return {
        "alerts": [alerts_service.serialize(a) for a in rows],
        "stats": {
            "total": sum(counts.values()),
            "by_level": counts,
            "unacknowledged": active,
        },
        "dispatch_mode": "SMS (Twilio configured)" if settings.sms_configured else "SIMULATED (in-app only)",
        "note": (
            "External SMS/WhatsApp dispatch is simulated unless Twilio credentials "
            "are supplied in backend/.env. Alerts are always recorded in-app."
        ),
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge(alert_id: int, payload: AcknowledgeRequest, db: Session = Depends(get_db)) -> dict:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    alert.acknowledged = 1
    alert.acknowledged_by = payload.acknowledged_by
    alert.acknowledged_at = utcnow()
    db.commit()
    db.refresh(alert)
    return alerts_service.serialize(alert)


@router.post("/acknowledge-all")
def acknowledge_all(payload: AcknowledgeRequest, db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Alert).where(Alert.acknowledged == 0)).scalars().all()
    now = utcnow()
    for alert in rows:
        alert.acknowledged = 1
        alert.acknowledged_by = payload.acknowledged_by
        alert.acknowledged_at = now
    db.commit()
    return {"acknowledged": len(rows)}
