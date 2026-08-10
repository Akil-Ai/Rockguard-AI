"""Alert generation and dispatch.

Alerts are raised whenever a zone assessment lands on HIGH or CRITICAL.

Dispatch is SIMULATED by default: the alert is written to the database and shown
in the UI, and the outbound record is stamped `SIMULATED`. If Twilio credentials
are supplied via .env the same alert is additionally sent as a real SMS. No keys
are hard-coded anywhere in this repo.
"""
from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Alert, iso_utc, utcnow

ALERTABLE_LEVELS = ("HIGH", "CRITICAL")


def _dispatch(alert: Alert) -> tuple[str, str]:
    """Return (channel, status). Real send only if credentials are configured."""
    if not settings.sms_configured or not settings.recipient_list:
        return "IN_APP", "SIMULATED"

    try:  # pragma: no cover - requires network + credentials
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        body = f"{alert.title}\n{alert.message}\nAction: {alert.recommended_action}"
        for number in settings.recipient_list:
            client.messages.create(body=body[:1500], from_=settings.twilio_from_number, to=number)
        return "SMS", "SENT"
    except Exception as exc:
        return "SMS", f"FAILED: {type(exc).__name__}"


def _recent_duplicate(db: Session, zone_id: str, level: str) -> Alert | None:
    """Suppress repeats so a 5-second tick loop cannot flood the alert list."""
    # Naive UTC to match the stored column convention (see models.utcnow).
    cutoff = utcnow() - timedelta(minutes=settings.alert_cooldown_minutes)
    stmt = (
        select(Alert)
        .where(Alert.zone_id == zone_id, Alert.risk_level == level, Alert.created_at >= cutoff)
        .order_by(Alert.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def build_message(zone_id: str, zone_name: str, level: str, score: float,
                  personnel: int, top_factors: list[dict]) -> tuple[str, str]:
    icon = "🚨" if level == "CRITICAL" else "⚠️"
    title = f"{icon} ROCKFALL {'WARNING' if level == 'CRITICAL' else 'ADVISORY'} — {zone_id}"
    drivers = ", ".join(f"{f['label']} {f['level']}" for f in top_factors[:3]) or "multiple factors"
    message = (
        f"Zone: {zone_id} ({zone_name})\n"
        f"Risk: {score:.0f}/100 [{level}]\n"
        f"Personnel in zone: {personnel}\n"
        f"Primary drivers: {drivers}"
    )
    return title, message


def maybe_raise(db: Session, assessment: dict) -> Alert | None:
    """Create an alert for an assessment if it warrants one. Returns None otherwise."""
    level = assessment["risk_level"]
    if level not in ALERTABLE_LEVELS:
        return None

    zone_id = assessment["zone_id"]
    if _recent_duplicate(db, zone_id, level) is not None:
        return None

    top_factors = [c for c in assessment.get("contributions", []) if c["contribution_points"] > 0][:3]
    title, message = build_message(
        zone_id, assessment["zone_name"], level, assessment["risk_score"],
        assessment.get("personnel", 0), top_factors,
    )

    alert = Alert(
        zone_id=zone_id,
        zone_name=assessment["zone_name"],
        risk_level=level,
        risk_score=assessment["risk_score"],
        title=title,
        message=message,
        recommended_action=assessment["recommended_action"],
        top_factors_json=json.dumps(top_factors),
    )
    alert.channel, alert.dispatch_status = _dispatch(alert)

    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def serialize(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "created_at": iso_utc(alert.created_at),
        "zone_id": alert.zone_id,
        "zone_name": alert.zone_name,
        "risk_level": alert.risk_level,
        "risk_score": round(alert.risk_score, 1),
        "title": alert.title,
        "message": alert.message,
        "recommended_action": alert.recommended_action,
        "top_factors": json.loads(alert.top_factors_json or "[]"),
        "channel": alert.channel,
        "dispatch_status": alert.dispatch_status,
        "acknowledged": bool(alert.acknowledged),
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": iso_utc(alert.acknowledged_at),
    }
