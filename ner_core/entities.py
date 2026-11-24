"""Regroupement et normalisation des entités prédites par le modèle NER.

Utilisé par l'étape 4 (enrichissement du corpus) et par l'API, pour que
les deux produisent exactement les mêmes valeurs.
"""

# label du modèle -> nom du champ dans le document
FIELD = {"WEAPON": "weapons", "MIL_UNIT": "mil_units", "MIL_ORG": "mil_orgs"}

# regroupement de synonymes évidents (clés et valeurs en minuscules)
# On NE fusionne PAS les nationalités (russian/ukrainian) : c'est du renseignement.
ALIAS = {
    "uavs": "uav",
    "unmanned aerial vehicle": "uav",
    "unmanned aerial vehicles": "uav",
    "drones": "drone",
    "tanks": "tank",
    "mortars": "mortar",
    "missiles": "missile",
}


def normalize(text):
    """Minuscules, espaces normalisés, puis alias éventuel."""
    t = " ".join(text.lower().split())
    return ALIAS.get(t, t)


def group_entities(doc):
    """Entités d'un Doc spaCy regroupées par champ, normalisées, uniques, dans l'ordre."""
    groups = {field: [] for field in FIELD.values()}
    for ent in doc.ents:
        if ent.label_ in FIELD:
            field = FIELD[ent.label_]
            value = normalize(ent.text)
            if value not in groups[field]:
                groups[field].append(value)
    return groups
