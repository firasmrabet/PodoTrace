# Modèles Deep Learning PodoTrace

Ce dossier contient les points de contrôle (*checkpoints*) PyTorch entraînés pour le pipeline d'inférence de PodoTrace :

1. **`fusegnet_effb7_best_model_1.pth`** (~768 Mo) :
   - Modèle de segmentation sémantique binaire FUSegNet (`smp.Unet` avec encodeur `efficientnet-b7` et attention `pscse`).
   - Délimitation fine du lit de la plaie du pied diabétique.

2. **`wound_risk_effb3.pth`** (~47 Mo) :
   - Classifieur multi-têtes (`EfficientNet-B3`) pour le risque d'infection, risque d'ischémie et incertitude (Monte-Carlo Dropout).

3. **`wound_seg_unetpp_effb3.pth`** (~195 Mo) :
   - U-Net++ multiclasse de secours.

> ℹ️ Les fichiers `.pth` étant volumineux (> 100 Mo), ils sont exclus de Git conformément aux limites GitHub.
> En leur absence, le pipeline bascule de manière transparente sur le moteur colorimétrique et géométrique calibré (`ALLOW_SIMULATION_FALLBACK=true`).
