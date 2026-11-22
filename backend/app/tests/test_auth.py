"""Tests du parcours d'authentification (OTP, JWT, rôles)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "inference" in body


def test_root_disclaimer(client: TestClient):
    r = client.get("/api-info")
    assert r.status_code == 200
    assert "avis médical" in r.json()["disclaimer"]


def test_register_requires_consent(client: TestClient):
    r = client.post("/api/v1/auth/register", json={
        "email": "noconsent@podotrace.health",
        "password": "Sentinel#2026!x",
        "consent_accepted": False,
    })
    assert r.status_code == 422


def test_register_weak_password(client: TestClient):
    r = client.post("/api/v1/auth/register", json={
        "email": "weak@podotrace.health",
        "password": "azerty",
        "consent_accepted": True,
    })
    assert r.status_code in (422, 400)


def test_full_auth_flow(client: TestClient):
    email = "flow.user@podotrace.health"
    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Sentinel#2026!x",
        "full_name": "Flow User",
        "consent_accepted": True,
        "diabetes_type": "type_1",
    })
    assert r.status_code == 201
    otp = r.json()["dev_otp"]
    assert otp and len(otp) == 6

    # Un code erroné est refusé
    bad = client.post("/api/v1/auth/verify-otp", json={"email": email, "code": "000000"})
    assert bad.status_code == 400

    # Le bon code ouvre la session
    ok = client.post("/api/v1/auth/verify-otp", json={"email": email, "code": otp})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["email_verified"] is True

    # Login par mot de passe
    login = client.post("/api/v1/auth/login",
                        json={"email": email, "password": "Sentinel#2026!x"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"

    # Mauvais mot de passe
    assert client.post("/api/v1/auth/login",
                       json={"email": email, "password": "Wrong#2026!x"}).status_code == 401

    # Profil modifiable
    patch = client.patch("/api/v1/auth/me", headers=headers,
                         json={"neuropathy": True, "onboarding_done": True})
    assert patch.status_code == 200
    assert patch.json()["neuropathy"] is True


def test_duplicate_email(client: TestClient, registered_user: dict):
    r = client.post("/api/v1/auth/register", json={
        "email": registered_user["email"],
        "password": "Sentinel#2026!x",
        "consent_accepted": True,
    })
    assert r.status_code == 409


def test_protected_route_requires_token(client: TestClient):
    assert client.get("/api/v1/wounds").status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": "Bearer garbage"}).status_code == 401
