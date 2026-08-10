"""The RockGuard AI risk engine.

Turns a feature vector into: probability -> risk score -> risk level ->
explanation -> recommended action.

Two inference paths:
  1. The trained scikit-learn model (preferred).
  2. A deterministic fallback that evaluates the same latent hazard function
     the training data was drawn from. This keeps the API alive if the model
     artifact is missing, so a demo never dies on a missing .joblib file.

Explainability uses *counterfactual ablation*: for each feature we re-score the
sample with that one feature reset to a safe reference value and attribute the
drop in risk score to it. With only 8 features this is exact, cheap and
model-agnostic (no SHAP dependency), and it answers the operator's real
question: "how many risk points is this factor adding right now?"
"""
from __future__ import annotations

import threading
from typing import Any

import numpy as np
import pandas as pd

from ..config import settings
from ..ml.synthetic import FEATURE_META, FEATURE_NAMES, SAFE_BASELINE, latent_hazard

# Presentation transform: maps a small event probability onto an operator-legible
# 0-100 scale. Strictly monotone, so it never reorders risk — it only spreads the
# low-probability region out so the difference between "quiet" and "watch this"
# is visible on a gauge.
RISK_EXPONENT = 0.45

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

_model_lock = threading.Lock()
_model_bundle: dict | None = None
_model_load_attempted = False


# --------------------------------------------------------------------------- #
# Model loading
# --------------------------------------------------------------------------- #
def load_model() -> dict | None:
    """Lazily load the trained model bundle; None means fallback mode."""
    global _model_bundle, _model_load_attempted
    with _model_lock:
        if _model_bundle is None and not _model_load_attempted:
            _model_load_attempted = True
            try:
                import joblib

                from ..ml.train_model import MODEL_PATH

                if MODEL_PATH.exists():
                    _model_bundle = joblib.load(MODEL_PATH)
            except Exception:  # pragma: no cover - defensive, demo must not die
                _model_bundle = None
        return _model_bundle


def model_info() -> dict:
    bundle = load_model()
    if bundle is None:
        return {
            "loaded": False,
            "engine": "analytical-fallback",
            "detail": "Trained artifact not found; using the deterministic hazard function.",
        }
    return {"loaded": True, "engine": bundle.get("kind", "unknown"), "detail": "Trained on synthetic data."}


