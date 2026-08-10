"""Static description of the (FICTIONAL) demo mine.

"Bharat Open-Cast Mine, Sector 7" does not exist. Coordinates place it in a
coal-bearing region of Jharkhand so the basemap looks plausible, but no real
mine, lease or company is represented and the geometry is invented.

Each zone models one bench sector with its own geotechnical character, so the
map shows a realistic spread of risk rather than one uniform number.
"""
from __future__ import annotations

import math

MINE_NAME = "Bharat Open-Cast Mine — Sector 7 (FICTIONAL DEMO SITE)"
PIT_CENTER = (23.7520, 86.4210)  # lat, lon
PIT_RADIUS_M = 900.0


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    """Metre offsets to lat/lon, good enough at this scale."""
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def _sector_polygon(start_deg: float, end_deg: float, r_inner: float, r_outer: float,
                    steps: int = 10) -> list[list[float]]:
    """An annular sector of the pit — one bench of one wall."""
    lat0, lon0 = PIT_CENTER
    pts: list[list[float]] = []
    for i in range(steps + 1):  # outer arc, sweeping forward
        a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        lat, lon = _offset(lat0, lon0, math.cos(a) * r_outer, math.sin(a) * r_outer)
        pts.append([round(lat, 6), round(lon, 6)])
    for i in range(steps + 1):  # inner arc, sweeping back to close the ring
        a = math.radians(end_deg + (start_deg - end_deg) * i / steps)
        lat, lon = _offset(lat0, lon0, math.cos(a) * r_inner, math.sin(a) * r_inner)
        pts.append([round(lat, 6), round(lon, 6)])
    return pts


# zone_id, name, wall, bench, arc(start,end), radii(inner,outer), geotech baseline
_ZONE_SPEC = [
    ("A-01", "North Wall — Bench 1", "North", 1, (-35, 30), (620, 900),
     {"slope_angle": 38.0, "rock_condition": 78.0, "crack_density": 4.0, "crack_severity": 14.0},
     {"personnel": 12, "equipment": "2 haul trucks, 1 excavator"}),

    ("A-04", "North-East Wall — Bench 3", "North-East", 3, (30, 88), (430, 720),
     {"slope_angle": 52.0, "rock_condition": 52.0, "crack_density": 11.0, "crack_severity": 36.0},
     {"personnel": 23, "equipment": "3 haul trucks, 1 shovel, 1 drill rig"}),

    ("B-02", "East Wall — Bench 2", "East", 2, (88, 150), (520, 830),
     {"slope_angle": 47.0, "rock_condition": 62.0, "crack_density": 9.0, "crack_severity": 28.0},
     {"personnel": 9, "equipment": "1 haul truck, 1 dozer"}),

    ("B-05", "South Wall — Haul Ramp", "South", 2, (150, 215), (500, 880),
     {"slope_angle": 43.0, "rock_condition": 69.0, "crack_density": 6.5, "crack_severity": 20.0},
     {"personnel": 17, "equipment": "5 haul trucks (active ramp)"}),

    ("C-03", "South-West Wall — Bench 4", "South-West", 4, (215, 278), (380, 680),
     {"slope_angle": 55.0, "rock_condition": 47.0, "crack_density": 14.0, "crack_severity": 44.0},
     {"personnel": 6, "equipment": "1 drill rig (blast prep)"}),

    ("C-06", "West Wall — Bench 1", "West", 1, (278, 325), (600, 900),
     {"slope_angle": 35.0, "rock_condition": 82.0, "crack_density": 3.0, "crack_severity": 9.0},
     {"personnel": 4, "equipment": "1 water bowser"}),
]

ZONES: list[dict] = []
for zid, name, wall, bench, (a0, a1), (ri, ro), geo, ops in _ZONE_SPEC:
    lat_c, lon_c = _offset(
        *PIT_CENTER,
        north_m=math.cos(math.radians((a0 + a1) / 2)) * (ri + ro) / 2,
        east_m=math.sin(math.radians((a0 + a1) / 2)) * (ri + ro) / 2,
    )
    ZONES.append(
        {
            "zone_id": zid,
            "name": name,
            "wall": wall,
            "bench": bench,
            "polygon": _sector_polygon(a0, a1, ri, ro),
            "center": [round(lat_c, 6), round(lon_c, 6)],
            "baseline": geo,
            "personnel": ops["personnel"],
            "equipment": ops["equipment"],
        }
    )

ZONE_BY_ID: dict[str, dict] = {z["zone_id"]: z for z in ZONES}
ZONE_IDS: list[str] = [z["zone_id"] for z in ZONES]

PIT_OUTLINE = _sector_polygon(0, 359.9, 0.0, PIT_RADIUS_M, steps=48)[:49]


def mine_summary() -> dict:
    return {
        "name": MINE_NAME,
        "center": list(PIT_CENTER),
        "radius_m": PIT_RADIUS_M,
        "outline": PIT_OUTLINE,
        "zone_count": len(ZONES),
        "total_personnel": sum(z["personnel"] for z in ZONES),
        "disclaimer": "Fictional site. Geometry, zones and personnel counts are invented for the demo.",
    }
