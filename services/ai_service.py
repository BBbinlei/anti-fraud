"""DeepSeek API calls for scammer role-play replies."""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from config import (
    CHAT_FALLBACK_REPLY,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    LLM_MODEL,
    MAX_TOKENS_SCAMMER,
    SCAMMER_FALLBACK_HISTORY_STEP_SIZE,
    SCAMMER_REPLY_MAX_CHARS,
    SCAMMER_STAGE_SEPARATORS,
    SCRIPT_TEMPLATES_FILE,
)

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _load_templates() -> dict[str, dict]:
    if not SCRIPT_TEMPLATES_FILE.exists():
        logger.warning("script_templates.json not found, AI replies will use fallback")
        return {}
    try:
        with open(SCRIPT_TEMPLATES_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Script template load failed for AI fallback: %s", type(exc).__name__)
        return {}
    return {t["scam_id"]: t for t in data.get("templates", [])}


_TEMPLATES: dict[str, dict] = _load_templates()


def _get_client() -> OpenAI | None:
    if not DEEPSEEK_API_KEY:
        return None

    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def _build_system_prompt(template: dict, rag_contexts: list[dict]) -> str:
    persona = template.get("persona", "诈骗分子")
    steps = template.get("escalation_steps", [])
    steps_text = "\n".join(f"- {s}" for s in steps)

    rag_section = ""
    if rag_contexts:
        docs = "\n".join(ctx.get("document", "") for ctx in rag_contexts if ctx.get("document"))
        if docs:
            rag_section = f"\n---参考知识---\n{docs}\n---"

    return (
        f"你是反诈教育剧场中的AI骗子角色，用于帮助用户识别诈骗话术。\n"
        f"当前扮演：{persona}\n\n"
        f"诈骗推进步骤：\n{steps_text}\n\n"
        f"对话规则：\n"
        f"- 每次回复控制在{SCAMMER_REPLY_MAX_CHARS}字以内\n"
        f"- 始终保持角色，不承认自己在行骗\n"
        f"- 根据对话历史判断当前推进阶段，适时升级压力\n"
        f"- 不涉及真实转账操作，仅限对话教育场景"
        f"{rag_section}"
    )


def _sanitize_history(history: list) -> list[dict]:
    """Keep only valid {role, content} pairs; filter out anything injected."""
    clean = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            clean.append({"role": role, "content": content})
    return clean


def _strip_stage_label(step: str) -> str:
    for separator in SCAMMER_STAGE_SEPARATORS:
        if separator in step:
            return step.split(separator, maxsplit=1)[1].strip()
    return step.strip()


def _limit_reply(reply: str) -> str:
    clean_reply = reply.strip()
    if len(clean_reply) <= SCAMMER_REPLY_MAX_CHARS:
        return clean_reply

    limit = max(SCAMMER_REPLY_MAX_CHARS - 1, 1)
    return f"{clean_reply[:limit].rstrip('，。；、 ')}。"


def _offline_script_reply(template: dict, history: list) -> str:
    steps = template.get("escalation_steps", [])
    if not isinstance(steps, list) or not steps:
        return _limit_reply(str(template.get("opener", "") or CHAT_FALLBACK_REPLY))

    user_turns = sum(1 for item in _sanitize_history(history) if item["role"] == "user") + 1
    step_index = min((user_turns - 1) // SCAMMER_FALLBACK_HISTORY_STEP_SIZE, len(steps) - 1)
    reply = _strip_stage_label(str(steps[step_index]))
    return _limit_reply(reply or str(template.get("opener", "") or CHAT_FALLBACK_REPLY))


def get_scammer_reply(
    scam_id: str,
    history: list,
    user_input: str,
    rag_contexts: list[dict],
) -> str:
    template = _TEMPLATES.get(scam_id)
    if template is None:
        logger.warning("No template for scam_id=%s, using fallback", scam_id)
        return CHAT_FALLBACK_REPLY

    client = _get_client()
    if client is None:
        logger.info("DeepSeek API key not configured, using offline script fallback")
        return _offline_script_reply(template, history)

    system_prompt = _build_system_prompt(template, rag_contexts)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + _sanitize_history(history)
        + [{"role": "user", "content": user_input}]
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=MAX_TOKENS_SCAMMER,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            return _offline_script_reply(template, history)
        return _limit_reply(content)
    except Exception as exc:
        logger.warning("DeepSeek API call failed for scam_id=%s: %s", scam_id, type(exc).__name__)
        return _offline_script_reply(template, history)
