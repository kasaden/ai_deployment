"""Etape 2b - Pre-annoter le corpus avec un LLM (Mistral).

Objectif : produire annotations.json au format spaCy a partir de
to_annotate.json.

Approche :
- On envoie les phrases par lots a mistral-small-latest (temperature 0).
- Le LLM renvoie, pour chaque phrase, la liste des entites : {texte, label}.
- IMPORTANT : on ne demande PAS les offsets au LLM (peu fiable). C'est le
  script qui calcule les offsets exacts en cherchant la sous-chaine dans la
  phrase. Ainsi text[start:end] == entite, toujours.

Format de sortie (spaCy) :
  [ ["texte de la phrase", {"entities": [[start, end, "LABEL"], ...]}], ... ]
"""

import json
import os
import time

import requests

INPUT = "../data/to_annotate.json"
OUTPUT = "../data/annotations.json"
ENV_FILE = "../.env"

MODEL = "mistral-small-latest"
API_URL = "https://api.mistral.ai/v1/chat/completions"

LABELS = ["WEAPON", "MIL_UNIT", "MIL_ORG"]
BATCH_SIZE = 20          # phrases par appel API
LIMIT = 2000               # nb de phrases a traiter (mettre None pour tout)
SLEEP = 1.0              # pause entre appels (free tier ~1 req/s)

PROMPT = f"""You are an OSINT annotation assistant. Extract named entities from war news sentences.

Use ONLY these 3 labels:
- WEAPON: weapon systems and materiel (missiles, tanks, drones, rocket launchers, e.g. "S-300", "Kalibr", "T-90").
- MIL_UNIT: combat units (brigades, battalions, regiments, divisions, e.g. "3rd brigade", "five divisions").
- MIL_ORG: high-level military organizations (general staffs, defense ministries, armed forces, e.g. "General Staff", "Ministry of Defense").

Rules:
- Copy the entity span EXACTLY as it appears in the sentence (same casing, same characters).
- Do NOT include labels other than the 3 above. Ignore persons, countries, cities, dates.
- If a sentence has no entity, return an empty list for it.

You receive a JSON list of sentences (with their index).
Return ONLY a JSON object of this exact shape:
{{"results": [{{"i": <index>, "entities": [{{"text": "<exact span>", "label": "<LABEL>"}}]}}]}}
"""


def load_key():
    """Lit API_MISTRAL depuis le .env (parseur minimal)."""
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("API_MISTRAL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("API_MISTRAL introuvable dans .env")


def call_mistral(key, batch):
    """Envoie un lot de phrases, renvoie la liste des resultats du LLM."""
    numbered = [{"i": i, "sentence": s} for i, s in batch]
    body = {
        "model": MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(numbered, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    for attempt in range(4):
        r = requests.post(API_URL, headers=headers, json=body, timeout=60)
        if r.status_code == 429:            # rate limit -> on attend et on reessaie
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content).get("results", [])
    raise RuntimeError("Trop de 429, abandon du lot")


def find_offsets(text, entities):
    """Transforme {texte,label} en [start, end, label] sans chevauchement."""
    used = []
    out = []
    for ent in entities:
        span_text = ent.get("text", "")
        label = ent.get("label", "")
        if label not in LABELS or not span_text:
            continue
        start = 0
        while True:
            idx = text.find(span_text, start)
            if idx == -1:
                break  # sous-chaine introuvable -> on ignore cette entite
            s, e = idx, idx + len(span_text)
            if all(e <= u[0] or s >= u[1] for u in used):  # pas de chevauchement
                used.append((s, e))
                out.append([s, e, label])
                break
            start = idx + 1
    out.sort()
    return out


def main():
    key = load_key()
    with open(INPUT, encoding="utf-8") as f:
        sentences = json.load(f)

    if LIMIT is not None:
        sentences = sentences[:LIMIT]

    annotations = []
    for start in range(0, len(sentences), BATCH_SIZE):
        batch = list(enumerate(sentences[start:start + BATCH_SIZE], start=start))
        results = call_mistral(key, batch)

        by_index = {r["i"]: r.get("entities", []) for r in results}
        for i, sentence in batch:
            ents = find_offsets(sentence, by_index.get(i, []))
            annotations.append([sentence, {"entities": ents}])

        done = min(start + BATCH_SIZE, len(sentences))
        print(f"  {done}/{len(sentences)} phrases annotees")
        time.sleep(SLEEP)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)

    total_ents = sum(len(a[1]["entities"]) for a in annotations)
    print(f"\n{len(annotations)} phrases -> {total_ents} entites dans {OUTPUT}")


if __name__ == "__main__":
    main()
