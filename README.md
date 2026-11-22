# PodoTrace

**Plateforme intelligente de télésurveillance et d'aide à la décision clinique pour les ulcères du pied diabétique.**  
Photographiez la plaie : **PodoTrace** mesure la surface exacte en cm², segmente les tissus (nécrose, fibrine, granulation, épithélialisation), estime le risque infectieux et ischémique, explique sa décision par Grad-CAM, trace la trajectoire de cicatrisation (score PUSH, indice de Gilman) et assiste le praticien et le patient.

> ⚠️ **Dispositif médical d'aide à la décision (SaMD) en phase de validation clinique (IWGDF 2023).**  
> Ne remplace pas l'évaluation d'un médecin. En cas d'urgence vitale, douleur brutale, fièvre ou extension rapide de l'érythème :  
> **appelez immédiatement le 15 (SAMU)** ou le **190 (Tunisie)**.

---

## Démarrage rapide

```bash
# 1. Cloner et installer les dépendances
git clone https://github.com/firasmrabet/PodoTrace.git
cd PodoTrace
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements.txt

# 2. Configurer les variables d'environnement
cp backend/.env.example backend/.env

# 3. Lancer le serveur (API FastAPI + Interface Web servies sur le même port)
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
```

Puis ouvrez **http://localhost:8000** dans votre navigateur.  
La documentation interactive de l'API REST est accessible sur **http://localhost:8000/docs**.

---

## Architecture IA & Deep Learning

Le pipeline d'inférence de **PodoTrace** combine intelligence artificielle profonde et sécurité clinique déterministe :

1. **Segmentation sémantique fine (FUSegNet & U-Net++)** :
   - Encodeur **EfficientNet-B7** avec mécanismes d'attention spatiale et de canaux (scSE).
   - Délimitation précise du lit de la plaie à l'exclusion stricte de la peau saine.
2. **Classification et composition tissulaire (4 classes TIME)** :
   - Quantification en temps réel des fractions tissulaires : **Nécrose**, **Fibrine**, **Granulation**, **Épithélialisation**.
3. **Évaluation du risque infectieux et ischémique (EfficientNet-B3)** :
   - Réseau multi-têtes avec quantification d'incertitude épistémique par **Monte-Carlo Dropout**.
   - **Fusion de sécurité clinique** : le modèle neuronal ne peut jamais sous-estimer la sévérité en présence de nécrose ou de signes cardinaux d'infection (IWGDF 2023).
4. **Explicabilité IA (Grad-CAM & Saillance)** :
   - Cartes de chaleur d'activation pondérées par gradients pour objectiver les zones influençant la prédiction du risque.
5. **Portes de rejet clinique & anti-faux-positifs** :
   - Tout cliché non lésionnel (visage, objet, peau saine) est automatiquement détecté et refusé médicalement avec conseils de reprise.

---

## Fonctionnalités Clés

* 📷 **Capture guidée par caméra & import** : Réticule de centrage, inclinomètre virtuel (niveau à bulle), détection de repères de calibration métrique (gommette 2 cm / marqueurs ArUco / échelle manuelle).
* 🛰️ **Cartographie des centres de soins & urgences** : Carte interactive satellite HD (Esri World Imagery) et plan des rues (OpenStreetMap) géolocalisant les urgences 24/7, services de plaies & cicatrisation, podologues et diabétologues proches.
* 📈 **Suivi temporel de cicatrisation** : Trajectoires de surface, vitesse de réduction ($cm^2/\text{semaine}$), score PUSH (0–17) et index de Gilman.
* 🤖 **Assistant conversationnel clinique** : RAG adossé aux recommandations internationales IWGDF, détection immédiate des signaux d'alerte vitale (drapeaux rouges), compatible avec les LLMs via Groq / Mistral et repli heuristique local hors-ligne.
* 🔒 **Sécurité & Confidentialité de santé (HDS / RGPD)** : Chiffrement symétrique fort AES-256 (Fernet) au repos de toutes les photographies médicales, authentification JWT/OAuth2, cloisonnement strict des accès par rôles (patient, praticien, proche).
* 📄 **Rapports médicaux PDF exportables** : Synthèse clinique imprimable pour transmission au dossier patient informatisé.

---

## Comptes de démonstration

L'application est pré-configurée avec des profils types :

| Rôle | Email | Mot de passe |
| :--- | :--- | :--- |
| **Patient** | `amine@diafoot.tn` | `diafoot2026` |
| **Praticien** | `dr.mansouri@diafoot.tn` | `diafoot2026` |
| **Proche / Aidant** | `monia@diafoot.tn` | `diafoot2026` |

---

## Licence

Projet développé sous licence MIT. Conçu à des fins de recherche clinique et d'innovation en télésanté.

