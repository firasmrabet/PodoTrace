"""Pipeline d'inférence DiaFoot Sentinel (`WoundAnalyzer`).

Chaîne complète, exécutée hors event-loop (thread pool) :

    bytes ──► décodage ──► quality gate ──► segmentation 5 classes
          ──► calibrage métrique ──► quantification ──► risques (+MC Dropout)
          ──► explicabilité (Grad-CAM / saillance) ──► recommandations
          ──► rendus PNG base64 (original, masque, heatmap)

Si les poids `.pth` sont absents, le pipeline bascule automatiquement sur
`app.inference.engine` (analyse colorimétrique + morphologique réelle) :
l'application reste testable de bout en bout sans GPU, sans jamais inventer
de mesure (les valeurs dépendent strictement des pixels).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageOps

from app.core.config import settings
from app.inference import engine
from app.inference.calibration import CalibrationResult, calibrate
from app.inference.gradcam import GradCAMGenerator, cam_stats, heatmap_png_bgr, saliency_proxy
from app.inference.models import TISSUE_CLASSES, TISSUE_COLORS, TISSUE_LABELS_FR
from app.inference.risk import RiskAssessment, calibrated_risk, deep_risk, push_score_estimate

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

MAX_SIDE = 1280
TARGET_SIDE = 640
logger = logging.getLogger(__name__)


class ImageQualityError(ValueError):
    """Image inexploitable ou rejetée : rejet motivé avec conseils cliniques de reprise."""

    def __init__(
        self,
        report: Optional[engine.QualityReport] = None,
        *,
        title: str = "Image inexploitable",
        message: Optional[str] = None,
        issues: Optional[list[str]] = None,
        guidance: Optional[str] = None,
        error_code: str = "image_quality_rejected",
    ) -> None:
        super().__init__(message or (report.issues[0] if report and report.issues else "Image non exploitable"))
        self.report = report
        self.title = title
        self.custom_message = message
        self.issues = issues if issues is not None else (report.issues if report else [])
        self.guidance = guidance
        self.error_code = error_code

    def payload(self) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "title": self.title,
            "message": self.custom_message or (
                "L'image ne permet pas une analyse fiable. "
                "Reprenez la photo en suivant les conseils ci-dessous."
            ),
            "issues": self.issues,
            "guidance": self.guidance,
            "quality": self.report.to_dict() if self.report else None,
        }


@dataclass
class AnalysisResult:
    payload: dict[str, Any]
    engine: str
    processing_ms: int


def _b64_png(bgr: np.ndarray, max_side: int = 900, quality_suffix: str = ".png") -> str:
    rgb = bgr[..., ::-1]
    img = Image.fromarray(rgb)
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    if quality_suffix == ".jpg":
        img.convert("RGB").save(buf, format="JPEG", quality=86, optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)
    return "data:image/" + ("jpeg" if quality_suffix == ".jpg" else "png") + ";base64," + base64.b64encode(
        buf.getvalue()
    ).decode()


def decode_image(data: bytes) -> np.ndarray:
    """Décode (et redresse via EXIF) n'importe quel format supporté en BGR."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return np.array(img)[..., ::-1].copy()


