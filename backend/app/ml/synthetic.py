"""SYNTHETIC training-data generator for the RockGuard AI risk engine.

=====================================================================
IMPORTANT / HONESTY NOTE
No public labelled rockfall dataset for Indian open-pit mines was used
here. Every row produced by this module is ARTIFICIAL. It is sampled
from a hand-written latent hazard function whose coefficients encode
*qualitative* slope-stability relationships found in the geotechnical
literature (water ingress into joints, blast-induced vibration, joint
density, slope geometry, rock-mass quality).

The coefficients are NOT fitted to real failures and carry no
real-world predictive validity. The trained model demonstrates the
pipeline; it must never be used for actual mine-safety decisions.
=====================================================================
"""
from __future__ import annotations

import numpy as np

# Canonical feature order — every consumer must use this exact ordering.
FEATURE_NAMES: list[str] = [
    "rainfall",
    "humidity",
    "temperature",
    "slope_angle",
    "vibration",
    "crack_density",
    "crack_severity",
    "rock_condition",
]

# Human-facing metadata: units, plausible operating range, and whether a
# *higher* value means *more* hazard (rock_condition is inverted).
FEATURE_META: dict[str, dict] = {
    "rainfall":       {"label": "Rainfall",        "unit": "mm/24h", "min": 0,  "max": 120, "higher_is_worse": True},
    "humidity":       {"label": "Humidity",        "unit": "%",      "min": 15, "max": 100, "higher_is_worse": True},
    "temperature":    {"label": "Temperature",     "unit": "°C", "min": -5, "max": 48, "higher_is_worse": False},
    "slope_angle":    {"label": "Slope Angle",     "unit": "°",  "min": 20, "max": 80, "higher_is_worse": True},
    "vibration":      {"label": "Vibration (PPV)", "unit": "mm/s",   "min": 0,  "max": 30,  "higher_is_worse": True},
    "crack_density":  {"label": "Crack Density",   "unit": "%",      "min": 0,  "max": 45,  "higher_is_worse": True},
    "crack_severity": {"label": "Crack Severity",  "unit": "/100",   "min": 0,  "max": 100, "higher_is_worse": True},
    "rock_condition": {"label": "Rock Quality",    "unit": "/100",   "min": 0,  "max": 100, "higher_is_worse": False},
}

# Reference "as safe as it plausibly gets" vector. Used as the counterfactual
# baseline for the ablation-based explainability in services/risk_engine.py.
SAFE_BASELINE: dict[str, float] = {
    "rainfall": 2.0,
    "humidity": 40.0,
    "temperature": 26.0,
    "slope_angle": 34.0,
    "vibration": 1.0,
    "crack_density": 3.0,
    "crack_severity": 8.0,
    "rock_condition": 82.0,
}


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


# Weights of the artificial hazard index. Each input is first normalised to
# roughly 0..1 over its operating range, so the weights are directly comparable
# and sum to ~1.0 before the interaction terms are added.
HAZARD_WEIGHTS = {
    "rainfall": 0.16,
    "humidity": 0.06,
    "slope_angle": 0.16,
    "vibration": 0.16,
    "crack_density": 0.18,
    "crack_severity": 0.10,
    "rock_quality_deficit": 0.14,
    "freeze_thaw": 0.04,
}
# Interaction weights (coupled failure mechanisms).
W_RAIN_X_CRACK = 0.18   # water pressure inside an open joint network
W_VIB_X_SLOPE = 0.10    # blast energy into an over-steepened bench
W_FREEZE_X_CRACK = 0.06  # ice wedging needs a joint to wedge

# Logit mapping: z = LOGIT_GAIN * (H - LOGIT_MIDPOINT).
# Tuned so a quiet bench sits near p=0.01, a wet+fractured face near p=0.3,
# and a blasted, severely-cracked, saturated face above p=0.9 — without ever
# saturating to exactly 0 or 1 (which would destroy the explanations).
LOGIT_GAIN = 9.0
LOGIT_MIDPOINT = 0.60


