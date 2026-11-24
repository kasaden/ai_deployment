import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "step5_ingest.py"


def load_step5():
    spec = importlib.util.spec_from_file_location("step5", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_env_url_without_key_targets_local_es(monkeypatch, tmp_path):
    step5 = load_step5()
    monkeypatch.setattr(step5, "ENV_FILE", tmp_path / "absent.env")
    monkeypatch.setenv("ES_URL", "http://localhost:9200/")
    monkeypatch.delenv("ES_API_KEY", raising=False)
    assert step5.load_env() == ("http://localhost:9200", None)


def test_headers_without_key_have_no_authorization():
    step5 = load_step5()
    assert "Authorization" not in step5.build_headers(None)
    assert step5.build_headers("k")["Authorization"] == "ApiKey k"
