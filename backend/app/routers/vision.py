"""Rock-face image analysis endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImageAnalysis, iso_utc
from ..services import assessment, crack_detector
from ..services.mine import ZONE_BY_ID
from ..services.simulator import simulator

router = APIRouter(prefix="/vision", tags=["vision"])

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
ALLOWED_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")


@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    zone_id: str = Form("A-04"),
    apply_to_zone: bool = Form(True),
    db: Session = Depends(get_db),
) -> dict:
    """Run crack detection on an uploaded rock-face or drone image.

    When `apply_to_zone` is set, the measured crack density/severity and the
    inferred rock quality are pushed into that zone's live sensor state, so the
    dashboard risk immediately reflects what the camera saw.
    """
    name = (file.filename or "upload").lower()
    if not name.endswith(ALLOWED_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Expected one of: {', '.join(ALLOWED_SUFFIXES)}",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large ({len(raw) / 1e6:.1f} MB). Limit is {MAX_UPLOAD_BYTES / 1e6:.0f} MB.",
        )

    try:
        result = crack_detector.analyze(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    metrics = {
        "crack_density": result.crack_density,
        "crack_severity": result.crack_severity,
        "crack_count": result.crack_count,
        "max_crack_length": result.max_crack_length,
        "mean_crack_width": result.mean_crack_width,
        "total_crack_length": result.total_crack_length,
        "orientation_spread": result.orientation_spread,
        "rock_condition": result.rock_condition,
        "severity_band": result.severity_band,
    }

    record = ImageAnalysis(
        zone_id=zone_id if zone_id in ZONE_BY_ID else "A-04",
        filename=file.filename or "upload",
        crack_density=result.crack_density,
        crack_severity=result.crack_severity,
        crack_count=result.crack_count,
        max_crack_length=result.max_crack_length,
        rock_condition=result.rock_condition,
        detector=result.detector,
        metrics_json=json.dumps(metrics),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    zone_assessment = None
    alerts_raised: list[dict] = []
    if apply_to_zone and record.zone_id in ZONE_BY_ID:
        simulator.apply_image_analysis(
            record.zone_id, result.crack_density, result.crack_severity, result.rock_condition
        )
        zone_assessment = assessment.assess_zone(record.zone_id)
        alerts_raised = assessment.persist_tick(db, [zone_assessment], source="image")

    return {
        "id": record.id,
        "created_at": iso_utc(record.created_at),
        "filename": record.filename,
        "zone_id": record.zone_id,
        "detector": result.detector,
        "metrics": metrics,
        "cracks": result.cracks,
        "annotated_image": result.annotated_b64,
        "notes": result.notes,
        "applied_to_zone": zone_assessment is not None,
        "zone_assessment": zone_assessment,
        "alerts_raised": alerts_raised,
        "disclaimer": (
            "Heuristic computer vision on a demo image. Detections are indicative "
            "measurements, not verified geotechnical observations."
        ),
    }


@router.get("/history")
def vision_history(limit: int = 25, db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(ImageAnalysis).order_by(ImageAnalysis.created_at.desc()).limit(min(limit, 200))
    ).scalars().all()

    return {
        "analyses": [
            {
                "id": r.id,
                "created_at": iso_utc(r.created_at),
                "zone_id": r.zone_id,
                "filename": r.filename,
                "detector": r.detector,
                "crack_density": r.crack_density,
                "crack_severity": r.crack_severity,
                "crack_count": r.crack_count,
                "rock_condition": r.rock_condition,
                "metrics": json.loads(r.metrics_json or "{}"),
            }
            for r in rows
        ]
    }
