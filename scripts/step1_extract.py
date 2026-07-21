"""Etape 1 - Extraire le texte.

Lit Instructions/data_set.json, isole le champ texte de chaque article,
nettoie legerement, et ecrit un corpus propre dans corpus.json.
On garde le decoupage par article (une entree = un article).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # racine du projet
INPUT = ROOT / "Instructions" / "data_set.json"
OUTPUT = ROOT / "data" / "corpus.json"


def clean(text):
    """Nettoyage minimal : espaces superflus et caracteres parasites."""
    text = text.replace("\xa0", " ")        # espace insecable
    text = re.sub(r"\s+", " ", text)         # espaces/retours multiples -> un seul
    return text.strip()


def main():
    with open(INPUT, encoding="utf-8") as f:
        articles = json.load(f)

    corpus = []
    for a in articles:
        text = clean(a.get("text") or "")
        if not text:
            continue  # on ignore les articles sans texte

        # date Unix -> ISO (utile plus tard pour Elasticsearch/Kibana)
        date_iso = None
        if a.get("date"):
            date_iso = datetime.fromtimestamp(a["date"], tz=timezone.utc).isoformat()

        corpus.append({
            "id": a.get("id"),
            "date": date_iso,
            "title": clean(a.get("title") or ""),
            "url": "https://tass.com" + (a.get("link") or ""),
            "text": text,
        })

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)

    print(f"{len(corpus)} articles ecrits dans {OUTPUT} (sur {len(articles)} lus)")


if __name__ == "__main__":
    main()
