import spacy
from spacy.tokens import Doc, Span

from ner_core.entities import FIELD, group_entities, normalize


def test_normalize_alias():
    assert normalize("  UAVs ") == "uav"


def test_normalize_collapses_inner_spaces():
    assert normalize("General   Staff") == "general staff"


def test_group_entities_matches_step4_aliases():
    nlp = spacy.blank("en")
    doc = Doc(nlp.vocab, words=["Drones", "and", "drones", "hit", "the", "brigade"])
    doc.ents = [
        Span(doc, 0, 1, label="WEAPON"),
        Span(doc, 2, 3, label="WEAPON"),
        Span(doc, 5, 6, label="MIL_UNIT"),
    ]
    assert group_entities(doc) == {"weapons": ["drone"], "mil_units": ["brigade"], "mil_orgs": []}


def test_field_covers_the_three_labels():
    assert FIELD == {"WEAPON": "weapons", "MIL_UNIT": "mil_units", "MIL_ORG": "mil_orgs"}
