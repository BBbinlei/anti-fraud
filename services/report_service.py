"""Report submission business logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException

from config import (
    MAX_REPORT_CONTENT_LEN,
    MAX_REPORT_URL_LEN,
    MAX_SESSION_ID_LEN,
    REPORT_EMPTY_ERROR_MESSAGE,
    REPORT_RISK_LEVEL_INVALID_ERROR_MESSAGE,
    REPORT_SAVE_ERROR_MESSAGE,
    REPORT_STATUS_RECEIVED,
    REPORT_SUBMIT_SUCCESS_MESSAGE,
    RISK_LEVELS,
)
from services import db_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportData:
    report_id: str
    status: str
    message: str


def submit_report(
    session_id: str | None,
    content: str | None,
    url: str | None,
    risk_level: str | None = None,
) -> ReportData:
    safe_content = (content or "").strip()
    safe_url = (url or "").strip()
    safe_session_id = (session_id or "").strip()[:MAX_SESSION_ID_LEN] or None
    safe_risk_level = (risk_level or "").strip() or None
    if not safe_content and not safe_url:
        raise HTTPException(status_code=400, detail=REPORT_EMPTY_ERROR_MESSAGE)
    if safe_risk_level is not None and safe_risk_level not in RISK_LEVELS:
        raise HTTPException(status_code=400, detail=REPORT_RISK_LEVEL_INVALID_ERROR_MESSAGE)

    safe_content = safe_content[:MAX_REPORT_CONTENT_LEN]
    safe_url = safe_url[:MAX_REPORT_URL_LEN]

    try:
        report_id = db_service.save_report(
            session_id=safe_session_id,
            content=safe_content,
            url=safe_url,
            risk_level=safe_risk_level,
        )
    except Exception as exc:
        logger.warning("Report submission failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=REPORT_SAVE_ERROR_MESSAGE) from exc

    return ReportData(
        report_id=report_id,
        status=REPORT_STATUS_RECEIVED,
        message=REPORT_SUBMIT_SUCCESS_MESSAGE,
    )
