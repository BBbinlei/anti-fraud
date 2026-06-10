import inspect

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import (
    DEFAULT_RISK_LEVEL,
    REVIEW_GENERATE_ERROR_MESSAGE,
    SCAM_CARD_LOAD_ERROR_MESSAGE,
    SCAM_ID_INVALID_ERROR_MESSAGE,
    SESSION_ID_EMPTY_ERROR_MESSAGE,
)
from main import app
from routers import theater as theater_router
from services import db_service, review_service
from services.review_service import ReviewReportData


def test_review_service_generates_fallback_report_from_messages(monkeypatch):
    messages = [
        {
            "role": "user",
            "content": "对方要求我做兼职刷单，还让我垫付",
            "risk_level": "medium",
            "risk_score": 40,
            "ts": "2026-01-01T00:00:00+00:00",
        },
        {
            "role": "user",
            "content": "我马上转账",
            "risk_level": "critical",
            "risk_score": 90,
            "ts": "2026-01-01T00:01:00+00:00",
        },
    ]
    monkeypatch.setattr(review_service.db_service, "get_session_messages", lambda session_id: messages)

    report = review_service.generate_review_report(" session-1 ", "shuadan")

    assert report.session_id == "session-1"
    assert report.scam_id == "shuadan"
    assert report.scam_name == "刷单返利诈骗"
    assert report.conversation_turns == 2
    assert report.highest_risk_level == "critical"
    assert report.highest_risk_score == 90
    assert "垫付" in report.red_flags
    assert report.tactics
    assert report.prevention
    assert report.review_title == "刷单返利复盘要点"
    assert "垫资" in report.review_content
    assert report.key_takeaways


def test_review_service_degrades_when_review_card_file_is_unavailable(monkeypatch, tmp_path):
    missing_review_cards = tmp_path / "missing_review_cards.json"
    monkeypatch.setattr(review_service, "REVIEW_CARDS_FILE", missing_review_cards)
    monkeypatch.setattr(review_service.db_service, "get_session_messages", lambda session_id: [])

    report = review_service.generate_review_report("session-1", "shuadan")

    assert report.highest_risk_level == DEFAULT_RISK_LEVEL
    assert report.review_title == ""
    assert report.review_content == ""


def test_theater_reveal_route_returns_service_result(monkeypatch):
    def fake_generate_review_report(session_id, scam_id):
        assert session_id == "session-route"
        assert scam_id == "shuadan"
        return ReviewReportData(
            session_id="session-route",
            scam_id="shuadan",
            scam_name="刷单返利诈骗",
            summary="summary",
            conversation_turns=1,
            highest_risk_level="medium",
            highest_risk_score=40,
            tactics=["先小额返利"],
            red_flags=["垫付"],
            prevention=["不要垫资"],
            legal="legal",
            typical_case="case",
            review_title="复盘要点",
            review_content="复盘内容",
            key_takeaways=["takeaway"],
        )

    monkeypatch.setattr(theater_router, "generate_review_report", fake_generate_review_report)

    with TestClient(app) as client:
        response = client.post(
            "/theater/reveal",
            json={"session_id": "session-route", "scam_id": "shuadan"},
        )

    assert response.status_code == 200
    assert response.json()["summary"] == "summary"
    assert response.json()["red_flags"] == ["垫付"]
    assert response.json()["review_title"] == "复盘要点"
    assert response.json()["review_content"] == "复盘内容"


def test_review_service_rejects_empty_session_id():
    with pytest.raises(HTTPException) as exc:
        review_service.generate_review_report(" ", "shuadan")

    assert exc.value.status_code == 400
    assert exc.value.detail == SESSION_ID_EMPTY_ERROR_MESSAGE


def test_review_service_rejects_invalid_scam_id():
    with pytest.raises(HTTPException) as exc:
        review_service.generate_review_report("session-1", "unknown")

    assert exc.value.status_code == 400
    assert exc.value.detail == SCAM_ID_INVALID_ERROR_MESSAGE


def test_review_service_db_error_returns_safe_message(monkeypatch):
    def fail_get_session_messages(session_id):
        raise RuntimeError("/Users/binlei/Documents/project/anti_fraud/app.db locked")

    monkeypatch.setattr(review_service.db_service, "get_session_messages", fail_get_session_messages)

    with pytest.raises(HTTPException) as exc:
        review_service.generate_review_report("session-1", "shuadan")

    assert exc.value.status_code == 500
    assert exc.value.detail == REVIEW_GENERATE_ERROR_MESSAGE
    assert "/Users" not in exc.value.detail
    assert "app.db" not in exc.value.detail


def test_review_service_scam_card_error_returns_safe_message(monkeypatch):
    def fail_open(*args, **kwargs):
        raise RuntimeError("/Users/binlei/Documents/project/anti_fraud/data/scam_cards.json")

    monkeypatch.setattr(review_service, "open", fail_open, raising=False)

    with pytest.raises(HTTPException) as exc:
        review_service.generate_review_report("session-1", "shuadan")

    assert exc.value.status_code == 500
    assert exc.value.detail == SCAM_CARD_LOAD_ERROR_MESSAGE
    assert "/Users" not in exc.value.detail
    assert "scam_cards" not in exc.value.detail


def test_db_service_get_session_messages_reads_ordered_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "review.db"
    monkeypatch.setattr(db_service, "APP_DB", str(db_path))

    db_service.init_db()
    db_service.save_message("session-db", "user", "第一条", "medium", 40)
    db_service.save_message("session-db", "scammer", "第二条")

    messages = db_service.get_session_messages("session-db")

    assert [message["content"] for message in messages] == ["第一条", "第二条"]
    assert messages[0]["risk_level"] == "medium"
    assert messages[0]["risk_score"] == 40


def test_theater_reveal_route_is_async_and_router_has_no_forbidden_calls():
    source = inspect.getsource(theater_router)

    assert inspect.iscoroutinefunction(theater_router.theater_reveal)
    assert "sqlite3" not in source
    assert "OpenAI(" not in source
    assert "collection.query" not in source
