# Architecture — DiaFoot Sentinel

> Outil d'aide en phase de validation clinique pour les ulcères du pied diabétique.
> Ce document décrit **ce qui est réellement implémenté** dans le dépôt.

---

## 1. Vue d'ensemble

```
┌───────────────────────────────────────────────────────────────────────┐
│  Navigateur (patient / praticien / proche)                            │
│  web/  — SPA ES-modules sans build, servie par le backend             │
│  index.html · css/app.css · js/app.js · js/core.js · js/views/*.js    │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ fetch + JWT (Authorization: Bearer)
┌───────────────────────────────▼───────────────────────────────────────┐
│  FastAPI (backend/app)                                                │
│  api/v1/routes : auth · wounds · analysis · chat · geo · reports      │
│  deps.py : get_current_user · get_user_from_header_or_query · gardes  │
├───────────────┬──────────────────┬────────────────────┬───────────────┤
│ services      │ inference        │ core               │ db            │
│ llm · geo     │ pipeline/engine  │ config · security  │ session       │
│ pdf_report    │ risk · gradcam   │ storage (Fernet)   │ (async)       │
│ demo_seed     │ temporal         │                    │               │
└───────────────┴──────────────────┴──────────┬─────────┴───────────────┘
                                              │
                        SQLite diafoot.db  +  storage/images (chiffré)
```

Un **seul processus** sert l'API et l'interface : `uvicorn app.main:app`.
`web/` est monté sur `/` (`SERVE_WEB=true`), `GET /api-info` décrit l'API pour
éviter que la SPA soit masquée par une route racine JSON.

L'application Flutter (`app_flutter/`) est un client **secondaire** : même API,
même palette, mais elle nécessite le SDK Flutter et ne fait pas partie du
chemin d'exécution web.

---

## 2. Arborescence

```
diafoot-sentinel/
├── README.md                  démarrage en 3 commandes
├── .env.example               toutes les variables, toutes optionnelles
├── .vscode/                   launch, tasks, settings, extensions
├── docs/
│   ├── ARCHITECTURE.md        ce document
│   └── DESIGN_SYSTEM.md       système « Sérénité »
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py            app FastAPI, CORS, SPA, lifespan
│   │   ├── api/deps.py        authentification + autorisation par ligne
│   │   ├── api/v1/routes/     auth, wounds, analysis, chat, geo, reports
│   │   ├── core/              config, security (JWT/OTP), storage (Fernet)
│   │   ├── db/session.py      moteur async, `init_db()` (create_all)
│   │   ├── models/            entities.py (User, Wound, Analysis…), wound_models.py
│   │   ├── schemas/           contrats Pydantic
│   │   ├── inference/         engine, pipeline, risk, gradcam, temporal, calibration
│   │   ├── services/          llm, geo, pdf_report, demo_seed, demo_images, mailer
│   │   └── tests/             pytest (25 tests, base isolée)
│   ├── scripts/reset_demo.py  réamorçage du jeu de démonstration
│   └── storage/               images/ + reports/ (chiffrés, créés au 1er boot)
├── web/                       interface active (aucun build, aucun CDN)
│   ├── index.html
│   ├── css/app.css
│   └── js/{app,core}.js + js/views/{auth,home,capture,result,history,chat,map,patients,settings}.js
└── app_flutter/               client Flutter (mobile/web), thème aligné
    └── lib/{core/theme, features/*, services/*}
```

---

## 3. Modèle de données

Créé par `Base.metadata.create_all` au démarrage — **aucune migration**
(assumé : le schéma est stable, `scripts/reset_demo.py` repart de zéro).

| Table | Rôle | Champs saillants |
|---|---|---|
| `users` | patient / praticien / proche | `role`, `otp_code`, `otp_expires_at`, `is_verified`, `diabetes_type`, `specialty` |
| `wounds` | plaie suivie | `patient_id`, `location`, `wagner_grade`, `side`, `is_active` |
| `analyses` | mesure à un instant t | `area_cm2`, `perimeter_cm`, `tissue_composition` (JSON), `risk` (JSON), `explainability` (JSON, dont `variants`), `engine`, `reviewed_by` |
| `chat_messages` | conversation assistant | `role`, `content`, `sources` (JSON), `red_flag` |
| `otp_*` | codes à usage unique | — |

`analyses.explainability` porte **les clés de stockage** des couches dérivées :

