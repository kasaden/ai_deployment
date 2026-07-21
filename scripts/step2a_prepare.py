"""Etape 2a - Preparer l'echantillon a annoter.

Objectif : produire to_annotate.json, une liste de textes courts (phrases)
qui seront ensuite annotes au format spaCy (etape 2b).

Pourquoi des phrases et pas des articles entiers ?
- Les offsets (positions debut/fin) doivent etre EXACTS.
- Un LLM est bien plus fiable sur un texte court que sur un long article.
- On obtient plus d'exemples d'entrainement avec peu d'articles.
"""

import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # racine du projet
INPUT = ROOT / "data" / "corpus.json"
OUTPUT = ROOT / "data" / "to_annotate.json"

N_ARTICLES = None    # nombre d'articles (None = tous)
MAX_SENTENCES = None  # plafond d'unites a annoter (None = aucun)
MIN_LEN = 40          # longueur mini d'une phrase (0 = pas de mini)
SEED = 42            # graine fixe -> echantillon reproductible


def split_sentences(text):
    """Decoupage simple en phrases : coupe apres . ! ? suivi d'un espace."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) >= MIN_LEN]


def main():
    with open(INPUT, encoding="utf-8") as f:
        corpus = json.load(f)

    if N_ARTICLES is None:
        sample = corpus                       # tous les articles
    else:
        random.seed(SEED)
        sample = random.sample(corpus, N_ARTICLES)

    sentences = []
    for article in sample:
        sentences.extend(split_sentences(article["text"]))

    if MAX_SENTENCES is not None:
        sentences = sentences[:MAX_SENTENCES]

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(sentences, f, ensure_ascii=False, indent=2)

    print(f"{len(sentences)} phrases ecrites dans {OUTPUT} "
          f"(a partir de {len(sample)} articles)")


if __name__ == "__main__":
    main()
