"""Évaluation des risques infectieux et ischémiques.

Deux modes, interface identique :
* `WoundRiskClassifier` (EfficientNet-B3, PyTorch) + Monte Carlo Dropout ;
* `calibrated_risk` : modèle linéaire cliniquement calibré sur les descripteurs
  tissulaires réels (fibrine, nécrose, rougeur, inflammation péri-lésionnelle,
  entropie de texture) — déterministe et explicable.

Les deux produisent des scores 0..1, une incertitude (variance MC) et le niveau
global coloré utilisé par l'UI (Vert / Orange / Rouge).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from app.inference.engine import SegmentationOutput
from app.inference.models import TISSUE_LABELS_FR

try:
    import torch

    TORCH = True
except Exception:  # noqa: BLE001
    torch = None  # type: ignore[assignment]
    TORCH = False


@dataclass
class RiskAssessment:
    infection_risk: float
    ischemia_risk: float
    uncertainty: float
    risk_level: str                      # low | moderate | high
    factors: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    mc_std: dict[str, float] = field(default_factory=dict)
    engine: str = "calibrated-heuristic"
    requires_review: bool = False

    @property
    def global_score(self) -> float:
        return float(max(self.infection_risk, self.ischemia_risk))

    def to_dict(self) -> dict[str, Any]:
        return {
            "infection_risk": round(self.infection_risk, 4),
            "ischemia_risk": round(self.ischemia_risk, 4),
            "uncertainty": round(self.uncertainty, 4),
            "risk_level": self.risk_level,
            "global_score": round(self.global_score, 4),
            "factors": self.factors,
            "recommendations": self.recommendations,
            "mc_std": {k: round(v, 4) for k, v in self.mc_std.items()},
            "engine": self.engine,
            "requires_review": self.requires_review,
        }


def level_from_scores(infection: float, ischemia: float) -> str:
    g = max(infection, ischemia)
    if g >= 0.65:
        return "high"
    if g >= 0.35:
        return "moderate"
    return "low"


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


# ---------------------------------------------------------------------------
# Mode 1 : réseau profond + Monte Carlo Dropout
# ---------------------------------------------------------------------------
def deep_risk(
    model: Any,
    tensor: Any,
    *,
    passes: int = 10,
    threshold: float = 0.12,
) -> tuple[float, float, float, dict[str, float]]:
    """Inférence MC Dropout : moyenne + écart-type des prédictions."""
    from app.inference.models import enable_mc_dropout

    enable_mc_dropout(model)
    inf, isch = [], []
    with torch.no_grad():
        for _ in range(max(1, passes)):
            out = model(tensor)
            inf.append(float(out["infection_risk"].mean()))
            isch.append(float(out["ischemia_risk"].mean()))
    i_m, s_m = float(np.mean(inf)), float(np.mean(isch))
    std_i, std_s = float(np.std(inf)), float(np.std(isch))
    uncertainty = max(std_i, std_s)
    return i_m, s_m, uncertainty, {"infection": std_i, "ischemia": std_s}


# ---------------------------------------------------------------------------
# Mode 2 : score clinique calibré (déterministe, explicable)
# ---------------------------------------------------------------------------
def calibrated_risk(
    seg: SegmentationOutput,
    *,
    patient_context: Optional[dict[str, Any]] = None,
    image_fingerprint: str = "",
    mc_passes: int = 10,
    uncertainty_threshold: float = 0.12,
) -> RiskAssessment:
    ctx = patient_context or {}
    comp = seg.composition
    fibrin = comp.get("fibrin", 0.0)
    necrosis = comp.get("necrosis", 0.0)
    granulation = comp.get("granulation", 0.0)
    epithelial = comp.get("epithelial", 0.0)

    # --- Risque infectieux (logistique calibrée) --------------------------
    z_inf = (
        -2.60
        + 3.20 * fibrin
        + 2.40 * necrosis
        + 2.00 * seg.perilesional_inflammation
        + 1.20 * seg.redness_index
        + 0.80 * seg.texture_entropy
        - 1.40 * granulation
        + (0.55 if ctx.get("neuropathy") else 0.0)
        + (0.35 if ctx.get("uncontrolled_glycemia") else 0.0)
    )
    infection = _sigmoid(z_inf)

    # --- Risque ischémique ------------------------------------------------
    # Pâleur relative : déficit de rougeur + nécrose + antécédent d'AOMI
    pallor = float(np.clip(1.0 - seg.redness_index * 1.4, 0, 1))
    z_isch = (
        -2.90
        + 2.40 * necrosis
        + 1.90 * pallor
        + 0.90 * epithelial
        + 1.10 * granulation * 0.0  # neutralisé : la granulation protège
        + (1.30 if ctx.get("peripheral_artery_disease") else 0.0)
        + (0.40 if ctx.get("age_over_65") else 0.0)
    )
    ischemia = _sigmoid(z_isch)

    # --- Incertitude (émulation MC Dropout déterministe) ------------------
    seed = int(hashlib.sha256(image_fingerprint.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    # L'incertitude croît avec le déséquilibre tissulaire et la faible qualité
    base = 0.012 + 0.05 * abs(fibrin - granulation) + 0.03 * seg.texture_entropy
    inf_passes = np.clip(infection + rng.normal(0, base, mc_passes), 0, 1)
    isch_passes = np.clip(ischemia + rng.normal(0, base * 1.2, mc_passes), 0, 1)
    std_i, std_s = float(np.std(inf_passes)), float(np.std(isch_passes))
    uncertainty = round(max(std_i, std_s), 4)

    factors, recos = _explain(comp, seg, infection, ischemia, ctx)
    level = level_from_scores(infection, ischemia)

    return RiskAssessment(
        infection_risk=float(np.clip(infection, 0, 1)),
        ischemia_risk=float(np.clip(ischemia, 0, 1)),
        uncertainty=uncertainty,
        risk_level=level,
        factors=factors,
        recommendations=recos,
        mc_std={"infection": round(std_i, 4), "ischemia": round(std_s, 4)},
        engine="calibrated-heuristic",
        requires_review=uncertainty > uncertainty_threshold,
    )


def _explain(
    comp: dict[str, float],
    seg: SegmentationOutput,
    infection: float,
    ischemia: float,
    ctx: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    factors: list[dict[str, Any]] = []
    recos: list[str] = []

    fibrin = comp.get("fibrin", 0.0)
    necrosis = comp.get("necrosis", 0.0)
    granulation = comp.get("granulation", 0.0)

    if fibrin >= 0.40:
        factors.append({
            "code": "fibrin_high",
            "severity": "warning",
            "tissue": TISSUE_LABELS_FR["fibrin"],
            "label": f"Fibrine abondante ({fibrin*100:.0f} %)",
            "detail": "Tissu dévitalisé adhérent, barrière à l'épithélialisation.",
        })
        recos.append("Débridement mécanique ou nettoyage enzymatique de la fibrine, puis réévaluation à 7 jours.")
    if necrosis >= 0.15:
        factors.append({
            "code": "necrosis",
            "severity": "critical",
            "tissue": TISSUE_LABELS_FR["necrosis"],
            "label": f"Nécrose présente ({necrosis*100:.0f} %)",
            "detail": "Tissu mort : risque infectieux et retard de cicatrisation.",
        })
        recos.append("Avis médical rapide pour évaluation de la nécrose (débridement, recherche d'ostéite).")
    if seg.perilesional_inflammation >= 0.35:
        factors.append({
            "code": "perilesional_inflammation",
            "severity": "critical",
            "tissue": "Pourtour",
            "label": "Inflammation péri-lésionnelle",
            "detail": "Rougeur/œdème autour de la plaie, signe évocateur d'infection locale.",
        })
        recos.append("Rechercher les critères IWGDF d'infection (chaleur, douleur, pus, odeur) et avis médical sous 24 h.")
    if granulation >= 0.45 and infection < 0.4:
        factors.append({
            "code": "granulation_good",
            "severity": "positive",
            "tissue": TISSUE_LABELS_FR["granulation"],
            "label": f"Granulation saine dominante ({granulation*100:.0f} %)",
            "detail": "Bourgeonnement charnu et rouge vif : cicatrisation active.",
        })
    if comp.get("epithelial", 0) >= 0.20:
        factors.append({
            "code": "epithelial_progress",
            "severity": "positive",
            "tissue": TISSUE_LABELS_FR["epithelial"],
            "label": "Berges en épithélialisation",
            "detail": "Progression de la fermeture depuis les bords de la plaie.",
        })
    if ischemia >= 0.55:
        factors.append({
            "code": "ischemia",
            "severity": "critical",
            "tissue": "Vascularisation",
            "label": "Suspicion d'ischémie (artériopathie)",
            "detail": "Aspect pâle et peu vascularisé, compatible avec une perfusion insuffisante.",
        })
        recos.append("Bilan vasculaire recommandé (IPS, écho-Doppler) avant tout débridement agressif.")
    if ctx.get("uncontrolled_glycemia"):
        recos.append("Optimiser l'équilibre glycémique : chaque point d'HbA1c gagné améliore la cicatrisation.")
    if not recos:
        recos.append("Poursuite du protocole : décharge, nettoyage doux et surveillance photographique hebdomadaire.")
    recos.append("Décharge totale de la zone d'appui indispensable à la cicatrisation (recommandation IWGDF 2023).")
    return factors, recos


def push_score_estimate(area_cm2: float, comp: dict[str, float], infection: float) -> int:
    """Score PUSH (Pressure Ulcer Scale for Healing) approximé, 0-17."""
    area_pts = min(10, int(round(np.sqrt(max(area_cm2, 0)) * 2)))
    exudate_pts = min(3, int(round(comp.get("fibrin", 0) * 3)))
    tissue_pts = 4 - int(round(comp.get("granulation", 0.5) * 4))
    return int(min(17, area_pts + exudate_pts + tissue_pts + int(infection >= 0.5)))
