"""Fixtures de test : base isolée, client HTTP, générateur d'images synthétiques."""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

TMP = Path(tempfile.mkdtemp(prefix="diafoot-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TMP / 'test.db'}"
os.environ["STORAGE_DIR"] = str(TMP / "storage")
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "False"
os.environ["EXPOSE_OTP_IN_RESPONSE"] = "True"
os.environ["SECRET_KEY"] = "test-secret-key-diafoot-sentinel"
os.environ["ALLOW_SIMULATION_FALLBACK"] = "True"

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Génération d'images de plaie synthétiques (contrôlées et réalistes)
# ---------------------------------------------------------------------------
def make_wound_image(
    *,
    size: int = 900,
    fibrin: float = 0.35,
    necrosis: float = 0.12,
    green_dot_diameter_cm: float = 2.0,
    pixels_per_cm: float = 40.0,
    blur: bool = False,
    dark: bool = False,
    mirror: bool = False,
    radius_scale: float = 1.0,
    seed: int = 7,
) -> bytes:
    rng = np.random.default_rng(seed)
    img = np.zeros((size, size, 3), np.uint8)

    # Peau : base beige + texture poreuse (garantit une variance laplacienne élevée)
    base = np.array([176, 190, 214], np.float32)   # BGR
    skin = base + rng.normal(0, 13, (size, size, 3))
    img = np.clip(skin, 0, 255).astype(np.uint8)

    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size * (0.62 if mirror else 0.44), size * 0.5
    r_outer = size * 0.17 * radius_scale
    r_inner = r_outer * 0.72
    noise = rng.normal(0, 9, (size, size))
    r_field = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) + noise

    # Berges épithéliales (rose)
    epit = (r_field < r_outer) & (r_field >= r_inner)
    img[epit] = np.clip(np.array([168, 152, 226], np.float32) +
                        rng.normal(0, 10, (epit.sum(), 3)), 0, 255).astype(np.uint8)

    # Lit de la plaie : granulation rouge + fibrine jaune + nécrose noire
    bed = r_field < r_inner
    bed_idx = np.argwhere(bed)
    n = len(bed_idx)
    perm = rng.permutation(n)
    n_f = int(n * fibrin)
    n_n = int(n * necrosis)

    red = bed_idx[perm[n_f + n_n:]]
    yellow = bed_idx[perm[:n_f]]
    black = bed_idx[perm[n_f:n_f + n_n]]

    img[red[:, 0], red[:, 1]] = np.clip(
        np.array([62, 58, 186], np.float32) + rng.normal(0, 16, (len(red), 3)), 0, 255
    ).astype(np.uint8)
    img[yellow[:, 0], yellow[:, 1]] = np.clip(
        np.array([176, 205, 231], np.float32) + rng.normal(0, 12, (len(yellow), 3)), 0, 255
    ).astype(np.uint8)
    if len(black):
        img[black[:, 0], black[:, 1]] = np.clip(
            np.array([34, 30, 32], np.float32) + rng.normal(0, 6, (len(black), 3)), 0, 255
        ).astype(np.uint8)

    # Gommette verte calibrée de 2 cm (diamètre en pixels = ppc * 2)
    dot_r = int(pixels_per_cm * green_dot_diameter_cm / 2)
    dot_cx, dot_cy = int(size * 0.82), int(size * 0.2)
    dot = (xx - dot_cx) ** 2 + (yy - dot_cy) ** 2 < dot_r**2
    img[dot] = np.clip(np.array([70, 180, 40], np.float32) +
                       rng.normal(0, 6, (dot.sum(), 3)), 0, 255).astype(np.uint8)

    pil = Image.fromarray(img[..., ::-1])
    if blur:
        from PIL import ImageFilter

        pil = pil.filter(ImageFilter.GaussianBlur(radius=14))
    if dark:
        pil = Image.fromarray((np.array(pil) * 0.08).astype(np.uint8))
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture(scope="session")
def wound_image() -> bytes:
    return make_wound_image()


@pytest.fixture(scope="session")
def registered_user(client: TestClient) -> dict:
    email = "patient.test@diafoot.health"
    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Sentinel#2026!x",
        "full_name": "Amine Ben Salah",
        "role": "patient",
        "diabetes_type": "type_2",
        "birth_year": 1958,
        "consent_accepted": True,
    })
    assert r.status_code == 201, r.text
    otp = r.json()["dev_otp"]
    r2 = client.post("/api/v1/auth/verify-otp", json={"email": email, "code": otp})
    assert r2.status_code == 200, r2.text
    data = r2.json()
    return {"email": email, "token": data["access_token"], "otp": otp,
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
            "user": data["user"]}


@pytest.fixture(scope="session")
def practitioner(client: TestClient) -> dict:
    email = "dr.mansouri@diafoot.health"
    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Podologue#2026!",
        "full_name": "Dr Leïla Mansouri",
        "role": "practitioner",
        "specialty": "diabetologist",
        "consent_accepted": True,
    })
    assert r.status_code == 201, r.text
    r2 = client.post("/api/v1/auth/verify-otp",
                     json={"email": email, "code": r.json()["dev_otp"]})
    token = r2.json()["access_token"]
    return {"email": email, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="session")
def wound(client: TestClient, registered_user: dict) -> dict:
    r = client.post("/api/v1/wounds", headers=registered_user["headers"], json={
        "label": "Ulcère plantaire hallux",
        "anatomical_site": "hallux",
        "foot_side": "right",
        "wagner_grade": 2,
    })
    assert r.status_code == 201, r.text
    return r.json()
