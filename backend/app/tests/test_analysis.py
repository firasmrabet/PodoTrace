"""Tests du parcours d'analyse IA, de la sécurité des images et des rapports."""
from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core import storage
from app.inference import pipeline
from app.tests.conftest import make_wound_image


def _upload(client: TestClient, headers: dict, wound_id: int, image: bytes, **form):
    data = {"wound_id": str(wound_id), "scale_ref": "2.0", **{k: str(v) for k, v in form.items()}}
    return client.post(
        "/api/v1/analysis/full-analysis",
        headers=headers,
        data=data,
        files={"file": ("wound.jpg", image, "image/jpeg")},
    )


def test_engine_status(client: TestClient):
    r = client.get("/api/v1/analysis/engine/status")
    assert r.status_code == 200
    assert "engine" in r.json()
    assert r.json()["segmentation_model_loaded"] == (
        r.json()["segmentation_model_error"] is None
    )
    assert r.json()["risk_model_loaded"] == (r.json()["risk_model_error"] is None)


@pytest.mark.skipif(not pipeline.TORCH, reason="PyTorch absent")
def test_incompatible_checkpoint_is_not_reported_as_loaded(monkeypatch, tmp_path):
    checkpoint = tmp_path / "wound_seg_unetpp_effb3.pth"
    pipeline.torch.save({"not_a_model_parameter": pipeline.torch.zeros(1)}, checkpoint)
    monkeypatch.setattr(pipeline.settings, "WEIGHTS_DIR", tmp_path)

    status = pipeline.WoundAnalyzer().status()

    assert status["segmentation_model_loaded"] is False
    assert status["risk_model_loaded"] is False
    assert status["engine"] == "segmenter-hsv+risk-logistic-score"
    assert status["segmentation_model_error"]


def test_full_analysis_pipeline(client: TestClient, registered_user: dict,
                                wound: dict, wound_image: bytes):
    r = _upload(client, registered_user["headers"], wound["id"], wound_image)
    assert r.status_code == 200, r.text
    body = r.json()

    # --- Calibrage : gommette verte détectée (40 px/cm attendus) ----------
    calib = body["calibration"]
    assert calib["method"] in {"green_dot", "manual", "assumed"}
    assert 25.0 <= calib["pixels_per_cm"] <= 60.0

    # --- Métriques cohérentes ---------------------------------------------
    metrics = body["metrics"]
    assert metrics["area_cm2"] > 5          # plaie large et nette
    assert metrics["area_cm2"] < 200
    assert metrics["perimeter_cm"] > 5

    # --- Composition tissulaire = 100 % ------------------------------------
    comp = body["tissues"]["composition"]
    assert set(comp) == {"necrosis", "fibrin", "granulation", "epithelial"}
    assert abs(sum(comp.values()) - 1.0) < 0.02
    assert body["tissues"]["dominant"] in comp

    # --- Risques bornés ----------------------------------------------------
    risk = body["risk"]
    assert 0.0 <= risk["infection_risk"] <= 1.0
    assert 0.0 <= risk["ischemia_risk"] <= 1.0
    assert risk["risk_level"] in {"low", "moderate", "high"}
    assert risk["recommendations"]

    # --- Rendus visuels ----------------------------------------------------
    for key in ("original", "segmentation", "heatmap"):
        assert body["images"][key].startswith("data:image")
    assert body["explainability"]["method"] in {"grad-cam", "saliency-proxy"}
    assert "attention_inside_wound" in body["explainability"]["stats"]

    # --- Persistance -------------------------------------------------------
    analysis = body["analysis"]
    assert analysis["area_cm2"] == metrics["area_cm2"]
    assert analysis["engine"]
    assert analysis["processing_ms"] >= 0

    fetched = client.get(f"/api/v1/analysis/{analysis['id']}",
                         headers=registered_user["headers"])
    assert fetched.status_code == 200


def test_analysis_rejects_dark_image(client: TestClient, registered_user: dict, wound: dict):
    dark = make_wound_image(dark=True)
    r = _upload(client, registered_user["headers"], wound["id"], dark)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "image_quality_rejected"
    assert detail["issues"]


def test_analysis_rejects_blurry_image(client: TestClient, registered_user: dict, wound: dict):
    blurry = make_wound_image(blur=True)
    r = _upload(client, registered_user["headers"], wound["id"], blurry)
    # Une image floue doit être signalée (rejet strict ou score de qualité dégradé)
    if r.status_code == 200:
        assert r.json()["quality"]["score"] < 1.0
        assert r.json()["quality"]["issues"]
    else:
        assert r.status_code == 422


