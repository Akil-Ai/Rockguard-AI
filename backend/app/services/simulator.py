"""SIMULATED IoT sensor network.

There is no real hardware behind any of this. The simulator holds an in-memory
state per zone and advances it on every tick with a bounded random walk pulled
toward the target profile of the currently selected scenario.

Scenarios (driven from the UI buttons):
    NORMAL   - dry, quiet bench
    WARNING  - sustained rainfall, saturated slope, some blasting
    CRITICAL - storm + heavy blasting on a fractured, over-steepened face

The random walk (rather than snapping straight to target values) is what makes
the dashboard trend charts look like instrumentation instead of a step function,
and it lets an operator watch risk climb as a scenario takes hold.
"""
from __future__ import annotations

import random
import threading
from datetime import datetime, timezone

from .mine import ZONES, ZONE_BY_ID

SCENARIOS = ("NORMAL", "WARNING", "CRITICAL")

# Target values each scenario pulls the sensors toward.
# (weather is mine-wide; vibration/slope vary per zone)
_PROFILES: dict[str, dict[str, float]] = {
    "NORMAL": {
        "rainfall": 1.5, "humidity": 46.0, "temperature": 29.0,
        "vibration": 0.7, "displacement": 0.4, "pore_pressure": 12.0,
        "crack_growth": 0.0,
    },
    "WARNING": {
        "rainfall": 68.0, "humidity": 87.0, "temperature": 25.0,
        "vibration": 6.5, "displacement": 5.0, "pore_pressure": 55.0,
        "crack_growth": 6.0,
    },
    "CRITICAL": {
        "rainfall": 114.0, "humidity": 97.0, "temperature": 22.5,
        "vibration": 23.0, "displacement": 14.0, "pore_pressure": 88.0,
        "crack_growth": 18.0,
    },
}

# Per-zone exposure multipliers. A ramp carrying loaded trucks sees more
# vibration; a sheltered wall collects less run-off. This is what stops every
# zone on the map from lighting up in lockstep.
_ZONE_EXPOSURE: dict[str, dict[str, float]] = {
    "A-01": {"rainfall": 0.85, "vibration": 0.55, "crack_growth": 0.5},
    "A-04": {"rainfall": 1.20, "vibration": 1.45, "crack_growth": 1.6},
    "B-02": {"rainfall": 1.00, "vibration": 0.80, "crack_growth": 0.9},
    "B-05": {"rainfall": 0.95, "vibration": 1.30, "crack_growth": 0.7},
    "C-03": {"rainfall": 1.15, "vibration": 1.25, "crack_growth": 1.5},
    "C-06": {"rainfall": 0.75, "vibration": 0.45, "crack_growth": 0.4},
}

_BOUNDS = {
    "rainfall": (0.0, 120.0),
    "humidity": (15.0, 100.0),
    "temperature": (-5.0, 48.0),
    "vibration": (0.0, 30.0),
    "displacement": (0.0, 40.0),
    "pore_pressure": (0.0, 100.0),
    "slope_angle": (20.0, 80.0),
    "crack_density": (0.0, 45.0),
    "crack_severity": (0.0, 100.0),
    "rock_condition": (5.0, 98.0),
}

# How fast a reading closes the gap to its target each tick (0..1), and how much
# random jitter rides on top.
_INERTIA = 0.34
_JITTER = {
    "rainfall": 2.4, "humidity": 1.8, "temperature": 0.5,
    "vibration": 0.55, "displacement": 0.25, "pore_pressure": 1.6,
}


def _clamp(name: str, value: float) -> float:
    lo, hi = _BOUNDS.get(name, (-1e9, 1e9))
    return max(lo, min(hi, value))


