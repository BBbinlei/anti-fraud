"""Integration tests: service code against real data files (no mocking of file IO)."""

import json

import pytest

from config import (
    CHAT_FALLBACK_REPLY,
    CHROMA_DIR,
    FRAUD_TYPES,
    RAG_SIMILARITY_THRESHOLD,
    RISK_RULES_FILE,
    SCAM_CARDS_FILE,
)
from services import ai_service
from services.rule_engine import analyze_risk
from services.template_service import list_templates


def _load_real_rules():
    return json.loads(RISK_RULES_FILE.read_text(encoding="utf-8"))["rules"]


def _load_scam_cards_by_id():
    data = json.loads(SCAM_CARDS_FILE.read_text(encoding="utf-8"))
    return {card["id"]: card for card in data["scams"]}


def test_rule_engine_loads_real_risk_rules_and_hits_critical_keyword():
    real_rules = _load_real_rules()

    result = analyze_risk("我现在给你转账", real_rules)

    assert result.level == "critical", (
        f"Expected critical, got {result.level}. Keyword: '{result.matched_keyword}'"
    )


def test_rule_engine_loads_real_rules_for_all_fraud_type_keywords():
    real_rules = _load_real_rules()
    scam_cards = _load_scam_cards_by_id()

    # verify no exception for any real red_flag, and track total matches
    matched_types = []
    for fraud_type in FRAUD_TYPES:
        card = scam_cards[fraud_type]
        red_flags = card.get("red_flags", [])
        for flag in red_flags:
            result = analyze_risk(flag, real_rules)
            assert hasattr(result, "level"), f"analyze_risk returned non-RiskData for '{flag}'"
        if any(analyze_risk(flag, real_rules).level != "normal" for flag in red_flags):
            matched_types.append(fraud_type)

    assert matched_types, (
        "No fraud type has any red_flag matching a risk rule; "
        "check that risk_rules.json keywords align with scam_cards red_flags"
    )


def test_template_service_loads_real_files_for_all_fraud_types():
    templates = list_templates()

    assert len(templates) == len(FRAUD_TYPES), (
        f"Expected {len(FRAUD_TYPES)} templates, got {len(templates)}"
    )
    for tmpl in templates:
        assert tmpl.scam_name.strip(), f"Template {tmpl.scam_id} has empty scam_name"
        assert tmpl.opener.strip(), f"Template {tmpl.scam_id} has empty opener"


def test_ai_service_offline_fallback_works_for_all_fraud_types(monkeypatch):
    monkeypatch.setattr(ai_service, "DEEPSEEK_API_KEY", "")

    for scam_id in FRAUD_TYPES:
        reply = ai_service.get_scammer_reply(scam_id, [], "你好", [])
        assert reply != CHAT_FALLBACK_REPLY, (
            f"scam_id='{scam_id}' returned generic fallback; "
            "check that script_templates.json has an entry for this type"
        )
        assert reply.strip(), f"scam_id='{scam_id}' returned empty reply"


@pytest.mark.skipif(not CHROMA_DIR.exists(), reason="chroma_db 未构建，跳过真实向量检索测试")
def test_rag_retrieve_returns_relevant_result_for_real_query():
    from services.rag import retrieve

    results = retrieve("刷单垫付")

    assert len(results) >= 1, "Real Chroma query returned no results for '刷单垫付'"
    top = results[0]
    assert top["score"] >= RAG_SIMILARITY_THRESHOLD, (
        f"Top result score {top['score']} below threshold {RAG_SIMILARITY_THRESHOLD}"
    )
    assert top["metadata"].get("fraud_type") in FRAUD_TYPES, (
        f"metadata fraud_type '{top['metadata'].get('fraud_type')}' not in FRAUD_TYPES"
    )
