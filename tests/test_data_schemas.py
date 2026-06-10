"""Schema validation for scam_cards.json, script_templates.json, risk_rules.json."""

import json

import pytest

from config import (
    FRAUD_TYPES,
    RISK_RULES_FILE,
    SCAM_CARDS_FILE,
    SCRIPT_TEMPLATES_FILE,
)


def _load_scam_cards():
    return json.loads(SCAM_CARDS_FILE.read_text(encoding="utf-8"))["scams"]


def _load_templates():
    return json.loads(SCRIPT_TEMPLATES_FILE.read_text(encoding="utf-8"))["templates"]


def _load_rules():
    return json.loads(RISK_RULES_FILE.read_text(encoding="utf-8"))["rules"]


def test_scam_cards_covers_all_fraud_types():
    scams = _load_scam_cards()
    assert {card["id"] for card in scams} == set(FRAUD_TYPES)


def test_each_scam_card_has_required_fields():
    required_str_fields = ["id", "name", "target", "prevention", "legal"]
    required_list_fields = ["tactics", "red_flags"]

    for card in _load_scam_cards():
        scam_id = card.get("id", "<unknown>")
        for field in required_str_fields:
            assert field in card and str(card[field]).strip(), (
                f"scam_card '{scam_id}' missing or empty field '{field}'"
            )
        for field in required_list_fields:
            assert field in card and isinstance(card[field], list) and card[field], (
                f"scam_card '{scam_id}' field '{field}' must be a non-empty list"
            )


def test_script_templates_covers_all_fraud_types():
    templates = _load_templates()
    assert {t["scam_id"] for t in templates} == set(FRAUD_TYPES)


def test_each_template_has_required_fields():
    required_str_fields = ["scam_id", "persona", "opener"]

    for template in _load_templates():
        scam_id = template.get("scam_id", "<unknown>")
        for field in required_str_fields:
            assert field in template and str(template[field]).strip(), (
                f"template '{scam_id}' missing or empty field '{field}'"
            )
        steps = template.get("escalation_steps")
        assert isinstance(steps, list) and steps, (
            f"template '{scam_id}' escalation_steps must be a non-empty list"
        )
        for step in steps:
            assert isinstance(step, str) and step.strip(), (
                f"template '{scam_id}' has empty/non-string escalation step"
            )


def test_risk_rules_has_all_required_levels():
    rules = _load_rules()
    levels = {r["level"] for r in rules}
    for required_level in ("critical", "high", "medium"):
        assert required_level in levels, f"risk_rules.json missing level '{required_level}'"

    for rule in rules:
        rule_id = rule.get("level", "<unknown>")
        assert isinstance(rule.get("score"), int), (
            f"rule '{rule_id}' score must be int"
        )
        assert isinstance(rule.get("keywords"), list) and rule["keywords"] is not None, (
            f"rule '{rule_id}' keywords must be a list"
        )
        assert str(rule.get("action", "")).strip(), (
            f"rule '{rule_id}' missing action"
        )
        assert str(rule.get("message", "")).strip(), (
            f"rule '{rule_id}' missing message"
        )


def test_risk_rules_scores_are_ordered_correctly():
    rules = _load_rules()
    rules_by_level = {}
    for rule in rules:
        level = rule["level"]
        rules_by_level.setdefault(level, []).append(rule["score"])

    max_critical = max(rules_by_level["critical"])
    max_high = max(rules_by_level["high"])
    max_medium = max(rules_by_level["medium"])

    assert max_critical > max_high, (
        f"critical max score ({max_critical}) must exceed high max score ({max_high})"
    )
    assert max_high > max_medium, (
        f"high max score ({max_high}) must exceed medium max score ({max_medium})"
    )
