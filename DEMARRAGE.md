# Démarrage local — ce que tu fais, ce que l'agent VS Code fait

> Réponses courtes en haut, checklist ensuite.
> Le prompt complet à coller dans l'agent IA est dans **`PROMPT-AGENT-VSCODE.md`**.

---

## 1. « Est-ce que je peux lancer l'app dans un émulateur depuis VS Code ? »

**Pas besoin d'émulateur : l'application est déjà une application web complète, servie par son
propre backend.** Un émulateur (BlueStacks, Android Studio, etc.) n'apporte rien ici : l'app web
tourne dans Chrome, en plein écran, sur `http://localhost:8000`. C'est le chemin garanti — c'est
celui que j'ai testé de bout en bout (25 tests au vert + parcours complet au navigateur).

**Deux cas où un émulateur a un sens :**

| Cas | Réalité |
|---|---|
| Tu veux l'app dans une fenêtre « type mobile » | Inutile : ouvre `http://localhost:8000` dans Chrome puis `F12` → mode responsive `Ctrl+Shift+M` (390 × 844). L'interface est déjà responsive. |
| Tu veux tester le **client Flutter natif** (`app_flutter/`) sur Android | Possible, mais **c'est un second chemin, non vérifié** : il exige le SDK Flutter + Android Studio + la génération du dossier `android/` (absent du dépôt). Le prompt contient l'étape 7 pour ça. Je ne le recommande pas en premier. |

Autrement dit : **commence par le web (5 minutes, tout fonctionne), l'émulateur seulement si tu y tiens.**

## 2. « Est-ce que je peux télécharger le dossier maintenant ? »

**Oui.** L'archive `diafoot-sentinel.zip` est prête (code source complet, ~1 Mo, sans données de
santé). Ce qu'elle contient / ne contient pas :

| Inclus | Volontairement exclu |
|---|---|
| `backend/` (API, moteur IA, tests, scripts) | `backend/diafoot.db` (base locale) |
| `web/` (interface complète) | `backend/storage/` (photos chiffrées + PDF générés) |
| `app_flutter/` (client natif optionnel) | `backend/.diafoot_secret` (clé de chiffrement) |
| `docs/`, `.vscode/`, `README.md`, `.env.example` | `.venv/`, caches, `__pycache__` |

Exclure la base, les photos et la clé est **volontaire** : au premier lancement, tout est recréé
(base SQLite, clé propre, jeu de démonstration complet). Tu obtiens une installation neuve, sans
résidu de mes essais.

---

## 3. Ce que **tu** dois faire (5 minutes, une seule fois)

1. **Python 3.12** (ou 3.11) installé — [python.org](https://www.python.org/downloads/).
   Sur Windows, coche **« Add python.exe to PATH »** pendant l'installation.
2. **VS Code** + extension **Python** (Microsoft). Optionnel : **Pylance**, **Dart/Flutter**
   (seulement si tu explores `app_flutter/`).
3. **Dézippe** l'archive où tu veux (`~/dev/diafoot-sentinel`, **pas** dans OneDrive/iCloud :
   SQLite y pose des problèmes de verrou).
4. Dans VS Code : **Fichier → Ouvrir le dossier** → sélectionne le dossier **`diafoot-sentinel`**
   lui-même (celui qui contient `backend/`, `web/`, `README.md`), pas le dossier parent.
5. `Ctrl+Shift+B` → tâche **« 1 · Installer les dépendances Python »**, puis
   **« 2 · Lancer l'application (port 8000) »**. (Ou, en terminal :
   `python -m venv .venv` puis `.venv\Scripts\python.exe -m pip install -r backend\requirements.txt`.)
6. Ouvre **http://localhost:8000** → clique **« Entrer dans la démo »**.

Tu n'as **rien** d'autre à installer : ni Node/npm, ni Docker, ni PostgreSQL, ni clé d'API, ni GPU,
ni poids de modèle. Torch est explicitement optionnel.

## 4. Ce que tu dois **fournir à l'agent VS Code**

Colle ce bloc *avant* le prompt, en adaptant les valeurs :

```
OS : Windows 11 / macOS 15 / Ubuntu 24.04
Python : 3.12.x        (sortie de `python --version`)
Dossier projet : C:\Users\moi\dev\diafoot-sentinel
Port 8000 : libre
Flutter/Android Studio : non installé     (mets `oui` seulement si tu veux l'étape 7)
Objectif : lancer l'app web et me rendre le rapport de l'étape 8
Ne touche pas : web/, les comptes de démo, backend/.diafoot_secret
```

Puis colle **`PROMPT-AGENT-VSCODE.md`** en entier. C'est tout : le prompt contient les commandes
exactes, les sorties attendues, la matrice de dépannage et le rapport final à te rendre.

## 5. Ce que tu n'as pas à fournir

- Aucune **clé d'API** (OpenAI, Anthropic…) : l'assistant fonctionne en RAG local hors-ligne.
  La variable `LLM_PROVIDER` reste vide → l'interface affiche honnêtement « RAG local ».
- Aucun **fichier de poids** `.pth` : `backend/weights/` est vide et le moteur colorimétrique
  calibré prend le relais (`engine: segmenter-hsv+risk-calibrated`).
- Aucune **base de données** ni **jeu de données** : le seed de démonstration est déterministe.

---

## 6. Critères de réussite (ce que l'agent doit te prouver)

| Preuve | Attendu |
|---|---|
| `pip install -r backend/requirements.txt` | `deps OK` |
| `GET /` et `GET /docs` | `200` / `200` |
| `GET /api/v1/analysis/engine/status` | `"engine":"segmenter-hsv+risk-calibrated"`, `"opencv":true` |
| `POST /api/v1/auth/login` (`amine@diafoot.tn`) | `200` + `access_token` |
| `pytest app/tests -q` | `25 passed` |
| Navigateur | « Bonjour Amine », 6,68 cm², −78,1 % |
| Analyse IA | surface cm² + risque + 4 couches d'explicabilité |
| PDF | ~270 Ko, 2 pages A4 |
| Assistant | « odeur fétide + fièvre » → carte urgence **190** |
| Centres | 10 établissements du Grand Tunis + distances |

## 7. Si ça bloque

| Symptôme | Cause | Solution |
|---|---|---|
| `No module named 'app'` | uvicorn lancé depuis `backend/` | relancer depuis la racine avec `--app-dir backend` |
| `Address already in use` | port 8000 occupé | `--port 8001` puis ouvrir `http://localhost:8001` |
| Page blanche | cache navigateur | `Ctrl+Shift+R` |
| `database is locked` | ne doit plus arriver (WAL + `busy_timeout` 30 s + commits incrémentaux) | sinon : deux serveurs sur la même base → `lsof -ti:8000 \| xargs kill` |
| Le premier clic « démo » attend quelques secondes | amorçage en tâche de fond (~10 s) | c'est normal : l'interface attend `GET /health` → `demo_ready: true` |
| `greenlet` manquant | SQLAlchemy async | `pip install "greenlet>=3.0"` |
| Erreur de build `opencv` sous Windows | Python 3.13 sans roue | installer Python 3.12 |

Le détail complet (11 contrôles, matrice de 11 pannes, chemin Flutter) est dans
**`PROMPT-AGENT-VSCODE.md`**.
