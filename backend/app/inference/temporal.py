"""Suivi temporel : recalage ORB/SIFT (homographie) et trajectoire de cicatrisation.

Étape 7 du cahier des charges :
* alignement géométrique de l'image de référence J0 avec Jn ;
* calcul du Δsurface / semaine, détection de stagnation (< 50 % à 4 semaines) ;
* approximation du score PUSH et de l'indice de Gilman.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence

import numpy as np

try:
    import cv2

    CV2 = True
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore[assignment]
    CV2 = False


@dataclass
class RegistrationResult:
    ok: bool
    method: str
    inliers: int
    inlier_ratio: float
    homography: Optional[list[list[float]]] = None
    aligned: Optional[np.ndarray] = field(default=None, repr=False)
    overlap: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "method": self.method,
            "inliers": self.inliers,
            "inlier_ratio": round(self.inlier_ratio, 3),
            "overlap": round(self.overlap, 3),
            "notes": self.notes,
        }


def register_pair(
    reference_bgr: np.ndarray, current_bgr: np.ndarray, max_features: int = 4000
) -> RegistrationResult:
    """Recale `current` sur `reference` via ORB puis homographie RANSAC."""
    if not CV2:
        return RegistrationResult(
            ok=False, method="none", inliers=0, inlier_ratio=0.0,
            notes=["OpenCV indisponible : recalage ignoré"],
        )

    g0 = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2GRAY)
    g1 = cv2.cvtColor(current_bgr, cv2.COLOR_BGR2GRAY)

    detector_name = "ORB"
    try:
        detector = cv2.ORB_create(nfeatures=max_features, fastThreshold=12)
        norm = cv2.NORM_HAMMING
    except Exception:  # noqa: BLE001
        detector = cv2.SIFT_create(nfeatures=max_features)
        norm = cv2.NORM_L2
        detector_name = "SIFT"

    k0, d0 = detector.detectAndCompute(g0, None)
    k1, d1 = detector.detectAndCompute(g1, None)
    if d0 is None or d1 is None or len(k0) < 12 or len(k1) < 12:
        return RegistrationResult(
            ok=False, method=detector_name, inliers=0, inlier_ratio=0.0,
            notes=["Trop peu de points d'intérêt — cadrage trop différent"],
        )

    matcher = cv2.BFMatcher(norm, crossCheck=False)
    knn = matcher.knnMatch(d1, d0, k=2)
    good = [m for pair in knn if len(pair) == 2 for m, n in [pair] if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return RegistrationResult(
            ok=False, method=detector_name, inliers=len(good),
            inlier_ratio=len(good) / max(1, len(knn)),
            notes=["Appariement insuffisant — reprenez la photo sous le même angle"],
        )

    src = np.float32([k1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([k0[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        return RegistrationResult(
            ok=False, method=detector_name, inliers=0,
            inlier_ratio=0.0, notes=["Homographie non estimable"],
        )
    inliers = int(mask.sum()) if mask is not None else 0
    ratio = inliers / max(1, len(good))
    h, w = reference_bgr.shape[:2]
    aligned = cv2.warpPerspective(current_bgr, H, (w, h), flags=cv2.INTER_LINEAR)
    # Chevauchement utile = pixels valides après transformation
    valid = cv2.warpPerspective(np.ones_like(g1), H, (w, h))
    overlap = float(valid.mean())

    notes: list[str] = []
    if ratio < 0.35:
        notes.append("Recalage fragile : la comparaison de surface reste indicative.")
    if overlap < 0.6:
        notes.append("Cadrage partiellement hors champ — recadrez la plaie au centre.")

    return RegistrationResult(
        ok=inliers >= 12 and overlap > 0.5,
        method=detector_name,
        inliers=inliers,
        inlier_ratio=ratio,
        homography=H.tolist() if H is not None else None,
        aligned=aligned,
        overlap=overlap,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Trajectoire de cicatrisation
# ---------------------------------------------------------------------------
@dataclass
class TrajectoryPoint:
    date: datetime
    area_cm2: float
    infection_risk: float
    ischemia_risk: float
    composition: dict[str, float] = field(default_factory=dict)


def weekly_slope(points: Sequence[TrajectoryPoint]) -> float:
    """Δ surface (cm²) par semaine, régression linéaire simple."""
    if len(points) < 2:
        return 0.0
    t0 = points[0].date
    xs = np.array([(p.date - t0).total_seconds() / 604800.0 for p in points], float)
    ys = np.array([p.area_cm2 for p in points], float)
    if np.allclose(xs, xs[0]):
        return 0.0
    return float(np.polyfit(xs, ys, 1)[0])


def healing_trajectory(points: Sequence[TrajectoryPoint]) -> dict[str, Any]:
    """Synthèse clinique : réduction relative, stagnation, pronostic."""
    if not points:
        return {"status": "no_data", "message": "Aucune mesure disponible."}

    pts = sorted(points, key=lambda p: p.date)
    first, last = pts[0], pts[-1]
    weeks = max(1e-6, (last.date - first.date).total_seconds() / 604800.0)
    reduction_pct = (
        0.0 if first.area_cm2 <= 0 else (first.area_cm2 - last.area_cm2) / first.area_cm2 * 100
    )
    slope = weekly_slope(pts)
    rate_per_week = -slope  # > 0 signifie que la plaie se referme

    if reduction_pct >= 40:
        status, label = "healing", "Cicatrisation active"
    elif reduction_pct >= 10:
        status, label = "slow", "Évolution lente mais favorable"
    elif reduction_pct > -10:
        status, label = "stagnant", "Stagnation"
    else:
        status, label = "worsening", "Aggravation"

    alerts: list[str] = []
    if weeks >= 4 and reduction_pct < 50:
        alerts.append(
            "Réduction < 50 % après 4 semaines : risque de chronicité, réévaluation "
            "de la décharge et de la vascularisation recommandée (IWGDF)."
        )
    if rate_per_week < 0.05 and len(pts) >= 3:
        alerts.append("Vitesse de fermeture quasi nulle sur les dernières mesures.")
    if last.infection_risk >= 0.65:
        alerts.append("Risque infectieux élevé sur la dernière analyse : avis médical rapide.")

    # Score PUSH approximé (0-17) : surface, exsudat (proxy fibrine), tissu, infection
    tissue_rank = 4 - int(round(last.composition.get("granulation", 0.5) * 4))
    push = int(
        min(10, round(np.sqrt(max(last.area_cm2, 0)) * 2))
        + min(3, round(last.composition.get("fibrin", 0) * 3))
        + min(3, tissue_rank)
        + int(last.infection_risk >= 0.5)
    )

    return {
        "status": status,
        "label": label,
        "reduction_pct": round(reduction_pct, 2),
        "weeks_followed": round(weeks, 2),
        "rate_cm2_per_week": round(rate_per_week, 4),
        "push_score": int(min(17, push)),
        "gilman_index": round(reduction_pct / (last.area_cm2 + 1e-6), 3),
        "alerts": alerts,
        "series": [
            {
                "date": p.date.isoformat(),
                "area_cm2": round(p.area_cm2, 3),
                "infection_risk": round(p.infection_risk, 3),
                "ischemia_risk": round(p.ischemia_risk, 3),
            }
            for p in pts
        ],
    }
