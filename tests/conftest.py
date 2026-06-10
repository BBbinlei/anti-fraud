import builtins
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def block_observability_dependencies(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        blocked_names = (
            "phoenix",
            "openinference.instrumentation.anthropic",
        )
        if name == blocked_names[0] or name.startswith(f"{blocked_names[0]}."):
            raise ImportError("observability disabled in tests")
        if name == blocked_names[1]:
            raise ImportError("observability disabled in tests")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