def test_image_encrypted_at_rest(client: TestClient, registered_user: dict,
                                 wound: dict, wound_image: bytes):
    """Le fichier sur disque ne doit JAMAIS contenir les octets de l'image."""
    r = _upload(client, registered_user["headers"], wound["id"], wound_image)
    assert r.status_code == 200
    analysis_id = r.json()["analysis"]["id"]

    from app.db.session import SessionLocal
    from app.models.entities import WoundAnalysis

    import asyncio

    async def fetch():
        async with SessionLocal() as s:
            return await s.get(WoundAnalysis, analysis_id)

    row = asyncio.get_event_loop().run_until_complete(fetch()) if False else None
    # Vérifie via l'API puis le stockage
    img = client.get(f"/api/v1/analysis/{analysis_id}/image/original",
                     headers=registered_user["headers"])
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/jpeg"

    raw = None
    for f in (Path(storage.IMAGES_DIR)).rglob("*"):
        if f.is_file():
            raw = f.read_bytes()
            if raw.startswith(b"\x80") is False:  # chiffré => pas d'entête JPEG
                break
    assert raw is not None
    assert not raw.startswith(b"\xff\xd8"), "L'image ne doit pas être stockée en clair"


def test_image_access_denied_for_other_patient(client: TestClient, registered_user: dict,
                                               wound: dict, wound_image: bytes):
    r = _upload(client, registered_user["headers"], wound["id"], wound_image)
    analysis_id = r.json()["analysis"]["id"]

    other = client.post("/api/v1/auth/register", json={
        "email": "intrus@diafoot.health",
        "password": "Sentinel#2026!x",
        "consent_accepted": True,
    })
    email = "intrus@diafoot.health"
    token_r = client.post("/api/v1/auth/verify-otp",
                          json={"email": email, "code": other.json()["dev_otp"]})
    headers = {"Authorization": f"Bearer {token_r.json()['access_token']}"}

    assert client.get(f"/api/v1/analysis/{analysis_id}", headers=headers).status_code == 403
    assert client.get(f"/api/v1/analysis/{analysis_id}/image/original",
                      headers=headers).status_code == 403


