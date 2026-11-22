# Prompt à coller dans l'agent IA de VS Code

Copie **tout le bloc ci-dessous** (du titre « MISSION » jusqu'à « FIN DU PROMPT ») et colle-le dans
GitHub Copilot Chat (mode Agent), Cursor, Windsurf ou Claude Code, avec le dossier `diafoot-sentinel`
ouvert comme racine du workspace. Ne modifie rien : le prompt est déjà calibré sur le code livré.

---

## MISSION

Tu es l'agent technique chargé de faire tourner **DiaFoot Sentinel** (FastAPI + SQLite + interface
web vanilla) sur ma machine, en local, jusqu'à ce que **toutes** les fonctionnalités répondent
réellement. Tu exécutes les commandes toi-même, tu vérifies chaque étape par une preuve (sortie de
commande, code HTTP, JSON), et tu ne me déclares « terminé » que si les 11 tests d'acceptation de
l'étape 5 passent.

## CONTEXTE VÉRIFIÉ DU PROJET (ne le remets pas en cause, vérifie-le)

- Le dépôt à la racine contient : `backend/` (API FastAPI), `web/` (client, servi par l'API),
  `app_flutter/` (client natif optionnel), `docs/`, `.vscode/`, `README.md`, `.env.example`.
- **Un seul processus suffit** : `uvicorn` sert l'API sur `/api/v1/*`, la documentation sur `/docs`,
  et le client web sur `/`. Il n'y a **ni Node, ni npm, ni bundler, ni Docker, ni PostgreSQL** à installer.
- Base de données : **SQLite** créée automatiquement au premier démarrage (`backend/diafoot.db`).
- Le **jeu de démonstration** (3 comptes, 3 plaies, 9 analyses, rapports, 10 centres du Grand Tunis)
  est créé automatiquement si `AUTO_SEED_DEMO=true` (valeur par défaut).
- Le **moteur d'IA est réel mais sans PyTorch** : segmentation colorimétrique calibrée
  (`segmenter-hsv+risk-calibrated`) + Grad-CAM de saillance. Les poids `.pth` sont **optionnels** :
  `backend/weights/` est vide et l'application fonctionne quand même. **N'installe pas torch.**
- Les photos sont **chiffrées au repos** avec une clé générée une seule fois dans
  `backend/.diafoot_secret` (créé au premier lancement, permissions 600).
- Le client Flutter (`app_flutter/`) est **optionnel** et ne concerne que l'émulateur Android
  (étape 7). L'application web ne nécessite **aucun émulateur**.

## RÈGLES NON NÉGOCIABLES

1. **Ne réécris pas l'architecture.** Pas de Docker, pas de Node, pas de PostgreSQL, pas de torch,
   pas de migration vers un autre framework, pas de `npm install`.
2. **N'ajoute aucune dépendance Python** hors de `backend/requirements.txt` (déjà complet et testé).
3. **Ne supprime jamais** `backend/.diafoot_secret` sans prévenir : cela rendrait illisibles les
   photos déjà chiffrées.
4. Ne modifie pas les fichiers de `web/` ni les valeurs de démonstration (comptes, mesures) :
   ce sont des résultats vérifiés. Si un correctif est indispensable, dis-le-moi avant de l'appliquer.
5. Si une commande échoue **deux fois** de la même façon, arrête-toi et présente-moi la matrice de
   l'étape 6 au lieu d'improviser.
6. À la fin, rends-moi le **rapport final** de l'étape 8 (tableau, pas de prose).

## ÉTAPE 0 — Diagnostic (lecture seule, aucune installation)

```bash
python3 --version || python --version      # attendu : 3.11 ou 3.12 (3.13 accepté)
python3 -c "import sys; print(sys.executable)"
ls -la                                     # attendu : backend/ web/ app_flutter/ docs/ README.md
ls backend/requirements.txt .env.example .vscode/tasks.json
```

Sur Windows, remplace `python3` par `python` et `ls` par `dir`. Note la version exacte de Python :
les roues binaires d'`opencv-python-headless` et `cryptography` exigent Python ≤ 3.13.

Vérifie qu'aucun serveur ne squatte déjà le port 8000 :

```bash
# macOS / Linux
lsof -i :8000 || echo "port 8000 libre"
# Windows PowerShell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

## ÉTAPE 1 — Environnement Python isolé

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r backend/requirements.txt

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Preuve attendue : la commande se termine sans erreur et

```bash
.venv/bin/python -c "import fastapi, uvicorn, sqlalchemy, cv2, numpy, reportlab, jose, passlib; print('deps OK')"
```

affiche `deps OK`. `cv2.__version__` doit être ≥ 4.10 (5.x accepté).

Points de vigilance connus :
- `ImportError: the greenlet library is required` → `SQLAlchemy[asyncio]` a été installé sans
  greenlet : relance simplement `pip install "greenlet>=3.0"`.
- `error: Microsoft Visual C++ 14.0 required` sur Windows → utilise Python 3.12 (roues
  précompilées disponibles) plutôt que 3.13.

## ÉTAPE 2 — Configuration locale (facultative, recommandée)

```bash
cp backend/.env.example backend/.env      # Windows : copy backend\.env.example backend\.env
```

Ne remplis **rien** : les valeurs par défaut en `ENV=development` suffisent (SQLite, stockage local,
OTP affiché à l'écran, seed de démonstration). Aucune clé d'API n'est nécessaire — l'assistant
fonctionne en RAG local hors-ligne.

## ÉTAPE 3 — Lancement

Depuis la **racine** du dépôt :

```bash
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend
```

Windows : `.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend`

Laisse ce processus tourner (terminal dédié, ou `Ctrl+Shift+B` → tâche
**« 2 · Lancer l'application (port 8000) »**, ou `F5` → **« DiaFoot Sentinel — API + Web »**).
Ne lance **pas** `uvicorn` depuis `backend/` : `--app-dir backend` évite les erreurs d'import.

Preuve attendue dans les logs :

```
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

## ÉTAPE 4 — Vérifications automatiques (API, sans navigateur)

Exécute ces commandes dans un **second** terminal et compare aux sorties attendues.

```bash
# 1. L'interface est bien servie (doit renvoyer 200 et du HTML)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/

# 2. Documentation interactive → 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs

# 3. Moteur d'IA : doit annoncer le moteur colorimétrique, torch=false (c'est normal)
curl -s http://127.0.0.1:8000/api/v1/analysis/engine/status

# 3 bis. Sonde de disponibilité : "demo_ready" doit être true (attendre ~15 s au 1er lancement)
curl -s http://127.0.0.1:8000/health | head -c 120

# 4. Connexion de démonstration → 200 + access_token
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"amine@diafoot.tn","password":"diafoot2026"}' | head -c 120

# 5. Tests unitaires (depuis backend/)
cd backend && ../.venv/bin/python -m pytest app/tests -q ; cd ..
```

Attendus :
- `1.` → `200` ; `2.` → `200` ;
- `3.` → `{"torch":false,"opencv":true,...,"engine":"segmenter-hsv+risk-calibrated"}` ;
- `4.` → `{"access_token":"..."` ;
- `5.` → `25 passed`.

Si un test échoue : `cd backend && ../.venv/bin/python -m pytest app/tests -q -x -vv` et corrige
**uniquement** la cause (jamais en désactivant le test).

## ÉTAPE 5 — Tests d'acceptation fonctionnels (11 points)

Ouvre `http://localhost:8000` dans Chrome (ou `F5` → « Navigateur — Chrome sur localhost:8000 »),
puis exécute dans l'ordre. Chaque point doit produire le résultat indiqué ; sinon applique l'étape 6.

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Clic **« Entrer dans la démo »** | Arrivée sur **« Bonjour Amine »**, aucun message d'erreur |
| 2 | Écran d'accueil | 2 plaies suivies, surface **6,68 cm²**, tendance **−78,1 %**, statut « en amélioration » |
| 3 | Onglet **Trajectoire** | Courbe de **30,5 → 6,5 cm²** sur 35 semaines, PUSH 7/17, 6 mesures |
| 4 | **Nouvelle analyse** → bouton **✦** (image de test) → **Analyser** | Surface en cm², périmètre, 4 classes de tissus, risque infectieux chiffré |
| 5 | Vue résultat, onglets de couches | **Photo / Tissus / Contour / Grad-CAM** affichent 4 images différentes |
| 6 | Bandeau de calibration | **≈ 39,7 px/cm** (repère vert du patch) |
| 7 | Bouton **PDF** | Un PDF de ~2 pages A4 se télécharge (≈ 270 Ko) et s'ouvre |
| 8 | **Assistant** : « Ma plaie a une odeur fétide et j'ai de la fièvre » | Réponse + **carte d'urgence rouge** citant le **190** (Tunisie) / 15 (France) |
| 9 | **Centres de soin** (autoriser la géolocalisation) | 10 centres du Grand Tunis avec distances (Charles-Nicolle ≈ 1,0 km) |
| 10 | Déconnexion → **Praticien** | Écran **« Mes patients »** : 1 critique, 9 analyses à valider |
| 11 | **Profil & données** | Terrain clinique, état du moteur d'inférence, mentions RGPD/SaMD |

Rapporte chaque point par ✅ ou ❌ avec le message d'erreur exact de la console du navigateur
(`F12` → Console) le cas échéant.

## ÉTAPE 6 — Matrice de dépannage (applique la ligne, ne réinstalle pas tout)

| Symptôme | Cause | Correction |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | uvicorn lancé depuis `backend/` sans `--app-dir` | relance avec `--app-dir backend` depuis la racine |
| `Address already in use` | port 8000 occupé | tue l'ancien processus (`lsof -ti:8000 \| xargs kill`) ou utilise `--port 8001` |
| Page blanche / ancienne version | cache navigateur | `Ctrl+Shift+R` ; le serveur envoie déjà `Cache-Control: no-store` en dev |
| « value is not a valid email address » | formulaire soumis vide | clique **« Entrer dans la démo »** : aucune saisie n'est requise |
| `POST /auth/login` → 422 | champ vide ou JSON mal formé | utilise le `curl` de l'étape 4 (guillemets simples) |
| Images de plaie grises / 401 | jeton absent | reconnecte-toi ; les images passent par `?token=` |
| `greenlet` manquant | SQLAlchemy async | `pip install "greenlet>=3.0"` |
| `psycopg` / `asyncpg` réclamé | `DATABASE_URL` défini dans `.env` | laisse `DATABASE_URL=` vide |
| Assistant muet | aucune question envoyée | `POST /api/v1/chat` répond `{reply, sources, red_flag, provider}` |
| `unable to open database file` | dossier en lecture seule / OneDrive synchronisé | déplace le dossier hors de OneDrive ou dans `~/dev` |
| Tests en échec avec `database is locked` | serveur encore actif sur la même base | arrête le serveur, relance les tests, puis relance le serveur |
| La connexion de démo échoue au 1er lancement | amorçage en tâche de fond (~10 s, `demo_ready=false`) | attends `"demo_ready":true` sur `GET /health`, puis réessaie ; le dépôt est en WAL + `busy_timeout` 30 s |

Réamorcer les données de démonstration (sans toucher au code) :

```bash
cd backend && ../.venv/bin/python scripts/reset_demo.py        # réamorce
cd backend && ../.venv/bin/python scripts/reset_demo.py --seed-only
# réinitialisation totale : supprimer backend/diafoot.db + backend/storage/{images,reports}
```

## ÉTAPE 7 — OPTIONNEL : émulateur Android avec le client Flutter

**Uniquement si je te le demande explicitement.** L'application web de l'étape 3 est complète ;
cette étape sert à voir la même API dans une app native. Prérequis que je fournis :
Flutter SDK ≥ 3.19 (`flutter --version`), Android Studio + un AVD démarré (`flutter emulators`),
`flutter doctor` sans erreur bloquante.

```bash
cd app_flutter
flutter create --platforms=android --org tn.diafoot .   # génère android/ (absent du dépôt)
flutter pub get
flutter run -d emulator-5554 --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` = `localhost` de ma machine vu depuis l'émulateur (déjà codé dans
`lib/core/config/app_config.dart`). Deux réglages **obligatoires** côté Android, sinon l'appli
affiche « réseau indisponible » :

