"""Etape 5 - Ingerer les articles enrichis dans Elasticsearch.

- Cree l'index avec un mapping explicite (texte, date, entites en keyword).
- Ingere data/enriched.json via l'API _bulk.

Prerequis dans le .env :
    ES_URL=https://xxxxx.es.region.cloud.es.io:443
    ES_API_KEY=ta_cle_encodee

On reste leger : requests + API REST, pas de SDK.
"""

import json
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
    """Lit ES_URL et ES_API_KEY depuis le .env."""
    values = {}
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(("ES_URL=", "ES_API_KEY=")):
                key, val = line.split("=", 1)
                values[key] = val.strip().strip('"').strip("'")
    if "ES_URL" not in values or "ES_API_KEY" not in values:
        raise RuntimeError("ES_URL et ES_API_KEY doivent etre definis dans .env")
    return values["ES_URL"].rstrip("/"), values["ES_API_KEY"]


def main():
    url, api_key = load_env()
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json",
    }

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