def test_delete_analysis_purges_original_and_variants(
    client: TestClient, registered_user: dict, wound: dict, wound_image: bytes
):
    response = _upload(client, registered_user["headers"], wound["id"], wound_image)
    assert response.status_code == 200, response.text
    analysis_id = response.json()["analysis"]["id"]

    from app.tests.conftest import TMP

    with sqlite3.connect(TMP / "test.db") as conn:
        row = conn.execute(
            "SELECT image_key, explainability FROM wound_analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    assert row is not None
    image_key, explainability_json = row
    variants = json.loads(explainability_json).get("variants", {})
    keys = {image_key, *variants.values()}
    assert keys
    assert all((Path(storage.IMAGES_DIR) / key).is_file() for key in keys)

    deleted = client.delete(
        f"/api/v1/analysis/{analysis_id}", headers=registered_user["headers"]
    )
    assert deleted.status_code == 204
    assert all(not (Path(storage.IMAGES_DIR) / key).exists() for key in keys)


def test_wound_trend_and_dashboard(client: TestClient, registered_user: dict,
                                   wound: dict, wound_image: bytes):
    # Deuxième mesure avec une plaie plus petite (fibrine moindre)
    smaller = make_wound_image(fibrin=0.15, necrosis=0.02, seed=21)
    assert _upload(client, registered_user["headers"], wound["id"], smaller).status_code == 200

    trend = client.get(f"/api/v1/wounds/{wound['id']}/trend",
                       headers=registered_user["headers"])
    assert trend.status_code == 200
    t = trend.json()
    assert t["status"] in {"healing", "slow", "stagnant", "worsening"}
    assert t["push_score"] >= 0
    assert isinstance(t["series"], list) and len(t["series"]) >= 2

    other_wound = client.post(
        "/api/v1/wounds",
        headers=registered_user["headers"],
        json={"label": "Autre plaie", "anatomical_site": "heel", "foot_side": "left"},
    )
    assert other_wound.status_code == 201
    assert _upload(
        client, registered_user["headers"], other_wound.json()["id"], wound_image
    ).status_code == 200

    dash = client.get("/api/v1/wounds/dashboard", headers=registered_user["headers"])
    assert dash.status_code == 200
    d = dash.json()
    assert d["active_wounds"] >= 1
    assert d["global_status"] in {"stable", "improving", "alert", "no_data"}
    assert d["banner_message"]
    assert d["trend_pct"] == t["reduction_pct"]


def test_doctor_review_human_in_the_loop(client: TestClient, registered_user: dict,
                                         practitioner: dict, wound: dict,
                                         wound_image: bytes):
    r = _upload(client, registered_user["headers"], wound["id"], wound_image)
    analysis_id = r.json()["analysis"]["id"]
    practitioner_user = client.get("/api/v1/auth/me", headers=practitioner["headers"]).json()
    from app.tests.conftest import TMP

    with sqlite3.connect(TMP / "test.db") as conn:
        conn.execute(
            "UPDATE users SET referent_practitioner_id = ? WHERE id = ?",
            (practitioner_user["id"], registered_user["user"]["id"]),
        )

    # Un patient ne peut pas valider un diagnostic
    denied = client.patch(f"/api/v1/analysis/{analysis_id}/review",
                          headers=registered_user["headers"],
                          json={"doctor_notes": "test"})
    assert denied.status_code == 403

    ok = client.patch(f"/api/v1/analysis/{analysis_id}/review",
                      headers=practitioner["headers"],
                      json={"doctor_notes": "Débridement réalisé le 12/11.",
                            "doctor_override_level": "moderate",
                            "dressing_prescription": "Hydrocolloïde + décharge TCC",
                            "validate": True})
    assert ok.status_code == 200
    assert ok.json()["doctor_validated"] is True
    assert ok.json()["doctor_override_level"] == "moderate"

    pending = client.get("/api/v1/practitioner/pending", headers=practitioner["headers"])
    assert pending.status_code == 200


def test_pdf_report(client: TestClient, registered_user: dict, wound: dict):
    r = client.get(f"/api/v1/reports/wound/{wound['id']}/pdf",
                   headers=registered_user["headers"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 8000


def test_geo_nearby(client: TestClient, registered_user: dict):
    r = client.get("/api/v1/geo/nearby", headers=registered_user["headers"],
                   params={"lat": 36.8065, "lon": 10.1815, "radius_km": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert body["places"][0]["distance_km"] <= 30
    # Tri par distance croissante
    distances = [p["distance_km"] for p in body["places"]]
    assert distances == sorted(distances)


def test_geo_emergency_filter(client: TestClient, registered_user: dict):
    r = client.get("/api/v1/geo/nearby", headers=registered_user["headers"],
                   params={"lat": 36.8065, "lon": 10.1815, "radius_km": 30,
                           "category": "emergency"})
    assert r.status_code == 200
    assert all(p["emergency_24_7"] for p in r.json()["places"])


@pytest.mark.asyncio
async def test_geo_reports_local_fallback_source(monkeypatch):
    from app.services import geo

    async def no_places(*_args, **_kwargs):
        return []

    monkeypatch.setattr(geo, "overpass_search", no_places)
    places, source = await geo.search_nearby(36.8066, 10.1809, 29.25)

    assert places
    assert source == "local-fallback"


def test_unassigned_practitioner_cannot_browse_patient_data(
    client: TestClient, registered_user: dict, wound: dict
):
    email = "unassigned.practitioner@diafoot.health"
    registered = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Podologue#2026!",
        "role": "practitioner",
        "consent_accepted": True,
    })
    verified = client.post("/api/v1/auth/verify-otp", json={
        "email": email,
        "code": registered.json()["dev_otp"],
    })
    headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}

    assert client.get("/api/v1/practitioner/patients", headers=headers).json()["count"] == 0
    assert client.get("/api/v1/practitioner/pending", headers=headers).json()["count"] == 0
    assert client.get(
        f"/api/v1/wounds?patient_id={registered_user['user']['id']}", headers=headers
    ).status_code == 403
    assert client.get(
        f"/api/v1/analysis?wound_id={wound['id']}", headers=headers
    ).status_code == 403
    assert client.get(
        f"/api/v1/wounds/{wound['id']}", headers=headers
    ).status_code == 403
    assert client.post("/api/v1/chat", headers=headers, json={
        "message": "Analyse cette plaie",
        "wound_id": wound["id"],
    }).status_code == 403
