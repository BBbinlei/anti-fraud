from fastapi.testclient import TestClient

from config import (
    CHAT_FALLBACK_REPLY,
    MAX_SESSION_ID_LEN,
    MAX_USER_INPUT_LLM,
    RISK_ACTION_BLOCK,
    RISK_ACTION_HINT,
    SCAM_ID_EMPTY_ERROR_MESSAGE,
    SCAM_ID_INVALID_ERROR_MESSAGE,
    SCAMMER_REPLY_MAX_CHARS,
    SESSION_ID_EMPTY_ERROR_MESSAGE,
)
from main import app
from services import theater_service


def _payload(message: str, session_id: str = "session-1", scam_id: str = "shuadan") -> dict:
    return {
        "session_id": session_id,
        "message": message,
        "history": [],
        "scam_id": scam_id,
    }


def _force_offline_ai(monkeypatch):
    monkeypatch.setattr(theater_service.ai_service, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(theater_service.ai_service, "_client", None)


def test_theater_chat_blocks_critical_risk():
    with TestClient(app) as client:
        response = client.post("/theater/chat", json=_payload("我现在给你转账"))

    assert response.status_code == 200
    data = response.json()
    assert data["scammer_reply"] is None
    assert data["risk_level"] == "critical"
    assert data["risk_score"] == 90
    assert "转账" in data["risk_message"] or "付款" in data["risk_message"]
    assert data["interrupted"] is True


def test_theater_chat_returns_scene_fallback_for_non_block_risk(monkeypatch):
    _force_offline_ai(monkeypatch)

    with TestClient(app) as client:
        response = client.post("/theater/chat", json=_payload("有人邀请我做兼职返利"))

    assert response.status_code == 200
    data = response.json()
    assert data["scammer_reply"] != CHAT_FALLBACK_REPLY
    assert "小额任务" in data["scammer_reply"]
    assert len(data["scammer_reply"]) <= SCAMMER_REPLY_MAX_CHARS
    assert data["risk_level"] == "medium"
    assert data["risk_score"] == 40
    assert data["interrupted"] is False


def test_theater_chat_rejects_empty_session_id():
    with TestClient(app) as client:
        response = client.post("/theater/chat", json=_payload("普通聊天", session_id=" "))

    assert response.status_code == 400
    assert response.json() == {"detail": SESSION_ID_EMPTY_ERROR_MESSAGE}


def test_theater_chat_rejects_empty_scam_id():
    with TestClient(app) as client:
        response = client.post("/theater/chat", json=_payload("普通聊天", scam_id=" "))

    assert response.status_code == 400
    assert response.json() == {"detail": SCAM_ID_EMPTY_ERROR_MESSAGE}


def test_theater_chat_rejects_unknown_scam_id_before_rag_or_ai():
    with TestClient(app) as client:
        response = client.post("/theater/chat", json=_payload("普通聊天", scam_id="unknown"))

    assert response.status_code == 400
    assert response.json() == {"detail": SCAM_ID_INVALID_ERROR_MESSAGE}


def test_theater_chat_analyzes_truncated_message(monkeypatch):
    _force_offline_ai(monkeypatch)
    long_prefix = "普通内容" * MAX_USER_INPUT_LLM
    message = f"{long_prefix}我现在给你转账"

    with TestClient(app) as client:
        response = client.post("/theater/chat", json=_payload(message))

    assert response.status_code == 200
    data = response.json()
    assert data["scammer_reply"] != CHAT_FALLBACK_REPLY
    assert "小额任务" in data["scammer_reply"]
    assert data["risk_level"] == "normal"
    assert data["interrupted"] is False


def test_blocked_service_path_skips_db_rag_and_ai(monkeypatch):
    calls = []

    def fail_if_called(name):
        def _fail(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not be called for BLOCK")

        return _fail

    monkeypatch.setattr(theater_service.db_service, "ensure_session", fail_if_called("ensure_session"))
    monkeypatch.setattr(theater_service.db_service, "save_message", fail_if_called("save_message"))
    monkeypatch.setattr(theater_service.rag, "retrieve", fail_if_called("rag.retrieve"))
    monkeypatch.setattr(
        theater_service.ai_service,
        "get_scammer_reply",
        fail_if_called("ai_service.get_scammer_reply"),
    )

    result = theater_service.process_chat_message(
        session_id="session-block",
        message="我准备给你转账",
        history=[],
        scam_id="shuadan",
        risk_rules=[
            {
                "level": "critical",
                "score": 90,
                "keywords": ["转账"],
                "action": RISK_ACTION_BLOCK,
                "message": "blocked",
            }
        ],
    )

    assert result.interrupted is True
    assert result.scammer_reply is None
    assert result.risk_level == "critical"
    assert calls == []


def test_unknown_scam_id_service_path_skips_db_rag_and_ai(monkeypatch):
    calls = []

    def fail_if_called(name):
        def _fail(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not be called for invalid scam_id")

        return _fail

    monkeypatch.setattr(theater_service.db_service, "ensure_session", fail_if_called("ensure_session"))
    monkeypatch.setattr(theater_service.db_service, "save_message", fail_if_called("save_message"))
    monkeypatch.setattr(theater_service.rag, "retrieve", fail_if_called("rag.retrieve"))
    monkeypatch.setattr(
        theater_service.ai_service,
        "get_scammer_reply",
        fail_if_called("ai_service.get_scammer_reply"),
    )

    try:
        theater_service.process_chat_message(
            session_id="session-invalid",
            message="普通聊天",
            history=[],
            scam_id="unknown",
            risk_rules=[],
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert getattr(exc, "detail", None) == SCAM_ID_INVALID_ERROR_MESSAGE
    else:
        raise AssertionError("invalid scam_id should raise HTTPException")

    assert calls == []


def test_non_block_service_path_calls_rag_ai_then_db_with_truncated_input(monkeypatch):
    calls = []
    message = "兼职" + ("长" * MAX_USER_INPUT_LLM)
    expected_safe_message = message[:MAX_USER_INPUT_LLM]
    history = [{"role": "user", "content": "你好"}]
    rag_contexts = [{"document": "刷单返利案例", "score": 0.9}]

    def fake_ensure_session(session_id, scam_id):
        calls.append(("ensure_session", session_id, scam_id))

    def fake_save_message(session_id, role, content, risk_level=None, risk_score=None):
        calls.append(("save_message", session_id, role, content, risk_level, risk_score))

    def fake_retrieve(query):
        calls.append(("rag.retrieve", query))
        return rag_contexts

    def fake_get_scammer_reply(scam_id, history, user_input, rag_contexts):
        calls.append(("ai_service.get_scammer_reply", scam_id, history, user_input, rag_contexts))
        return "mock scammer reply"

    monkeypatch.setattr(theater_service.db_service, "ensure_session", fake_ensure_session)
    monkeypatch.setattr(theater_service.db_service, "save_message", fake_save_message)
    monkeypatch.setattr(theater_service.rag, "retrieve", fake_retrieve)
    monkeypatch.setattr(theater_service.ai_service, "get_scammer_reply", fake_get_scammer_reply)

    result = theater_service.process_chat_message(
        session_id="session-ok",
        message=message,
        history=history,
        scam_id="shuadan",
        risk_rules=[
            {
                "level": "medium",
                "score": 40,
                "keywords": ["兼职"],
                "action": RISK_ACTION_HINT,
                "message": "hint",
            }
        ],
    )

    assert result.scammer_reply == "mock scammer reply"
    assert result.interrupted is False
    assert calls == [
        ("rag.retrieve", expected_safe_message),
        ("ai_service.get_scammer_reply", "shuadan", history, expected_safe_message, rag_contexts),
        ("ensure_session", "session-ok", "shuadan"),
        ("save_message", "session-ok", "user", expected_safe_message, "medium", 40),
        ("save_message", "session-ok", "scammer", "mock scammer reply", None, None),
    ]


def test_non_block_service_path_uses_normalized_ids(monkeypatch):
    calls = []
    long_session_id = f"{'s' * (MAX_SESSION_ID_LEN + 5)}"

    def fake_ensure_session(session_id, scam_id):
        calls.append(("ensure_session", session_id, scam_id))

    def fake_save_message(session_id, role, content, risk_level=None, risk_score=None):
        calls.append(("save_message", session_id, role, content, risk_level, risk_score))

    monkeypatch.setattr(theater_service.db_service, "ensure_session", fake_ensure_session)
    monkeypatch.setattr(theater_service.db_service, "save_message", fake_save_message)
    monkeypatch.setattr(theater_service.rag, "retrieve", lambda query: [])
    monkeypatch.setattr(
        theater_service.ai_service,
        "get_scammer_reply",
        lambda scam_id, history, user_input, rag_contexts: f"reply for {scam_id}",
    )

    result = theater_service.process_chat_message(
        session_id=f"  {long_session_id}  ",
        message="普通聊天",
        history=[],
        scam_id="  shuadan  ",
        risk_rules=[],
    )

    assert result.scammer_reply == "reply for shuadan"
    assert calls[0] == ("ensure_session", "s" * MAX_SESSION_ID_LEN, "shuadan")


def test_db_write_failure_does_not_expose_internal_error_or_skip_ai(monkeypatch):
    calls = []

    def failing_ensure_session(session_id, scam_id):
        calls.append("ensure_session")
        raise RuntimeError("database path leaked")

    def fake_save_message(*args, **kwargs):
        calls.append("save_message")
        raise RuntimeError("database path leaked")

    def fake_retrieve(query):
        calls.append("rag.retrieve")
        return []

    def fake_get_scammer_reply(scam_id, history, user_input, rag_contexts):
        calls.append("ai_service.get_scammer_reply")
        return "mock reply despite db failure"

    monkeypatch.setattr(theater_service.db_service, "ensure_session", failing_ensure_session)
    monkeypatch.setattr(theater_service.db_service, "save_message", fake_save_message)
    monkeypatch.setattr(theater_service.rag, "retrieve", fake_retrieve)
    monkeypatch.setattr(theater_service.ai_service, "get_scammer_reply", fake_get_scammer_reply)

    result = theater_service.process_chat_message(
        session_id="session-db-fail",
        message="兼职返利",
        history=[],
        scam_id="shuadan",
        risk_rules=[
            {
                "level": "medium",
                "score": 40,
                "keywords": ["兼职"],
                "action": RISK_ACTION_HINT,
                "message": "hint",
            }
        ],
    )

    assert result.scammer_reply == "mock reply despite db failure"
    assert result.interrupted is False
    assert calls == [
        "rag.retrieve",
        "ai_service.get_scammer_reply",
        "ensure_session",
        "save_message",
    ]


def test_ai_fallback_result_is_returned_without_crashing(monkeypatch):
    monkeypatch.setattr(theater_service.db_service, "ensure_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(theater_service.db_service, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(theater_service.rag, "retrieve", lambda query: [])
    monkeypatch.setattr(
        theater_service.ai_service,
        "get_scammer_reply",
        lambda scam_id, history, user_input, rag_contexts: CHAT_FALLBACK_REPLY,
    )

    result = theater_service.process_chat_message(
        session_id="session-ai-fallback",
        message="兼职返利",
        history=[],
        scam_id="shuadan",
        risk_rules=[
            {
                "level": "medium",
                "score": 40,
                "keywords": ["兼职"],
                "action": RISK_ACTION_HINT,
                "message": "hint",
            }
        ],
    )

    assert result.scammer_reply == CHAT_FALLBACK_REPLY
    assert result.interrupted is False
