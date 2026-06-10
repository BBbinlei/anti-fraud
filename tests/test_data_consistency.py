"""Cross-file ID consistency tests for all data JSON files."""

import json

from config import (
    EVAL_DATASET_FILE,
    FRAUD_TYPES,
    REVIEW_CARDS_FILE,
    RISK_ACTIONS,
    RISK_RULES_FILE,
    SCAM_CARDS_FILE,
    SCRIPT_TEMPLATES_FILE,
)


def _scam_card_ids():
    data = json.loads(SCAM_CARDS_FILE.read_text(encoding="utf-8"))
    return {card["id"] for card in data["scams"]}


def _template_scam_ids():
    data = json.loads(SCRIPT_TEMPLATES_FILE.read_text(encoding="utf-8"))
    return {t["scam_id"] for t in data["templates"]}


def test_scam_card_ids_match_template_scam_ids():
    card_ids = _scam_card_ids()
    tmpl_ids = _template_scam_ids()

    only_in_cards = card_ids - tmpl_ids
    only_in_templates = tmpl_ids - card_ids

    assert not only_in_cards, f"IDs in scam_cards but missing in script_templates: {only_in_cards}"
    assert not only_in_templates, f"IDs in script_templates but missing in scam_cards: {only_in_templates}"


def test_scam_card_ids_match_fraud_types_constant():
    card_ids = _scam_card_ids()
    fraud_type_set = set(FRAUD_TYPES)

    only_in_cards = card_ids - fraud_type_set
    only_in_constant = fraud_type_set - card_ids

    assert not only_in_cards, f"IDs in scam_cards.json but not in FRAUD_TYPES: {only_in_cards}"
    assert not only_in_constant, f"IDs in FRAUD_TYPES but missing in scam_cards.json: {only_in_constant}"


def test_risk_rules_action_values_are_valid_constants():
    data = json.loads(RISK_RULES_FILE.read_text(encoding="utf-8"))
    valid_actions = set(RISK_ACTIONS)

    for rule in data["rules"]:
        action = rule.get("action")
        assert action in valid_actions, (
            f"rule level='{rule.get('level')}' has invalid action '{action}'; "
            f"expected one of {sorted(valid_actions)}"
        )


def test_eval_dataset_scam_ids_are_valid():
    data = json.loads(EVAL_DATASET_FILE.read_text(encoding="utf-8"))
    valid_ids = set(FRAUD_TYPES)

    for case in data.get("generation_cases", []):
        scam_id = case.get("scam_id")
        if scam_id is not None:
            assert scam_id in valid_ids, (
                f"eval case '{case.get('id')}' has scam_id='{scam_id}' not in FRAUD_TYPES"
            )


def test_review_cards_fraud_types_match_fraud_types_constant():
    data = json.loads(REVIEW_CARDS_FILE.read_text(encoding="utf-8"))
    card_fraud_types = {card["fraud_type"] for card in data["cards"]}

    assert card_fraud_types == set(FRAUD_TYPES), (
        f"review_cards fraud_types {card_fraud_types} != FRAUD_TYPES {set(FRAUD_TYPES)}"
    )
