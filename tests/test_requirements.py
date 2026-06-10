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
