"""Stockage chiffré au repos des images médicales.

Chaque image est écrite sur disque *chiffrée* (Fernet / AES) sous un nom opaque.
Aucun accès direct au fichier : la lecture passe obligatoirement par l'API qui
vérifie le JWT et la propriété de la ressource (cf. `analysis` routes).
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.security import decrypt_bytes, encrypt_bytes

IMAGES_DIR = settings.STORAGE_DIR / "images"
REPORTS_DIR = settings.STORAGE_DIR / "reports"


@dataclass(frozen=True)
class StoredImage:
    key: str  # identifiant opaque stocké en base
    size_bytes: int
    sha256: str


def _opaque_name(ext: str = ".enc") -> str:
    return f"{secrets.token_hex(20)}{ext}"


def save_image(data: bytes, owner_id: int) -> StoredImage:
    """Chiffre puis persiste les octets de l'image. Retourne la clé de stockage."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    key = f"u{owner_id}/{_opaque_name()}"
    path = IMAGES_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = encrypt_bytes(data)
    path.write_bytes(payload)
    return StoredImage(
        key=key, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
    )


def load_image(key: str) -> bytes:
    path = IMAGES_DIR / key
    if not path.exists():
        raise FileNotFoundError(key)
    return decrypt_bytes(path.read_bytes())


def save_report(data: bytes, key: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt_bytes(data))
    return path


def load_report(key: str) -> bytes:
    path = REPORTS_DIR / key
    if not path.exists():
        raise FileNotFoundError(key)
    return decrypt_bytes(path.read_bytes())


def purge_image(key: str) -> None:
    path = IMAGES_DIR / key
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Couches dérivées (segmentation, contour, Grad-CAM)
# ---------------------------------------------------------------------------
import base64 as _b64  # noqa: E402


def _recompress(raw: bytes, max_side: int = 760, threshold: int = 240_000) -> bytes:
    """Allège les couches PNG volumineuses (aucune perte clinique visible)."""
    if len(raw) < threshold:
        return raw
    try:
        import io as _io

        from PIL import Image as _Image

        img = _Image.open(_io.BytesIO(raw))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), _Image.LANCZOS)
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        out = buf.getvalue()
        return out if len(out) < len(raw) else raw
    except Exception:  # noqa: BLE001
        return raw


def save_variants(images: dict[str, str], owner_id: int) -> dict[str, str]:
    """Persiste les couches dérivées (data-URI base64 → fichiers chiffrés).

    Retourne un mapping {variante: clé de stockage} stocké dans le JSON
    `explainability` de l'analyse : aucune migration de schéma n'est requise.
    """
    keys: dict[str, str] = {}
    for name, data_uri in images.items():
        if name == "original" or not isinstance(data_uri, str):
            continue
        payload = data_uri.split(",", 1)[1] if data_uri.startswith("data:") and "," in data_uri else None
        if not payload:
            continue
        try:
            raw = _b64.b64decode(payload)
        except Exception:  # noqa: BLE001
            continue
        if len(raw) < 256:
            continue
        raw = _recompress(raw)
        keys[name] = save_image(raw, owner_id).key
    return keys