Spécification complète (tokens, composants, mouvements, interdits) :
[`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md).

---

## Structure du dépôt

```
diafoot-sentinel/
├── backend/          FastAPI + moteur d'inférence + services (Python 3.10+)
│   ├── app/          api · core · db · inference · models · schemas · services · tests
│   ├── scripts/      reset_demo.py (réamorçage du jeu de démonstration)
│   ├── storage/      images chiffrées (créé au 1er démarrage)
│   └── requirements.txt
├── web/              interface active — SPA sans build, sans CDN
│   ├── index.html · css/app.css · js/{app,core}.js · js/views/*.js
├── app_flutter/      client Flutter (mobile/web), même API, même palette
├── docs/             ARCHITECTURE.md · DESIGN_SYSTEM.md
├── .vscode/          launch · tasks · settings · extensions
└── .env.example      toutes les variables (toutes optionnelles)
```

---

## Configuration

Tout est optionnel : sans fichier `.env`, l'application démarre en mode
développement (SQLite, stockage local, comptes de démonstration).

```bash
cp .env.example backend/.env
```

| Variable | Défaut | Rôle |
|---|---|---|
| `PORT` | `8000` | port HTTP (API + interface) |
| `DATABASE_URL` | SQLite `backend/diafoot.db` | PostgreSQL en production |
| `SECRET_KEY` | généré → `backend/.diafoot_secret` | signature JWT + clé de chiffrement |
| `EXPOSE_OTP_IN_RESPONSE` | `true` | affiche l'OTP à l'écran (dev) |
| `AUTO_SEED_DEMO` | `true` | jeu de démonstration au 1er démarrage |
| `GROQ_API_KEY` / `MISTRAL_API_KEY` / `OPENROUTER_API_KEY` | — | assistant LLM distant |
| `ALLOW_SIMULATION_FALLBACK` | `true` | moteur colorimétrique si poids absents |

> 🔐 `backend/.diafoot_secret` chiffre les photos stockées. Le supprimer rend les
> images existantes illisibles **et** invalide les jetons : à réserver à une
> rotation de clé volontaire (puis `python scripts/reset_demo.py`).

---

## Réinitialiser / réamorcer la démo

```bash
cd backend
../.venv/bin/python scripts/reset_demo.py             # vide base + images, puis réamorce
../.venv/bin/python scripts/reset_demo.py --seed-only # complète les données démo sans effacer
```

---

## Client Flutter (optionnel)

`app_flutter/` contient un client Flutter (mobile et web) aligné sur la même API
et le même design system. Il nécessite le SDK Flutter, absent de
l'environnement de référence :

```bash
cd app_flutter && flutter pub get
flutter run -d chrome --web-port 5173 --dart-define=API_BASE_URL=http://localhost:8000
```

Le backend accepte déjà toutes les origines `localhost:*` (CORS) et expose les
en-têtes nécessaires à la caméra et à la géolocalisation.

---

## Déploiement

```bash
# production : PostgreSQL + secrets fournis par l'environnement
export ENV=production SECRET_KEY=... FERNET_KEY=... DATABASE_URL=postgresql+asyncpg://...
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
```

À faire avant toute mise en production : `ENV=production` (désactive l'OTP en
clair), `AUTO_SEED_DEMO=false`, HTTPS obligatoire (caméra + géolocalisation),
sauvegardes chiffrées, et revue clinique du moteur sur une cohorte locale.

---

## Dépannage

| Symptôme | Cause / solution |
|---|---|
| `Contenu chiffré illisible` | `backend/.diafoot_secret` a été supprimé/remplacé → `rm backend/diafoot.db && rm -rf backend/storage` puis relancer |
| La caméra ne s'ouvre pas | la capture exige HTTPS ou `localhost` ; sans caméra, le bouton « importer » et « générer une image de test » fonctionnent |
| Centres de soin en « source locale » | Overpass/OSM injoignable (fréquent hors-ligne) → jeu local Grand Tunis affiché, choix assumé |
| `database is locked` | SQLite est en WAL avec un `busy_timeout` de 30 s, et le jeu de démonstration est
commité mesure par mesure : ce cas ne doit plus apparaître. S'il persiste, un **second** serveur
écrit dans la même base — arrêtez-le (`lsof -ti:8000 \| xargs kill`) |
| La connexion de démo échoue au tout premier lancement | l'amorçage tourne en tâche de fond (~10 s) :
`GET /health` renvoie `"demo_ready": false` tant qu'il n'est pas fini, et l'interface attend ce
drapeau avant de se connecter. Attendez le message « Jeu de démonstration prêt » dans la console |
| Mot de passe refusé à l'inscription | 8 caractères minimum, une majuscule, un chiffre, un caractère spécial |
| Écran vide / 404 sur `/` | `SERVE_WEB=true` et le dossier `web/` doivent être présents à côté de `backend/` |

---

## Licence et avertissement

Code de démonstration à visée de recherche et de prototypage clinique.
Aucune donnée de patient réelle ne doit être utilisée sans base légale
(consentement, hébergement HDS/agrément local) et validation par un comité
d'éthique. Les sorties du modèle ne constituent pas un diagnostic.
