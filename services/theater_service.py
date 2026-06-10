"""Theater chat orchestration: rule engine → RAG → AI → DB."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from config import (
    FRAUD_TYPES,
    MAX_SCAM_ID_LEN,
    MAX_SESSION_ID_LEN,
    MAX_USER_INPUT_LLM,
    RISK_ACTION_BLOCK,
    SCAM_ID_EMPTY_ERROR_MESSAGE,
    SCAM_ID_INVALID_ERROR_MESSAGE,
    SESSION_ID_EMPTY_ERROR_MESSAGE,
)
from services import ai_service, db_service, rag
from services.rule_engine import analyze_risk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatData:
    scammer_reply: str | None
    risk_level: str
    risk_score: int
    risk_message: str
    interrupted: bool


def process_chat_message(
    session_id: str,
    message: str,
    history: list[dict[str, Any]],
    scam_id: str,
    risk_rules: list[dict[str, Any]],
) -> ChatData:
    safe_session_id = session_id.strip()[:MAX_SESSION_ID_LEN]
    safe_scam_id = scam_id.strip()[:MAX_SCAM_ID_LEN]
    if not safe_session_id:
        raise HTTPException(status_code=400, detail=SESSION_ID_EMPTY_ERROR_MESSAGE)
    if not safe_scam_id:
        raise HTTPException(status_code=400, detail=SCAM_ID_EMPTY_ERROR_MESSAGE)
    if safe_scam_id not in FRAUD_TYPES:
        raise HTTPException(status_code=400, detail=SCAM_ID_INVALID_ERROR_MESSAGE)

    safe_message = message[:MAX_USER_INPUT_LLM]
    risk = analyze_risk(safe_message, risk_rules)

    if risk.action == RISK_ACTION_BLOCK:
        return ChatData(
            scammer_reply=None,
            risk_level=risk.level,
            risk_score=risk.score,
            risk_message=risk.message,
            interrupted=True,
        )

    rag_contexts = rag.retrieve(safe_message)

    scammer_reply = ai_service.get_scammer_reply(
        scam_id=safe_scam_id,
        history=history,
        user_input=safe_message,
        rag_contexts=rag_contexts,
    )

    try:
        db_service.ensure_session(safe_session_id, safe_scam_id)
        db_service.save_message(safe_session_id, "user", safe_message, risk.level, risk.score)
    except Exception:
        logger.warning("DB save user message failed", exc_info=True)

    try:
        db_service.save_message(safe_session_id, "scammer", scammer_reply)
    except Exception:
        logger.warning("DB save scammer reply failed", exc_info=True)

    return ChatData(
        scammer_reply=scammer_reply,
        risk_level=risk.level,
        risk_score=risk.score,
        risk_message=risk.message,
        interrupted=False,
    )