```json
{ "variants": { "segmentation": "<clé>", "contour": "<clé>", "heatmap": "<clé>" },
  "gradcam": { ... }, "calibration": { ... } }
```

Pas de nouvelle colonne : la couche dérivée est un fichier, la base ne garde
qu'un pointeur.

---

## 4. Flux : analyse d'une photo

```
POST /api/v1/analysis/full-analysis  (multipart: wound_id, file, variant)
  1. contrôle de propriété de la plaie (patient ou praticien rattaché)
  2. qualité d'image (netteté, exposition, cadrage) → 422 explicite si refusée
  3. segmentation multi-tissus → masque, composition %, surface, périmètre
  4. calibration px/cm (repère vert du patch) → surface absolue en cm²
  5. risque infectieux + ischémique (score calibré, facteurs explicatifs)
  6. explicabilité : masque tissulaire, contour, Grad-CAM (ou carte de saillance)
  7. persistance : image source chiffrée + 3 couches dérivées chiffrées
  8. trajectoire : delta vs mesure précédente, statut, prochaine photo
```

Lecture des images : `GET /api/v1/analysis/{id}/image/{original|segmentation|contour|heatmap}`.

`GET /api/v1/analysis/sample-image?variant=0..2` renvoie une **photographie de
plaie synthétique calibrée** (peau texturée, halo d'érythème, berge
épithélialisée, gommette verte de 2 cm) produite par
`services/demo_images.py` : c'est le bouton « image de test » de l'écran de
capture, utilisable sans caméra et sans réseau.

> ⚠️ Une balise `<img>` ne peut pas envoyer d'en-tête `Authorization`. Cette
> route accepte donc le jeton **en query** (`?token=…`) via
> `get_user_from_header_or_query`, puis **revérifie l'appartenance ligne par
> ligne** (`_assert_access`). Aucun accès inter-utilisateurs n'est possible.

---

## 5. Moteur d'inférence

Deux chemins, choisis automatiquement au démarrage :

| Chemin | Condition | Identifiant renvoyé |
|---|---|---|
| Réseau profond U-Net++ / EfficientNet-B3 + MC-dropout | poids présents dans `backend/weights/` **et** torch installé | `unetpp-effb3+risk-effb3` |
| Moteur colorimétrique + morphologique calibré | sinon (cas par défaut, hors-ligne) | `segmenter-hsv+risk-calibrated` |

Le moteur par défaut **n'est pas un faux résultat** : il segmente réellement
(espace HSV + morphologie), quantifie (surface, périmètre, circularité,
inflammation péri-lésionnelle), classe les tissus et calcule un risque à partir
de facteurs mesurés (surface, nécrose, fibrine, rougeur péri-lésionnelle,
évolution). `GET /api/v1/analysis/engine/status` expose l'état réel du moteur.

Pour brancher les poids : déposer `wound_seg_unetpp_effb3.pth` et
`wound_risk_effb3.pth` dans `backend/weights/` et `pip install torch timm`.
Aucun autre changement de code n'est nécessaire.

---

## 6. Chiffrement au repos

- Les images (source et couches) et les rapports PDF sont chiffrés **Fernet**
  avant écriture dans `backend/storage/`.
- La clé dérive de `SECRET_KEY`. En développement, `SECRET_KEY` est généré une
  fois et persisté dans `backend/.diafoot_secret` (0600) : les images restent
  lisibles après un redémarrage.
- Supprimer `.diafoot_secret` **invalide** toutes les images chiffrées et tous
  les jetons : c'est l'effet voulu en cas de fuite, pas une manœuvre de routine.
- Les couches dérivées lourdes sont recompressées avant chiffrement
  (`_recompress`, > 240 Ko → JPEG q82, max 760 px) : temps de chargement divisé
  par 8 sans perte clinique visible.

---

## 7. Assistant (LLM + RAG lexical)

`services/llm.py` enchaîne les fournisseurs dans l'ordre, jusqu'au premier qui
répond :

| Ordre | Fournisseur | Variable d'environnement | Modèle |
|---|---|---|---|
| 1 | Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| 2 | Mistral | `MISTRAL_API_KEY` | `mistral-large-latest` |
| 3 | OpenRouter | `OPENROUTER_API_KEY` | `meta-llama/llama-3.3-70b-instruct` |
| 4 | **Heuristique locale** | aucune | moteur de règles maison |

