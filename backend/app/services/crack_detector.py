"""Rock-face crack detection.

=====================================================================
METHOD NOTE — please read before quoting any number from this module.

The default detector is a CLASSICAL COMPUTER-VISION HEURISTIC, not a
trained neural network. No public labelled rockfall/crack dataset for
open-pit benches was available, so rather than ship a model trained on
nothing and call it "AI detection", this uses a deterministic OpenCV
pipeline that finds dark, thin, elongated structures on a rock face:

    CLAHE -> bilateral denoise -> black-hat morphology
    -> adaptive threshold -> morphological bridging
    -> contour filtering by elongation & length

That is a genuine, explainable crack-segmentation technique. It will
also happily flag shadows, drill marks, wet streaks and cable lines,
because it has no semantic understanding of a rock face. Treat the
outputs as *indicative feature measurements*, not verified detections.

A YOLO path is wired in and used automatically if BOTH `ultralytics`
is installed AND a weights file exists at
`app/ml/artifacts/yolo_cracks.pt`. Neither is shipped — training that
model requires an annotated dataset that this project does not have.
=====================================================================
"""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ..config import ARTIFACT_DIR

YOLO_WEIGHTS = ARTIFACT_DIR / "yolo_cracks.pt"
MAX_DIM = 1000  # working resolution; keeps analysis fast and scale-consistent

# Minimum grey-level margin between a candidate and the rock around it.
# Calibrated on the synthetic faces in scripts/generate_sample_faces.py, where
# noise artefacts top out near 19 and genuine fractures start around 24. Biased
# toward precision on purpose: reporting CRITICAL fracturing on a photo of a
# blank wall would discredit the whole system, so a faint hairline crack is the
# acceptable thing to miss.
MIN_CRACK_CONTRAST = 20.0
_RING_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

# Colours (BGR) used for the annotated overlay.
_SEVERITY_COLOURS = {
    "LOW": (120, 220, 120),
    "MEDIUM": (60, 200, 250),
    "HIGH": (60, 130, 255),
    "CRITICAL": (70, 70, 255),
}


@dataclass
class CrackResult:
    crack_density: float          # % of rock-face area occupied by crack pixels
    crack_severity: float         # 0-100 composite severity
    crack_count: int
    max_crack_length: float       # % of image diagonal
    mean_crack_width: float       # pixels at working resolution
    total_crack_length: float     # % of image diagonal
    orientation_spread: float     # 0-100, how varied the crack directions are
    rock_condition: float         # 0-100 proxy for rock-mass quality (higher = better)
    severity_band: str
    detector: str
    annotated_b64: str = ""
    cracks: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Image loading
