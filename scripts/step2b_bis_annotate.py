"""Etape 2b (bis) - Convertir annotations_with_keywords.json -> annotations.json.

Variante de step2b SANS appel API : on part d'un fichier intermediaire deja
produit (par ex. via l'interface d'un LLM), au format :
  {"results": [{"i": <index>, "entities": [{"text","label","keywords":[...]}]}]}

Ce script calcule les offsets exacts dans la phrase source (to_annotate.json,
reperee par l'index "i") et ecrit le format spaCy attendu :
  [ ["texte de la phrase", {"entities": [[start, end, "LABEL"], ...]}], ... ]

Le "text" de l'entite est cherche en priorite ; si introuvable tel quel,
on tente les "keywords" comme solution de secours.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_SENTENCES = ROOT / "data" / "to_annotate.json"
INPUT_KEYWORDS = ROOT / "data" / "annotations_with_keywords.json"
OUTPUT = ROOT / "data" / "annotations.json"

LABELS = ["WEAPON", "MIL_UNIT", "MIL_ORG"]


def find_offsets(text, entities):
    """Transforme les entites en [start, end, label] sans chevauchement."""
    used = []
    out = []
    for ent in entities:
        label = ent.get("label", "")
        if label not in LABELS:
            continue
        # on essaie d'abord le span exact, puis les keywords en secours
        candidates = [ent.get("text", "")] + ent.get("keywords", [])
        for cand in candidates:
            if not cand:
                continue
            start = 0
            placed = False
            while True:
                idx = text.find(cand, start)
                if idx == -1:
                    break
                s, e = idx, idx + len(cand)
                if all(e <= u[0] or s >= u[1] for u in used):  # pas de chevauchement
                    used.append((s, e))
                    out.append([s, e, label])
                    placed = True
                    break
                start = idx + 1
            if placed:
                break  # entite placee, on passe a la suivante
    out.sort()
    return out


def main():
    with open(INPUT_SENTENCES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(INPUT_KEYWORDS, encoding="utf-8") as f:
        results = json.load(f)["results"]

    annotations = []
    n_ents = 0
    for r in results:
        i = r["i"]
        if i >= len(sentences):
            continue  # index hors de to_annotate.json -> on ignore
        sentence = sentences[i]
        ents = find_offsets(sentence, r.get("entities", []))
        annotations.append([sentence, {"entities": ents}])
        n_ents += len(ents)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)

    print(f"{len(annotations)} phrases -> {n_ents} entites dans {OUTPUT}")


if __name__ == "__main__":
    main()