class SensorSimulator:
    """Thread-safe in-memory state of the simulated sensor network."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._scenario = "NORMAL"
        self._tick = 0
        self._last_update = datetime.now(timezone.utc)
        self._rng = random.Random(7)
        self._manual: dict[str, dict[str, float]] = {}
        self._state: dict[str, dict[str, float]] = {}
        self._reset_state()

    # -- state ------------------------------------------------------------- #
    def _reset_state(self) -> None:
        prof = _PROFILES["NORMAL"]
        self._state = {}
        for zone in ZONES:
            base = zone["baseline"]
            self._state[zone["zone_id"]] = {
                "rainfall": prof["rainfall"],
                "humidity": prof["humidity"],
                "temperature": prof["temperature"],
                "vibration": prof["vibration"],
                "displacement": prof["displacement"],
                "pore_pressure": prof["pore_pressure"],
                "slope_angle": base["slope_angle"],
                "crack_density": base["crack_density"],
                "crack_severity": base["crack_severity"],
                "rock_condition": base["rock_condition"],
            }

    @property
    def scenario(self) -> str:
        with self._lock:
            return self._scenario

    def set_scenario(self, scenario: str) -> str:
        scenario = scenario.upper()
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario '{scenario}'. Expected one of {SCENARIOS}.")
        with self._lock:
            self._scenario = scenario
            # Jump most of the way immediately so a demo button press is visible
            # on the very next frame, then let the walk settle the rest.
            for _ in range(5):
                self._advance()
        return scenario

    def reset(self) -> None:
        with self._lock:
            self._scenario = "NORMAL"
            self._manual.clear()
            self._tick = 0
            self._reset_state()

    # -- manual overrides -------------------------------------------------- #
    def set_override(self, zone_id: str, values: dict[str, float]) -> dict[str, float]:
        """Pin specific channels for a zone (used by the Sensor Monitoring sliders)."""
        if zone_id not in ZONE_BY_ID:
            raise ValueError(f"Unknown zone '{zone_id}'.")
        with self._lock:
            zone_overrides = self._manual.setdefault(zone_id, {})
            for key, val in values.items():
                if val is None:
                    zone_overrides.pop(key, None)
                elif key in _BOUNDS:
                    zone_overrides[key] = _clamp(key, float(val))
            if not zone_overrides:
                self._manual.pop(zone_id, None)
            self._apply_overrides()
            return dict(self._manual.get(zone_id, {}))

    def clear_overrides(self, zone_id: str | None = None) -> None:
        with self._lock:
            if zone_id is None:
                self._manual.clear()
            else:
                self._manual.pop(zone_id, None)

    def _apply_overrides(self) -> None:
        for zone_id, overrides in self._manual.items():
            self._state[zone_id].update(overrides)

    # -- ticking ----------------------------------------------------------- #
    def _advance(self) -> None:
        prof = _PROFILES[self._scenario]
        self._tick += 1

        for zone in ZONES:
            zid = zone["zone_id"]
            base = zone["baseline"]
            exposure = _ZONE_EXPOSURE.get(zid, {})
            cur = self._state[zid]

            for channel in ("rainfall", "humidity", "temperature", "vibration",
                            "displacement", "pore_pressure"):
                target = prof[channel] * exposure.get(channel, 1.0)
                noise = self._rng.gauss(0.0, _JITTER[channel])
                cur[channel] = _clamp(channel, cur[channel] + (target - cur[channel]) * _INERTIA + noise)

            # Fractures propagate under sustained load — they do not heal when the
            # weather improves, so growth is one-way and only resets on reset().
            growth = prof["crack_growth"] * exposure.get("crack_growth", 1.0)
            if growth > 0:
                step = growth * 0.05 * self._rng.uniform(0.6, 1.4)
                cur["crack_density"] = _clamp("crack_density", cur["crack_density"] + step)
                cur["crack_severity"] = _clamp("crack_severity", cur["crack_severity"] + step * 2.6)
                cur["rock_condition"] = _clamp("rock_condition", cur["rock_condition"] - step * 0.9)

            # Measurable slope movement on a saturated, heavily loaded wall.
            cur["slope_angle"] = _clamp(
                "slope_angle",
                base["slope_angle"] + cur["displacement"] * 0.12 + self._rng.gauss(0, 0.10),
            )

        self._apply_overrides()
        self._last_update = datetime.now(timezone.utc)

    def tick(self) -> dict[str, dict[str, float]]:
        with self._lock:
            self._advance()
            return self.snapshot()

    # -- reads ------------------------------------------------------------- #
    def snapshot(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {zid: {k: round(v, 2) for k, v in vals.items()}
                    for zid, vals in self._state.items()}

    def zone_state(self, zone_id: str) -> dict[str, float]:
        with self._lock:
            if zone_id not in self._state:
                raise ValueError(f"Unknown zone '{zone_id}'.")
            return {k: round(v, 2) for k, v in self._state[zone_id].items()}

    def apply_image_analysis(self, zone_id: str, crack_density: float,
                             crack_severity: float, rock_condition: float) -> None:
        """Feed a rock-face CV result back into the live state for that zone.

        This is what closes the loop between the Rock Analysis page and the
        dashboard: what the camera saw becomes what the risk engine scores.
        """
        with self._lock:
            if zone_id not in self._state:
                raise ValueError(f"Unknown zone '{zone_id}'.")
            self._state[zone_id].update(
                {
                    "crack_density": _clamp("crack_density", crack_density),
                    "crack_severity": _clamp("crack_severity", crack_severity),
                    "rock_condition": _clamp("rock_condition", rock_condition),
                }
            )

    def status(self) -> dict:
        with self._lock:
            return {
                "scenario": self._scenario,
                "tick": self._tick,
                "last_update": self._last_update.isoformat(),
                "overrides": {k: dict(v) for k, v in self._manual.items()},
                "available_scenarios": list(SCENARIOS),
                "data_source": "SIMULATED — no physical sensors are connected.",
            }


simulator = SensorSimulator()
