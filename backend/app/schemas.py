"""Request/response models for the public API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .ml.synthetic import FEATURE_META


class PredictRequest(BaseModel):
    """Manual "what-if" input for the Risk Prediction page."""

    rainfall: float = Field(2.0, ge=0, le=120, description="mm in the last 24 h")
    humidity: float = Field(45.0, ge=15, le=100, description="relative humidity %")
    temperature: float = Field(28.0, ge=-5, le=48, description="degrees Celsius")
    slope_angle: float = Field(40.0, ge=20, le=80, description="bench face angle in degrees")
    vibration: float = Field(1.0, ge=0, le=30, description="peak particle velocity, mm/s")
    crack_density: float = Field(4.0, ge=0, le=45, description="% of face area showing fractures")
    crack_severity: float = Field(12.0, ge=0, le=100, description="composite 0-100 severity")
    rock_condition: float = Field(75.0, ge=5, le=98, description="rock-mass quality, higher is better")
    zone_id: str | None = Field(None, description="Optional zone to attribute the prediction to")
    persist: bool = Field(True, description="Store the result in the history table")


class ScenarioRequest(BaseModel):
    scenario: Literal["NORMAL", "WARNING", "CRITICAL"]


class OverrideRequest(BaseModel):
    zone_id: str
    values: dict[str, float | None] = Field(
        default_factory=dict,
        description="Channel -> value. Pass null for a channel to release the override.",
    )


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field("Control Room Operator", max_length=64)


def feature_schema() -> list[dict]:
    """Slider metadata for the frontend, derived from the single source of truth."""
    return [
        {
            "name": name,
            "label": meta["label"],
            "unit": meta["unit"],
            "min": meta["min"],
            "max": meta["max"],
            "step": 0.5 if meta["max"] <= 50 else 1,
            "higher_is_worse": meta["higher_is_worse"],
        }
        for name, meta in FEATURE_META.items()
    ]
