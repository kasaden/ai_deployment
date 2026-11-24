"""Monitoring : un document par requête dans l'index Elasticsearch `api_logs`.

Règle : le monitoring ne doit jamais faire échouer une requête. Toute erreur
réseau est avalée ; le timeout est court.
"""

import logging
import os
from typing import Protocol

import requests

logger = logging.getLogger(__name__)

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
        self.ready = False  # index créé avec son mapping ?

    @classmethod
    def from_env(cls):
        url = os.environ.get("ES_URL")
        return cls(url) if url else None

    def ensure_index(self) -> bool:
        """Crée l'index avec son mapping s'il n'existe pas. False (tracé) en cas d'échec."""
        url = f"{self.es_url}/{self.index}"
        try:
            if requests.head(url, timeout=self.timeout).status_code == 200:
                self.ready = True
            else:
                self.ready = requests.put(url, json=MAPPING, timeout=self.timeout).status_code < 300
        except requests.RequestException as err:
            logger.warning("index de monitoring %s non créé : %s", self.index, err)
            return False
        if not self.ready:
            logger.warning("index de monitoring %s non créé (réponse refusée)", self.index)
        return self.ready

    def log(self, record: dict) -> None:
        # Sans mapping, Elasticsearch devinerait les types au premier document :
        # on retente la création tant qu'elle n'a pas réussi.
        if not self.ready and not self.ensure_index():
            return
        try:
            r = requests.post(f"{self.es_url}/{self.index}/_doc", json=record, timeout=self.timeout)
        except requests.RequestException as err:
            # Le monitoring ne doit pas faire échouer la requête : on trace et on continue.
            logger.warning("journal de monitoring non écrit dans %s : %s", self.index, err)
            return
        if r.status_code >= 300:
            logger.warning("journal de monitoring refusé par %s : HTTP %s", self.index, r.status_code)
