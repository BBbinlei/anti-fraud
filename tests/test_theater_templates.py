import inspect

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import FRAUD_TYPES, TEMPLATE_LOAD_ERROR_MESSAGE
from main import app
from routers import theater as theater_router
from services import template_service


def test_theater_templates_route_returns_configured_templates():
    with TestClient(app) as client:
        response = client.get("/theater/templates")

    assert response.status_code == 200
    data = response.json()
    assert len(data["templates"]) == len(FRAUD_TYPES)
    assert {template["scam_id"] for template in data["templates"]} == set(FRAUD_TYPES)
    first_template = data["templates"][0]
    assert first_template["scam_name"]
    assert first_template["target"]
    assert first_template["difficulty"] >= 1
    assert first_template["opener"]
    assert first_template["persona"]
    assert first_template["escalation_steps"]
    assert first_template["red_flags"]
    assert first_template["prevention"]


def test_template_service_filters_invalid_templates(monkeypatch):
    payload = {
        "templates": [
            {
                "scam_id": "shuadan",
                "difficulty": "2",
                "opener": "hello",
                "persona": "persona",
                "escalation_steps": [" step one ", ""],
            },
            {
                "scam_id": "unknown",
                "difficulty": 1,
                "opener": "bad",
                "persona": "bad",
                "escalation_steps": [],
            },
            "bad template",
        ]
    }
    scam_payload = {
        "scams": [
            {
                "id": "shuadan",
                "name": "刷单返利诈骗",
                "target": "在校学生",
                "red_flags": ["刷单"],
                "prevention": ["不要垫资"],
            }
        ]
    }
    loads = [payload, scam_payload]

    class FakeFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_open(*args, **kwargs):
        return FakeFile()

    monkeypatch.setattr(template_service, "open", fake_open, raising=False)
    monkeypatch.setattr(template_service.json, "load", lambda f: loads.pop(0))

    templates = template_service.list_templates()

    assert len(templates) == 1
    assert templates[0].scam_id == "shuadan"
    assert templates[0].scam_name == "刷单返利诈骗"
    assert templates[0].difficulty == 2
    assert templates[0].escalation_steps == ["step one"]


def test_template_service_merges_scam_card_summary(monkeypatch):
    payload = {
        "templates": [
            {
                "scam_id": "shuadan",
                "difficulty": 1,
                "opener": "hello",
                "persona": "persona",
                "escalation_steps": ["step"],
            }
        ]
    }
    scam_payload = {
        "scams": [
            {
                "id": "shuadan",
                "name": "刷单返利诈骗",
                "target": "在校学生",
                "red_flags": ["刷单", "垫付", "返利", "日结", "超额"],
                "prevention": ["不要垫资", "保留证据", "额外提示"],
            }
        ]
    }
    loads = [payload, scam_payload]

    class FakeFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(template_service, "open", lambda *args, **kwargs: FakeFile(), raising=False)
    monkeypatch.setattr(template_service.json, "load", lambda f: loads.pop(0))

    templates = template_service.list_templates()

    assert templates[0].scam_name == "刷单返利诈骗"
    assert templates[0].target == "在校学生"
    assert templates[0].red_flags == ["刷单", "垫付", "返利", "日结"]
    assert templates[0].prevention == ["不要垫资", "保留证据"]


def test_template_service_degrades_when_scam_card_summary_fails(monkeypatch):
    payload = {
        "templates": [
            {
                "scam_id": "shuadan",
                "difficulty": 1,
                "opener": "hello",
                "persona": "persona",
                "escalation_steps": ["step"],
            }
        ]
    }

    class FakeFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    calls = []

    def fake_open(*args, **kwargs):
        calls.append(args[0])
        if len(calls) == 2:
            raise RuntimeError("/Users/binlei/Documents/project/anti_fraud/data/scam_cards.json")
        return FakeFile()

    monkeypatch.setattr(template_service, "open", fake_open, raising=False)
    monkeypatch.setattr(template_service.json, "load", lambda f: payload)

    templates = template_service.list_templates()

    assert templates[0].scam_name == "shuadan"
    assert templates[0].target == ""
    assert templates[0].red_flags == []
    assert templates[0].prevention == []


def test_template_service_load_error_returns_safe_message(monkeypatch):
    def fail_open(*args, **kwargs):
        raise RuntimeError("/Users/binlei/Documents/project/anti_fraud/data/script_templates.json")

    monkeypatch.setattr(template_service, "open", fail_open, raising=False)

    with pytest.raises(HTTPException) as exc:
        template_service.list_templates()

    assert exc.value.status_code == 500
    assert exc.value.detail == TEMPLATE_LOAD_ERROR_MESSAGE
    assert "/Users" not in exc.value.detail
    assert "script_templates" not in exc.value.detail


def test_theater_templates_route_is_async_and_router_has_no_forbidden_calls():
    source = inspect.getsource(theater_router)

    assert inspect.iscoroutinefunction(theater_router.theater_templates)
    assert "sqlite3" not in source
    assert "OpenAI(" not in source
    assert "collection.query" not in source
