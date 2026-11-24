import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import MAX_CHARS, create_app
from api.monitoring import EsRequestLogger

MODEL = Path(__file__).resolve().parent.parent / "output" / "model-best"
SENTENCE = "The Russian Defense Ministry said Iskander missiles hit a brigade."


class FakeLogger:
    def __init__(self):
        self.records = []

    def ensure_index(self):
        return True

    def log(self, record):
        self.records.append(record)


@pytest.fixture(scope="module")
def logger():
    return FakeLogger()


@pytest.fixture(scope="module")
def client(logger):
    with TestClient(create_app(MODEL, logger)) as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert sorted(body["labels"]) == ["MIL_ORG", "MIL_UNIT", "WEAPON"]


def test_extract_structure(client):
    r = client.post("/extract", json={"text": SENTENCE})
    assert r.status_code == 200
    body = r.json()
    for key in ("entities", "weapons", "mil_units", "mil_orgs", "model", "latency_ms"):
        assert key in body
    assert body["entities"], "le modèle devrait trouver au moins une entité"
    assert {e["label"] for e in body["entities"]} <= {"WEAPON", "MIL_UNIT", "MIL_ORG"}


@pytest.mark.parametrize("text", [SENTENCE, "Russia�s Iskander missile struck a brigade."])
def test_extract_offsets_match_text(client, text):
    body = client.post("/extract", json={"text": text}).json()
    for e in body["entities"]:
        assert text[e["start"]:e["end"]] == e["text"]


@pytest.mark.parametrize("text", ["", "   "])
def test_extract_rejects_empty(client, text):
    assert client.post("/extract", json={"text": text}).status_code == 422


def test_extract_rejects_too_long(client):
    assert client.post("/extract", json={"text": "a" * (MAX_CHARS + 1)}).status_code == 422


def test_extract_logs_one_record(client, logger):
    before = len(logger.records)
    client.post("/extract", json={"text": SENTENCE})
    new = logger.records[before:]
    assert len(new) == 1
    expected = {"@timestamp", "route", "status", "latency_ms", "n_chars",
                "n_weapons", "n_mil_units", "n_mil_orgs", "model"}
    assert expected <= set(new[0])
    assert new[0]["status"] == 200


def test_rejected_request_not_logged_as_prediction(client, logger):
    before = len(logger.records)
    client.post("/extract", json={"text": ""})
    assert all("n_weapons" not in rec for rec in logger.records[before:])


def test_extract_survives_es_down():
    dead = EsRequestLogger("http://127.0.0.1:9", timeout=0.5)
    with TestClient(create_app(MODEL, dead)) as c:
        start = time.perf_counter()
        r = c.post("/extract", json={"text": SENTENCE})
        elapsed = time.perf_counter() - start
    assert r.status_code == 200
    assert elapsed < 1.0
