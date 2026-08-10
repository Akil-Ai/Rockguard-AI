"""Generate SYNTHETIC rock-face images for the Rock Analysis demo.

These are procedurally drawn, not photographs of a real mine. They exist so the
demo has a deterministic, offline-safe input to run the CV pipeline on.

    python -m scripts.generate_sample_faces

Writes PNGs into ../frontend/public/samples/.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

OUT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "samples"
W, H = 900, 640


def _fbm(rng: np.random.Generator, shape: tuple[int, int], octaves: int = 5) -> np.ndarray:
    """Fractal noise — cheap stand-in for rock texture."""
    out = np.zeros(shape, dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        scale = 2 ** o
        small = rng.normal(0, 1, (max(shape[0] // (16 // max(scale, 1) or 1), 2),
                                  max(shape[1] // (16 // max(scale, 1) or 1), 2))).astype(np.float32)
        layer = cv2.resize(small, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
        out += amp * layer
        total += amp
        amp *= 0.55
    return out / max(total, 1e-6)


def _rock_base(rng: np.random.Generator) -> np.ndarray:
    tex = _fbm(rng, (H, W), octaves=6)
    tex = cv2.normalize(tex, None, 0, 1, cv2.NORM_MINMAX)

    # Bedding planes: faint horizontal banding typical of a sedimentary bench.
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    bands = 0.06 * np.sin(yy * math.pi * rng.uniform(7, 12) + rng.uniform(0, 3))
    lum = np.clip(0.42 + 0.34 * tex + bands, 0, 1)

    # Directional lighting across the face.
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    lum *= np.clip(0.78 + 0.34 * (1 - xx), 0.4, 1.25)

    gray = (np.clip(lum, 0, 1) * 255).astype(np.uint8)
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).astype(np.float32)
    img *= np.array([0.86, 0.93, 1.02], dtype=np.float32)  # warm iron-stained tint
    return np.clip(img, 0, 255).astype(np.uint8)


def _draw_crack(img: np.ndarray, rng: np.random.Generator, length: int, thickness: int,
                depth: int = 3) -> None:
    """Random walk with branching, drawn dark with a soft halo."""
    x, y = rng.integers(60, W - 60), rng.integers(50, H - 50)
    ang = rng.uniform(0, math.pi)
    pts = [(int(x), int(y))]
    steps = max(6, length // 22)
    for _ in range(steps):
        ang += rng.normal(0, 0.20)
        x += math.cos(ang) * (length / steps)
        y += math.sin(ang) * (length / steps)
        x = float(np.clip(x, 4, W - 5))
        y = float(np.clip(y, 4, H - 5))
        pts.append((int(x), int(y)))

    poly = np.array(pts, dtype=np.int32)
    shade = int(rng.integers(28, 58))
    # Halo first (weathered edge), then the dark core.
    cv2.polylines(img, [poly], False, (shade + 55, shade + 58, shade + 62),
                  thickness + 3, cv2.LINE_AA)
    cv2.polylines(img, [poly], False, (shade, shade + 2, shade + 4), thickness, cv2.LINE_AA)

    if depth > 0 and thickness > 1 and rng.random() < 0.55:
        i = int(rng.integers(1, len(pts) - 1))
        sub = img[max(pts[i][1] - 1, 0):, :]  # noop slice; branch drawn below
        del sub
        _branch(img, rng, pts[i], ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1),
                int(length * 0.45), max(thickness - 1, 1), depth - 1)


def _branch(img: np.ndarray, rng: np.random.Generator, start, ang: float,
            length: int, thickness: int, depth: int) -> None:
    x, y = float(start[0]), float(start[1])
    pts = [(int(x), int(y))]
    steps = max(4, length // 20)
    for _ in range(steps):
        ang += rng.normal(0, 0.22)
        x = float(np.clip(x + math.cos(ang) * (length / steps), 4, W - 5))
        y = float(np.clip(y + math.sin(ang) * (length / steps), 4, H - 5))
        pts.append((int(x), int(y)))
    shade = int(rng.integers(35, 65))
    cv2.polylines(img, [np.array(pts, dtype=np.int32)], False,
                  (shade, shade + 2, shade + 4), thickness, cv2.LINE_AA)


def build(name: str, n_cracks: int, len_range: tuple[int, int], thick_range: tuple[int, int],
          seed: int) -> Path:
    rng = np.random.default_rng(seed)
    img = _rock_base(rng)

    for _ in range(n_cracks):
        _draw_crack(img, rng,
                    int(rng.integers(*len_range)),
                    int(rng.integers(*thick_range)))

    # Loose scree / boulders at the toe of the face.
    for _ in range(rng.integers(8, 18)):
        cx, cy = int(rng.integers(0, W)), int(rng.integers(H - 90, H))
        cv2.circle(img, (cx, cy), int(rng.integers(4, 15)),
                   (int(rng.integers(60, 105)),) * 3, -1, cv2.LINE_AA)

    img = cv2.GaussianBlur(img, (3, 3), 0)
    img = np.clip(img.astype(np.float32) + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)

    # Label the image itself so a screenshot can never be mistaken for a real photo.
    cv2.rectangle(img, (0, 0), (W, 26), (28, 24, 20), -1)
    cv2.putText(img, f"SYNTHETIC ROCK FACE - {name.upper()} - GENERATED, NOT A REAL MINE PHOTO",
                (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 200, 250), 1, cv2.LINE_AA)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"rockface_{name}.png"
    cv2.imwrite(str(path), img)
    return path


PRESETS = [
    ("stable", 3, (70, 140), (1, 2), 11),
    ("moderate", 11, (110, 240), (1, 4), 23),
    ("fractured", 26, (150, 380), (2, 6), 37),
]


if __name__ == "__main__":
    from app.services import crack_detector as cd

    for name, n, lr, tr, seed in PRESETS:
        p = build(name, n, lr, tr, seed)
        res = cd.analyze(p.read_bytes(), annotate=False)
        print(f"{p.name:26s} traces={res.crack_count:3d}  density={res.crack_density:5.2f}%  "
              f"severity={res.crack_severity:5.1f} [{res.severity_band}]  rock={res.rock_condition:.0f}")
