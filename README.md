# AI Deployment — OSINT NER sur articles TASS

Chaîne de traitement complète qui part d'articles de presse bruts (rubrique
« Guerre » de **tass.com**, en anglais) et aboutit à des **dashboards
analytiques**. L'objectif : repérer automatiquement **quelles armes, unités et
organisations militaires** sont citées, et comment cela évolue dans le temps.

> ⚠️ TASS est un média d'État russe : les données portent un **biais éditorial
> fort**. On n'extrait jamais « la vérité », mais **ce qu'une source affirme**.

## Comment ça marche

Le cœur du projet est un modèle **NER** (Named Entity Recognition) entraîné à
reconnaître 3 types d'entités :

| Label      | Définition                   | Exemples                         |
| ---------- | ---------------------------- | -------------------------------- |
| `WEAPON`   | systèmes et matériels        | missiles, blindés, drones        |
| `MIL_UNIT` | unités combattantes          | brigades, bataillons, divisions  |
| `MIL_ORG`  | organisations de haut niveau | états-majors, ministères, forces |

Le principe clé : un **LLM (Mistral)** sert _une seule fois_ à pré-annoter un
échantillon de phrases, ce qui crée le jeu d'entraînement. Le **NER** apprend
dessus, puis traite ensuite tout le corpus — **localement, gratuitement et de
façon déterministe** (le LLM n'est plus jamais appelé en production).

```
articles JSON → texte propre → annotations → entraînement NER → inférence → Elasticsearch → dashboards
   step1          step1          step2         step3            step4         step5          Kibana
```

## Prérequis

- Python 3.10+
- Le corpus source `Instructions/data_set.json` (non versionné — à fournir)
- Un compte **Mistral AI** (clé API) pour l'annotation — free tier suffisant
- Un compte **Elastic Cloud** (14 jours gratuits) pour la visualisation

## Installation

```bash
# 1. Environnement virtuel
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # Linux / macOS

# 2. Dépendances Python
pip install -r requirements.txt

# 3. Modèle de base spaCy (point de départ du transfer learning)
python -m spacy download en_core_web_sm

# 4. Variables d'environnement
cp .env.example .env                # puis remplir les clés dans .env
```

Le fichier `.env` doit contenir :

```
API_MISTRAL="votre_cle_mistral"
ES_URL="https://xxxxx.es.region.cloud.es.io:443"
ES_API_KEY="votre_cle_elasticsearch"
```

## Lancer le pipeline

Les scripts fonctionnent depuis n'importe quel dossier (chemins ancrés sur la
racine du projet).

```bash
# Étape 1 — extraire un texte propre depuis le corpus source
python scripts/step1_extract.py            # -> data/corpus.json

# Étape 2a — découper le corpus en phrases à annoter
python scripts/step2a_prepare.py           # -> data/to_annotate.json

# Étape 2b — pré-annotation au format spaCy (2 options) :
python scripts/step2b_annotate.py          # via l'API Mistral
# ou, si l'on part d'un fichier d'annotations déjà généré (sans API) :
python scripts/step2b_bis_annotate.py      # data/annotations_with_keywords.json -> data/annotations.json

# Étape 3a — split train/dev (80/20) + conversion binaire
python scripts/step3a_convert.py           # -> data/train.spacy, data/dev.spacy

# Étape 3b/3c — entraîner le modèle NER (config.cfg source en_core_web_sm)
python -m spacy train config.cfg --output ./output `
  --paths.train ./data/train.spacy --paths.dev ./data/dev.spacy   # -> output/model-best

# Étape 4 — appliquer le modèle et enrichir les articles (entités par label)
python scripts/step4_infer.py              # -> data/enriched.json

# Étape 5 — ingérer les articles enrichis dans Elasticsearch
python scripts/step5_ingest.py             # -> index "tass_articles"
```

> Le paramétrage (taille des échantillons, nombre d'articles, limites d'appels
> API) se règle en tête de chaque script.

## Mise en production : API, Docker, monitoring

Le modèle entraîné (`output/model-best`, versionné) est servi par une API
FastAPI. Chaque appel est journalisé dans Elasticsearch (index `api_logs`).

```bash
docker compose up -d --build          # api :8000 · elasticsearch :9200 · kibana :5601
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/extract -H "Content-Type: application/json" \
  -d '{"text": "The Russian Defense Ministry said Iskander missiles hit a brigade."}'
```

- Documentation interactive : `http://127.0.0.1:8000/docs`.
- `POST /extract` renvoie les entités (texte, label, positions) et les valeurs
  normalisées par champ. Un texte vide ou de plus de 20 000 caractères renvoie 422.
- Le monitoring ne bloque jamais l'API : si Elasticsearch est indisponible,
  `/extract` répond quand même.
- Les ports sont liés à `127.0.0.1`, car la sécurité d'Elasticsearch est désactivée
  dans ce déploiement local.

Charger les données et les dashboards (Elasticsearch local, sans clé) :

```bash
ES_URL=http://localhost:9200 python scripts/step5_ingest.py   # index tass_articles
python scripts/simulate_traffic.py 300 0.8                     # charge simulée (optionnel)
python scripts/kibana_setup.py                                 # dashboards + kibana/dashboards.ndjson
```

Dans Kibana, rubrique _Dashboards_ : « Renseignement TASS — entités militaires »
et « Monitoring API — NER TASS ». Sur un autre Kibana, importez
`kibana/dashboards.ndjson` (_Stack Management → Saved objects → Import_).

## Tests et CI/CD

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

GitHub Actions (`.github/workflows/ci.yml`) enchaîne, à chaque push : lint,
tests, construction de l'image et essai de l'API dans le conteneur. Sur `main`,
l'image est publiée sur `ghcr.io/kasaden/ai_deployment`.

## Structure du dépôt

```
scripts/      les étapes du pipeline (step1 … step5), trafic simulé, setup Kibana
ner_core/     normalisation des entités, partagée par l'étape 4 et l'API
api/          API FastAPI et journalisation de monitoring
tests/        tests pytest
kibana/       dashboards exportés (ndjson)
config.cfg    configuration d'entraînement spaCy
data/         fichiers générés (non versionnés)
Instructions/ corpus source et énoncé (non versionnés)
output/       modèle entraîné (seul model-best est versionné)
```
