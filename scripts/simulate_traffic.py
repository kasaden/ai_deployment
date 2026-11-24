"""Charge simulée pour le monitoring : rejoue de vraies phrases du corpus contre l'API.

Envoie N phrases tirées au hasard (graine fixe) de data/corpus.json vers
POST /extract, plus quelques requêtes invalides (texte vide, texte trop long)
pour faire apparaître des erreurs dans le dashboard de monitoring.

Usage : python scripts/simulate_traffic.py [N] [pause_en_secondes]
"""

import json
import random
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus.json"
API = "http://localhost:8000"
SEED = 42


def sentences(n):
    with open(CORPUS, encoding="utf-8") as f:
        corpus = json.load(f)
    rng = random.Random(SEED)
    out = []
    while len(out) < n:
        parts = [p.strip() for p in rng.choice(corpus)["text"].split(". ") if len(p.strip()) > 40]
        if parts:
            out.append(rng.choice(parts) + ".")
    return out


def main(n=300, pause=0.5):
    invalid = ["", "   "] * 4 + ["a" * 20_001] * 2
    payloads = sentences(n) + invalid
    random.Random(SEED).shuffle(payloads)
    status = {}
    for text in payloads:
        r = requests.post(f"{API}/extract", json={"text": text}, timeout=30)
        status[r.status_code] = status.get(r.status_code, 0) + 1
        time.sleep(pause)
    print(f"{len(payloads)} requêtes envoyées, codes HTTP : {status}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else 300, float(args[1]) if len(args) > 1 else 0.5)
