"""Etape 4 - Inference : appliquer le modele NER au corpus.

Objectif : charger output/model-best, l'appliquer sur une partie des articles,
et produire des articles ENRICHIS (entites regroupees par label).

Sortie : data/enriched.json -> directement ingerable dans Elasticsearch (etape 5).
Chaque document contient : id, date, title, url, text + weapons / mil_units / mil_orgs.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import spacy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # pour importer ner_core depuis scripts/

from ner_core.entities import FIELD, group_entities

MODEL = ROOT / "output" / "model-best"
INPUT = ROOT / "data" / "corpus.json"
OUTPUT = ROOT / "data" / "enriched.json"

LIMIT = None   # nb d'articles a traiter (mettre None pour tout le corpus)

# FIELD, ALIAS et la normalisation sont dans ner_core/entities.py (partages avec l'API).


def main():
    nlp = spacy.load(MODEL)

    with open(INPUT, encoding="utf-8") as f:
        corpus = json.load(f)
    if LIMIT is not None:
        corpus = corpus[:LIMIT]

    texts = [a["text"] for a in corpus]
    enriched = []
    totals = Counter()
    top = {f: Counter() for f in FIELD.values()}

    # nlp.pipe = inference par lots, plus rapide
    for article, doc in zip(corpus, nlp.pipe(texts, batch_size=64)):
        groups = group_entities(doc)   # valeurs normalisees, uniques par article

        enriched.append({
            "id": article["id"],
            "date": article["date"],
            "title": article["title"],
            "url": article["url"],
            "text": article["text"],
            **groups,
        })

        for field, values in groups.items():
            totals[field] += len(values)
            top[field].update(values)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    # --- Que constate-t-on ? ---
    print(f"{len(enriched)} articles enrichis -> {OUTPUT}\n")
    for field in FIELD.values():
        print(f"{field} : {totals[field]} entites")
        for value, n in top[field].most_common(8):
            print(f"    {n:4}  {value}")
        print()


if __name__ == "__main__":
    main()
