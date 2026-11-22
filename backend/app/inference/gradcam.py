"""Explicabilité clinique : Grad-CAM (PyTorch) + proxy de saillance déterministe.

`GradCAMGenerator` cible la dernière couche convolutionnelle de l'encodeur
(`conv_head` / `head`) et produit une carte d'attention normalisée de la taille
de l'image source. Sans PyTorch, un proxy de saillance calculé sur les cartes
tissulaires (fibrine, nécrose, rougeur péri-lésionnelle) fournit une
explication visuelle cohérente et reproductible.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from app.inference.engine import (
    FIBRIN,
    GRANULATION,
    NECROSIS,
    EPITHELIAL,
    jet_colormap,
    overlap_superpose,
)

try:
    import cv2

    CV2 = True
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore[assignment]
    CV2 = False

try:
    import torch

    TORCH = True
except Exception:  # noqa: BLE001
    torch = None  # type: ignore[assignment]
    TORCH = False


class GradCAMGenerator:
    """Grad-CAM générique pour un modèle de classification multi-têtes."""

    def __init__(self, model: Any, target_layer: Optional[Any] = None) -> None:
        if not TORCH:
            raise RuntimeError("PyTorch requis pour le Grad-CAM natif")
        self.model = model
        self.model.eval()
        self.activations: Optional[Any] = None
        self.gradients: Optional[Any] = None
        layer = target_layer or self._find_target_layer()
        self._fwd_handle = layer.register_forward_hook(self._fwd_hook)
        self._bwd_handle = layer.register_full_backward_hook(self._bwd_hook)

    def close(self) -> None:
        if hasattr(self, "_fwd_handle") and self._fwd_handle is not None:
            self._fwd_handle.remove()
            self._fwd_handle = None
        if hasattr(self, "_bwd_handle") and self._bwd_handle is not None:
            self._bwd_handle.remove()
            self._bwd_handle = None

    def _find_target_layer(self):
        for name, module in reversed(list(self.model.named_modules())):
            if isinstance(module, torch.nn.Conv2d) and "conv_head" in name:
                return module
        for name, module in reversed(list(self.model.named_modules())):
            if isinstance(module, torch.nn.Conv2d):
                return module
        raise ValueError("Aucune couche convolutionnelle cible trouvée")

    def _fwd_hook(self, _m, _i, output) -> None:
        self.activations = output

    def _bwd_hook(self, _m, _gin, gout) -> None:
        self.gradients = gout[0]

    def generate(self, tensor: Any, head: str = "infection_risk") -> np.ndarray:
        try:
            self.model.zero_grad(set_to_none=True)
            out = self.model(tensor)[head].sum()
            out.backward()
            weights = self.gradients.mean(dim=(2, 3), keepdim=True)
            cam = torch.relu((weights * self.activations).sum(dim=1, keepdim=True))
            cam = torch.nn.functional.interpolate(
                cam, size=tensor.shape[-2:], mode="bilinear", align_corners=False
            )
            cam = cam[0, 0].detach().cpu().numpy()
            cam -= cam.min()
            return cam / (cam.max() + 1e-8)
        finally:
            self.close()


# ---------------------------------------------------------------------------
# Proxy de saillance (sans poids ni GPU)
# ---------------------------------------------------------------------------
def saliency_proxy(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    target: str = "infection_risk",
) -> np.ndarray:
    """Carte 0..1 expliquant la décision, alignée sur la sémantique clinique."""
    h, w = image_bgr.shape[:2]
    img = image_bgr.astype(np.float32) / 255.0

    if target == "infection_risk":
        # Fibrine abondante + nécrose + rougeur péri-lésionnelle
        relevance = (
            0.55 * (mask == FIBRIN).astype(np.float32)
            + 0.30 * (mask == NECROSIS).astype(np.float32)
            + 0.15 * (mask == GRANULATION).astype(np.float32)
        )
        if CV2:
            import cv2 as _cv2

            lab = _cv2.cvtColor(image_bgr, _cv2.COLOR_BGR2LAB).astype(np.float32)
            a = np.clip((lab[..., 1] - 128.0) / 127.0, 0, 1)
            relevance = 0.72 * relevance + 0.28 * a
    else:  # ischemia_risk : pâleur, froideur chromatique, berges peu vascularisées
        mx = img.max(-1)
        mn = img.min(-1)
        sat = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
        pallor = np.clip((0.45 - sat) * 2.6, 0, 1) * np.clip(mx, 0, 1)
        dark = np.clip((0.32 - mx) * 3.0, 0, 1)
        peri = _ring(mask > 0, radius=12).astype(np.float32)
        relevance = (
            0.45 * pallor
            + 0.35 * dark
            + 0.20 * ((mask == EPITHELIAL).astype(np.float32) + peri * 0.4)
        )

    if CV2:
        import cv2 as _cv2

        relevance = _cv2.GaussianBlur(relevance, (0, 0), sigmaX=max(4, min(h, w) * 0.02))
    else:
        k = max(3, (min(h, w) // 40) | 1)
        relevance = _box_blur(relevance, k)

    relevance -= relevance.min()
    relevance /= relevance.max() + 1e-8
    # Rehaussement de contraste (gamma) pour une lecture clinique franche
    return np.power(relevance, 0.65).astype(np.float32)


def _ring(wm: np.ndarray, radius: int) -> np.ndarray:
    if not CV2:
        return np.zeros_like(wm)
    import cv2 as _cv2

    k = np.ones((radius * 2 + 1, radius * 2 + 1), np.uint8)
    dil = _cv2.dilate(wm.astype(np.uint8), k).astype(bool)
    return dil & ~wm


def _box_blur(a: np.ndarray, k: int) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view

    pad = k // 2
    p = np.pad(a, pad, mode="edge")
    win = sliding_window_view(p, (k, k))
    return win.mean(axis=(-1, -2))


def heatmap_png_bgr(image_bgr: np.ndarray, cam01: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Superposition Heatmap Jet + image originale (BGR uint8)."""
    h, w = image_bgr.shape[:2]
    if cam01.shape[:2] != (h, w):
        if CV2:
            cam01 = cv2.resize(cam01, (w, h), interpolation=cv2.INTER_CUBIC)
        else:
            cam01 = np.kron(cam01, np.ones((h // cam01.shape[0] + 1, w // cam01.shape[1] + 1)))[:h, :w]
    heat = jet_colormap(cam01)
    return overlap_superpose(image_bgr, heat, alpha)


def cam_stats(cam01: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    """Résumé clinique de l'attention (localisation du signal)."""
    if not CV2 or mask.size == 0:
        return {"peak_intensity": round(float(cam01.max()), 3), "focus": "diffuse"}
    ys, xs = np.where(cam01 >= np.percentile(cam01, 99))
    h, w = cam01.shape[:2]
    cx, cy = float(xs.mean()) / w, float(ys.mean()) / h
    inside = float((cam01 * (mask > 0)).sum() / (cam01.sum() + 1e-8))
    return {
        "peak_intensity": round(float(cam01.max()), 3),
        "hotspot_center": [round(cx, 3), round(cy, 3)],
        "attention_inside_wound": round(inside, 3),
        "focus": "intra-lésionnel" if inside > 0.55 else "péri-lésionnel",
    }
