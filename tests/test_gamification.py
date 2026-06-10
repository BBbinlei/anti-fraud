import inspect
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import (
    DEFAULT_USER_PROGRESS_SCORE,
    DEFAULT_USER_PROGRESS_STREAK,
    GAMIFICATION_COMPLETE_SUCCESS_MESSAGE,
    GAMIFICATION_POINTS_PER_COMPLETION,
    GAMIFICATION_STATUS_COMPLETED,
    SCAM_ID_INVALID_ERROR_MESSAGE,
    USER_ID_EMPTY_ERROR_MESSAGE,
    USER_PROGRESS_LOAD_ERROR_MESSAGE,
    USER_PROGRESS_SAVE_ERROR_MESSAGE,
)
from main import app
from routers import user as user_router
from services import db_service, gamification
from services.gamification import UserProgressData


def test_get_progress_returns_default_for_new_user(monkeypatch):
    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: None)

    progress = gamification.get_progress(" student-1 ")

    assert progress.user_id == "student-1"
    assert progress.total_score == DEFAULT_USER_PROGRESS_SCORE
    assert progress.streak == DEFAULT_USER_PROGRESS_STREAK
    assert progress.badges == []
    assert progress.completed == {}


def test_complete_scenario_adds_points_and_first_badge(monkeypatch):
    captured = {}
    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: None)

    def fake_save_user_progress(user_id, total_score, streak, badges, completed):
        captured.update(
            {
                "user_id": user_id,
                "total_score": total_score,
                "streak": streak,
                "badges": badges,
                "completed": completed,
            }
        )

    monkeypatch.setattr(gamification.db_service, "save_user_progress", fake_save_user_progress)

    result = gamification.complete_scenario("student-1", "shuadan")

    assert result.total_score == GAMIFICATION_POINTS_PER_COMPLETION
    assert result.streak == 1
    assert result.completed == {"shuadan": 1}
    assert result.badges == ["first_guard"]
    assert result.new_badges == ["first_guard"]
    assert result.status == GAMIFICATION_STATUS_COMPLETED
    assert result.message == GAMIFICATION_COMPLETE_SUCCESS_MESSAGE
    assert result.already_claimed is False
    assert captured["completed"] == {"shuadan": 1}


def test_complete_scenario_does_not_duplicate_existing_badge(monkeypatch):
    existing = {
        "user_id": "student-1",
        "total_score": 10,
        "streak": 1,
        "badges": ["first_guard"],
        "completed": {"shuadan": 1},
    }
    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: existing)
    monkeypatch.setattr(gamification.db_service, "save_user_progress", lambda *args, **kwargs: None)

    result = gamification.complete_scenario("student-1", "shuadan")

    assert result.badges == ["first_guard"]
    assert result.new_badges == []
    assert result.completed == {"shuadan": 2}


def test_complete_scenario_awards_threshold_badge(monkeypatch):
    existing = {
        "user_id": "student-1",
        "total_score": 20,
        "streak": 2,
        "badges": ["first_guard"],
        "completed": {"shuadan": 1, "gongjianfa": 1},
    }
    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: existing)
    monkeypatch.setattr(gamification.db_service, "save_user_progress", lambda *args, **kwargs: None)

    result = gamification.complete_scenario("student-1", "xiaoyuandai")

    assert result.total_score == 30
    assert result.badges == ["first_guard", "steady_learner"]
    assert result.new_badges == ["steady_learner"]


def test_complete_scenario_with_session_id_skips_duplicate_claim(monkeypatch):
    existing = {
        "user_id": "student-1",
        "total_score": 10,
        "streak": 1,
        "badges": ["first_guard"],
        "completed": {"shuadan": 1},
    }
    save_calls = []

    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: existing)
    monkeypatch.setattr(gamification.db_service, "claim_completion", lambda user_id, session_id, scam_id: False)
    monkeypatch.setattr(gamification.db_service, "save_user_progress", lambda *args, **kwargs: save_calls.append(args))

    result = gamification.complete_scenario("student-1", "shuadan", session_id="session-1")

    assert result.total_score == 10
    assert result.streak == 1
    assert result.completed == {"shuadan": 1}
    assert result.score_added == 0
    assert result.new_badges == []
    assert result.status == "already_claimed"
    assert result.already_claimed is True
    assert save_calls == []


def test_complete_scenario_with_new_session_claim_adds_points(monkeypatch):
    claim_args = {}
    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: None)
    monkeypatch.setattr(gamification.db_service, "save_user_progress", lambda *args, **kwargs: None)

    def fake_claim_completion(user_id, session_id, scam_id):
        claim_args.update({"user_id": user_id, "session_id": session_id, "scam_id": scam_id})
        return True

    monkeypatch.setattr(gamification.db_service, "claim_completion", fake_claim_completion)

    result = gamification.complete_scenario("student-1", "shuadan", session_id=" session-1 ")

    assert result.score_added == GAMIFICATION_POINTS_PER_COMPLETION
    assert result.already_claimed is False
    assert claim_args == {"user_id": "student-1", "session_id": "session-1", "scam_id": "shuadan"}


