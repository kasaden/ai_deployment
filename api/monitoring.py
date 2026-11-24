"""Monitoring : un document par requête dans l'index Elasticsearch `api_logs`.

Règle : le monitoring ne doit jamais faire échouer une requête. Toute erreur
réseau est avalée ; le timeout est court.
"""

import os
from typing import Protocol

import requests

INDEX = "api_logs"

MAPPING = {
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "route": {"type": "keyword"},
            "model": {"type": "keyword"},
            "status": {"type": "short"},
            "latency_ms": {"type": "float"},
            "n_chars": {"type": "integer"},
            "n_weapons": {"type": "integer"},
            "n_mil_units": {"type": "integer"},
            "n_mil_orgs": {"type": "integer"},
        }
    }
}


class RequestLogger(Protocol):
    def ensure_index(self) -> bool: ...

    def log(self, record: dict) -> None: ...


class EsRequestLogger:
    def __init__(self, es_url: str, index: str = INDEX, timeout: float = 0.5):
        self.es_url = es_url.rstrip("/")
        self.index = index
        self.timeout = timeout

    @classmethod
    def from_env(cls):
        url = os.environ.get("ES_URL")
        return cls(url) if url else None

    def ensure_index(self) -> bool:
        """Crée l'index avec son mapping s'il n'existe pas. False si ES est injoignable."""
        url = f"{self.es_url}/{self.index}"
        try:
            if requests.head(url, timeout=self.timeout).status_code == 200:
                return True
            return requests.put(url, json=MAPPING, timeout=self.timeout).status_code < 300
        except requests.RequestException:
            return False

    def log(self, record: dict) -> None:
        try:
            requests.post(f"{self.es_url}/{self.index}/_doc", json=record, timeout=self.timeout)
        except requests.RequestException:
            pass