# --------------------------------------------------------------------------- #
# Core scoring
# --------------------------------------------------------------------------- #
def _coerce(features: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in FEATURE_NAMES:
        meta = FEATURE_META[name]
        raw = features.get(name, SAFE_BASELINE[name])
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = float(SAFE_BASELINE[name])
        out[name] = float(np.clip(val, meta["min"], meta["max"]))
    return out


def _probabilities(rows: list[dict[str, float]]) -> np.ndarray:
    """Vectorised P(rockfall) for a batch of feature dicts."""
    frame = pd.DataFrame(rows)[FEATURE_NAMES]
    bundle = load_model()
    if bundle is not None:
        try:
            p = bundle["model"].predict_proba(frame)[:, 1]
            return np.clip(p, 1e-6, 1 - 1e-6)
        except Exception:
            pass
    p = latent_hazard({c: frame[c].to_numpy(dtype=float) for c in FEATURE_NAMES})
    return np.clip(p, 1e-6, 1 - 1e-6)


def probability_to_score(p: np.ndarray | float) -> np.ndarray | float:
    return 100.0 * np.power(p, RISK_EXPONENT)


def classify(score: float) -> str:
    if score >= settings.threshold_critical:
        return "CRITICAL"
    if score >= settings.threshold_high:
        return "HIGH"
    if score >= settings.threshold_medium:
        return "MEDIUM"
    return "LOW"


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
def _contribution_band(points: float, pct: float, overall_level: str) -> str:
    """Band a single factor as LOW..CRITICAL.

    Based on the factor's *share* of the total risk being driven, not on raw
    points: once several factors are extreme the score saturates near 100, and
    removing any single one barely moves it, so absolute points would under-rate
    every driver exactly when the situation is worst.

    Two guards keep the label honest:
      * a small absolute floor, so a big share of almost-no-risk stays LOW;
      * a cap at the mine-wide level, so no factor is ever flagged CRITICAL
        while the zone itself is only MEDIUM.
    """
    if points < 1.0:
        return "LOW"
    if pct >= 30.0:
        band = 3
    elif pct >= 18.0:
        band = 2
    elif pct >= 8.0:
        band = 1
    else:
        band = 0
    return LEVELS[min(band, LEVELS.index(overall_level))]


def explain(features: dict[str, float], overall_level: str) -> list[dict]:
    """Counterfactual ablation attribution over the 8 input features."""
    rows = [dict(features)]
    for name in FEATURE_NAMES:
        counterfactual = dict(features)
        counterfactual[name] = SAFE_BASELINE[name]
        rows.append(counterfactual)

    scores = np.asarray(probability_to_score(_probabilities(rows)), dtype=float)
    base_score = scores[0]
    deltas = base_score - scores[1:]  # points removed by making the factor safe

    positive_total = float(np.sum(np.clip(deltas, 0, None))) or 1.0

    out: list[dict] = []
    for name, delta in zip(FEATURE_NAMES, deltas):
        meta = FEATURE_META[name]
        points = float(delta)
        pct = max(points, 0.0) / positive_total * 100.0
        out.append(
            {
                "feature": name,
                "label": meta["label"],
                "value": round(float(features[name]), 2),
                "unit": meta["unit"],
                "contribution_points": round(points, 2),
                "contribution_pct": round(pct, 1),
                "level": _contribution_band(points, pct, overall_level),
                "direction": "increases risk" if points > 0.5 else ("reduces risk" if points < -0.5 else "neutral"),
            }
        )

    out.sort(key=lambda d: d["contribution_points"], reverse=True)
    return out


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #
_ACTION_BY_LEVEL = {
    "LOW": "Normal operations. Continue routine monitoring and scheduled slope inspections.",
    "MEDIUM": "Heighten monitoring. Brief the shift supervisor and increase visual inspection frequency of the affected bench.",
    "HIGH": "Restrict access to the bench. Suspend non-essential work below the face and dispatch a geotechnical inspection.",
    "CRITICAL": "EVACUATE personnel and equipment from the zone immediately. Barricade all access routes and halt blasting until a geotechnical clearance is issued.",
}

# Factor-specific follow-ups appended to the base action for the dominant driver.
_ACTION_BY_FACTOR = {
    "rainfall": "Inspect surface drainage and berm run-off channels; water is the dominant driver.",
    "humidity": "Sustained saturation detected — verify piezometer readings on this bench.",
    "temperature": "Freeze-thaw conditions — check for ice wedging in open joints before shift start.",
    "slope_angle": "Bench geometry is over-steepened — schedule re-profiling or slope-angle review.",
    "vibration": "Review the blast design and delay timing; consider reducing charge per delay near this face.",
    "crack_density": "Dense fracture network on the face — install crack meters and prioritise scaling.",
    "crack_severity": "Wide/propagating fractures observed — deploy prism or radar monitoring on this face.",
    "rock_condition": "Poor rock-mass quality — evaluate rock bolting, mesh or shotcrete support.",
}


def recommend(level: str, contributions: list[dict]) -> str:
    action = _ACTION_BY_LEVEL[level]
    if level == "LOW" or not contributions:
        return action
    top = contributions[0]
    if top["contribution_points"] < 3.0:
        return action
    extra = _ACTION_BY_FACTOR.get(top["feature"], "")
    return f"{action} {extra}".strip()


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def predict(features: dict[str, Any], explain_result: bool = True) -> dict:
    """Score one feature vector and return the full decision payload."""
    clean = _coerce(features)
    probability = float(_probabilities([clean])[0])
    score = float(probability_to_score(probability))
    score = float(np.clip(round(score, 1), 0.0, 100.0))
    level = classify(score)

    contributions = explain(clean, level) if explain_result else []
    return {
        "risk_score": score,
        "risk_level": level,
        "probability": round(probability, 4),
        "recommended_action": recommend(level, contributions),
        "features": {k: round(v, 2) for k, v in clean.items()},
        "contributions": contributions,
        "engine": model_info(),
        "data_note": "Inputs are SIMULATED. Model trained on synthetic data — not validated on real rockfall events.",
    }
