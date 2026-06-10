"""Gamification points, badge, and progress calculations."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException

from config import (
    DEFAULT_USER_PROGRESS_SCORE,
    DEFAULT_USER_PROGRESS_STREAK,
    DEFAULT_SCAM_COMPLETION_COUNT,
    FRAUD_TYPES,
    GAMIFICATION_BADGES,
    GAMIFICATION_ALREADY_CLAIMED_MESSAGE,
    GAMIFICATION_COMPLETE_SUCCESS_MESSAGE,
    GAMIFICATION_POINTS_PER_COMPLETION,
    GAMIFICATION_STATUS_ALREADY_CLAIMED,
    GAMIFICATION_STATUS_COMPLETED,
    GAMIFICATION_STREAK_INCREMENT,
    MAX_SCAM_ID_LEN,
    MAX_SESSION_ID_LEN,
    MAX_USER_ID_LEN,
    SCAM_ID_EMPTY_ERROR_MESSAGE,
    SCAM_ID_INVALID_ERROR_MESSAGE,
    USER_ID_EMPTY_ERROR_MESSAGE,
    USER_PROGRESS_LOAD_ERROR_MESSAGE,
    USER_PROGRESS_SAVE_ERROR_MESSAGE,
)
from services import db_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserProgressData:
    user_id: str
    total_score: int
    streak: int
    badges: list[str]
    completed: dict[str, int]


@dataclass(frozen=True)
class CompleteScenarioData:
    user_id: str
    total_score: int
    streak: int
    badges: list[str]
    completed: dict[str, int]
    score_added: int
    new_badges: list[str]
    status: str
    message: str
    already_claimed: bool = False


def get_progress(user_id: str | None) -> UserProgressData:
    safe_user_id = _normalize_user_id(user_id)
    try:
        stored_progress = db_service.get_user_progress(safe_user_id)
    except Exception as exc:
        logger.warning("User progress load failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=USER_PROGRESS_LOAD_ERROR_MESSAGE) from exc

    if stored_progress is None:
        return _empty_progress(safe_user_id)

    return _normalize_progress(stored_progress, safe_user_id)


def complete_scenario(
    user_id: str | None,
    scam_id: str | None,
    session_id: str | None = None,
) -> CompleteScenarioData:
    safe_user_id = _normalize_user_id(user_id)
    safe_scam_id = _normalize_scam_id(scam_id)
    safe_session_id = _normalize_optional_session_id(session_id)
    current_progress = get_progress(safe_user_id)

    if safe_session_id is not None:
        try:
            claim_created = db_service.claim_completion(
                user_id=safe_user_id,
                session_id=safe_session_id,
                scam_id=safe_scam_id,
            )
        except Exception as exc:
            logger.warning("Completion claim failed: %s", type(exc).__name__)
            raise HTTPException(status_code=500, detail=USER_PROGRESS_SAVE_ERROR_MESSAGE) from exc
        if not claim_created:
            return _already_claimed_result(current_progress)

    completed = dict(current_progress.completed)
    completed[safe_scam_id] = completed.get(safe_scam_id, 0) + 1
    total_score = current_progress.total_score + GAMIFICATION_POINTS_PER_COMPLETION
    streak = current_progress.streak + GAMIFICATION_STREAK_INCREMENT
    badges = _award_badges(
        existing_badges=current_progress.badges,
        total_score=total_score,
        completed=completed,
    )
    new_badges = [badge for badge in badges if badge not in current_progress.badges]

    try:
        db_service.save_user_progress(
            user_id=safe_user_id,
            total_score=total_score,
            streak=streak,
            badges=badges,
            completed=completed,
        )
    except Exception as exc:
        logger.warning("User progress save failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=USER_PROGRESS_SAVE_ERROR_MESSAGE) from exc

    return CompleteScenarioData(
        user_id=safe_user_id,
        total_score=total_score,
        streak=streak,
        badges=badges,
        completed=completed,
        score_added=GAMIFICATION_POINTS_PER_COMPLETION,
        new_badges=new_badges,
        status=GAMIFICATION_STATUS_COMPLETED,
        message=GAMIFICATION_COMPLETE_SUCCESS_MESSAGE,
    )


def _normalize_user_id(user_id: str | None) -> str:
    safe_user_id = (user_id or "").strip()[:MAX_USER_ID_LEN]
    if not safe_user_id:
        raise HTTPException(status_code=400, detail=USER_ID_EMPTY_ERROR_MESSAGE)
    return safe_user_id


def _normalize_scam_id(scam_id: str | None) -> str:
    safe_scam_id = (scam_id or "").strip()[:MAX_SCAM_ID_LEN]
    if not safe_scam_id:
        raise HTTPException(status_code=400, detail=SCAM_ID_EMPTY_ERROR_MESSAGE)
    if safe_scam_id not in FRAUD_TYPES:
        raise HTTPException(status_code=400, detail=SCAM_ID_INVALID_ERROR_MESSAGE)
    return safe_scam_id


def _normalize_optional_session_id(session_id: str | None) -> str | None:
    safe_session_id = (session_id or "").strip()[:MAX_SESSION_ID_LEN]
    return safe_session_id or None


def _empty_progress(user_id: str) -> UserProgressData:
    return UserProgressData(
        user_id=user_id,
        total_score=DEFAULT_USER_PROGRESS_SCORE,
        streak=DEFAULT_USER_PROGRESS_STREAK,
        badges=[],
        completed={},
    )


def _already_claimed_result(progress: UserProgressData) -> CompleteScenarioData:
    return CompleteScenarioData(
        user_id=progress.user_id,
        total_score=progress.total_score,
        streak=progress.streak,
        badges=progress.badges,
        completed=progress.completed,
        score_added=0,
        new_badges=[],
        status=GAMIFICATION_STATUS_ALREADY_CLAIMED,
        message=GAMIFICATION_ALREADY_CLAIMED_MESSAGE,
        already_claimed=True,
    )


def _normalize_progress(progress: dict, user_id: str) -> UserProgressData:
    badges = progress.get("badges")
    completed = progress.get("completed")
    return UserProgressData(
        user_id=user_id,
        total_score=max(
            _safe_int(progress.get("total_score"), DEFAULT_USER_PROGRESS_SCORE),
            DEFAULT_USER_PROGRESS_SCORE,
        ),
        streak=max(
            _safe_int(progress.get("streak"), DEFAULT_USER_PROGRESS_STREAK),
            DEFAULT_USER_PROGRESS_STREAK,
        ),
        badges=list(badges) if isinstance(badges, list) else [],
        completed=_normalize_completed(completed),
    )


def _normalize_completed(completed: object) -> dict[str, int]:
    if not isinstance(completed, dict):
        return {}
    normalized = {}
    for scam_id, count in completed.items():
        if scam_id in FRAUD_TYPES:
            normalized[scam_id] = max(
                _safe_int(count, DEFAULT_SCAM_COMPLETION_COUNT),
                DEFAULT_SCAM_COMPLETION_COUNT,
            )
    return normalized


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _award_badges(
    existing_badges: list[str],
    total_score: int,
    completed: dict[str, int],
) -> list[str]:
    badges = list(dict.fromkeys(existing_badges))
    completed_total = sum(completed.values())
    unique_scam_types = len([scam_id for scam_id, count in completed.items() if count > 0])

    for badge in GAMIFICATION_BADGES:
        badge_id = str(badge["id"])
        if badge_id in badges:
            continue
        if (
            total_score >= int(badge["min_score"])
            and completed_total >= int(badge["min_completed_total"])
            and unique_scam_types >= int(badge["min_unique_scam_types"])
        ):
            badges.append(badge_id)

    return badges
