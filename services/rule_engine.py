"""Pure risk rule matching for theater safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import (
    DEFAULT_MATCHED_KEYWORD,
    DEFAULT_RISK_ACTION,
    DEFAULT_RISK_LEVEL,
    DEFAULT_RISK_MESSAGE,
    DEFAULT_RISK_SCORE,
)


@dataclass(frozen=True)
class RiskData:
    level: str
    score: int
    action: str
    message: str
    matched_keyword: str = DEFAULT_MATCHED_KEYWORD


def analyze_risk(message: str, rules: list[dict[str, Any]] | None = None) -> RiskData:
    """Return the highest-scoring matching risk rule.

    The function is intentionally free of file, database, network, and SDK IO.
    Callers should load data/risk_rules.json outside this service.
    """
    text = _normalize_text(message)
    if not text:
        return _default_risk()

    for rule in _sorted_rules(rules):
        keyword = _first_matching_keyword(text, rule.get("keywords", []))
        if keyword:
            return RiskData(
                level=str(rule.get("level", DEFAULT_RISK_LEVEL)),
                score=_safe_int(rule.get("score"), DEFAULT_RISK_SCORE),
                action=str(rule.get("action", DEFAULT_RISK_ACTION)),
                message=str(rule.get("message", DEFAULT_RISK_MESSAGE)),
                matched_keyword=keyword,
            )

    return _default_risk()


def _normalize_text(message: object) -> str:
    if not isinstance(message, str):
        return ""
    return message.strip().casefold()


def _sorted_rules(rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not rules:
        return []
    return sorted(
        (rule for rule in rules if isinstance(rule, dict)),
        key=lambda rule: _safe_int(rule.get("score"), DEFAULT_RISK_SCORE),
        reverse=True,
    )


def _first_matching_keyword(text: str, keywords: object) -> str:
    if not isinstance(keywords, list):
        return DEFAULT_MATCHED_KEYWORD
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
        normalized_keyword = keyword.strip().casefold()
        if normalized_keyword and normalized_keyword in text:
            return keyword
    return DEFAULT_MATCHED_KEYWORD


def _default_risk() -> RiskData:
    return RiskData(
        level=DEFAULT_RISK_LEVEL,
        score=DEFAULT_RISK_SCORE,
        action=DEFAULT_RISK_ACTION,
        message=DEFAULT_RISK_MESSAGE,
    )


def _safe_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