1. `android/app/src/main/AndroidManifest.xml` : `<uses-permission android:name="android.permission.INTERNET"/>`
   et, dans la balise `<application>`, `android:usesCleartextTraffic="true"` (HTTP en clair, dev uniquement).
2. Autorisations runtime caméra et localisation (`camera`, `image_picker`, `geolocator` les déclarent
   déjà dans leurs manifestes fusionnés ; ajoute `CAMERA` et `ACCESS_FINE_LOCATION` explicitement).

Si `flutter pub get` échoue sur un paquet natif, ne « downgrade » pas tout : traite le paquet fautif
et rapporte-moi la version demandée. Cette partie n'a pas pu être compilée dans mon environnement
(pas de SDK Flutter) : considère-la comme **non vérifiée** et signale-moi tout écart.

## ÉTAPE 8 — Rapport final à me rendre

Termine par ce tableau, rempli, sans commentaire additionnel :

```
| # | Contrôle | Commande / action | Attendu | Obtenu | État |
|---|----------|-------------------|---------|--------|------|
| 1 | Python + deps | pip install -r backend/requirements.txt | deps OK | ... | ✅/❌ |
| 2 | Serveur | GET / | 200 | ... | ... |
| 3 | Docs | GET /docs | 200 | ... | ... |
| 4 | Moteur | GET /api/v1/analysis/engine/status | segmenter-hsv+risk-calibrated | ... | ... |
| 4b | Santé | GET /health | `demo_ready: true` | ... | ... |
| 5 | Auth | POST /auth/login (amine@diafoot.tn) | 200 + token | ... | ... |
| 6 | Tests | pytest app/tests -q | 25 passed | ... | ... |
| 7 | UI démo | clic « Entrer dans la démo » | « Bonjour Amine » | ... | ... |
| 8 | Analyse IA | image de test → Analyser | surface cm² + risque | ... | ... |
| 9 | PDF | bouton PDF | ~270 Ko, 2 pages | ... | ... |
| 10 | Assistant | message « odeur fétide + fièvre » | carte urgence 190 | ... | ... |
| 11 | Centres | #/centres | 10 centres + distances | ... | ... |
| 12 | Flutter (option) | flutter run -d emulator | app affichée | ... | ... |
```

Ajoute ensuite, en trois lignes maximum : l'URL locale à ouvrir, le chemin exact du `.venv`, et la
liste des écarts éventuels restant à ma charge.

FIN DU PROMPT
