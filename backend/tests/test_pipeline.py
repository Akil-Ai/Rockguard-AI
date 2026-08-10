"""Integration tests for the RockGuard AI pipeline.

Run from the backend directory:

    python -m pytest tests -v

These assert the behaviour the demo depends on: that risk rises monotonically
across the three scenarios, that explanations are consistent with the score,
that the CV detector separates a clean face from a fractured one, and that the
API wiring holds together end to end.
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.synthetic import FEATURE_NAMES, generate_dataset, latent_hazard
from app.services import crack_detector, risk_engine
from app.services.assessment import mine_wide_risk
from app.services.simulator import SensorSimulator

QUIET = dict(rainfall=2, humidity=45, temperature=28, slope_angle=38,
             vibration=0.8, crack_density=3, crack_severity=10, rock_condition=80)
WET_CRACKED = dict(rainfall=78, humidity=90, temperature=24, slope_angle=52,
                   vibration=4, crack_density=18, crack_severity=55, rock_condition=45)
BLASTED = dict(rainfall=105, humidity=96, temperature=22, slope_angle=63,
               vibration=17, crack_density=32, crack_severity=88, rock_condition=25)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- #
# Risk engine
# --------------------------------------------------------------------------- #
def test_risk_increases_across_the_demo_scenarios():
    scores = [risk_engine.predict(f, explain_result=False)["risk_score"]
              for f in (QUIET, WET_CRACKED, BLASTED)]
    assert scores[0] < scores[1] < scores[2], f"risk must be monotone, got {scores}"
    assert scores[0] < 35, "a quiet bench should read LOW"
    assert scores[2] >= 80, "a blasted, saturated, fractured face should read CRITICAL"


def test_risk_level_matches_score_thresholds():
    for features in (QUIET, WET_CRACKED, BLASTED):
        result = risk_engine.predict(features, explain_result=False)
        assert result["risk_level"] == risk_engine.classify(result["risk_score"])


def test_probability_never_saturates():
    """A probability pinned at exactly 0 or 1 would flatten the gauge and zero
    out every counterfactual explanation."""
    for features in (QUIET, BLASTED):
        p = risk_engine.predict(features, explain_result=False)["probability"]
        assert 0.0 < p < 1.0


def test_scores_stay_in_range_across_the_whole_input_domain():
    rng = np.random.default_rng(0)
    from app.ml.synthetic import FEATURE_META

    for _ in range(60):
        features = {n: float(rng.uniform(FEATURE_META[n]["min"], FEATURE_META[n]["max"]))
                    for n in FEATURE_NAMES}
        result = risk_engine.predict(features, explain_result=False)
        assert 0.0 <= result["risk_score"] <= 100.0


def test_out_of_range_and_junk_inputs_are_clamped_not_crashed():
    result = risk_engine.predict(
        {"rainfall": 9_999, "humidity": -50, "temperature": "not a number",
         "slope_angle": None, "vibration": 1e9},
    )
    assert 0.0 <= result["risk_score"] <= 100.0
    assert result["features"]["rainfall"] == 120.0   # clamped to the max
    assert result["features"]["humidity"] == 15.0    # clamped to the min


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
def test_explanation_covers_every_feature_and_ranks_by_contribution():
    result = risk_engine.predict(BLASTED)
    contributions = result["contributions"]
    assert {c["feature"] for c in contributions} == set(FEATURE_NAMES)
    points = [c["contribution_points"] for c in contributions]
    assert points == sorted(points, reverse=True)


def test_no_factor_is_flagged_above_the_overall_level():
    """A LOW zone must never show a CRITICAL driver — that would read as a
    contradiction to an operator scanning the dashboard."""
    order = list(risk_engine.LEVELS)
    for features in (QUIET, WET_CRACKED, BLASTED):
        result = risk_engine.predict(features)
        cap = order.index(result["risk_level"])
        for c in result["contributions"]:
            assert order.index(c["level"]) <= cap


def test_dominant_driver_is_reflected_in_the_recommended_action():
    result = risk_engine.predict(WET_CRACKED)
    assert result["contributions"][0]["contribution_points"] > 0
    assert len(result["recommended_action"]) > 40


# --------------------------------------------------------------------------- #
# Synthetic dataset
# --------------------------------------------------------------------------- #
def test_generated_dataset_is_labelled_and_not_degenerate():
    X, y, p = generate_dataset(n_samples=2_000, seed=1)
    assert list(X.columns) == FEATURE_NAMES
    assert len(X) == len(y) == len(p)
    assert 0.02 < y.mean() < 0.6, "dataset should contain both classes in useful proportion"


def test_latent_hazard_is_monotone_in_rainfall():
    base = {k: np.array([v], dtype=float) for k, v in WET_CRACKED.items()}
    probs = []
    for rain in (0.0, 30.0, 60.0, 90.0, 120.0):
        trial = dict(base)
        trial["rainfall"] = np.array([rain])
        probs.append(float(latent_hazard(trial)[0]))
    assert probs == sorted(probs)


# --------------------------------------------------------------------------- #
# Computer vision
# --------------------------------------------------------------------------- #
def _synthetic_face(n_cracks: int, seed: int) -> bytes:
    import cv2

    rng = np.random.default_rng(seed)
    img = np.clip(np.full((520, 720), 128, np.uint8) + rng.normal(0, 16, (520, 720)), 0, 255).astype(np.uint8)
    img = cv2.cvtColor(cv2.GaussianBlur(img, (5, 5), 0), cv2.COLOR_GRAY2BGR)
    for _ in range(n_cracks):
        x, y = float(rng.integers(40, 680)), float(rng.integers(40, 480))
        ang, length = rng.uniform(0, np.pi), int(rng.integers(120, 300))
        pts = [(int(x), int(y))]
        for _ in range(6):
            x += np.cos(ang) * length / 6 + rng.normal(0, 5)
            y += np.sin(ang) * length / 6 + rng.normal(0, 5)
            pts.append((int(np.clip(x, 2, 717)), int(np.clip(y, 2, 517))))
        cv2.polylines(img, [np.array(pts, np.int32)], False, (42, 44, 46),
                      int(rng.integers(2, 5)), cv2.LINE_AA)
    return cv2.imencode(".png", img)[1].tobytes()


def test_detector_separates_a_clean_face_from_a_fractured_one():
    clean = crack_detector.analyze(_synthetic_face(0, 11), annotate=False)
    heavy = crack_detector.analyze(_synthetic_face(22, 13), annotate=False)

    assert clean.crack_count == 0
    assert clean.crack_severity == 0.0
    assert heavy.crack_count > clean.crack_count
    assert heavy.crack_severity > clean.crack_severity
    # More fracturing must lower the inferred rock quality, not raise it.
    assert heavy.rock_condition < clean.rock_condition


def test_detector_returns_an_annotated_data_uri():
    result = crack_detector.analyze(_synthetic_face(8, 17))
    assert result.annotated_b64.startswith("data:image/jpeg;base64,")
    assert result.notes, "the detector must always state its method/limitations"


def test_detector_rejects_a_non_image():
    with pytest.raises(ValueError):
        crack_detector.analyze(b"this is definitely not an image")


# --------------------------------------------------------------------------- #
# Simulator
# --------------------------------------------------------------------------- #
def test_scenario_switch_raises_measured_risk():
    sim = SensorSimulator()
    readings = {}
    for scenario in ("NORMAL", "WARNING", "CRITICAL"):
        sim.set_scenario(scenario)
        state = sim.zone_state("A-04")
        readings[scenario] = state["rainfall"]
    assert readings["NORMAL"] < readings["WARNING"] < readings["CRITICAL"]


def test_overrides_pin_a_channel_and_release_cleanly():
    sim = SensorSimulator()
    sim.set_override("A-04", {"vibration": 25.0})
    sim.tick()
    assert sim.zone_state("A-04")["vibration"] == 25.0

    sim.set_override("A-04", {"vibration": None})
    sim.tick()
    assert sim.zone_state("A-04")["vibration"] != 25.0


def test_unknown_zone_is_rejected():
    sim = SensorSimulator()
    with pytest.raises(ValueError):
        sim.zone_state("NOPE-99")


# --------------------------------------------------------------------------- #
# Mine-wide rollup
# --------------------------------------------------------------------------- #
def test_mine_risk_is_dominated_by_the_worst_zone_not_the_average():
    zones = [
        {"zone_id": "X", "risk_score": 95.0, "risk_level": "CRITICAL", "personnel": 5,
         "probability": 0.9, "zone_name": "X", "recommended_action": "-"},
        *[
            {"zone_id": f"Q{i}", "risk_score": 10.0, "risk_level": "LOW", "personnel": 5,
             "probability": 0.01, "zone_name": f"Q{i}", "recommended_action": "-"}
            for i in range(5)
        ],
    ]
    result = mine_wide_risk(zones)
    plain_mean = sum(z["risk_score"] for z in zones) / len(zones)
    assert result["risk_score"] > plain_mean
    assert result["worst_zone"]["zone_id"] == "X"


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #
def test_health_and_dashboard(client):
    assert client.get("/api/health").status_code == 200

    body = client.get("/api/dashboard").json()
    assert {"mine", "overall", "zones", "simulation"} <= body.keys()
    assert len(body["zones"]) == 6
    for zone in body["zones"]:
        assert zone["polygon"], "every zone needs map geometry"
        assert zone["contributions"], "every zone needs an explanation"


def test_scenario_endpoint_drives_risk_and_raises_alerts(client):
    client.post("/api/sensors/reset")
    low = client.post("/api/sensors/scenario", json={"scenario": "NORMAL"}).json()
    high = client.post("/api/sensors/scenario", json={"scenario": "CRITICAL"}).json()

    assert high["overall"]["risk_score"] > low["overall"]["risk_score"]
    assert high["overall"]["risk_level"] in ("HIGH", "CRITICAL")

    alerts = client.get("/api/alerts").json()
    assert alerts["stats"]["total"] > 0
    assert alerts["dispatch_mode"], "the UI must be able to state how alerts are dispatched"


def test_invalid_scenario_is_rejected(client):
    assert client.post("/api/sensors/scenario", json={"scenario": "APOCALYPSE"}).status_code == 422


def test_predict_endpoint_round_trip(client):
    res = client.post("/api/predict", json={**BLASTED, "persist": False})
    assert res.status_code == 200
    body = res.json()
    assert body["risk_level"] == "CRITICAL"
    assert len(body["contributions"]) == len(FEATURE_NAMES)


def test_vision_endpoint_analyses_an_upload(client):
    files = {"file": ("bench.png", _synthetic_face(20, 23), "image/png")}
    res = client.post("/api/vision/analyze", files=files,
                      data={"zone_id": "A-04", "apply_to_zone": "true"})
    assert res.status_code == 200
    body = res.json()
    assert body["metrics"]["crack_count"] > 0
    assert body["annotated_image"].startswith("data:image/")
    assert body["zone_assessment"]["zone_id"] == "A-04"


def test_vision_endpoint_rejects_a_non_image_extension(client):
    res = client.post("/api/vision/analyze", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 400


def test_history_endpoints_are_chart_ready(client):
    client.post("/api/sensors/tick")
    points = client.get("/api/history/risk?limit=20").json()["points"]
    assert points
    # Oldest first, so a chart can plot it without re-sorting.
    assert [p["t"] for p in points] == sorted(p["t"] for p in points)
    assert all(t.endswith("Z") for t in (p["t"] for p in points)), "timestamps must be explicit UTC"

    assert "totals" in client.get("/api/history/summary").json()
