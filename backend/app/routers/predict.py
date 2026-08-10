"""Manual risk prediction and model metadata."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Prediction
from ..schemas import PredictRequest, feature_schema
from ..services import risk_engine
from ..services.mine import ZONE_BY_ID

router = APIRouter(tags=["prediction"])


@router.get("/features")
def get_features() -> dict:
    """Slider bounds/units so the frontend never hard-codes them."""
    return {
        "features": feature_schema(),
        "thresholds": {
            "MEDIUM": risk_engine.settings.threshold_medium,
            "HIGH": risk_engine.settings.threshold_high,
            "CRITICAL": risk_engine.settings.threshold_critical,
        },
        "presets": {
            "NORMAL": {"rainfall": 2, "humidity": 45, "temperature": 28, "slope_angle": 38,
                       "vibration": 0.8, "crack_density": 3, "crack_severity": 10, "rock_condition": 80},
            "HEAVY_RAIN_CRACKS": {"rainfall": 78, "humidity": 90, "temperature": 24, "slope_angle": 52,
                                  "vibration": 4, "crack_density": 18, "crack_severity": 55, "rock_condition": 45},
            "BLAST_SEVERE_CRACKS": {"rainfall": 105, "humidity": 96, "temperature": 22, "slope_angle": 63,
                                    "vibration": 17, "crack_density": 32, "crack_severity": 88, "rock_condition": 25},
        },
    }


@router.post("/predict")
def predict(payload: PredictRequest, db: Session = Depends(get_db)) -> dict:
    features = payload.model_dump(exclude={"zone_id", "persist"})
    result = risk_engine.predict(features)

    zone_id = payload.zone_id if payload.zone_id in ZONE_BY_ID else "MANUAL"
    if payload.persist:
        db.add(
            Prediction(
                zone_id=zone_id,
                source="manual",
                risk_score=result["risk_score"],
                risk_level=result["risk_level"],
                probability=result["probability"],
                recommended_action=result["recommended_action"],
                features_json=json.dumps(result["features"]),
                contributions_json=json.dumps(result["contributions"]),
            )
        )
        db.commit()

    return {"zone_id": zone_id, **result}


@router.get("/model/info")
def model_info() -> dict:
    """Engine status and the training metrics, with their caveats attached."""
    from ..ml.train_model import METRICS_PATH

    metrics = {}
    path = Path(METRICS_PATH)
    if path.exists():
        try:
            metrics = json.loads(path.read_text(encoding="utf-8"))
            metrics.pop("report", None)  # too verbose for the UI
        except (OSError, json.JSONDecodeError):
            metrics = {}

    return {
        "engine": risk_engine.model_info(),
        "metrics": metrics,
        "explainability": {
            "method": "counterfactual ablation",
            "description": (
                "Each feature is individually reset to a safe reference value and the "
                "drop in risk score is attributed to it. Exact for 8 features, "
                "model-agnostic, and no SHAP dependency."
            ),
        },
        "disclaimer": (
            "Trained on a SYNTHETIC dataset generated from a hand-written hazard "
            "function. Metrics describe hold-out performance on that synthetic data "
            "only and are NOT evidence of real-world rockfall prediction accuracy."
        ),
    }