# --------------------------------------------------------------------------- #
def decode_image(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the uploaded file as an image.")
    h, w = img.shape[:2]
    scale = MAX_DIM / float(max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


# --------------------------------------------------------------------------- #
# Classical CV pipeline
# --------------------------------------------------------------------------- #
def _crack_mask(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Segment thin dark linear structures — the crack candidates.

    Returns (enhanced_gray, mask). The enhanced gray is handed back because the
    contrast check in `_measure_contours` must measure against the same image
    the mask was derived from.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Local contrast boost: open-pit faces are unevenly lit.
    gray = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    # Edge-preserving denoise so rock texture doesn't become false cracks.
    gray = cv2.bilateralFilter(gray, 7, 60, 60)

    # Black-hat isolates structures DARKER than their surroundings and thinner
    # than the kernel — exactly the signature of an open fracture.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)

    # Threshold at a high percentile of the black-hat response rather than with
    # a fixed cut or a contrast-stretch. This bounds how much of the frame can
    # ever be marked (~2-4%) no matter how the photo is exposed; a fixed cut on
    # a normalised response blows up to tens of percent on a low-contrast face
    # and drowns the real traces in texture noise.
    cut = max(
        float(np.percentile(blackhat, 93.0)),
        float(blackhat.mean() + 1.8 * blackhat.std()),
        10.0,
    )
    _, mask = cv2.threshold(blackhat, cut, 255, cv2.THRESH_BINARY)

    # Bridge dashed fracture traces, then drop isolated speckle.
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    return gray, mask


def _local_contrast(gray: np.ndarray, contour: np.ndarray) -> float:
    """How much darker a candidate is than the rock immediately around it.

    Compares the mean intensity inside the contour against a dilated ring around
    it. This is the check that separates a fracture from image noise: the
    percentile threshold in `_crack_mask` is purely *relative*, so it marks the
    darkest few percent of pixels in every image — including one with no cracks
    at all. Noise blobs sit only a few grey levels below their surroundings;
    a real open joint is dramatically darker.
    """
    h, w = gray.shape[:2]
    x, y, bw, bh = cv2.boundingRect(contour)
    pad = 8
    x0, y0 = max(x - pad, 0), max(y - pad, 0)
    x1, y1 = min(x + bw + pad, w), min(y + bh + pad, h)
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0

    inner = np.zeros(roi.shape, dtype=np.uint8)
    cv2.drawContours(inner, [contour - [x0, y0]], 0, 255, -1)
    ring = cv2.subtract(cv2.dilate(inner, _RING_KERNEL), inner)
    if not inner.any() or not ring.any():
        return 0.0

    return float(roi[ring > 0].mean() - roi[inner > 0].mean())


def _measure_contours(mask: np.ndarray, gray: np.ndarray, img_shape: tuple[int, int]) -> list[dict]:
    """Keep only elongated contours and measure each one.

    Geometry comes from a *ribbon* approximation rather than minAreaRect:
    for a long thin shape the perimeter is roughly twice its centre-line, so

        length ~ perimeter / 2        width ~ area / length

    A real fracture wanders, and its minimum-area rectangle is therefore far
    fatter and longer than the crack itself — that measure reports near-identical
    numbers for a single hairline and a dense fracture network. The ribbon
    approximation follows the curve, so the two stay distinguishable.
    """
    h, w = img_shape[:2]
    diag = math.hypot(h, w)
    min_area = max(40.0, 0.00006 * h * w)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cracks: list[dict] = []

    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < min_area:
            continue

        length = float(cv2.arcLength(cnt, True)) / 2.0
        if length < 25.0:
            continue
        width = area / length
        if width <= 0.0:
            continue

        # A crack is long and thin. Blobs (shadows, ore patches) are rejected.
        elongation = length / width
        if elongation < 4.0:
            continue

        # Final gate: it must actually be darker than the surrounding rock.
        contrast = _local_contrast(gray, cnt)
        if contrast < MIN_CRACK_CONTRAST:
            continue

        rect = cv2.minAreaRect(cnt)
        (cx, cy), (rw, rh), angle = rect
        # minAreaRect reports the angle of the first edge; normalise so the value
        # always describes the crack's long axis, in [0, 180).
        long_axis_angle = (angle if rw >= rh else angle + 90.0) % 180.0

        cracks.append(
            {
                "area": area,
                "length_px": length,
                "width_px": width,
                "length_pct": round(length / diag * 100.0, 2),
                "elongation": round(elongation, 2),
                "contrast": round(contrast, 1),
                "angle": round(float(long_axis_angle), 1),
                "centroid": [round(float(cx), 1), round(float(cy), 1)],
                "contour": cnt,
                "box": cv2.boxPoints(rect).astype(int).tolist(),
            }
        )

    cracks.sort(key=lambda c: c["length_px"], reverse=True)
    return cracks


def _severity_band(severity: float) -> str:
    if severity >= 75:
        return "CRITICAL"
    if severity >= 50:
        return "HIGH"
    if severity >= 25:
        return "MEDIUM"
    return "LOW"


def _score(cracks: list[dict], mask: np.ndarray, shape: tuple[int, int]) -> dict:
    """Aggregate per-crack measurements into face-level indicators."""
    h, w = shape[:2]
    diag = math.hypot(h, w)
    area_px = float(h * w)

    if not cracks:
        return {
            "crack_density": 0.0,
            "crack_severity": 0.0,
            "crack_count": 0,
            "max_crack_length": 0.0,
            "mean_crack_width": 0.0,
            "total_crack_length": 0.0,
            "orientation_spread": 0.0,
        }

    crack_area = sum(c["area"] for c in cracks)
    density = crack_area / area_px * 100.0
    total_len = sum(c["length_px"] for c in cracks) / diag * 100.0
    max_len = max(c["length_px"] for c in cracks) / diag * 100.0
    mean_width = float(np.mean([c["width_px"] for c in cracks]))

    # Circular spread of crack orientations. Multiple intersecting joint sets
    # form detachable wedges, so directional variety is itself a hazard signal.
    angles = np.radians(np.array([c["angle"] for c in cracks]) * 2.0)  # axial data
    resultant = math.hypot(float(np.mean(np.cos(angles))), float(np.mean(np.sin(angles))))
    spread = (1.0 - resultant) * 100.0

    # Composite severity. Each term is normalised to 0..1 against a value that
    # represents a badly fractured face, then weighted and capped.
    #
    # CALIBRATION CAVEAT: the denominators below were tuned against the
    # synthetic faces in scripts/generate_sample_faces.py, because no labelled
    # rock-face imagery was available. They set the *scale* of the severity
    # number, so on real photographs the ordering should still hold but the
    # absolute value would need re-fitting against expert-rated images.
    #
    # Weighting favours trace count, cumulative length and areal density: those
    # separate a lightly-jointed face from a shattered one. The single longest
    # trace is deliberately down-weighted — almost any face contains one long
    # bedding plane or lithological contact, so that term saturates immediately
    # and carries little information.
    n_count = min(len(cracks) / 26.0, 1.0)
    n_total = min(total_len / 240.0, 1.0)
    n_dens = min(density / 7.0, 1.0)
    n_len = min(max_len / 70.0, 1.0)
    n_width = min(mean_width / 12.0, 1.0)
    n_spread = min(spread / 70.0, 1.0)

    severity = 100.0 * (
        0.26 * n_count + 0.26 * n_total + 0.18 * n_dens
        + 0.14 * n_len + 0.10 * n_width + 0.06 * n_spread
    )

    return {
        "crack_density": round(min(density, 45.0), 2),
        "crack_severity": round(min(severity, 100.0), 1),
        "crack_count": len(cracks),
        "max_crack_length": round(max_len, 2),
        "mean_crack_width": round(mean_width, 2),
        "total_crack_length": round(total_len, 2),
        "orientation_spread": round(spread, 1),
    }


def _annotate(img: np.ndarray, cracks: list[dict], metrics: dict, detector: str) -> str:
    """Draw the detections and a metrics panel; return a base64 PNG."""
    out = img.copy()
    h, w = out.shape[:2]
    band = _severity_band(metrics["crack_severity"])
    colour = _SEVERITY_COLOURS[band]

    overlay = out.copy()
    for i, c in enumerate(cracks[:60]):
        # Trace the actual crack outline where we have it — a bounding box around
        # a wandering fracture covers mostly intact rock and misleads the viewer.
        shape = c.get("contour")
        if shape is not None:
            cv2.drawContours(overlay, [shape], 0, colour, 2)
        else:
            cv2.drawContours(overlay, [np.array(c["box"], dtype=np.int32)], 0, colour, 2)
        if i < 12:  # label only the most significant traces to avoid clutter
            x, y = c["centroid"]
            cv2.putText(overlay, f"C{i + 1} {c['length_pct']:.0f}%", (int(x) + 6, max(int(y) - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, colour, 1, cv2.LINE_AA)
    out = cv2.addWeighted(overlay, 0.85, out, 0.15, 0)

    # Metrics panel (top-left), solid so it stays legible over any image.
    panel_h, panel_w = 104, min(340, w)
    cv2.rectangle(out, (0, 0), (panel_w, panel_h), (18, 16, 14), -1)
    cv2.rectangle(out, (0, 0), (panel_w, panel_h), (70, 70, 70), 1)

    lines = [
        (f"CRACK SEVERITY: {metrics['crack_severity']:.0f}/100  [{band}]", colour),
        (f"Density: {metrics['crack_density']:.2f}%   Traces: {metrics['crack_count']}", (235, 235, 235)),
        (f"Max length: {metrics['max_crack_length']:.1f}% of frame", (235, 235, 235)),
        (f"Detector: {detector}", (170, 170, 170)),
    ]
    for i, (text, col) in enumerate(lines):
        cv2.putText(out, text, (10, 24 + i * 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5 if i else 0.55, col, 1, cv2.LINE_AA)

    # Honesty watermark, bottom-left.
    cv2.putText(out, "HEURISTIC CV - DEMO ONLY, NOT A VERIFIED DETECTION",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 215, 255), 1, cv2.LINE_AA)

    # JPEG, not PNG: the annotated frame is a photo-like image, and a PNG data
    # URI runs to well over a megabyte of base64 on every upload response.
    ok, buf = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


# --------------------------------------------------------------------------- #
# Optional YOLO path
# --------------------------------------------------------------------------- #
def _yolo_available() -> bool:
    if not YOLO_WEIGHTS.exists():
        return False
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


def _analyze_yolo(img: np.ndarray) -> list[dict] | None:
    """Run YOLO if weights are present. Returns crack dicts, or None on failure."""
    try:
        from ultralytics import YOLO

        model = YOLO(str(YOLO_WEIGHTS))
        res = model.predict(img, verbose=False)[0]
        h, w = img.shape[:2]
        diag = math.hypot(h, w)
        cracks: list[dict] = []
        for box in res.boxes:
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            bw, bh = x2 - x1, y2 - y1
            length, width = max(bw, bh), max(min(bw, bh), 1.0)
            cracks.append(
                {
                    "area": float(bw * bh) * 0.35,  # box area over-states a thin crack
                    "length_px": length,
                    "width_px": width,
                    "length_pct": round(length / diag * 100.0, 2),
                    "elongation": round(length / width, 2),
                    "angle": 0.0 if bw >= bh else 90.0,
                    "centroid": [round((x1 + x2) / 2, 1), round((y1 + y2) / 2, 1)],
                    "box": [[int(x1), int(y1)], [int(x2), int(y1)], [int(x2), int(y2)], [int(x1), int(y2)]],
                    "confidence": round(float(box.conf[0]), 3),
                }
            )
        cracks.sort(key=lambda c: c["length_px"], reverse=True)
        return cracks
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze(raw: bytes, annotate: bool = True) -> CrackResult:
    img = decode_image(raw)
    notes: list[str] = []
    detector = "opencv-blackhat-heuristic"
    cracks: list[dict] | None = None

    if _yolo_available():
        cracks = _analyze_yolo(img)
        if cracks is not None:
            detector = "yolo"
            notes.append("YOLO weights found and used for detection.")
        else:
            notes.append("YOLO weights present but inference failed; fell back to OpenCV.")

    if cracks is None:
        gray, mask = _crack_mask(img)
        cracks = _measure_contours(mask, gray, img.shape)
        notes.append(
            "Classical OpenCV pipeline (black-hat morphology + elongation and contrast filtering). "
            "No trained crack model is bundled — shadows, drill marks and wet streaks "
            "can be misread as fractures."
        )
    else:
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        for c in cracks:
            cv2.drawContours(mask, [np.array(c["box"], dtype=np.int32)], 0, 255, -1)

    metrics = _score(cracks, mask, img.shape)
    severity = metrics["crack_severity"]
    density = metrics["crack_density"]

    # Rough rock-mass quality proxy derived from what the image shows. This is a
    # visual surrogate, not a geotechnical RMR/Q rating from a core log.
    rock_condition = float(np.clip(95.0 - 0.62 * severity - 1.1 * density, 5.0, 98.0))
    notes.append("Rock quality is inferred from surface fracturing only — not an RMR/Q rating.")

    return CrackResult(
        crack_density=density,
        crack_severity=severity,
        crack_count=metrics["crack_count"],
        max_crack_length=metrics["max_crack_length"],
        mean_crack_width=metrics["mean_crack_width"],
        total_crack_length=metrics["total_crack_length"],
        orientation_spread=metrics["orientation_spread"],
        rock_condition=round(rock_condition, 1),
        severity_band=_severity_band(severity),
        detector=detector,
        annotated_b64=_annotate(img, cracks, metrics, detector) if annotate else "",
        # `area`/`contour` are internal measurement scratch (and `contour` is a
        # numpy array, which will not serialise to JSON).
        cracks=[
            {k: v for k, v in c.items() if k not in ("area", "contour")}
            for c in cracks[:40]
        ],
        notes=notes,
    )
