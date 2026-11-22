"""Moteur d'analyse d'image déterministe (segmentation 5 classes + métriques).

Ce module implémente une **vraie** analyse colorimétrique et morphologique de
l'image — il ne renvoie jamais de valeurs aléatoires. Il sert de :

* moteur principal lorsque les poids `.pth` ne sont pas disponibles
  (développement, CI, démonstration clinique) ;
* garde-fou qualité en amont du réseau profond (`quality_gate`).

La sortie est strictement compatible avec celle de `WoundSegmentationModel`
(masque 5 classes + probabilités), ce qui permet de brancher les poids réels
sans changer une ligne du pipeline.
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

from app.inference.models import TISSUE_CLASSES, NUM_CLASSES

BACKGROUND, NECROSIS, FIBRIN, GRANULATION, EPITHELIAL = range(NUM_CLASSES)


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------
@dataclass
class QualityReport:
    is_acceptable: bool
    sharpness: float          # variance laplacienne
    brightness: float         # 0..255 (L moyen)
    exposure_clipped: float   # fraction de pixels saturés (0..1)
    contrast: float           # écart-type de L
    issues: list[str] = field(default_factory=list)
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_acceptable": self.is_acceptable,
            "sharpness": round(self.sharpness, 2),
            "brightness": round(self.brightness, 2),
            "exposure_clipped": round(self.exposure_clipped, 4),
            "contrast": round(self.contrast, 2),
            "issues": self.issues,
            "score": round(self.score, 3),
        }


@dataclass
class SegmentationOutput:
    mask: np.ndarray            # HxW uint8, valeurs 0..4
    wound_mask: np.ndarray      # HxW bool
    probs: np.ndarray           # HxWx5 float32 (pseudo-probabilités)
    composition: dict[str, float]
    area_px: float
    perimeter_px: float
    bbox: tuple[int, int, int, int]
    perilesional_inflammation: float
    redness_index: float
    texture_entropy: float


# ---------------------------------------------------------------------------
# Quality gate (Étape 4.2 du cahier des charges)
# ---------------------------------------------------------------------------
DARK_THRESHOLD = 40.0     # lux approximés via luminance
BRIGHT_THRESHOLD = 220.0
SHARPNESS_THRESHOLD = 100.0


def quality_gate(image_bgr: np.ndarray) -> QualityReport:
    image_bgr = np.ascontiguousarray(image_bgr)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if CV2 else _gray(image_bgr)
    # Redimensionnement pour rendre la métrique invariante à la résolution
    scale = 1024 / max(gray.shape[:2])
    g = cv2.resize(gray, None, fx=scale, fy=scale) if CV2 and scale < 1 else gray

    if CV2:
        sharpness = float(cv2.Laplacian(g, cv2.CV_64F).var())
    else:
        lap = np.abs(np.gradient(np.gradient(g.astype(np.float32), axis=0), axis=0))
        sharpness = float(lap.var())

    brightness = float(g.mean())
    clipped = float(((g > 250).sum() + (g < 5).sum()) / g.size)
    contrast = float(g.std())

    issues: list[str] = []
    if brightness < DARK_THRESHOLD:
        issues.append("Image trop sombre (éclairage insuffisant) — rapprochez-vous d'une source lumineuse.")
    if brightness > BRIGHT_THRESHOLD:
        issues.append("Image surexposée (reflet ou flash trop proche) — éloignez la source ou désactivez le flash.")
    if clipped > 0.12:
        issues.append("Zones brûlées importantes détectées — réduisez la lumière directe.")
    if sharpness < SHARPNESS_THRESHOLD:
        issues.append("Image floue (netteté insuffisante) — stabilisez le téléphone et refaites la mise au point.")
    if contrast < 18:
        issues.append("Contraste trop faible — la plaie se distingue mal du pourtour cutané.")

    score = 1.0
    score -= 0.22 * (brightness < DARK_THRESHOLD or brightness > BRIGHT_THRESHOLD)
    score -= 0.18 * min(1.0, clipped / 0.12)
    score -= 0.33 * max(0.0, (SHARPNESS_THRESHOLD - sharpness) / SHARPNESS_THRESHOLD)
    score -= 0.15 * max(0.0, (18 - contrast) / 18)
    score = float(np.clip(score, 0.0, 1.0))

    return QualityReport(
        is_acceptable=not issues or score >= 0.55,
        sharpness=sharpness,
        brightness=brightness,
        exposure_clipped=clipped,
        contrast=contrast,
        issues=issues,
        score=score,
    )


def _gray(bgr: np.ndarray) -> np.ndarray:
    b, g, r = bgr[..., 0], bgr[..., 1], bgr[..., 2]
    return np.clip(0.114 * b + 0.587 * g + 0.299 * r, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Segmentation tissulaire (5 classes) — analyse HSV/Lab + morphologie
# ---------------------------------------------------------------------------
def segment_tissues(image_bgr: np.ndarray) -> SegmentationOutput:
    image_bgr = np.ascontiguousarray(image_bgr)
    if CV2:
        return _segment_cv2(image_bgr)
    return _segment_numpy(image_bgr)


def _segment_cv2(image_bgr: np.ndarray) -> SegmentationOutput:
    """Segmentation Lab + référence cutanée locale (robuste aux carnations)."""
    h, w = image_bgr.shape[:2]
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * (100.0 / 255.0)
    A = lab[..., 1] - 128.0
    B = lab[..., 2] - 128.0

    # --- Référence cutanée : bande périphérique de l'image ------------------
    band = max(8, int(min(h, w) * 0.08))
    border = np.concatenate([
        L[:band].ravel(), L[-band:].ravel(), L[:, :band].ravel(), L[:, -band:].ravel()
    ])
    border_a = np.concatenate([
        A[:band].ravel(), A[-band:].ravel(), A[:, :band].ravel(), A[:, -band:].ravel()
    ])
    border_b = np.concatenate([
        B[:band].ravel(), B[-band:].ravel(), B[:, :band].ravel(), B[:, -band:].ravel()
    ])
    ref_L, ref_a, ref_b = (
        float(np.median(border)), float(np.median(border_a)), float(np.median(border_b))
    )
    ref_chroma = float(np.hypot(ref_a, ref_b))

    # Distance perceptuelle pondérée (les axes chromatiques pèsent davantage)
    dist = np.sqrt(
        (L - ref_L) ** 2 + 1.7 * (A - ref_a) ** 2 + 1.3 * (B - ref_b) ** 2
    )
    # Une lésion diffère soit en luminance/saturation, soit en chroma
    chroma_img = np.hypot(A, B)
    wound = (dist > 13.0) | (chroma_img > ref_chroma * 1.32 + 4.0)

    # Exclusion des repères de calibrage (gommette verte / marqueur ArUco) :
    # ils ne font jamais partie de la plaie et fausseraient la segmentation.
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    marker = cv2.inRange(hsv, np.array([32, 90, 50]), np.array([95, 255, 255]))
    marker = cv2.dilate(marker, np.ones((9, 9), np.uint8), iterations=2).astype(bool)
    wound &= ~marker

    # --- Croissance de région contrainte par la graine centrale ------------
    seed_y, seed_x = h // 2, w // 2
    if not wound[seed_y, seed_x]:
        # graine alternative : point le plus « distant » de la peau de référence
        idx = int(np.argmax(dist))
        seed_y, seed_x = divmod(idx, w)
    kh = np.ones((int(min(h, w) * 0.02) | 1, int(min(h, w) * 0.02) | 1), np.uint8)

    wm = wound.astype(np.uint8)
    wm = cv2.morphologyEx(wm, cv2.MORPH_OPEN, kh, iterations=1)
    wm = cv2.morphologyEx(wm, cv2.MORPH_CLOSE, kh, iterations=3)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(wm, connectivity=8)
    if n > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        best = 1 + int(np.argmax(areas))
        seed_lab = labels[seed_y, seed_x]
        if seed_lab != 0 and areas[seed_lab - 1] >= 0.003 * h * w:
            best = seed_lab
        wm = (labels == best).astype(np.uint8)
    contours, _ = cv2.findContours(wm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if contours:
        filled = np.zeros_like(wm)
        cv2.drawContours(filled, contours, -1, 1, thickness=-1)
        wm = filled
    wm_b = wm.astype(bool)

    # Si aucune région plausible n'est détectée (< 80 px ou < 0.04% de l'image),
    # ne jamais inventer de fausse plaie par seuillage forcé.
    if wm_b.sum() < 80 or wm_b.sum() < 0.0004 * h * w:
        wm_b = np.zeros((h, w), dtype=bool)
        contours = []

    mask, comp = classify_wound_tissues(image_bgr, wm_b)
    perim_px = float(sum(cv2.arcLength(c, True) for c in contours)) if contours else 0.0
    inflam = _perilesional_inflammation(image_bgr, wm_b)
    bbox = _bbox(wm_b)

    probs = np.zeros((h, w, NUM_CLASSES), np.float32)
    for i in range(NUM_CLASSES):
        probs[..., i] = (mask == i).astype(np.float32)
    probs = cv2.GaussianBlur(probs, (0, 0), sigmaX=3) + 1e-4
    probs /= probs.sum(axis=-1, keepdims=True)

    redness, entropy = tissue_descriptors(image_bgr, wm_b)

    return SegmentationOutput(
        mask=mask,
        wound_mask=wm_b,
        probs=probs,
        composition=comp,
        area_px=float(wm_b.sum()),
        perimeter_px=perim_px,
        bbox=bbox,
        perilesional_inflammation=inflam,
        redness_index=redness,
        texture_entropy=entropy,
    )


def tissue_descriptors(image_bgr: np.ndarray, wm: np.ndarray) -> tuple[float, float]:
    """Calcule l'indice de rougeur et l'entropie de texture dans le masque."""
    if not wm.any():
        return 0.0, 0.0
    if CV2:
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        L = lab[..., 0] * (100.0 / 255.0)
        A = lab[..., 1] - 128.0
        redness = float(np.clip(np.median(A[wm]) / 50.0, 0, 1))
        entropy = _entropy(L / 100.0, wm)
        return redness, entropy
    gray = _gray(image_bgr).astype(np.float32) / 255.0
    r = image_bgr[..., 2].astype(np.float32) / 255.0
    g = image_bgr[..., 1].astype(np.float32) / 255.0
    b = image_bgr[..., 0].astype(np.float32) / 255.0
    redness = float(np.clip(float(np.mean((r - (g + b) / 2)[wm])) * 3, 0, 1))
    entropy = _entropy(gray, wm)
    return redness, entropy


def classify_wound_tissues(
    image_bgr: np.ndarray, wm: np.ndarray
) -> tuple[np.ndarray, dict[str, float]]:
    """Classifie les tissus (5 classes) strictement à l'intérieur d'un masque de lésion."""
    h, w = image_bgr.shape[:2]
    wm_b = wm.astype(bool)
    if not wm_b.any():
        return np.zeros((h, w), np.uint8), {c: 0.0 for c in TISSUE_CLASSES[1:]}

    if CV2:
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        L = lab[..., 0] * (100.0 / 255.0)
        A = lab[..., 1] - 128.0
        B = lab[..., 2] - 128.0
        chroma = np.hypot(A, B)

        # Discrimination clinique :
        # · nécrose     : très sombre (L < 28) ou noirâtre dévitalisé (L < 36, faible saturation)
        # · granulation : rouge/rosé vif vascularisé (A >= 24, L 20..62)
        # · épithélial  : clair rosé (L >= 58, A >= 12, B < 16)
        # · fibrine     : jaune / blanc dévitalisé / slough adhérent
        necrosis = wm_b & ((L < 28.0) | ((L < 36.0) & (chroma < 26.0)))
        granulation = wm_b & ~necrosis & (A >= 24.0) & (L >= 20.0) & (L < 62.0)
        epithelial = wm_b & ~necrosis & ~granulation & (L >= 58.0) & (A >= 12.0) & (B < 16.0)
        fibrin = wm_b & ~necrosis & ~granulation & ~epithelial

        mask = np.zeros((h, w), np.uint8)
        assigned = np.zeros((h, w), bool)
        for cls, sel in (
            (NECROSIS, necrosis),
            (GRANULATION, granulation),
            (EPITHELIAL, epithelial),
            (FIBRIN, fibrin),
        ):
            take = sel & ~assigned
            mask[take] = cls
            assigned |= take

        # Lissage médian intra-lésionnel
        r_eq = float(np.sqrt(wm_b.sum() / np.pi))
        ksize = max(3, int(r_eq * 0.16) | 1)
        if ksize > 1 and mask.shape[0] >= ksize and mask.shape[1] >= ksize:
            smooth = cv2.medianBlur(mask, ksize)
            smooth[~wm_b] = 0
            mask = smooth

        comp = tissue_composition(mask)
        return mask, comp

    # Repli numpy sans OpenCV
    img = image_bgr.astype(np.float32) / 255.0
    r, g, b = img[..., 2], img[..., 1], img[..., 0]
    redness = r - (g + b) / 2
    v = img.max(-1)
    s = np.where(v > 0, (v - img.min(-1)) / (v + 1e-6), 0)

    necrosis = wm_b & (v < 0.20) & (s < 0.65)
    granulation = wm_b & ~necrosis & (redness > 0.10) & (s > 0.35) & (v > 0.15)
    epithelial = wm_b & ~necrosis & ~granulation & (redness > 0.04) & (s > 0.08) & (s <= 0.34) & (v > 0.55)
    fibrin = wm_b & ~necrosis & ~granulation & ~epithelial

    mask = np.zeros(img.shape[:2], np.uint8)
    mask[necrosis] = NECROSIS
    mask[granulation] = GRANULATION
    mask[epithelial] = EPITHELIAL
    mask[fibrin] = FIBRIN
    return mask, tissue_composition(mask)


def _segment_numpy(image_bgr: np.ndarray) -> SegmentationOutput:
    """Repli sans OpenCV (dégradé mais déterministe)."""
    img = image_bgr.astype(np.float32) / 255.0
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    mx, mn = img.max(-1), img.min(-1)
    v = mx
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    redness = r - (g + b) / 2

    necrosis = (v < 0.20) & (s < 0.65)
    granulation = (redness > 0.10) & (s > 0.35) & (v > 0.15)
    fibrin = (r > 0.45) & (g > 0.42) & (b < 0.55) & (redness < 0.12) & (v > 0.3)
    epithelial = (redness > 0.04) & (s > 0.08) & (s <= 0.34) & (v > 0.55)

    mask = np.zeros(img.shape[:2], np.uint8)
    wm = necrosis | granulation | fibrin | epithelial
    assigned = np.zeros_like(wm)
    for cls, m in ((NECROSIS, necrosis), (GRANULATION, granulation), (FIBRIN, fibrin), (EPITHELIAL, epithelial)):
        take = m & ~assigned
        mask[take] = cls
        assigned |= take
    mask[wm & ~assigned] = GRANULATION

    probs = np.zeros(mask.shape + (NUM_CLASSES,), np.float32)
    for i in range(NUM_CLASSES):
        probs[..., i] = (mask == i).astype(np.float32)
    probs += 1e-4
    probs /= probs.sum(axis=-1, keepdims=True)

    return SegmentationOutput(
        mask=mask,
        wound_mask=wm,
        probs=probs,
        composition=tissue_composition(mask),
        area_px=float(wm.sum()),
        perimeter_px=float(2 * np.sqrt(np.pi * wm.sum())),
        bbox=_bbox(wm),
        perilesional_inflammation=0.0,
        redness_index=float(np.clip(redness[wm].mean() * 3, 0, 1)) if wm.any() else 0.0,
        texture_entropy=_entropy(v, wm),
    )


# ---------------------------------------------------------------------------
# Métriques dérivées
# ---------------------------------------------------------------------------
def tissue_composition(mask: np.ndarray) -> dict[str, float]:
    wound = mask > 0
    total = int(wound.sum())
    if total == 0:
        return {c: 0.0 for c in TISSUE_CLASSES[1:]}
    out = {}
    for idx, name in enumerate(TISSUE_CLASSES):
        if idx == BACKGROUND:
            continue
        out[name] = round(float((mask == idx).sum()) / total, 4)
    # Normalisation exacte à 100 %
    s = sum(out.values())
    if s > 0:
        out = {k: round(v / s, 4) for k, v in out.items()}
    return out


def _bbox(wm: np.ndarray) -> tuple[int, int, int, int]:
    if not wm.any():
        return (0, 0, 0, 0)
    ys, xs = np.where(wm)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _entropy(gray01: np.ndarray, wm: np.ndarray) -> float:
    vals = gray01[wm] if wm.any() else gray01.ravel()
    hist, _ = np.histogram(vals, bins=32, range=(0, 1), density=False)
    p = hist / max(1, hist.sum())
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum() / 5.0)  # normalisé ~0..1


def _perilesional_inflammation(
    image_bgr: np.ndarray, wm: np.ndarray, ring_px: int = 0
) -> float:
    """Rougeur / œdème de la peau entourant la plaie (signe d'infection).

    La largeur de l'anneau est proportionnelle au rayon équivalent de la plaie
    (≈ 15 %) afin de rester valide pour les petites comme pour les grandes
    lésions.
    """
    if not CV2 or not wm.any():
        return 0.0
    if ring_px <= 0:
        r_eq = float(np.sqrt(wm.sum() / np.pi))
        ring_px = int(np.clip(r_eq * 0.15, 6, 34))
    kernel = np.ones((ring_px, ring_px), np.uint8)
    dilated = cv2.dilate(wm.astype(np.uint8), kernel, iterations=1).astype(bool)
    ring = dilated & ~wm
    if ring.sum() < 50:
        return 0.0
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    a_ring = (lab[..., 1][ring] - 128.0) / 127.0
    a_far = (lab[..., 1][~dilated] - 128.0) / 127.0
    if a_far.size < 100:
        return float(np.clip(a_ring.mean() * 2, 0, 1))
    delta = float(a_ring.mean() - a_far.mean())
    return float(np.clip(delta * 6.0, 0.0, 1.0))


def quantify(seg: SegmentationOutput, pixels_per_cm: float) -> dict[str, Any]:
    ppc = max(1e-6, pixels_per_cm)
    area_cm2 = seg.area_px / (ppc**2)
    perim_cm = seg.perimeter_px / ppc
    depth_proxy = float(np.sqrt(seg.area_px) / ppc)  # largeur de référence
    return {
        "area_cm2": round(area_cm2, 3),
        "perimeter_cm": round(perim_cm, 3),
        "max_dimension_cm": round(depth_proxy, 3),
        "pixels_per_cm": round(ppc, 3),
        "wound_pixels": int(seg.area_px),
        "bbox": list(seg.bbox),
    }


def render_tissue_overlay(image_bgr: np.ndarray, mask: np.ndarray, alpha: float = 0.55) -> np.ndarray:
    """Rendu RGBA-like du masque tissulaire (couche « Carte des Tissus »)."""
    palette = {
        NECROSIS: (27, 20, 24),
        FIBRIN: (232, 200, 120),
        GRANULATION: (192, 57, 43),
        EPITHELIAL: (231, 168, 160),
    }
    out = image_bgr.copy()
    for cls, color in palette.items():
        sel = mask == cls
        if not sel.any():
            continue
        overlay = np.zeros_like(image_bgr)
        overlay[:] = color[::-1]  # BGR
        out[sel] = ((1 - alpha) * image_bgr[sel] + alpha * overlay[sel]).astype(np.uint8)
    return out


def jet_colormap(norm01: np.ndarray) -> np.ndarray:
    """Colormap Jet (BGR) pour la heatmap Grad-CAM."""
    if CV2:
        u8 = (np.clip(norm01, 0, 1) * 255).astype(np.uint8)
        return cv2.applyColorMap(u8, cv2.COLORMAP_JET)
    x = np.clip(norm01, 0, 1)
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return (np.stack([b, g, r], -1) * 255).astype(np.uint8)


def overlap_superpose(image_bgr: np.ndarray, heat_bgr: np.ndarray, weight: float = 0.45) -> np.ndarray:
    return ((1 - weight) * image_bgr + weight * heat_bgr).astype(np.uint8)


def placeholders_ok(image_bgr: np.ndarray) -> bool:
    return image_bgr is not None and image_bgr.size > 0 and image_bgr.ndim == 3
