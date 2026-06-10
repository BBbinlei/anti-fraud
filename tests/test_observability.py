"""Tests for main.init_observability — graceful degradation and success paths.

conftest.py 的 autouse fixture 会把 `phoenix` 的 import 强制抛错，
因此默认降级路径天然被覆盖；成功路径需在测试内注入伪模块并绕过该守卫。
"""

import builtins
import importlib
import sys
import types

import main
from config import PHOENIX_PROJECT_NAME


def test_init_observability_returns_false_when_phoenix_missing():
    # conftest 已强制 phoenix import 失败：断言优雅降级，返回 False 且不抛异常。
    assert main.init_observability() is False


def test_init_observability_returns_true_with_stubbed_dependencies(monkeypatch):
    calls = {}

    fake_phoenix = types.ModuleType("phoenix")
    fake_phoenix.launch_app = lambda: calls.setdefault("launch_app", True)

    fake_otel = types.ModuleType("phoenix.otel")

    def fake_register(project_name, auto_instrument):
        calls["register"] = {"project_name": project_name, "auto_instrument": auto_instrument}
        return "fake-tracer-provider"

    fake_otel.register = fake_register

    fake_instr = types.ModuleType("openinference.instrumentation.openai")

    class FakeInstrumentor:
        def instrument(self, tracer_provider=None):
            calls["instrument"] = tracer_provider

    fake_instr.OpenAIInstrumentor = FakeInstrumentor

    stub_modules = {
        "phoenix": fake_phoenix,
        "phoenix.otel": fake_otel,
        "openinference.instrumentation.openai": fake_instr,
    }

    # 绕过 conftest 的 __import__ 守卫：返回伪模块，其余委托给真实 import。
    def patched_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in stub_modules:
            return stub_modules[name]
        return importlib.__import__(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", patched_import)
    for name, module in stub_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    assert main.init_observability() is True
    assert calls.get("launch_app") is True
    assert calls["register"] == {
        "project_name": PHOENIX_PROJECT_NAME,
        "auto_instrument": True,
    }
    assert calls["instrument"] == "fake-tracer-provider"
