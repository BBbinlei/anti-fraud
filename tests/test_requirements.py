from pathlib import Path


def _requirement_names() -> set[str]:
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    names = set()
    for line in requirements:
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        for separator in ("==", ">=", "<=", "~=", ">", "<"):
            if separator in clean:
                clean = clean.split(separator, maxsplit=1)[0]
                break
        names.add(clean)
    return names


def test_requirements_include_runtime_rag_and_eval_dependencies():
    names = _requirement_names()

    assert "fastapi" in names
    assert "uvicorn[standard]" in names
    assert "openai" in names
    assert "chromadb" in names
    assert "sentence-transformers" in names
    assert "deepeval" in names


def test_requirements_include_observability_and_env_dependencies():
    names = _requirement_names()

    # pytz: Phoenix 的隐式依赖，缺失会让 init_observability 静默降级
    assert "pytz" in names
    # python-dotenv: 用于加载 .env，让 DEEPSEEK_API_KEY 真正生效
    assert "python-dotenv" in names
    # Python 3.13 兼容性锁定：缺这两个会让 Phoenix 在 import 阶段崩溃
    # （evals 3.x 删了 phoenix.evals.models；graphql-core 3.3a 破坏 strawberry）
    assert "arize-phoenix-evals" in names
    assert "graphql-core" in names
