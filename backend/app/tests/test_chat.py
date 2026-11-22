"""Tests de l'assistant IA : red flags, RAG, historique."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.llm import detect_red_flags, retrieve


def test_red_flag_detection():
    flag, terms = detect_red_flags("J'ai de la fièvre et une odeur fétide depuis hier")
    assert flag is True
    assert "fièvre" in terms and "odeur fétide" in terms


def test_no_red_flag():
    flag, terms = detect_red_flags("Comment décharger mon appui quand je marche ?")
    assert flag is False
    assert terms == []


def test_retrieval_offloading():
    docs = retrieve("comment faire la décharge de l'appui ?")
    assert docs
    assert any("décharge" in d["title"].lower() or "offloading" in d["id"] for d in docs)


def test_chat_red_flag_response(client: TestClient, registered_user: dict, wound: dict):
    r = client.post("/api/v1/chat", headers=registered_user["headers"], json={
        "message": "Ma plaie a une odeur fétide, j'ai de la fièvre et la rougeur s'étend",
        "wound_id": wound["id"],
        "locale": "fr",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["red_flag"] is True
    assert body["emergency_message"]
    assert "15" in body["emergency_message"] or "190" in body["emergency_message"]
    assert body["sources"]
    assert body["reply"]


def test_chat_standard_question(client: TestClient, registered_user: dict, wound: dict):
    r = client.post("/api/v1/chat", headers=registered_user["headers"], json={
        "message": "Que signifie la fibrine jaune dans ma plaie ?",
        "wound_id": wound["id"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["red_flag"] is False
    assert body["provider"] in {"heuristic", "groq", "mistral", "openrouter"}
    assert len(body["reply"]) > 80


def test_chat_history(client: TestClient, registered_user: dict, wound: dict):
    other_wound = client.post(
        "/api/v1/wounds",
        headers=registered_user["headers"],
        json={"label": "Autre plaie", "anatomical_site": "heel", "foot_side": "left"},
    ).json()
    unrelated_message = "Question au sujet de l'autre plaie"
    client.post("/api/v1/chat", headers=registered_user["headers"], json={
        "message": unrelated_message,
        "wound_id": other_wound["id"],
    })
    before = client.get(
        "/api/v1/chat/history",
        headers=registered_user["headers"],
        params={"wound_id": wound["id"]},
    ).json()
    client.post("/api/v1/chat", headers=registered_user["headers"], json={
        "message": "Comment suivre la surface de ma plaie ?",
        "wound_id": wound["id"],
    })
    r = client.get(
        "/api/v1/chat/history",
        headers=registered_user["headers"],
        params={"wound_id": wound["id"]},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == len(before) + 2
    assert unrelated_message not in [message["content"] for message in r.json()]


def test_chat_suggestions(client: TestClient):
    r = client.get("/api/v1/chat/suggestions", params={"locale": "fr"})
    assert r.status_code == 200
    assert len(r.json()["suggestions"]) == 4