class WoundAnalyzer:
    """Orchestrateur d'inférence (singleton applicatif)."""

    def __init__(self) -> None:
        self.seg_model: Any = None
        self.risk_model: Any = None
        self.seg_ready = False
        self.risk_ready = False
        self.seg_load_error: Optional[str] = None
        self.risk_load_error: Optional[str] = None
        self._warmup()

    # -- chargement des poids ------------------------------------------------
    def _warmup(self) -> None:
        if not TORCH:
            self.seg_load_error = "PyTorch indisponible"
            self.risk_load_error = "PyTorch indisponible"
            return
        seg_path = settings.WEIGHTS_DIR / settings.SEG_CHECKPOINT
        risk_path = settings.WEIGHTS_DIR / settings.RISK_CHECKPOINT
        try:
            from app.inference.models import (
                FUSegNetBinary,
                WoundRiskClassifier,
                WoundSegmentationModel,
            )
        except Exception as exc:  # noqa: BLE001
            message = f"Architecture indisponible: {type(exc).__name__}: {str(exc)[:240]}"
            self.seg_load_error = message
            self.risk_load_error = message
            logger.exception("Impossible d'importer les architectures d'inférence")
            return

        seg_class = FUSegNetBinary if seg_path.name.startswith("fusegnet") else WoundSegmentationModel
        self.seg_model, self.seg_ready, self.seg_load_error = self._load_checkpoint(
            seg_class, seg_path, "segmentation"
        )
        self.risk_model, self.risk_ready, self.risk_load_error = self._load_checkpoint(
            WoundRiskClassifier, risk_path, "risque"
        )

    @staticmethod
    def _load_checkpoint(
        model_class: Any, checkpoint_path: Any, label: str
    ) -> tuple[Any, bool, Optional[str]]:
        if not checkpoint_path.is_file():
            return None, False, "Fichier de poids absent"
        try:
            model = model_class(pretrained=False)
            state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
            if isinstance(state, dict):
                for key in ("state_dict", "model_state_dict"):
                    if isinstance(state.get(key), dict):
                        state = state[key]
                        break
            if not isinstance(state, dict) or not state:
                raise TypeError("Le checkpoint ne contient pas de state_dict")
            if all(isinstance(key, str) and key.startswith("module.") for key in state):
                state = {key.removeprefix("module."): value for key, value in state.items()}
            if getattr(model, "_binary_wound_mask", False):
                model.model.load_state_dict(state, strict=True)
            else:
                model.load_state_dict(state, strict=True)
            model.eval()
            return model, True, None
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {str(exc)[:240]}"
            logger.info("Checkpoint %s absent ou incompatible: %s", label, error)
            return None, False, error

    @property
    def engine_name(self) -> str:
        parts = []
        if self.seg_ready:
            parts.append("fusegnet-effb7" if getattr(self.seg_model, "_binary_wound_mask", False) else "unetpp-effb3")
        else:
            parts.append("segmenter-hsv")
        parts.append("effb3-mc" if self.risk_ready else "risk-logistic-score")
        return "+".join(parts)

    def status(self) -> dict[str, Any]:
        return {
            "torch": TORCH,
            "opencv": CV2,
            "segmentation_model_loaded": self.seg_ready,
            "risk_model_loaded": self.risk_ready,
            "segmentation_model_error": self.seg_load_error,
            "risk_model_error": self.risk_load_error,
            "engine": self.engine_name,
            "simulation_fallback_allowed": settings.ALLOW_SIMULATION_FALLBACK,
        }

    # -- analyse -------------------------------------------------------------
    def analyze(
        self,
        image_bytes: bytes,
        *,
        scale_ref_cm: float = 2.0,
        manual_segment_px: Optional[float] = None,
        patient_context: Optional[dict[str, Any]] = None,
        with_heatmap: bool = True,
    ) -> AnalysisResult:
        t_start = time.perf_counter()
        if not image_bytes or len(image_bytes) < 512:
            raise ImageQualityError(
                engine.QualityReport(
                    is_acceptable=False, sharpness=0, brightness=0, exposure_clipped=1,
                    contrast=0, issues=["Fichier image vide ou illisible."], score=0.0,
                )
            )
        try:
            bgr = decode_image(image_bytes)
        except Exception as exc:  # noqa: BLE001
            raise ImageQualityError(
                engine.QualityReport(
                    is_acceptable=False, sharpness=0, brightness=0, exposure_clipped=1,
                    contrast=0, issues=[f"Format d'image non pris en charge ({exc})."], score=0.0,
                )
            ) from exc

        fingerprint = hashlib.sha256(image_bytes).hexdigest()
        quality = engine.quality_gate(bgr)
        if not quality.is_acceptable:
            raise ImageQualityError(quality)

        # 1) Segmentation
        seg = self._segment(bgr)

        # 2) Calibrage métrique
        calib: CalibrationResult = calibrate(
            bgr, scale_ref_cm=scale_ref_cm, manual_segment_px=manual_segment_px
        )
        metrics = engine.quantify(seg, calib.pixels_per_cm)

        # 3) Risques
        risk = self._risk(bgr, seg, patient_context, fingerprint)

        # 4) Explicabilité
        explain = self._explain(bgr, seg, risk, with_heatmap=with_heatmap)

        # 5) Rendus
        mask_overlay = engine.render_tissue_overlay(bgr, seg.mask, alpha=0.62)
        images = {
            "original": _b64_png(bgr, max_side=880, quality_suffix=".jpg"),
            "segmentation": _b64_png(mask_overlay, max_side=880),
        }
        if explain.get("heatmap_png"):
            images["heatmap"] = explain["heatmap_png"]
        contour = self._contour_render(bgr, seg.mask)
        if contour is not None:
            images["contour"] = _b64_png(contour, max_side=880)

        payload: dict[str, Any] = {
            "engine": self.engine_name,
            "image_sha256": fingerprint,
            "quality": quality.to_dict(),
            "calibration": {
                "pixels_per_cm": round(calib.pixels_per_cm, 3),
                "method": calib.method,
                "confidence": round(calib.confidence, 3),
                "reference_cm": calib.reference_cm,
                "details": calib.details,
                "reliable": calib.is_reliable,
            },
            "metrics": metrics,
            "tissues": {
                "composition": seg.composition,
                "classes": [
                    {
                        "key": c,
                        "label": TISSUE_LABELS_FR[c],
                        "color": TISSUE_COLORS[c],
                        "fraction": seg.composition.get(c, 0.0),
                    }
                    for c in TISSUE_CLASSES[1:]
                ],
                "dominant": max(seg.composition, key=seg.composition.get)
                if seg.composition
                else "granulation",
            },
            "risk": risk.to_dict(),
            "push_score": push_score_estimate(
                metrics["area_cm2"], seg.composition, risk.infection_risk
            ),
            "explainability": {k: v for k, v in explain.items() if k != "heatmap_png"},
            "images": images,
            "descriptors": {
                "perilesional_inflammation": round(seg.perilesional_inflammation, 3),
                "redness_index": round(seg.redness_index, 3),
                "texture_entropy": round(seg.texture_entropy, 3),
                "wound_pixels": int(seg.area_px),
            },
            "recommendations": risk.recommendations,
            "disclaimer": (
                "DiaFoot Sentinel est un outil d'aide à la télésurveillance en phase de validation clinique. "
                "Il ne remplace pas l'évaluation d'un professionnel de santé et ne "
                "pose pas de diagnostic. En cas de doute, consultez sans délai."
            ),
        }
        return AnalysisResult(
            payload=payload,
            engine=self.engine_name,
            processing_ms=int((time.perf_counter() - t_start) * 1000),
        )

    # -- étapes --------------------------------------------------------------
    def _segment(self, bgr: np.ndarray) -> engine.SegmentationOutput:
        total_px = bgr.shape[0] * bgr.shape[1]

        if self.seg_ready and TORCH:
            try:
                tensor = self._to_tensor(bgr)
                with torch.no_grad():
                    logits = self.seg_model(tensor)
                    if getattr(self.seg_model, "_binary_wound_mask", False):
                        # FUSegNetBinary a déjà une activation sigmoid dans smp.Unet.
                        # Éviter impérativement le double-sigmoid qui projette 0.0 -> 0.50.
                        raw_seg = logits[0, 0].cpu().numpy()
                        if raw_seg.min() >= 0.0 and raw_seg.max() <= 1.0:
                            probs_bin = raw_seg
                        else:
                            probs_bin = torch.sigmoid(logits)[0, 0].cpu().numpy()
                        mask = (probs_bin >= 0.5).astype(np.uint8)
                        probs = np.expand_dims(probs_bin, axis=-1)
                        max_wound_prob = float(probs_bin.max())
                    else:
                        probs_5 = torch.softmax(logits, dim=1)[0].cpu().numpy()
                        mask = probs_5.argmax(0).astype(np.uint8)
                        probs = probs_5
                        max_wound_prob = float(probs_5[1:].max()) if probs_5.shape[0] > 1 else float(probs_5.max())

                mask = self._resize_mask(mask, bgr.shape[:2])
                wm = mask > 0
                wound_px = int(wm.sum())

                # --- Validation clinique de présence de plaie ---
                # Si le modèle profond FUSegNet conclut à l'absence de plaie (probabilité maximale
                # faible ou surface insignifiante < 80 px), l'image est rejetée médicalement.
                # Il est STRICTEMENT INTERDIT de basculer sur un repli colorimétrique qui hallucinerait
                # une fausse plaie sur un visage ou un objet du quotidien.
                if wound_px < 80 or wound_px < 0.0004 * total_px or max_wound_prob < 0.40:
                    raise ImageQualityError(
                        title="Aucune plaie détectée",
                        message="L'intelligence artificielle n'a détecté aucune plaie ni lésion ulcéreuse sur cette photographie.",
                        issues=[
                            "Aucune lésion cutanée ulcéreuse n'a été identifiée par le réseau de neurones FUSegNet.",
                            "L'image semble être un visage, un objet ou une peau saine sans plaie.",
                        ],
                        guidance=(
                            "DiaFoot Sentinel est spécifiquement conçu pour l'évaluation et le suivi des plaies du "
                            "pied diabétique. Cadrez directement la lésion sur le pied, bien centrée et sous un éclairage naturel."
                        ),
                        error_code="no_wound_detected",
                    )

                # Validation de cadrage : une plaie clinique ne couvre pas plus de 65 % du champ
                if wound_px >= 0.65 * total_px:
                    raise ImageQualityError(
                        title="Cadrage inadapté",
                        message="La zone sélectionnée couvre plus de 65 % de l'image. Le contour de la plaie ne peut pas être délimité de façon fiable.",
                        issues=[
                            "La lésion remplit la quasi-totalité du cadre.",
                            "Une marge de peau saine périphérique (au moins 2 à 3 cm) est nécessaire pour évaluer les berges et l'érythème péri-lésionnel.",
                        ],
                        guidance="Éloignez légèrement l'appareil pour que la plaie et la peau saine environnante soient visibles.",
                        error_code="framing_invalid",
                    )

                # Re-classification tissulaire précise à l'intérieur du masque neural FUSegNet validé
                if getattr(self.seg_model, "_binary_wound_mask", False):
                    t_mask, comp = engine.classify_wound_tissues(bgr, wm)
                    mask = t_mask
                else:
                    comp = engine.tissue_composition(mask)

                redness, entropy = engine.tissue_descriptors(bgr, wm)
                return engine.SegmentationOutput(
                    mask=mask, wound_mask=wm, probs=probs.transpose(1, 2, 0),
                    composition=comp, area_px=float(wound_px),
                    perimeter_px=self._perimeter(wm), bbox=engine._bbox(wm),
                    perilesional_inflammation=engine._perilesional_inflammation(bgr, wm),
                    redness_index=redness, texture_entropy=entropy,
                )
            except ImageQualityError:
                raise
            except Exception as exc:  # noqa: BLE001
                print(f"[DiaFoot] Inférence U-Net++ adaptée ({exc}) → segmentation morphologique clinique")

        # Repli uniquement si le modèle neural est indisponible ou a échoué techniquement
        base_seg = engine.segment_tissues(bgr)
        if base_seg.area_px < 80 or base_seg.area_px < 0.0004 * total_px:
            raise ImageQualityError(
                title="Aucune plaie détectée",
                message="Aucune zone lésionnelle caractéristique n'a pu être identifiée sur cette photographie.",
                issues=["L'analyse n'a décelé aucun contraste de tissu lésionnel caractéristique."],
                guidance="Cadrez la lésion du pied au centre de la photo avec un éclairage suffisant.",
                error_code="no_wound_detected",
            )
        if base_seg.area_px >= 0.65 * total_px:
            raise ImageQualityError(
                title="Cadrage inadapté",
                message="La zone détectée couvre une surface excessive de l'image.",
                issues=["Zone détectée supérieure à 65% de la surface."],
                guidance="Éloignez légèrement l'appareil pour faire apparaître la peau saine environnante.",
                error_code="framing_invalid",
            )
        return base_seg

    def _risk(
        self,
        bgr: np.ndarray,
        seg: engine.SegmentationOutput,
        ctx: Optional[dict[str, Any]],
        fingerprint: str,
    ) -> RiskAssessment:
        base = calibrated_risk(seg, patient_context=ctx, image_fingerprint=fingerprint)
        if self.risk_ready and TORCH:
            try:
                tensor = self._to_tensor(bgr)
                inf, isch, unc, stds = deep_risk(
                    self.risk_model, tensor, passes=settings.MC_DROPOUT_PASSES,
                    threshold=settings.UNCERTAINTY_THRESHOLD,
                )
                from app.inference.risk import level_from_scores

                # --- Fusion de sécurité clinique (IWGDF 2023 / TIME) ---
                # Un réseau de neurones CNN ne doit jamais déclasser une plaie grave
                # (nécrose/fibrine importante) en dessous des règles cliniques déterministes.
                final_inf = max(float(inf), float(base.infection_risk))
                final_isch = max(float(isch), float(base.ischemia_risk))
                final_unc = max(float(unc), float(base.uncertainty))

                return RiskAssessment(
                    infection_risk=final_inf,
                    ischemia_risk=final_isch,
                    uncertainty=final_unc,
                    risk_level=level_from_scores(final_inf, final_isch),
                    factors=base.factors,
                    recommendations=base.recommendations,
                    mc_std=stds,
                    engine="fusegnet+effb3-mc+clinical-fusion",
                    requires_review=final_unc > settings.UNCERTAINTY_THRESHOLD,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[DiaFoot] Classifieur profond indisponible ({exc}) → score calibré")
        return base

    def _explain(
        self,
        bgr: np.ndarray,
        seg: engine.SegmentationOutput,
        risk: RiskAssessment,
        *,
        with_heatmap: bool = True,
    ) -> dict[str, Any]:
        target = "infection_risk" if risk.infection_risk >= risk.ischemia_risk else "ischemia_risk"
        cam: Optional[np.ndarray] = None
        method = "saliency-proxy"
        if self.risk_ready and TORCH:
            try:
                gen = GradCAMGenerator(self.risk_model)
                cam = gen.generate(self._to_tensor(bgr), head=target)
                method = "grad-cam"
            except Exception as exc:  # noqa: BLE001
                print(f"[DiaFoot] Grad-CAM indisponible ({exc}) → proxy de saillance")
        if cam is None:
            cam = saliency_proxy(bgr, seg.mask, target=target)
        elif CV2 and cam.shape[:2] != bgr.shape[:2]:
            cam = cv2.resize(cam, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)

        out: dict[str, Any] = {
            "method": method,
            "target": target,
            "stats": cam_stats(cam, seg.wound_mask),
        }
        if with_heatmap:
            out["heatmap_png"] = _b64_png(
                heatmap_png_bgr(bgr, cam), max_side=880, quality_suffix=".jpg"
            )
        return out

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _to_tensor(bgr: np.ndarray) -> Any:
        rgb = bgr[..., ::-1].astype(np.float32) / 255.0
        img = Image.fromarray((rgb * 255).astype(np.uint8)).resize((512, 512), Image.BILINEAR)
        arr = np.array(img).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], np.float32)
        std = np.array([0.229, 0.224, 0.225], np.float32)
        arr = (arr - mean) / std
        return torch.from_numpy(arr.transpose(2, 0, 1)[None]).float()

    @staticmethod
    def _resize_mask(mask: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
        h, w = target_hw
        if mask.shape[:2] == (h, w):
            return mask
        if CV2:
            return cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        return np.array(
            Image.fromarray(mask).resize((w, h), Image.NEAREST)
        )

    @staticmethod
    def _perimeter(wm: np.ndarray) -> float:
        if not CV2 or not wm.any():
            return float(2 * np.sqrt(np.pi * wm.sum()))
        contours, _ = cv2.findContours(
            wm.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        return float(sum(cv2.arcLength(c, True) for c in contours))

    @staticmethod
    def _contour_render(bgr: np.ndarray, mask: np.ndarray) -> Optional[np.ndarray]:
        if not CV2:
            return None
        out = bgr.copy()
        contours, _ = cv2.findContours(
            (mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if contours:
            cv2.drawContours(out, contours, -1, (200, 190, 255), 3)
        return out


# ---------------------------------------------------------------------------
# Façade asynchrone (à appeler depuis les routes FastAPI)
# ---------------------------------------------------------------------------
_analyzer: Optional[WoundAnalyzer] = None


def get_analyzer() -> WoundAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = WoundAnalyzer()
    return _analyzer


async def analyze_async(
    image_bytes: bytes,
    *,
    scale_ref_cm: float = 2.0,
    manual_segment_px: Optional[float] = None,
    patient_context: Optional[dict[str, Any]] = None,
    with_heatmap: bool = True,
) -> AnalysisResult:
    """Exécute le pipeline dans un thread pour ne pas bloquer l'event loop."""
    return await asyncio.to_thread(
        get_analyzer().analyze,
        image_bytes,
        scale_ref_cm=scale_ref_cm,
        manual_segment_px=manual_segment_px,
        patient_context=patient_context,
        with_heatmap=with_heatmap,
    )
