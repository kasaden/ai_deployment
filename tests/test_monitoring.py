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


def test_log_swallows_connection_error(monkeypatch, caplog):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(monitoring.requests, "post", boom)
    es = EsRequestLogger("http://es:9200")
    es.ready = True
    es.log({"route": "/extract"})  # ne doit rien lever
    assert "api_logs" in caplog.text  # l'échec est tracé, pas avalé en silence


def test_log_retries_index_creation_until_it_succeeds(monkeypatch):
    calls = []

    class R:
        def __init__(self, code):
            self.status_code = code

    monkeypatch.setattr(monitoring.requests, "head", lambda url, timeout=None: R(404))
    monkeypatch.setattr(monitoring.requests, "put",
                        lambda url, json=None, timeout=None: calls.append("PUT") or R(200))
    monkeypatch.setattr(monitoring.requests, "post",
                        lambda url, json=None, timeout=None: calls.append("POST") or R(201))
    es = EsRequestLogger("http://es:9200")
    es.ready = False  # comme si ensure_index avait échoué au démarrage
    es.log({"route": "/extract"})
    es.log({"route": "/extract"})
    assert calls == ["PUT", "POST", "POST"]


def test_failed_index_creation_is_traced(monkeypatch, caplog):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(monitoring.requests, "head", boom)
    assert EsRequestLogger("http://es:9200").ensure_index() is False
    assert "api_logs" in caplog.text


def test_rejected_log_is_traced(monkeypatch, caplog):
    class R:
        status_code = 429

    monkeypatch.setattr(monitoring.requests, "post", lambda *a, **k: R())
    es = EsRequestLogger("http://es:9200")
    es.ready = True
    es.log({"route": "/extract"})
    assert "429" in caplog.text


def test_from_env_without_url_returns_none(monkeypatch):
    monkeypatch.delenv("ES_URL", raising=False)
    assert EsRequestLogger.from_env() is None
