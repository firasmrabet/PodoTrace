"""Re-export des modèles d'inférence (compat imports historiques).

Le pipeline consomme `app.inference.models.WoundSegmentationModel` (5 classes).
Ce module conserve l'API publique attendue par le reste du code.
"""
from app.inference.models import (  # noqa: F401
    TISSUE_CLASSES,
    TISSUE_LABELS_FR,
    WoundRiskClassifier,
    WoundSegmentationModel,
    count_parameters,
)
