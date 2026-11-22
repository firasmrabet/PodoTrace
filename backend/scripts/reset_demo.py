"""Réamorçage du jeu de démonstration PodoTrace.

Usage (depuis `backend/`) :

    python scripts/reset_demo.py            # vide la base + le stockage, puis réamorce
    python scripts/reset_demo.py --seed-only  # complète les données démo sans effacer

Le script travaille sur la **vraie** base de l'application (`podotrace.db`) et le
vrai stockage chiffré : après exécution, connectez-vous simplement avec
`amine@podotrace.tn` ou `dr.mansouri@podotrace.tn` (mot de passe `podotrace2026`).
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


async def _reset() -> None:
    from app.core.config import settings
    from app.db.session import engine

    await engine.dispose()

    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        db_path = Path(url.split("///")[-1])
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(str(db_path) + suffix)
            if candidate.exists():
                candidate.unlink()
                print(f"  supprimé : {candidate.name}")
    else:
        print(f"  base non SQLite ({url.split('://')[0]}) — aucune suppression automatique")

    for sub in ("images", "reports"):
        target = Path(settings.STORAGE_DIR) / sub
        if target.exists():
            shutil.rmtree(target)
            print(f"  supprimé : {target}")


async def _seed() -> None:
    from app.db.session import init_db
    from app.services.demo_seed import seed_demo_if_empty

    await init_db()
    created = await seed_demo_if_empty()
    if created:
        print("\nJeu de démonstration créé :")
        print("  patient     amine@podotrace.tn      · podotrace2026")
        print("  praticien   dr.mansouri@podotrace.tn · podotrace2026")
        print("  proche      monia@podotrace.tn       · podotrace2026")
    else:
        print("Jeu de démonstration déjà complet — rien à ajouter.")


async def main(seed_only: bool) -> None:
    if not seed_only:
        print("Réinitialisation des données locales…")
        await _reset()
    await _seed()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Réamorce le jeu de démonstration.")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="n'efface rien, complète les comptes et données démo manquants",
    )
    args = parser.parse_args()
    asyncio.run(main(args.seed_only))
