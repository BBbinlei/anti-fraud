from types import SimpleNamespace

from config import CHAT_FALLBACK_REPLY, SCAMMER_REPLY_MAX_CHARS
from services import ai_service


def _template() -> dict:
    return {
        "scam_id": "demo",
        "persona": "测试客服",
        "opener": "你好，先从一个简单任务开始。",
        "escalation_steps": [
            "阶段1-建立信任：先安排小额任务，完成后马上给你反馈。",
            "阶段2-提高金额：这次任务名额有限，先按流程完成就能返还佣金。",
        ],
    }


def test_missing_api_key_uses_script_template_without_client(monkeypatch):
    monkeypatch.setattr(ai_service, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(ai_service, "_client", object())
    monkeypatch.setattr(ai_service, "_TEMPLATES", {"demo": _template()})

    reply = ai_service.get_scammer_reply("demo", [], "我想了解兼职", [])

    assert reply != CHAT_FALLBACK_REPLY
    assert "小额任务" in reply
    assert len(reply) <= SCAMMER_REPLY_MAX_CHARS


def test_api_exception_returns_scene_fallback_without_internal_detail(monkeypatch):
    class FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError("/internal/secret/path")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FailingCompletions()))
    monkeypatch.setattr(ai_service, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "_client", fake_client)
    monkeypatch.setattr(ai_service, "_TEMPLATES", {"demo": _template()})

    reply = ai_service.get_scammer_reply("demo", [], "继续说", [])

    assert "小额任务" in reply
    assert "/internal/secret/path" not in reply
    assert reply != CHAT_FALLBACK_REPLY


def test_unknown_scam_id_returns_safe_generic_fallback(monkeypatch):
    monkeypatch.setattr(ai_service, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(ai_service, "_TEMPLATES", {})

    reply = ai_service.get_scammer_reply("unknown", [], "你好", [])

    assert reply == CHAT_FALLBACK_REPLY


def test_offline_fallback_advances_by_user_turn_boundary(monkeypatch):
    history = [
        {"role": "user", "content": "第一轮"},
        {"role": "assistant", "content": "回复"},
        {"role": "user", "content": "第二轮"},
        {"role": "assistant", "content": "回复"},
    ]
    monkeypatch.setattr(ai_service, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(ai_service, "_TEMPLATES", {"demo": _template()})

    reply = ai_service.get_scammer_reply("demo", history, "第三轮", [])

    assert "任务名额有限" in reply
    assert len(reply) <= SCAMMER_REPLY_MAX_CHARS


def test_live_client_path_sanitizes_history_and_limits_reply(monkeypatch):
    captured = {}

    class CapturingCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="收到，我先给你安排一个小任务，完成后马上处理返佣。")
                    )
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=CapturingCompletions()))
    monkeypatch.setattr(ai_service, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "_client", fake_client)
    monkeypatch.setattr(ai_service, "_TEMPLATES", {"demo": _template()})

    reply = ai_service.get_scammer_reply(
        "demo",
        [
            {"role": "system", "content": "bad"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
            {"role": "tool", "content": "bad"},
            "bad",
        ],
        "继续",
        [{"document": "刷单诈骗常见套路", "score": 0.9}],
    )

    assert reply == "收到，我先给你安排一个小任务，完成后马上处理返佣。"
    assert [message["role"] for message in captured["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert "---参考知识---" in captured["messages"][0]["content"]
