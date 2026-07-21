# ai_deployment

Déploiement de solutions d’IA. OSINT

'''bash

## init

python -m venv .venv
pip install -r requirements.txt
python -m pip install click
python -m spacy download en_core_web_sm

cp .env.example .env
'''

## Pipeline (à lancer depuis scripts/)

# Étape 1 — extraire le texte propre depuis le corpus source

python scripts/step1_extract.py # -> data/corpus.json

# Étape 2a — échantillonner les phrases à annoter

python scripts/step2a_prepare.py # -> data/to_annotate.json

# Étape 2b — pré-annotation LLM (Mistral) au format spaCy

python scripts/step2b_annotate.py # -> data/annotations.json

# Étape 3a — split train/dev + conversion .spacy

python scripts/step3a_convert.py # -> data/train.spacy, data/dev.spacy

# Étape 3c — entraîner le modèle NER

python -m spacy train config.cfg \
 --output ./output \
 --paths.train ./data/train.spacy \
 --paths.dev ./data/dev.spacy # -> output/model-best