def hazard_index(df_like: dict[str, np.ndarray]) -> np.ndarray:
    """Normalised 0..~1.3 hazard index — the artificial "physics" of the demo.

    Terms:
      * linear drivers   - each factor normalised over its operating range
      * water x fracture - rain matters far more in a fractured face
      * blast x geometry - vibration matters more on an over-steepened bench
      * freeze x fracture- ice wedging requires an existing joint
      * rock-mass quality- competent rock suppresses everything
    """
    rain = np.asarray(df_like["rainfall"], dtype=float)
    hum = np.asarray(df_like["humidity"], dtype=float)
    temp = np.asarray(df_like["temperature"], dtype=float)
    slope = np.asarray(df_like["slope_angle"], dtype=float)
    vib = np.asarray(df_like["vibration"], dtype=float)
    dens = np.asarray(df_like["crack_density"], dtype=float)
    sev = np.asarray(df_like["crack_severity"], dtype=float)
    rock = np.asarray(df_like["rock_condition"], dtype=float)

    r = np.clip(rain / 120.0, 0, 1)
    h = np.clip((hum - 15.0) / 85.0, 0, 1)
    s = np.clip((slope - 30.0) / 40.0, 0, 1)
    v = np.clip(vib / 30.0, 0, 1)
    d = np.clip(dens / 45.0, 0, 1)
    c = np.clip(sev / 100.0, 0, 1)
    q = np.clip(1.0 - rock / 100.0, 0, 1)          # rock-quality deficit
    ft = np.clip((4.0 - temp) / 20.0, 0, 1)        # freeze-thaw exposure

    w = HAZARD_WEIGHTS
    H = (
        w["rainfall"] * r
        + w["humidity"] * h
        + w["slope_angle"] * s
        + w["vibration"] * v
        + w["crack_density"] * d
        + w["crack_severity"] * c
        + w["rock_quality_deficit"] * q
        + w["freeze_thaw"] * ft
    )
    H += W_RAIN_X_CRACK * r * d
    H += W_VIB_X_SLOPE * v * s
    H += W_FREEZE_X_CRACK * ft * d
    return H


def latent_hazard(df_like: dict[str, np.ndarray]) -> np.ndarray:
    """Ground-truth failure probability used to *label* the synthetic rows."""
    return _sigmoid(LOGIT_GAIN * (hazard_index(df_like) - LOGIT_MIDPOINT))


def generate_dataset(n_samples: int = 24_000, seed: int = 42, uniform_fraction: float = 0.35):
    """Sample a labelled SYNTHETIC dataset.

    Returns (X, y, p_true) where y is a Bernoulli draw from the latent
    hazard, so the model has to learn a genuinely noisy decision surface
    rather than memorising a threshold.
    """
    import pandas as pd

    rng = np.random.default_rng(seed)
    n = n_samples

    # Mixture of weather regimes so the model sees monsoon and dry seasons.
    regime = rng.choice(["dry", "wet", "monsoon"], size=n, p=[0.45, 0.35, 0.20])
    rainfall = np.where(
        regime == "dry", rng.gamma(1.2, 2.0, n),
        np.where(regime == "wet", rng.gamma(2.5, 9.0, n), rng.gamma(4.0, 18.0, n)),
    ).clip(0, 120)

    humidity = (35 + 0.42 * rainfall + rng.normal(0, 11, n)).clip(15, 100)
    temperature = np.where(
        regime == "monsoon", rng.normal(27, 4, n), rng.normal(29, 9, n)
    ).clip(-5, 48)

    slope_angle = rng.normal(46, 11, n).clip(20, 80)
    # Bench blasting produces occasional high-PPV events.
    vibration = np.where(
        rng.random(n) < 0.18, rng.gamma(3.0, 3.2, n), rng.gamma(1.4, 1.1, n)
    ).clip(0, 30)

    rock_condition = rng.normal(58, 17, n).clip(5, 98)
    # Poor rock is naturally more fractured; steep faces relax and open joints.
    crack_density = (
        1.5 + 0.30 * (100 - rock_condition) * rng.uniform(0.25, 0.75, n)
        + 0.10 * np.maximum(slope_angle - 45, 0)
        + rng.normal(0, 2.5, n)
    ).clip(0, 45)
    crack_severity = (
        1.9 * crack_density + 0.25 * (100 - rock_condition) + rng.normal(0, 9, n)
    ).clip(0, 100)

    X = pd.DataFrame(
        {
            "rainfall": rainfall,
            "humidity": humidity,
            "temperature": temperature,
            "slope_angle": slope_angle,
            "vibration": vibration,
            "crack_density": crack_density,
            "crack_severity": crack_severity,
            "rock_condition": rock_condition,
        }
    )[FEATURE_NAMES]

    # The correlated sampling above reflects a plausible mine, but the UI lets an
    # operator dial any combination. Blend in uniformly-sampled rows so the model
    # is defined everywhere the sliders can reach instead of extrapolating.
    n_uniform = int(n_samples * uniform_fraction)
    if n_uniform > 0:
        uni = pd.DataFrame(
            {
                name: rng.uniform(FEATURE_META[name]["min"], FEATURE_META[name]["max"], n_uniform)
                for name in FEATURE_NAMES
            }
        )[FEATURE_NAMES]
        X = pd.concat([X, uni], ignore_index=True)

    p_true = latent_hazard({c: X[c].to_numpy() for c in FEATURE_NAMES})
    y = (rng.random(len(X)) < p_true).astype(int)
    return X, y, p_true
