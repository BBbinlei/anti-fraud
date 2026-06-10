import inspect
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import (
    MAX_REPORT_CONTENT_LEN,
    MAX_REPORT_URL_LEN,
    MAX_SESSION_ID_LEN,
    REPORT_EMPTY_ERROR_MESSAGE,
    REPORT_RISK_LEVEL_INVALID_ERROR_MESSAGE,
    REPORT_SAVE_ERROR_MESSAGE,
    REPORT_STATUS_RECEIVED,
    REPORT_SUBMIT_SUCCESS_MESSAGE,
)
from main import app
from routers import report as report_router
from services import db_service, report_service
from services.report_service import ReportData


def test_report_submit_route_returns_stable_response(monkeypatch):
    def fake_submit_report(session_id, content, url, risk_level=None):
        assert session_id == "session-1"
        assert content == "对方让我转保证金"
        assert url is None
        assert risk_level == "high"
        return ReportData(
            report_id="report-1",
            status=REPORT_STATUS_RECEIVED,
            message=REPORT_SUBMIT_SUCCESS_MESSAGE,
        )

    monkeypatch.setattr(report_router, "submit_report", fake_submit_report)

    with TestClient(app) as client:
        response = client.post(
            "/report/submit",
            json={
                "session_id": "session-1",
                "content": "对方让我转保证金",
                "risk_level": "high",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "report_id": "report-1",
        "status": REPORT_STATUS_RECEIVED,
        "message": REPORT_SUBMIT_SUCCESS_MESSAGE,
    }


def test_report_service_accepts_url_only(monkeypatch):
    captured = {}

    def fake_save_report(session_id, content, url, risk_level=None):
        captured.update(
            {
                "session_id": session_id,
                "content": content,
                "url": url,
                "risk_level": risk_level,
            }
        )
        return "report-url"

    monkeypatch.setattr(report_service.db_service, "save_report", fake_save_report)

    result = report_service.submit_report(
        session_id=None,
        content="   ",
        url=" https://example.test/fake-job ",
    )

    assert result.report_id == "report-url"
    assert result.status == REPORT_STATUS_RECEIVED
    assert captured == {
        "session_id": None,
        "content": "",
        "url": "https://example.test/fake-job",
        "risk_level": None,
    }


def test_report_service_normalizes_valid_risk_level(monkeypatch):
    captured = {}

    def fake_save_report(session_id, content, url, risk_level=None):
        captured["risk_level"] = risk_level
        return "report-risk"

    monkeypatch.setattr(report_service.db_service, "save_report", fake_save_report)

    report_service.submit_report(
        session_id="session-risk",
        content="可疑内容",
        url=None,
        risk_level=" high ",
    )

    assert captured["risk_level"] == "high"


def test_report_service_treats_blank_risk_level_as_none(monkeypatch):
    captured = {}

    def fake_save_report(session_id, content, url, risk_level=None):
        captured["risk_level"] = risk_level
        return "report-blank-risk"

    monkeypatch.setattr(report_service.db_service, "save_report", fake_save_report)

    report_service.submit_report(
        session_id="session-risk-blank",
        content="可疑内容",
        url=None,
        risk_level=" ",
    )

    assert captured["risk_level"] is None


def test_report_service_treats_blank_session_id_as_none(monkeypatch):
    captured = {}

    def fake_save_report(session_id, content, url, risk_level=None):
        captured["session_id"] = session_id
        return "report-blank-session"

    monkeypatch.setattr(report_service.db_service, "save_report", fake_save_report)

    report_service.submit_report(
        session_id="   ",
        content="可疑内容",
        url=None,
    )

    assert captured["session_id"] is None


def test_report_service_truncates_session_id_before_save(monkeypatch):
    captured = {}

    def fake_save_report(session_id, content, url, risk_level=None):
        captured["session_id"] = session_id
        return "report-long-session"

    monkeypatch.setattr(report_service.db_service, "save_report", fake_save_report)

    report_service.submit_report(
        session_id="s" * (MAX_SESSION_ID_LEN + 5),
        content="可疑内容",
        url=None,
    )

    assert captured["session_id"] == "s" * MAX_SESSION_ID_LEN


def test_report_submit_rejects_empty_content_and_url():
    with TestClient(app) as client:
        response = client.post(
            "/report/submit",
            json={"session_id": "session-empty", "content": " ", "url": ""},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": REPORT_EMPTY_ERROR_MESSAGE}


def test_report_submit_rejects_invalid_risk_level_before_db(monkeypatch):
    calls = []

    def fail_save_report(*args, **kwargs):
        calls.append("save_report")
        raise AssertionError("save_report should not be called for invalid risk_level")

    monkeypatch.setattr(report_service.db_service, "save_report", fail_save_report)

    with pytest.raises(HTTPException) as exc:
        report_service.submit_report(
            session_id="session-invalid-risk",
            content="可疑内容",
            url=None,
            risk_level="severe",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == REPORT_RISK_LEVEL_INVALID_ERROR_MESSAGE
    assert calls == []


def test_report_submit_route_rejects_invalid_risk_level():
    with TestClient(app) as client:
        response = client.post(
            "/report/submit",
            json={
                "session_id": "session-invalid-risk-route",
                "content": "可疑内容",
                "risk_level": "severe",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": REPORT_RISK_LEVEL_INVALID_ERROR_MESSAGE}


def test_report_service_truncates_content_and_url_before_save(monkeypatch):
    captured = {}

    def fake_save_report(session_id, content, url, risk_level=None):
        captured["content"] = content
        captured["url"] = url
        return "report-long"

    monkeypatch.setattr(report_service.db_service, "save_report", fake_save_report)

    report_service.submit_report(
        session_id="session-long",
        content="内" * (MAX_REPORT_CONTENT_LEN + 5),
        url="u" * (MAX_REPORT_URL_LEN + 5),
    )

    assert captured["content"] == "内" * MAX_REPORT_CONTENT_LEN
    assert captured["url"] == "u" * MAX_REPORT_URL_LEN


def test_report_service_db_error_returns_safe_message(monkeypatch):
    def fail_save_report(*args, **kwargs):
        raise RuntimeError("/Users/binlei/Documents/project/anti_fraud/app.db locked")

    monkeypatch.setattr(report_service.db_service, "save_report", fail_save_report)

    with pytest.raises(HTTPException) as exc:
        report_service.submit_report(
            session_id="session-fail",
            content="举报内容",
            url=None,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == REPORT_SAVE_ERROR_MESSAGE
    assert "app.db" not in exc.value.detail
    assert "/Users" not in exc.value.detail


def test_db_service_save_report_persists_with_parameterized_api(tmp_path, monkeypatch):
    db_path = tmp_path / "reports.db"
    monkeypatch.setattr(db_service, "APP_DB", str(db_path))

    db_service.init_db()
    report_id = db_service.save_report(
        session_id="session-db",
        content="可疑链接",
        url="https://example.test",
        risk_level="medium",
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT session_id, content, url, risk_level FROM reports WHERE report_id=?",
            (report_id,),
        ).fetchone()

    assert row == ("session-db", "可疑链接", "https://example.test", "medium")


def test_report_submit_route_is_async_and_router_has_no_sqlite_or_sdk_calls():
    source = inspect.getsource(report_router)

    assert inspect.iscoroutinefunction(report_router.report_submit)
    assert "sqlite3" not in source
    assert "OpenAI(" not in source
    assert "collection.query" not in source
