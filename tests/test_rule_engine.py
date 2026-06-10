from config import (
    DEFAULT_MATCHED_KEYWORD,
    DEFAULT_RISK_ACTION,
    DEFAULT_RISK_LEVEL,
    DEFAULT_RISK_MESSAGE,
    DEFAULT_RISK_SCORE,
    RISK_ACTION_BLOCK,
    RISK_ACTION_HINT,
    RISK_ACTION_PRAISE,
    RISK_ACTION_WARN,
)
from services.rule_engine import RiskData, analyze_risk


RULES = [
    {
        "level": "medium",
        "score": 40,
        "keywords": ["兼职", "返利"],
        "action": RISK_ACTION_HINT,
        "message": "medium message",
    },
    {
        "level": "critical",
        "score": 90,
        "keywords": ["转账", "付款码"],
        "action": RISK_ACTION_BLOCK,
        "message": "critical message",
    },
    {
        "level": "high",
        "score": 70,
        "keywords": ["验证码", "保证金"],
        "action": RISK_ACTION_WARN,
        "message": "high message",
    },
    {
        "level": "safe",
        "score": 0,
        "keywords": ["我要报警"],
        "action": RISK_ACTION_PRAISE,
        "message": "safe message",
    },
]


def test_critical_block_wins_over_lower_score_match():
    result = analyze_risk("这个兼职返利不错，我现在给你转账", RULES)

    assert result == RiskData(
        level="critical",
        score=90,
        action=RISK_ACTION_BLOCK,
        message="critical message",
        matched_keyword="转账",
    )


def test_high_warning_match():
    result = analyze_risk("对方要求我提供验证码才能继续", RULES)

    assert result.level == "high"
    assert result.score == 70
    assert result.action == RISK_ACTION_WARN
    assert result.matched_keyword == "验证码"


def test_medium_hint_match():
    result = analyze_risk("有人说可以做兼职日结", RULES)

    assert result.level == "medium"
    assert result.score == 40
    assert result.action == RISK_ACTION_HINT
    assert result.matched_keyword == "兼职"


def test_safe_praise_match():
    result = analyze_risk("我要报警，我要先核实", RULES)

    assert result.level == "safe"
    assert result.score == 0
    assert result.action == RISK_ACTION_PRAISE
    assert result.matched_keyword == "我要报警"


def test_empty_input_returns_default_normal():
    result = analyze_risk("   ", RULES)

    assert result == RiskData(
        level=DEFAULT_RISK_LEVEL,
        score=DEFAULT_RISK_SCORE,
        action=DEFAULT_RISK_ACTION,
        message=DEFAULT_RISK_MESSAGE,
        matched_keyword=DEFAULT_MATCHED_KEYWORD,
    )


def test_no_match_returns_default_normal():
    result = analyze_risk("今天只是普通聊天", RULES)

    assert result.level == DEFAULT_RISK_LEVEL
    assert result.score == DEFAULT_RISK_SCORE
    assert result.action == DEFAULT_RISK_ACTION
    assert result.matched_keyword == DEFAULT_MATCHED_KEYWORD


def test_unsorted_rules_still_use_score_priority():
    rules = [
        {
            "level": "medium",
            "score": 40,
            "keywords": ["验证码"],
            "action": RISK_ACTION_HINT,
            "message": "medium message",
        },
        {
            "level": "high",
            "score": 70,
            "keywords": ["验证码"],
            "action": RISK_ACTION_WARN,
            "message": "high message",
        },
    ]

    result = analyze_risk("验证码发给你可以吗", rules)

    assert result.level == "high"
    assert result.action == RISK_ACTION_WARN


def test_malformed_rules_and_non_string_input_do_not_raise():
    malformed_rules = [
        "bad rule",
        {"score": "not-an-int", "keywords": "验证码"},
        {"level": "high", "score": "70", "keywords": [None, "验证码"], "action": RISK_ACTION_WARN},
    ]

    assert analyze_risk(None, malformed_rules).level == DEFAULT_RISK_LEVEL

    result = analyze_risk("验证码", malformed_rules)

    assert result.level == "high"
    assert result.score == 70
    assert result.action == RISK_ACTION_WARN
    assert result.message == DEFAULT_RISK_MESSAGE
