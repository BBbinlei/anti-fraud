import inspect
import importlib
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_main_app_imports_as_fastapi_instance():
    import main

    assert isinstance(main.app, FastAPI)


def test_health_routes_are_registered_and_stable():
    import main

    client = TestClient(main.app)

    assert client.get("/theater/health").json() == {
        "status": "ok",
        "service": "theater",
    }
    assert client.get("/report/health").json() == {
        "status": "ok",
        "service": "report",
    }
    assert client.get("/user/health").json() == {
        "status": "ok",
        "service": "user",
    }


def test_health_handlers_are_async():
    from routers.report import report_health
    from routers.theater import theater_health
    from routers.user import user_health

    assert inspect.iscoroutinefunction(theater_health)
    assert inspect.iscoroutinefunction(report_health)
    assert inspect.iscoroutinefunction(user_health)


def test_observability_failure_does_not_block_app_creation(monkeypatch):
    import main

    def fail_observability():
        raise RuntimeError("phoenix unavailable")

    monkeypatch.setattr(main, "init_observability", fail_observability)

    try:
        app = main.create_app()
    except RuntimeError:
        raise AssertionError("create_app leaked observability failure")

    assert isinstance(app, FastAPI)


def test_main_import_survives_missing_observability_dependencies():
    sys.modules.pop("main", None)

    imported_main = importlib.import_module("main")

    assert isinstance(imported_main.app, FastAPI)
    assert imported_main.app.state.observability_enabled is False
