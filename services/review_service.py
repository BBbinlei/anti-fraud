"""Fallback reveal and review report generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from fastapi import HTTPException

from config import (
    DEFAULT_RISK_LEVEL,
    FRAUD_TYPES,
    MAX_SCAM_ID_LEN,
    MAX_SESSION_ID_LEN,
    REVIEW_CARDS_FILE,
    REVIEW_GENERATE_ERROR_MESSAGE,
    SCAM_CARD_LOAD_ERROR_MESSAGE,
    SCAM_ID_EMPTY_ERROR_MESSAGE,
    SCAM_ID_INVALID_ERROR_MESSAGE,
    SCAM_CARDS_FILE,
    SESSION_ID_EMPTY_ERROR_MESSAGE,
)
from services import db_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewReportData:
    session_id: str
    scam_id: str
    scam_name: str
    summary: str
    conversation_turns: int
    highest_risk_level: str
    highest_risk_score: int
    tactics: list[str]
    red_flags: list[str]
    prevention: list[str]
    legal: str
    typical_case: str
    review_title: str
    review_content: str
    key_takeaways: list[str]


def generate_review_report(session_id: str | None, scam_id: str | None) -> ReviewReportData:
    safe_session_id = _normalize_session_id(session_id)
    safe_scam_id = _normalize_scam_id(scam_id)
    scam_card = _load_scam_card(safe_scam_id)
    review_card = _load_review_card(safe_scam_id)

    try:
        messages = db_service.get_session_messages(safe_session_id)
    except Exception as exc:
        logger.warning("Session messages load failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=REVIEW_GENERATE_ERROR_MESSAGE) from exc

    highest_risk_score = max(
        [_safe_int(message.get("risk_score"), 0) for message in messages],
        default=0,
    )
    highest_risk_level = _highest_risk_level(messages)
    conversation_turns = len(messages)
    red_flags = _select_red_flags(scam_card, messages)
    tactics = _as_string_list(scam_card.get("tactics"))
    prevention = _as_string_list(scam_card.get("prevention"))

    return ReviewReportData(
        session_id=safe_session_id,
        scam_id=safe_scam_id,
        scam_name=str(scam_card.get("name", safe_scam_id)),
        summary=_build_summary(scam_card, conversation_turns, highest_risk_level, highest_risk_score),
        conversation_turns=conversation_turns,
        highest_risk_level=highest_risk_level,
        highest_risk_score=highest_risk_score,
        tactics=tactics,
        red_flags=red_flags,
        prevention=prevention,
        legal=str(scam_card.get("legal", "")),
        typical_case=str(scam_card.get("typical_case", "")),
        review_title=str(review_card.get("title", "")),
        review_content=str(review_card.get("content", "")),
        key_takeaways=_build_takeaways(red_flags, prevention),
    )


def _normalize_session_id(session_id: str | None) -> str:
    safe_session_id = (session_id or "").strip()[:MAX_SESSION_ID_LEN]
    if not safe_session_id:
        raise HTTPException(status_code=400, detail=SESSION_ID_EMPTY_ERROR_MESSAGE)
    return safe_session_id


def _normalize_scam_id(scam_id: str | None) -> str:
    safe_scam_id = (scam_id or "").strip()[:MAX_SCAM_ID_LEN]
    if not safe_scam_id:
        raise HTTPException(status_code=400, detail=SCAM_ID_EMPTY_ERROR_MESSAGE)
    if safe_scam_id not in FRAUD_TYPES:
        raise HTTPException(status_code=400, detail=SCAM_ID_INVALID_ERROR_MESSAGE)
    return safe_scam_id


def _load_scam_card(scam_id: str) -> dict:
    try:
        with open(SCAM_CARDS_FILE, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning("Scam cards load failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=SCAM_CARD_LOAD_ERROR_MESSAGE) from exc

    for scam_card in payload.get("scams", []):
        if isinstance(scam_card, dict) and scam_card.get("id") == scam_id:
            return scam_card
    return {"id": scam_id, "name": scam_id}


def _load_review_card(scam_id: str) -> dict:
    try:
        with open(REVIEW_CARDS_FILE, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning("Review cards load failed: %s", type(exc).__name__)
        return {}

    for review_card in payload.get("cards", []):
        if isinstance(review_card, dict) and review_card.get("fraud_type") == scam_id:
            return review_card
    return {}


def _highest_risk_level(messages: list[dict]) -> str:
    ranked_levels = [
        (message.get("risk_level"), _safe_int(message.get("risk_score"), 0))
        for message in messages
        if message.get("risk_level")
    ]
    if not ranked_levels:
        return DEFAULT_RISK_LEVEL
    return max(ranked_levels, key=lambda item: item[1])[0]


def _select_red_flags(scam_card: dict, messages: list[dict]) -> list[str]:
    red_flags = _as_string_list(scam_card.get("red_flags"))
    combined_text = " ".join(str(message.get("content", "")) for message in messages)
    matched = [flag for flag in red_flags if flag and flag in combined_text]
    return matched or red_flags[:3]


def _build_summary(
    scam_card: dict,
    conversation_turns: int,
    highest_risk_level: str,
    highest_risk_score: int,
) -> str:
    scam_name = str(scam_card.get("name", scam_card.get("id", "")))
    return (
        f"本次剧场围绕{scam_name}展开，共记录{conversation_turns}条对话；"
        f"最高风险等级为{highest_risk_level}，风险分数为{highest_risk_score}。"
    )


def _build_takeaways(red_flags: list[str], prevention: list[str]) -> list[str]:
    takeaways = []
    if red_flags:
        takeaways.append(f"重点识别信号：{red_flags[0]}")
    takeaways.extend(prevention[:2])
    return takeaways


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
