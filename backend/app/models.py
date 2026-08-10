"""Persisted records. All values in this demo originate from SIMULATED sensors."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    """Naive UTC — the single time convention used by every column here.

    The columns are plain DateTime (no timezone), so an aware value would have
    its offset silently dropped on write. SQLite then compares the stored text
    against any aware bind parameter, whose "+00:00" suffix makes those
    comparisons unreliable. Storing naive UTC everywhere keeps writes, reads and
    range filters consistent; the API appends the UTC marker on serialisation.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(dt: datetime | None) -> str | None:
    """Serialise a stored (naive UTC) timestamp with an explicit UTC marker,
    so clients parse it correctly instead of assuming local time."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class SensorReading(Base):
    """One tick of the simulated IoT network for a single zone."""

    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    zone_id: Mapped[str] = mapped_column(String(16), index=True)
    mode: Mapped[str] = mapped_column(String(16))  # NORMAL | WARNING | CRITICAL

    rainfall: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    vibration: Mapped[float] = mapped_column(Float)
    slope_angle: Mapped[float] = mapped_column(Float)
    displacement: Mapped[float] = mapped_column(Float)
    pore_pressure: Mapped[float] = mapped_column(Float)


class Prediction(Base):
    """A risk-engine inference, stored for the history page and trend charts."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    zone_id: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(24), default="simulation")  # simulation | manual | image

    risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    probability: Mapped[float] = mapped_column(Float)
    recommended_action: Mapped[str] = mapped_column(Text)

    features_json: Mapped[str] = mapped_column(Text)       # inputs used
    contributions_json: Mapped[str] = mapped_column(Text)  # explainability payload


class Alert(Base):
    """Raised when a zone reaches HIGH or CRITICAL."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    zone_id: Mapped[str] = mapped_column(String(16), index=True)
    zone_name: Mapped[str] = mapped_column(String(64))

    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(128))
    message: Mapped[Text] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    top_factors_json: Mapped[str] = mapped_column(Text, default="[]")

    channel: Mapped[str] = mapped_column(String(32), default="IN_APP")
    dispatch_status: Mapped[str] = mapped_column(String(24), default="SIMULATED")
    acknowledged: Mapped[int] = mapped_column(Integer, default=0)
    acknowledged_by: Mapped[str] = mapped_column(String(64), default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ImageAnalysis(Base):
    """Result of a rock-face computer-vision scan."""

    __tablename__ = "image_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    zone_id: Mapped[str] = mapped_column(String(16), index=True, default="A-01")
    filename: Mapped[str] = mapped_column(String(256))

    crack_density: Mapped[float] = mapped_column(Float)
    crack_severity: Mapped[float] = mapped_column(Float)
    crack_count: Mapped[int] = mapped_column(Integer)
    max_crack_length: Mapped[float] = mapped_column(Float)
    rock_condition: Mapped[float] = mapped_column(Float)
    detector: Mapped[str] = mapped_column(String(32), default="opencv")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
