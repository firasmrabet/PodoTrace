"""Primitives de sécurité : hachage, JWT, OTP, chiffrement Fernet."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings

# ---------------------------------------------------------------------------
# Mots de passe — PBKDF2-HMAC-SHA256 (stdlib, aucun binaire natif requis)
# ---------------------------------------------------------------------------
_PBKDF2_ROUNDS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(expected, computed)
    except Exception:
        return False


def password_strength(password: str) -> tuple[bool, list[str]]:
    """Politique de mot de passe fort (SaMD : compte soignant = accès données santé)."""
    issues: list[str] = []
    if len(password) < 10:
        issues.append("10 caractères minimum")
    if not any(c.isupper() for c in password):
        issues.append("une majuscule")
    if not any(c.islower() for c in password):
        issues.append("une minuscule")
    if not any(c.isdigit() for c in password):
        issues.append("un chiffre")
    if not any(c in "!@#$%^&*()-_=+[]{};:,.?/\\|~`\"'" for c in password):
        issues.append("un caractère spécial")
    return (not issues, issues)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "iss": "diafoot-sentinel",
        **(extra or {}),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
def generate_otp(length: int | None = None) -> str:
    length = length or settings.OTP_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(code: str) -> str:
    return hashlib.sha256(f"{code}:{settings.SECRET_KEY}".encode()).hexdigest()


def verify_otp(code: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_otp(code), hashed)


# ---------------------------------------------------------------------------
# Chiffrement au repos (AES-128/256 via Fernet, données de santé)
# ---------------------------------------------------------------------------
def _fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        # Clé dérivée déterministe pour le dev (jamais en production).
        key = base64.urlsafe_b64encode(
            hashlib.sha256(f"diafoot:{settings.SECRET_KEY}".encode()).digest()
        ).decode()
    return Fernet(key.encode())


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as exc:  # pragma: no cover - corruption / mauvaise clé
        raise ValueError("Contenu chiffré illisible") from exc


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


if __name__ == "__main__":  # pragma: no cover
    print("FERNET_KEY=" + generate_fernet_key())
    print("SECRET_KEY=" + secrets.token_urlsafe(64))