La **récupération** (`retrieve()`) est un RAG lexical sans dépendance : le corpus
IWGDF / Wagner / Texas est embarqué dans le module, scoré par mots-clés et
recouvrement lexical (top 3 passages), puis injecté dans le contexte avec
l'état réel de la plaie (surface, tissus, risque, tendance, 4 derniers échanges).
Aucune base vectorielle, aucun service externe requis.

Le **repli heuristique** (`provider = "heuristic"`) détecte d'abord les drapeaux
rouges — fièvre/frissons, extension rapide, douleur brutale ou perte de
sensibilité, purulence/odeur fétide, ischémie critique — et renvoie
`red_flag = true` avec le message d'urgence **190** (Tunisie) / 15 (France).
Il ne prescrit jamais de posologie et termine systématiquement par le rappel
« ne remplace pas un avis médical ».

Contrat de réponse : `{ reply, sources[], red_flag, emergency_message, provider }`.
L'interface affiche « RAG local » quand `provider == "heuristic"`, sinon
« LLM · <fournisseur> ».

## 8. Localisation tunisienne

`services/geo.py` interroge Overpass (OpenStreetMap) avec un **budget de 2,5 s**
par appel, une requête `[timeout:8]` et un cache mémoire de 10 min par
`(lat, lon arrondis à 3 décimales, rayon)`. Si Overpass est injoignable
(réseau coupé, environnement hors-ligne), le service renvoie un jeu **local
réel** de 10 structures du Grand Tunis, `source = "local-fallback"` :
Charles-Nicolle (0,97 km), Aziza Othmana (1,42 km), La Rabta (1,50 km),
INN Diabétologie (2,25 km)…

L'interface ne bloque **jamais** sur le réseau : les pins s'affichent
immédiatement avec la source indiquée. Le numéro d'urgence affiché est le 190.

---

## 9. Rapports PDF

`services/pdf_report.py` (ReportLab) compose un rapport A4 sur 2 pages :
identité de la plaie, photo source, segmentation, Grad-CAM, courbe de surface,
composition tissulaire, risques et facteurs, note du praticien, mentions
« aide à la décision ». Le PDF est généré à la demande
(`GET /api/v1/reports/wound/{id}/pdf`) puis chiffré sur disque.
Les caractères non-ASCII sont gérés côté serveur ; le nom de fichier transmis
reste ASCII (`Content-Disposition` sûr).

---

## 10. Sécurité & conformité

- Mots de passe : `passlib` (bcrypt/PBKDF2), politique de robustesse appliquée
  côté serveur **et** rappelée côté client.
- Inscription en deux temps : `POST /auth/register` → OTP à 6 chiffres
  (`EXPOSE_OTP_IN_RESPONSE=true` en dev seulement) → `POST /auth/verify-otp`.
- Jetons JWT signés HS256, expiration 7 jours, portés par `Authorization: Bearer`.
- Autorisations : patient = ses plaies ; praticien = plaies des patients
  rattachés ; proche = lecture seule des plaies partagées.
- Aucune donnée de santé n'est journalisée en clair ; aucune requête vers un
  service tiers n'est nécessaire au fonctionnement (hors LLM/Overpass optionnels).
- Mentions « outil d'aide en phase de validation clinique, ne remplace pas un avis médical »
  visibles dans l'interface, le rapport PDF et l'API (`/api-info`).

---

## 11. Tests

```bash
cd backend && ../.venv/bin/python -m pytest app/tests -q   # 25 passed
```

- Base isolée (`ENV=test` → `AUTO_SEED_DEMO=false`, pas d'amorçage concurrent).
- Couverture : inscription/OTP/connexion, CRUD plaies, analyse complète
  (surface, tissus, risque, variantes d'image), isolation entre utilisateurs,
  assistant (drapeau rouge + repli), géolocalisation.

---

## 12. Limites assumées

| Limite | Conséquence pour l'utilisateur |
|---|---|
| Pas de torch/timm dans l'environnement par défaut | moteur colorimétrique calibré au lieu du réseau profond (résultats réels, moins précis sur peaux très pigmentées) |
| Overpass souvent injoignable en sandbox | cache + jeu local Grand Tunis, affiché comme tel |
| Pas de comptes OAuth réels | bouton Google présent, désactivé proprement si `GOOGLE_CLIENT_ID` absent |
| SQLite mono-fichier | parfait en démonstration, `DATABASE_URL` PostgreSQL pour un usage multi-utilisateurs |
| Pas de migrations | schéma figé ; `scripts/reset_demo.py` repart de zéro |