def test_complete_scenario_rejects_empty_user_id():
    with pytest.raises(HTTPException) as exc:
        gamification.complete_scenario(" ", "shuadan")

    assert exc.value.status_code == 400
    assert exc.value.detail == USER_ID_EMPTY_ERROR_MESSAGE


def test_complete_scenario_rejects_invalid_scam_id():
    with pytest.raises(HTTPException) as exc:
        gamification.complete_scenario("student-1", "unknown")

    assert exc.value.status_code == 400
    assert exc.value.detail == SCAM_ID_INVALID_ERROR_MESSAGE


def test_get_progress_db_error_returns_safe_message(monkeypatch):
    def fail_get_user_progress(user_id):
        raise RuntimeError("/Users/binlei/Documents/project/anti_fraud/app.db")

    monkeypatch.setattr(gamification.db_service, "get_user_progress", fail_get_user_progress)

    with pytest.raises(HTTPException) as exc:
        gamification.get_progress("student-1")

    assert exc.value.status_code == 500
    assert exc.value.detail == USER_PROGRESS_LOAD_ERROR_MESSAGE
    assert "/Users" not in exc.value.detail
    assert "app.db" not in exc.value.detail


def test_complete_scenario_save_error_returns_safe_message(monkeypatch):
    monkeypatch.setattr(gamification.db_service, "get_user_progress", lambda user_id: None)

    def fail_save_user_progress(*args, **kwargs):
        raise RuntimeError("database is locked at /tmp/app.db")

    monkeypatch.setattr(gamification.db_service, "save_user_progress", fail_save_user_progress)

    with pytest.raises(HTTPException) as exc:
        gamification.complete_scenario("student-1", "shuadan")

    assert exc.value.status_code == 500
    assert exc.value.detail == USER_PROGRESS_SAVE_ERROR_MESSAGE
    assert "database" not in exc.value.detail
    assert "/tmp" not in exc.value.detail


def test_user_progress_route_returns_service_result(monkeypatch):
    def fake_get_progress(user_id):
        assert user_id == "student-1"
        return UserProgressData(
            user_id="student-1",
            total_score=10,
            streak=1,
            badges=["first_guard"],
            completed={"shuadan": 1},
        )

    monkeypatch.setattr(user_router, "get_progress", fake_get_progress)

    with TestClient(app) as client:
        response = client.get("/user/progress", params={"user_id": "student-1"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "student-1",
        "total_score": 10,
        "streak": 1,
        "badges": ["first_guard"],
        "completed": {"shuadan": 1},
    }


def test_user_complete_route_returns_service_result(monkeypatch):
    def fake_complete_scenario(user_id, scam_id, session_id=None):
        assert user_id == "student-1"
        assert scam_id == "shuadan"
        assert session_id == "session-route"
        return gamification.CompleteScenarioData(
            user_id="student-1",
            total_score=10,
            streak=1,
            badges=["first_guard"],
            completed={"shuadan": 1},
            score_added=10,
            new_badges=["first_guard"],
            status=GAMIFICATION_STATUS_COMPLETED,
            message=GAMIFICATION_COMPLETE_SUCCESS_MESSAGE,
        )

    monkeypatch.setattr(user_router, "complete_scenario", fake_complete_scenario)

    with TestClient(app) as client:
        response = client.post(
            "/user/complete",
            json={"user_id": "student-1", "scam_id": "shuadan", "session_id": "session-route"},
        )

    assert response.status_code == 200
    assert response.json()["new_badges"] == ["first_guard"]
    assert response.json()["completed"] == {"shuadan": 1}
    assert response.json()["already_claimed"] is False


def test_db_service_user_progress_persists_with_parameterized_api(tmp_path, monkeypatch):
    db_path = tmp_path / "progress.db"
    monkeypatch.setattr(db_service, "APP_DB", str(db_path))

    db_service.init_db()
    db_service.save_user_progress(
        user_id="student-db",
        total_score=30,
        streak=3,
        badges=["first_guard", "steady_learner"],
        completed={"shuadan": 2, "gongjianfa": 1},
    )

    progress = db_service.get_user_progress("student-db")
    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM user_progress WHERE user_id=?", ("student-db",)).fetchone()[0]

    assert row_count == 1
    assert progress == {
        "user_id": "student-db",
        "total_score": 30,
        "streak": 3,
        "badges": ["first_guard", "steady_learner"],
        "completed": {"shuadan": 2, "gongjianfa": 1},
    }


def test_db_service_completion_claim_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "claims.db"
    monkeypatch.setattr(db_service, "APP_DB", str(db_path))

    db_service.init_db()

    assert db_service.claim_completion("student-db", "session-db", "shuadan") is True
    assert db_service.claim_completion("student-db", "session-db", "shuadan") is False
    assert db_service.claim_completion("student-db", "another-session", "shuadan") is True

    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM completion_claims WHERE user_id=?", ("student-db",)).fetchone()[0]

    assert row_count == 2


def test_user_routes_are_async_and_have_no_sqlite_or_sdk_calls():
    source = inspect.getsource(user_router)

    assert inspect.iscoroutinefunction(user_router.user_progress)
    assert inspect.iscoroutinefunction(user_router.user_complete)
    assert "sqlite3" not in source
    assert "OpenAI(" not in source
    assert "collection.query" not in source
