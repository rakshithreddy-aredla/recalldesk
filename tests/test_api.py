"""Integration tests for the RecallDesk API.

Run against a live server: set HINDSIGHT_TEST_URL (default http://localhost:8000).
Tests skip cleanly when the server is unreachable, so `pytest` passes without
the full stack running.
"""

import os

import httpx
import pytest

BASE_URL = os.getenv("HINDSIGHT_TEST_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def client():
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        pytest.skip("RecallDesk API is not reachable — start uvicorn first")
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as http_client:
        yield http_client


@pytest.fixture(scope="session", autouse=True)
def seeded(client):
    resp = client.post("/seed")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health(client):
    body = client.get("/health").json()
    assert set(body) >= {"status", "hindsight", "llm"}
    assert body["status"] == "ok"


def test_seed_idempotent(client, seeded):
    first = seeded
    second = client.post("/seed").json()
    assert first["customers"] == second["customers"]


def test_chat_memory_on_shape(client):
    body = client.post(
        "/chat",
        json={
            "customer_id": "cust-1042",
            "message": "My invoice download is broken again",
            "memory_mode": "on",
        },
    ).json()
    assert body["reply"].strip()
    assert isinstance(body["memories_used"], list)
    assert body["frustration"] in {"calm", "frustrated", "angry"}
    assert isinstance(body["retained"], bool)


def test_chat_memory_off_generic(client):
    body = client.post(
        "/chat",
        json={"customer_id": "cust-1042", "message": "I need help", "memory_mode": "off"},
    ).json()
    assert body["memories_used"] == []
    assert body["retained"] is False


def test_memory_endpoint_shape(client):
    body = client.get("/customer/cust-1042/memory").json()
    assert isinstance(body["observations"], list)
    assert isinstance(body["memories"], list)
    assert isinstance(body["count"], int)


def test_chat_invalid_body(client):
    resp = client.post("/chat", json={"customer_id": "cust-1042"})
    assert resp.status_code == 422


def test_consecutive_frustration(client):
    first = client.post(
        "/chat",
        json={
            "customer_id": "cust-1045",
            "message": "This export is BROKEN and I am angry",
            "memory_mode": "on",
        },
    ).json()
    second = client.post(
        "/chat",
        json={
            "customer_id": "cust-1045",
            "message": "I am still furious, this is unacceptable",
            "memory_mode": "on",
        },
    ).json()
    assert second["frustration"] == "angry"
