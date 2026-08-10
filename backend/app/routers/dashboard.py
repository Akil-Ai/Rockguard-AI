"""Dashboard, mine metadata and zone endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import assessment
from ..services.mine import ZONE_BY_ID, mine_summary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    """Everything the control-room home screen needs, in one round trip."""
    return assessment.dashboard_payload(db)


@router.get("/mine")
def get_mine() -> dict:
    return mine_summary()


@router.get("/zones")
def list_zones() -> dict:
    zones = assessment.assess_all()
    return {
        "mine": mine_summary(),
        "overall": assessment.mine_wide_risk(zones),
        "zones": zones,
    }


@router.get("/zones/{zone_id}")
def get_zone(zone_id: str) -> dict:
    if zone_id not in ZONE_BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_id}'.")
    return assessment.assess_zone(zone_id)
