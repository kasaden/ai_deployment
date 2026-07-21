"""Etape 3a - Split train/dev + conversion au format spaCy (.spacy).

Objectif :
- Separer les annotations en train (80%) et dev (20%).
- Convertir chaque exemple en Doc spaCy et l'ecrire dans un DocBin binaire.

Sortie : ../Data/train.spacy et ../Data/dev.spacy (consommes par `spacy train`).

Note : un offset qui ne tombe pas sur une frontiere de token ne peut pas
devenir une entite -> on l'ignore et on le compte (alignment_mode="contract").
"""

import json
import random
from pathlib import Path

import spacy
from spacy.tokens import DocBin
from spacy.util import filter_spans

ROOT = Path(__file__).resolve().parent.parent   # racine du projet
INPUT = ROOT / "data" / "annotations.json"
TRAIN_OUT = ROOT / "data" / "train.spacy"
DEV_OUT = ROOT / "data" / "dev.spacy"

SPLIT = 0.8   # part de train
SEED = 42


def build_docbin(nlp, examples):
    """Convertit une liste [texte, {entities}] en DocBin. Renvoie (docbin, nb_ignores)."""
    doc_bin = DocBin()
    skipped = 0
    for text, ann in examples:
        doc = nlp.make_doc(text)
        spans = []
        for start, end, label in ann["entities"]:
            span = doc.char_span(start, end, label=label, alignment_mode="contract")
            if span is None:
                skipped += 1          # offset non aligne sur un token
            else:
                spans.append(span)
        doc.ents = filter_spans(spans)  # securite anti-chevauchement
        doc_bin.add(doc)
    return doc_bin, skipped


def main():
    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    random.seed(SEED)
    random.shuffle(data)
    cut = int(len(data) * SPLIT)
    train, dev = data[:cut], data[cut:]

    nlp = spacy.blank("en")  # tokenizer anglais, sans composants

    train_bin, s1 = build_docbin(nlp, train)
    dev_bin, s2 = build_docbin(nlp, dev)

    train_bin.to_disk(TRAIN_OUT)
    dev_bin.to_disk(DEV_OUT)

    print(f"train : {len(train)} phrases -> {TRAIN_OUT}")
    print(f"dev   : {len(dev)} phrases -> {DEV_OUT}")
    if s1 + s2:
        print(f"entites ignorees (offset non aligne) : {s1 + s2}")


if __name__ == "__main__":
    main()
