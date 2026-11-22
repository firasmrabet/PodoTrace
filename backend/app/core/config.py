"""Configuration centrale de PodoTrace.

Toutes les valeurs sensibles proviennent de l'environnement (12-factor).
Le module expose un `settings` unique et immuable consommé par l'application.
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # -> backend/

load_dotenv(BASE_DIR / ".env", override=False)


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _persisted_secret(filename: str = ".podotrace_secret") -> str:
    """Clé de signature persistée localement.

    En développement (aucune variable d'environnement fournie), la clé est
    écrite une seule fois sur disque : les jetons JWT et les images chiffrées
    restent lisibles après un redémarrage du serveur. En production, `SECRET_KEY`
    doit être fourni par l'environnement (12-factor).
    """
    import secrets as _secrets

    path = BASE_DIR / filename
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    try:
        if path.exists():
            value = path.read_text().strip()
            if value:
                return value
        value = _secrets.token_urlsafe(64)
        path.write_text(value)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return value
    except OSError:
        return _secrets.token_urlsafe(64)


class Settings:
    """Paramètres applicatifs (lecture unique au démarrage)."""

    # --- Identité -----------------------------------------------------------
    PROJECT_NAME: str = "PodoTrace"
    VERSION: str = "1.0.0"
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = _bool("DEBUG", True)

    # --- Réseau -------------------------------------------------------------
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = _int("PORT", 8000)
    API_V1_PREFIX: str = "/api/v1"

    # --- Sécurité -----------------------------------------------------------
    SECRET_KEY: str = _persisted_secret()
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)
    OTP_LENGTH: int = 6
    OTP_TTL_MINUTES: int = _int("OTP_TTL_MINUTES", 15)

    # Clé Fernet (chiffrement au repos des images médicales).
    # Générée automatiquement en développement : à fournir en production (HDS).
    FERNET_KEY: str = os.getenv("FERNET_KEY", "")

    # --- Base de données ----------------------------------------------------
    DATABASE_URL: str = (
        os.getenv("DATABASE_URL", "").strip()
        or f"sqlite+aiosqlite:///{BASE_DIR / 'podotrace.db'}"
    )

    # --- Stockage -----------------------------------------------------------
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", "").strip() or (BASE_DIR / "storage"))
    MAX_UPLOAD_MB: int = _int("MAX_UPLOAD_MB", 15)

    # --- CORS ---------------------------------------------------------------
    # Regex dynamique : accepte tout port localhost / 127.0.0.1 (Flutter Web dev)
    CORS_ORIGIN_REGEX: str = os.getenv(
        "CORS_ORIGIN_REGEX",
        r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    )
    CORS_EXTRA_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv("CORS_EXTRA_ORIGINS", "").split(",")
        if o.strip()
    ]

    # --- Email / OTP --------------------------------------------------------
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = _int("SMTP_PORT", 587)
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "no-reply@podotrace.health")
    # En dev : l'OTP est renvoyé dans la réponse API pour permettre les tests E2E.
    EXPOSE_OTP_IN_RESPONSE: bool = _bool("EXPOSE_OTP_IN_RESPONSE", True)

    # --- Interface web & jeu de démonstration -------------------------------
    SERVE_WEB: bool = _bool("SERVE_WEB", True)
    # Jamais en environnement de test : la base doit rester déterministe.
    AUTO_SEED_DEMO: bool = _bool("AUTO_SEED_DEMO", os.getenv("ENV", "development") != "test")
    WEB_DIR: Path = BASE_DIR.parent / "web"

    # --- OAuth Google -------------------------------------------------------
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # --- IA / Inférence -----------------------------------------------------
    WEIGHTS_DIR: Path = Path(os.getenv("WEIGHTS_DIR", BASE_DIR / "weights"))
    SEG_CHECKPOINT: str = os.getenv("SEG_CHECKPOINT", "fusegnet_effb7_best_model_1.pth")
    RISK_CHECKPOINT: str = os.getenv("RISK_CHECKPOINT", "wound_risk_effb3.pth")
    MC_DROPOUT_PASSES: int = _int("MC_DROPOUT_PASSES", 4)
    UNCERTAINTY_THRESHOLD: float = 0.12  # variance normalisée -> avis médical
    # Fallback clinique calibré lorsque les poids .pth sont absents (dev / CI).
    ALLOW_SIMULATION_FALLBACK: bool = _bool("ALLOW_SIMULATION_FALLBACK", True)

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in {"prod", "production"}

    def describe(self) -> dict[str, Any]:
        return {
            "env": self.ENV,
            "version": self.VERSION,
            "database": self.DATABASE_URL.split("://")[0],
            "storage": str(self.STORAGE_DIR),
            "simulation_fallback": self.ALLOW_SIMULATION_FALLBACK,
        }


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    (s.STORAGE_DIR / "images").mkdir(parents=True, exist_ok=True)
    (s.STORAGE_DIR / "reports").mkdir(parents=True, exist_ok=True)
    s.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
