"""Script template loading for theater scenario selection."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from fastapi import HTTPException

from config import FRAUD_TYPES, SCAM_CARDS_FILE, SCRIPT_TEMPLATES_FILE, TEMPLATE_LOAD_ERROR_MESSAGE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TheaterTemplateData:
    scam_id: str
    scam_name: str
    target: str
    difficulty: int
    opener: str
    persona: str
    escalation_steps: list[str]
    red_flags: list[str]
    prevention: list[str]


def list_templates() -> list[TheaterTemplateData]:
    try:
        with open(SCRIPT_TEMPLATES_FILE, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning("Script template load failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=TEMPLATE_LOAD_ERROR_MESSAGE) from exc

    templates = payload.get("templates", [])
    if not isinstance(templates, list):
        return []

    scam_cards = _load_scam_cards()
    normalized = [_normalize_template(template, scam_cards) for template in templates]
    return [template for template in normalized if template is not None]


def _load_scam_cards() -> dict[str, dict]:
    try:
        with open(SCAM_CARDS_FILE, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning("Scam card summary load failed for templates: %s", type(exc).__name__)
        return {}

    scams = payload.get("scams", [])
    if not isinstance(scams, list):
        return {}
    return {
        str(card.get("id", "")).strip(): card
        for card in scams
        if isinstance(card, dict) and str(card.get("id", "")).strip() in FRAUD_TYPES
    }


def _normalize_template(template: object, scam_cards: dict[str, dict]) -> TheaterTemplateData | None:
    if not isinstance(template, dict):
        return None

    scam_id = str(template.get("scam_id", "")).strip()
    if scam_id not in FRAUD_TYPES:
        return None

    escalation_steps = template.get("escalation_steps", [])
    if not isinstance(escalation_steps, list):
        escalation_steps = []
    scam_card = scam_cards.get(scam_id, {})

    return TheaterTemplateData(
        scam_id=scam_id,
        scam_name=str(scam_card.get("name", scam_id)).strip(),
        target=str(scam_card.get("target", "")).strip(),
        difficulty=max(_safe_int(template.get("difficulty"), 1), 1),
        opener=str(template.get("opener", "")).strip(),
        persona=str(template.get("persona", "")).strip(),
        escalation_steps=[str(step).strip() for step in escalation_steps if str(step).strip()],
        red_flags=_as_string_list(scam_card.get("red_flags"))[:4],
        prevention=_as_string_list(scam_card.get("prevention"))[:2],
    )


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
