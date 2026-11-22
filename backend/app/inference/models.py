"""Architectures d'inférence médicale DiaFoot Sentinel.

Contient les définitions PyTorch réelles (chargées uniquement si `torch` est
disponible). Le backend reste pleinement opérationnel sans GPU ni poids `.pth`
grâce au moteur de simulation clinique calibré de `app.inference.pipeline`.

- `WoundSegmentationModel` : U-Net++ (encodeur timm-efficientnet-b3) — 5 classes.
- `WoundRiskClassifier`   : EfficientNet-B3 multi-têtes (infection / ischémie).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any

# --- Vocabulaire canonique des tissus (index == canal de sortie) -------------
TISSUE_CLASSES: tuple[str, ...] = (
    "background",   # 0 — fond / peau saine
    "necrosis",     # 1 — nécrose / escarre (noir)
    "fibrin",       # 2 — fibrine / slough (jaune)
    "granulation",  # 3 — granulation saine (rouge)
    "epithelial",   # 4 — épithélialisation (rose)
)

TISSUE_LABELS_FR: dict[str, str] = {
    "background": "Peau saine",
    "necrosis": "Nécrose",
    "fibrin": "Fibrine / Slough",
    "granulation": "Granulation",
    "epithelial": "Épithélialisation",
}

TISSUE_COLORS: dict[str, str] = {
    "background": "#00000000",
    "necrosis": "#1B1418",
    "fibrin": "#E8C878",
    "granulation": "#C0392B",
    "epithelial": "#E7A8A0",
}

NUM_CLASSES = len(TISSUE_CLASSES)

try:  # pragma: no cover - dépend de l'environnement d'exécution
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    TORCH_AVAILABLE = True
except Exception:  # noqa: BLE001
    torch = None  # type: ignore[assignment]
    nn = object  # type: ignore[assignment]
    TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Pertes
# ---------------------------------------------------------------------------
if TORCH_AVAILABLE:  # pragma: no cover

    class FUSegNetBinary(nn.Module):
        """FUSegNet EfficientNet-B7 entraîné pour la segmentation binaire des plaies."""

        def __init__(self, pretrained: bool = False) -> None:
            super().__init__()
            vendor_dir = Path(__file__).resolve().parent / "vendor"
            for module_name in list(sys.modules):
                if module_name == "segmentation_models_pytorch" or module_name.startswith(
                    "segmentation_models_pytorch."
                ):
                    sys.modules.pop(module_name, None)
            sys.path.insert(0, str(vendor_dir))
            warnings.filterwarnings(
                "ignore",
                message=r"`torch\.jit\.script` is deprecated.*",
                category=FutureWarning,
                module=r"torch\.jit\._script",
            )
            import segmentation_models_pytorch as smp
            Unet = smp.Unet

            self.model = Unet(
                encoder_name="efficientnet-b7",
                encoder_weights=None,
                classes=1,
                activation="sigmoid",
                decoder_attention_type="pscse",
            )
            self._binary_wound_mask = True

        def forward(self, x):
            return self.model(x)

    class DiceLoss(nn.Module):
        def __init__(self, smooth: float = 1.0) -> None:
            super().__init__()
            self.smooth = smooth

        def forward(self, logits, targets):
            probs = torch.softmax(logits, dim=1)
            onehot = F.one_hot(targets, NUM_CLASSES).permute(0, 3, 1, 2).float()
            dims = (0, 2, 3)
            inter = (probs * onehot).sum(dims)
            card = probs.sum(dims) + onehot.sum(dims)
            dice = (2 * inter + self.smooth) / (card + self.smooth)
            return 1 - dice[1:].mean()  # le fond n'entre pas dans la perte

    class FocalLoss(nn.Module):
        def __init__(self, gamma: float = 2.0, alpha: float | None = 0.25) -> None:
            super().__init__()
            self.gamma = gamma
            self.alpha = alpha

        def forward(self, logits, targets):
            logp = F.log_softmax(logits, dim=1)
            logpt = logp.gather(1, targets.unsqueeze(1)).squeeze(1)
            pt = logpt.exp()
            loss = -((1 - pt) ** self.gamma) * logpt
            if self.alpha is not None:
                loss = self.alpha * loss
            return loss.mean()

    class CombinedLoss(nn.Module):
        """0.5 * DiceLoss + 0.5 * FocalLoss (cf. spécification §4.A)."""

        def __init__(self) -> None:
            super().__init__()
            self.dice = DiceLoss()
            self.focal = FocalLoss()

        def forward(self, logits, targets):
            return 0.5 * self.dice(logits, targets) + 0.5 * self.focal(logits, targets)

    # -----------------------------------------------------------------------
    # Encodeur EfficientNet-B3 (timm si présent, sinon backbone interne)
    # -----------------------------------------------------------------------
    def _build_encoder(pretrained: bool = True) -> tuple[Any, list[int]]:
        try:
            import timm

            model_name = "efficientnet_b3" if hasattr(timm, "is_model") and timm.is_model("efficientnet_b3") else "timm-efficientnet-b3"
            enc = timm.create_model(
                model_name, pretrained=pretrained, features_only=True
            )
            return enc, enc.feature_info.channels()
        except Exception:  # noqa: BLE001 - pas de timm : backbone minimal
            class _MiniEnc(nn.Module):
                def __init__(self) -> None:
                    super().__init__()
                    c = [40, 32, 56, 160, 448]
                    self.stem = nn.Sequential(
                        nn.Conv2d(3, c[0], 3, 2, 1), nn.BatchNorm2d(c[0]), nn.SiLU()
                    )
                    self.s1 = nn.Sequential(nn.Conv2d(c[0], c[1], 3, 2, 1), nn.BatchNorm2d(c[1]), nn.SiLU())
                    self.s2 = nn.Sequential(nn.Conv2d(c[1], c[2], 3, 2, 1), nn.BatchNorm2d(c[2]), nn.SiLU())
                    self.s3 = nn.Sequential(nn.Conv2d(c[2], c[3], 3, 2, 1), nn.BatchNorm2d(c[3]), nn.SiLU())
                    self.s4 = nn.Sequential(nn.Conv2d(c[3], c[4], 3, 2, 1), nn.BatchNorm2d(c[4]), nn.SiLU())
                    self._channels = c

                @property
                def feature_info(self):
                    class _Info:
                        def __init__(self, ch):
                            self._ch = ch

                        def channels(self):
                            return self._ch

                    return _Info(self._channels)

                def forward(self, x):
                    x0 = self.stem(x)
                    x1 = self.s1(x0)
                    x2 = self.s2(x1)
                    x3 = self.s3(x2)
                    x4 = self.s4(x3)
                    return [x1, x2, x3, x4]

            m = _MiniEnc()
            return m, m.feature_info.channels()

    class ConvBlock(nn.Module):
        def __init__(self, cin: int, cout: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(cin, cout, 3, padding=1, bias=False),
                nn.BatchNorm2d(cout),
                nn.SiLU(inplace=True),
                nn.Conv2d(cout, cout, 3, padding=1, bias=False),
                nn.BatchNorm2d(cout),
                nn.Dropout2d(0.15),  # MC Dropout : incertitude clinique
                nn.SiLU(inplace=True),
            )

        def forward(self, x):
            return self.net(x)

    class WoundSegmentationModel(nn.Module):
        """U-Net++ avec encodeur EfficientNet-B3 (segmentation_models_pytorch) SOTA."""

        def __init__(self, num_classes: int = NUM_CLASSES, pretrained: bool = True):
            super().__init__()
            try:
                import segmentation_models_pytorch as smp

                self.model = smp.UnetPlusPlus(
                    encoder_name="timm-efficientnet-b3",
                    encoder_weights="imagenet" if pretrained else None,
                    in_channels=3,
                    classes=num_classes,
                    activation=None,
                )
                self.cam_target_layer = "model.segmentation_head"
                self._is_smp = True
            except Exception:
                self._is_smp = False
                self.encoder, ch = _build_encoder(pretrained=pretrained)
                dec = [64, 96, 128, 192]
                self.up3 = nn.ConvTranspose2d(ch[-1], dec[3], 2, 2)
                self.c3 = ConvBlock(ch[-2] + dec[3], dec[2])
                self.up2 = nn.ConvTranspose2d(dec[2], dec[2], 2, 2)
                self.c2 = ConvBlock(ch[-3] + dec[2], dec[1])
                self.up1 = nn.ConvTranspose2d(dec[1], dec[1], 2, 2)
                self.c1 = ConvBlock(ch[-4] + dec[1], dec[0])
                self.head = nn.Conv2d(dec[0], num_classes, 1)
                self.cam_target_layer = "head"

        def forward(self, x):
            if getattr(self, "_is_smp", False):
                return self.model(x)
            feats = self.encoder(x)
            x3 = self.up3(feats[-1])
            d2 = self.c3(torch.cat([x3, feats[-2]], dim=1))
            x2 = self.up2(d2)
            d1 = self.c2(torch.cat([x2, feats[-3]], dim=1))
            x1 = self.up1(d1)
            d0 = self.c1(torch.cat([x1, feats[-4]], dim=1))
            logits = self.head(d0)
            return F.interpolate(
                logits, size=x.shape[-2:], mode="bilinear", align_corners=False
            )

    class _GEGLU(nn.Module):
        def __init__(self, cin: int, cout: int) -> None:
            super().__init__()
            self.proj = nn.Linear(cin, cout * 2)

        def forward(self, x):
            a, b = self.proj(x).chunk(2, dim=-1)
            return a * F.gelu(b)

    class WoundRiskClassifier(nn.Module):
        """EfficientNet-B3 multi-tâches : infection + ischémie (+ incertitude MC)."""

        def __init__(self, pretrained: bool = True) -> None:
            super().__init__()
            try:
                import timm

                model_name = "efficientnet_b3" if hasattr(timm, "is_model") and timm.is_model("efficientnet_b3") else "timm-efficientnet-b3"
                self.backbone = timm.create_model(
                    model_name, pretrained=pretrained, num_classes=0
                )
                n_feat = self.backbone.num_features
            except Exception:  # noqa: BLE001
                self.backbone = nn.Sequential(
                    nn.Conv2d(3, 32, 3, 2, 1), nn.BatchNorm2d(32), nn.SiLU(),
                    nn.Conv2d(32, 64, 3, 2, 1), nn.BatchNorm2d(64), nn.SiLU(),
                    nn.Conv2d(64, 128, 3, 2, 1), nn.BatchNorm2d(128), nn.SiLU(),
                    nn.AdaptiveAvgPool2d(1),
                )
                n_feat = 128

            self.trunk = nn.Sequential(nn.LayerNorm(n_feat), nn.Dropout(0.3))
            self.head_infection = nn.Sequential(
                _GEGLU(n_feat, 256), nn.Dropout(0.25), nn.Linear(256, 1)
            )
            self.head_ischemia = nn.Sequential(
                _GEGLU(n_feat, 256), nn.Dropout(0.25), nn.Linear(256, 1)
            )

        def forward(self, x):
            feat = self.backbone(x)
            if feat.dim() > 2:
                feat = torch.flatten(feat, 1)
            feat = self.trunk(feat)
            return {
                "infection_risk": torch.sigmoid(self.head_infection(feat)).squeeze(-1),
                "ischemia_risk": torch.sigmoid(self.head_ischemia(feat)).squeeze(-1),
            }

    def enable_mc_dropout(model: nn.Module) -> None:
        """Active les couches Dropout en mode eval => Monte Carlo Dropout."""
        for m in model.modules():
            if isinstance(m, (nn.Dropout, nn.Dropout2d)):
                m.train()

    def count_parameters(model: Any) -> int:
        return sum(p.numel() for p in model.parameters() if p.requires_grad)

else:  # pragma: no cover - environnement sans PyTorch

    class _TorchUnavailable:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "PyTorch n'est pas installé : `pip install torch timm`. "
                "DiaFoot Sentinel bascule sur le moteur de simulation calibré."
            )

    WoundSegmentationModel = _TorchUnavailable  # type: ignore[misc,assignment]
    WoundRiskClassifier = _TorchUnavailable  # type: ignore[misc,assignment]

    def enable_mc_dropout(model: Any) -> None:  # noqa: D103
        raise RuntimeError("PyTorch requis pour le Monte Carlo Dropout")

    def count_parameters(model: Any) -> int:  # noqa: D103
        return 0
