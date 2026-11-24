import requests

from api import monitoring
from api.monitoring import EsRequestLogger


class Recorder:
    def __init__(self):
        self.calls = []

    def put(self, url, json=None, timeout=None):
        self.calls.append(("PUT", url, json))

        class R:
            status_code = 200

        return R()

    def head(self, url, timeout=None):
        class R:
            status_code = 404

        return R()


def test_logger_creates_index_with_mapping(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(monitoring.requests, "put", rec.put)
    monkeypatch.setattr(monitoring.requests, "head", rec.head)
    assert EsRequestLogger("http://es:9200").ensure_index() is True
    method, url, body = rec.calls[0]
    assert (method, url) == ("PUT", "http://es:9200/api_logs")
    props = body["mappings"]["properties"]
    assert props["latency_ms"] == {"type": "float"}
    assert props["@timestamp"] == {"type": "date"}
    assert props["route"] == {"type": "keyword"}


def test_log_swallows_connection_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(monitoring.requests, "post", boom)
    EsRequestLogger("http://es:9200").log({"route": "/extract"})  # ne doit rien lever


def test_from_env_without_url_returns_none(monkeypatch):
    monkeypatch.delenv("ES_URL", raising=False)
    assert EsRequestLogger.from_env() is None
