"""Calibrage métrique (pixels → cm) : gommette verte, ArUco ou référence manuelle.

Trois stratégies, par ordre de robustesse :
1. `aruco`    : marqueur ArUco 4x4 (50 mm) — robuste aux perspectives.
2. `green_dot`: gommette verte 2 cm — segmentation HSV + affinage circulaire Hough.
3. `manual`   : segment tracé par l'utilisateur / échelle saisie (fallback).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

try:
    import cv2

    CV2 = True
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore[assignment]
    CV2 = False


@dataclass
class CalibrationResult:
    pixels_per_cm: float
    method: str
    confidence: float
    reference_cm: float
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_reliable(self) -> bool:
        return self.pixels_per_cm > 0 and self.confidence >= 0.35


# ---------------------------------------------------------------------------
# 1. Marqueur ArUco
# ---------------------------------------------------------------------------
def detect_aruco(image_bgr: np.ndarray, marker_size_cm: float = 5.0) -> Optional[CalibrationResult]:
    if not CV2:
        return None
    try:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, params)
        corners, ids, _ = detector.detectMarkers(image_bgr)
        if ids is None or len(corners) == 0:
            return None
        # Côté moyen du marqueur en pixels (moyenne des 4 côtés, tous marqueurs)
        sides: list[float] = []
        for quad in corners:
            pts = quad.reshape(4, 2)
            for i in range(4):
                sides.append(float(np.linalg.norm(pts[i] - pts[(i + 1) % 4])))
        side_px = float(np.mean(sides))
        if side_px <= 4:
            return None
        return CalibrationResult(
            pixels_per_cm=side_px / marker_size_cm,
            method="aruco",
            confidence=0.97,
            reference_cm=marker_size_cm,
            details={
                "markers_detected": int(len(ids)),
                "marker_side_px": round(side_px, 2),
                "marker_ids": [int(i) for i in ids.flatten()],
            },
        )
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 2. Gommette verte (HSV 35-85) + Hough
# ---------------------------------------------------------------------------
def detect_green_dot(
    image_bgr: np.ndarray, dot_diameter_cm: float = 2.0, min_area_ratio: float = 0.0004
) -> Optional[CalibrationResult]:
    if not CV2:
        return None
    h, w = image_bgr.shape[:2]
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 70, 60])
    upper = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    best = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(best))
    if area < min_area_ratio * h * w:
        return None

    (cx, cy), radius = cv2.minEnclosingCircle(best)
    circularity = area / (np.pi * radius**2 + 1e-6)
    if circularity < 0.55:  # forme trop irrégulière : probablement pas la gommette
        return None

    # Affinage : Hough Circles dans la ROI du blob détecté
    diameter_px = radius * 2
    try:
        r_pad = int(radius * 1.6) + 6
        x0, y0 = max(0, int(cx) - r_pad), max(0, int(cy) - r_pad)
        roi = image_bgr[y0 : int(cy) + r_pad, x0 : int(cx) + r_pad]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=roi.shape[0] / 2,
            param1=110,
            param2=26,
            minRadius=max(4, int(radius * 0.6)),
            maxRadius=max(6, int(radius * 1.5)),
        )
        conf = 0.82
        if circles is not None:
            diameter_px = float(circles[0][0][2]) * 2
            conf = 0.94
    except Exception:  # noqa: BLE001
        conf = 0.72

    return CalibrationResult(
        pixels_per_cm=diameter_px / dot_diameter_cm,
        method="green_dot",
        confidence=conf,
        reference_cm=dot_diameter_cm,
        details={
            "center": [round(float(cx), 1), round(float(cy), 1)],
            "diameter_px": round(diameter_px, 2),
            "circularity": round(float(circularity), 3),
        },
    )


# ---------------------------------------------------------------------------
# 3. Référence manuelle (segment tracé par l'utilisateur)
# ---------------------------------------------------------------------------
def manual_calibration(
    segment_px: float, reference_cm: float = 2.0, image_diagonal_px: Optional[float] = None
) -> CalibrationResult:
    segment_px = max(1.0, float(segment_px))
    reference_cm = max(0.2, float(reference_cm))
    conf = 0.66
    if image_diagonal_px:
        ratio = segment_px / image_diagonal_px
        # Un segment aberrant (trop court/long) voit sa confiance dégradée
        conf = 0.66 if 0.02 <= ratio <= 0.9 else 0.3
    return CalibrationResult(
        pixels_per_cm=segment_px / reference_cm,
        method="manual",
        confidence=conf,
        reference_cm=reference_cm,
        details={"segment_px": round(segment_px, 2)},
    )


def default_calibration(image_bgr: np.ndarray) -> CalibrationResult:
    """Aucun repère détecté : hypothèse d'un cadrage plein pied (~24 cm de large)."""
    h, w = image_bgr.shape[:2]
    ppc = max(w, h) / 24.0
    return CalibrationResult(
        pixels_per_cm=ppc,
        method="assumed",
        confidence=0.2,
        reference_cm=24.0,
        details={"assumption": "largeur de cadre ≈ 24 cm", "image": [int(w), int(h)]},
    )


def calibrate(
    image_bgr: np.ndarray,
    *,
    scale_ref_cm: float = 2.0,
    manual_segment_px: Optional[float] = None,
    aruco_size_cm: float = 5.0,
) -> CalibrationResult:
    """Chaîne de calibrage : manuel explicite > ArUco > gommette > hypothèse."""
    if manual_segment_px:
        h, w = image_bgr.shape[:2]
        return manual_calibration(manual_segment_px, scale_ref_cm, float(np.hypot(w, h)))
    return (
        detect_aruco(image_bgr, aruco_size_cm)
        or detect_green_dot(image_bgr, scale_ref_cm)
        or default_calibration(image_bgr)
    )
