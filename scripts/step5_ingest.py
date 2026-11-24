"""Etape 5 - Ingerer les articles enrichis dans Elasticsearch.

- Cree l'index avec un mapping explicite (texte, date, entites en keyword).
- Ingere data/enriched.json via l'API _bulk.

Prerequis (variables d'environnement ou .env) :
    Elastic Cloud :  ES_URL=https://xxxxx.es.region.cloud.es.io:443  et  ES_API_KEY=ta_cle
    Docker local  :  ES_URL=http://localhost:9200  (pas de cle)

On reste leger : requests + API REST, pas de SDK.
"""

import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "enriched.json"
ENV_FILE = ROOT / ".env"

INDEX = "tass_articles"
BATCH = 500   # documents par requete _bulk

# Mapping : comment Elasticsearch doit typer chaque champ.
# keyword = valeur exacte, indispensable pour les agregations (top entites).
MAPPING = {
    "mappings": {
        "properties": {
            "text":      {"type": "text"},
            "title":     {"type": "text"},
            "url":       {"type": "keyword"},
            "date":      {"type": "date"},
            "weapons":   {"type": "keyword"},
            "mil_units": {"type": "keyword"},
            "mil_orgs":  {"type": "keyword"},
        }
    }
}


def load_env():
    """Lit ES_URL et ES_API_KEY : variables d'environnement d'abord, puis le .env.

    ES_API_KEY est facultative : sans cle, on vise un Elasticsearch local
    sans securite (docker compose), par ex. ES_URL=http://localhost:9200.
    """
    values = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(("ES_URL=", "ES_API_KEY=")):
                    key, val = line.split("=", 1)
                    values[key] = val.strip().strip('"').strip("'")
    for key in ("ES_URL", "ES_API_KEY"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    if not values.get("ES_URL"):
        raise RuntimeError("ES_URL doit etre defini (variable d'environnement ou .env)")
    return values["ES_URL"].rstrip("/"), values.get("ES_API_KEY") or None


def build_headers(api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    return headers


def main():
    url, api_key = load_env()
    headers = build_headers(api_key)

    # 1. (Re)creer l'index avec le mapping. On supprime l'ancien s'il existe.
    requests.delete(f"{url}/{INDEX}", headers=headers, timeout=30)
    r = requests.put(f"{url}/{INDEX}", headers=headers, json=MAPPING, timeout=30)
    r.raise_for_status()
    print(f"Index '{INDEX}' cree.")

    # 2. Ingestion par lots via _bulk.
    with open(INPUT, encoding="utf-8") as f:
        docs = json.load(f)

    for start in range(0, len(docs), BATCH):
        chunk = docs[start:start + BATCH]
        lines = []
        for doc in chunk:
            lines.append(json.dumps({"index": {"_id": doc["id"]}}))
            lines.append(json.dumps(doc, ensure_ascii=False))
        payload = "\n".join(lines) + "\n"

        r = requests.post(
            f"{url}/{INDEX}/_bulk",
            headers={**headers, "Content-Type": "application/x-ndjson"},
            data=payload.encode("utf-8"),
            timeout=120,
        )
        r.raise_for_status()
        if r.json().get("errors"):
            print("  ! des erreurs sont survenues dans ce lot")
        print(f"  {min(start + BATCH, len(docs))}/{len(docs)} documents ingeres")

    print(f"\nTermine : {len(docs)} documents dans l'index '{INDEX}'.")


if __name__ == "__main__":
    main()
