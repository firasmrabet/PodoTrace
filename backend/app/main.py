"""DiaFoot Sentinel — point d'entrée FastAPI.

Configuration CORS dynamique (Flutter Web en développement sur n'importe quel
port) et en-têtes de sécurité compatibles avec la caméra et la géolocalisation
navigateur (cf. `Permissions-Policy`).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import analysis, auth, chat, geo, reports, wounds
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    from app.inference.pipeline import get_analyzer

    status = get_analyzer().status()
    print(f"[DiaFoot] Moteur d'inférence : {status['engine']} "
          f"(torch={status['torch']}, opencv={status['opencv']})")

    # Jeu de démonstration : exécuté en tâche de fond pour ne jamais retarder
    # l'ouverture de l'interface web.
    seed_task = None
    if settings.AUTO_SEED_DEMO and settings.ENV != "test":
        async def _seed() -> None:
            try:
                from app.services.demo_seed import seed_demo_if_empty

                created = await seed_demo_if_empty()
                if created:
                    print("[DiaFoot] Comptes de démonstration : "
                          "amine@diafoot.tn / dr.mansouri@diafoot.tn (mot de passe diafoot2026)")
            except Exception as exc:  # noqa: BLE001 — le service doit démarrer quoi qu'il arrive
                print(f"[DiaFoot] Amorçage ignoré : {exc}")

        seed_task = asyncio.create_task(_seed())

    yield

    if seed_task and not seed_task.done():
        seed_task.cancel()


app = FastAPI(
    title="DiaFoot Sentinel API",
    description=(
        "API de télésurveillance et d'évaluation des ulcères du pied diabétique. "
        "Segmentation multi-tissus, risques infectieux/ischémiques, Grad-CAM, "
        "suivi temporel, assistant IA RAG (IWGDF) et rapports PDF.\n\n"
        "**Outil d'aide en phase de validation clinique — ne remplace pas un avis médical.**"
    ),
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS — accepte tout port localhost/127.0.0.1 (Flutter Web) + origines déclarées
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_origins=settings.CORS_EXTRA_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Processing-Time"],
    max_age=3600,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Processing-Time"] = f"{elapsed_ms:.1f}ms"
    response.headers["X-Content-Type-Options"] = "nosniff"
    # En développement, l'interface (HTML/CSS/ES-modules) ne doit jamais être
    # servie depuis le cache : chaque rechargement reflète le code courant.
    path = request.url.path
    if not settings.is_production and not path.startswith(settings.API_V1_PREFIX):
        if path.endswith((".html", ".js", ".css", ".webmanifest")) or path == "/":
            response.headers["Cache-Control"] = "no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    # L'interface est destinée à être ouverte dans un onglet local, mais aussi
    # dans un cadre d'aperçu (proxy de développement). En production, le cadrage
    # reste verrouillé sur l'origine applicative.
    if settings.is_production:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'self'; "
            "img-src 'self' data: blob: https: http:; "
            "media-src 'self' blob:;"
        )
    else:
        # Mode démonstration : l'interface peut être affichée dans le cadre
        # d'aperçu d'un environnement de développement (origine quelconque).
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'self' * http: https: file: data:; "
            "img-src 'self' data: blob: https: http:; "
            "media-src 'self' blob:;"
        )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # ⚠️ La caméra ET la géolocalisation sont nécessaires au parcours Web :
    # une politique restrictive casserait getUserMedia / getCurrentPosition.
    response.headers["Permissions-Policy"] = (
        "camera=*, geolocation=*, microphone=(), payment=(), usb=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne. L'incident a été journalisé."},
    )


# ---------------------------------------------------------------------------
# Routage
# ---------------------------------------------------------------------------
API = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=API)
app.include_router(wounds.router, prefix=API)
app.include_router(wounds.practitioner_router, prefix=API)
app.include_router(analysis.router, prefix=API)
app.include_router(chat.router, prefix=API)
app.include_router(geo.router, prefix=API)
app.include_router(reports.router, prefix=API)


@app.get("/api-info", tags=["Santé"])
async def api_info():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs": "/docs",
        "disclaimer": "Aide à la décision médicale — ne remplace pas un avis médical.",
    }


@app.get("/config", tags=["Santé"])
async def public_config():
    """Configuration publique consommée par l'interface web."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api": settings.API_V1_PREFIX,
        "google_client_id": settings.GOOGLE_CLIENT_ID or None,
        "expose_otp": settings.EXPOSE_OTP_IN_RESPONSE,
        "auto_seed": settings.AUTO_SEED_DEMO,
        "demo_accounts": settings.AUTO_SEED_DEMO,
    }


@app.get("/health", tags=["Santé"])
async def health():
    from app.inference.pipeline import get_analyzer
    from app.services.demo_seed import demo_ready

    return {
        "status": "ok",
        # `demo_ready` = comptes et mesures de démonstration disponibles.
        # L'interface peut l'attendre avant de proposer le bouton de connexion.
        "demo_ready": demo_ready(),
        "config": settings.describe(),
        "inference": get_analyzer().status(),
    }


# ---------------------------------------------------------------------------
# Interface web (SPA) — servie par le backend : une seule commande suffit.
# Le montage est déclaré en dernier pour laisser la priorité à /api, /docs, /health.
# ---------------------------------------------------------------------------
if settings.SERVE_WEB and (settings.WEB_DIR / "index.html").exists():
    app.mount(
        "/",
        StaticFiles(directory=str(settings.WEB_DIR), html=True),
        name="web",
    )
    print(f"[DiaFoot] Interface web servie depuis {settings.WEB_DIR}")
