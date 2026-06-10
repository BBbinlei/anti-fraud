import json

import pytest

from config import DEEPEVAL_MAX_CASES
from scripts import run_eval


class FakeMetric:
    def __init__(self, threshold, model):
        self.threshold = threshold
        self.model = model


class FakeModel:
    def __init__(self, model, base_url, _openai_api_key):
        self.model = model
        self.base_url = base_url
        self._openai_api_key = _openai_api_key


class FakeLLMTestCase:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _fake_bundle(captured):
    def fake_evaluate(test_cases, metrics):
        captured["test_cases"] = test_cases
        captured["metrics"] = metrics
        return {"evaluated": len(test_cases)}

    return {
        "evaluate": fake_evaluate,
        "FaithfulnessMetric": FakeMetric,
        "AnswerRelevancyMetric": FakeMetric,
        "ContextualPrecisionMetric": FakeMetric,
        "ContextualRecallMetric": FakeMetric,
        "LLMTestCase": FakeLLMTestCase,
        "GPTModel": FakeModel,
    }


def test_load_eval_cases_filters_invalid_items_and_limits_count(tmp_path, monkeypatch):
    dataset_file = tmp_path / "eval_dataset.json"
    payload = {
        "generation_cases": [
            {"id": f"case_{index}", "query": f"问题{index}", "ground_truth": "答案"}
            for index in range(DEEPEVAL_MAX_CASES + 5)
        ]
        + [
            {"id": "missing_query", "query": "", "ground_truth": "答案"},
            {"id": "missing_answer", "query": "问题", "ground_truth": ""},
            "invalid",
        ]
    }
    dataset_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    cases = run_eval.load_eval_cases(dataset_file)

    assert len(cases) == DEEPEVAL_MAX_CASES
    assert cases[0].case_id == "case_0"
    assert cases[-1].case_id == f"case_{DEEPEVAL_MAX_CASES - 1}"


def test_run_evaluation_builds_deepeval_cases_without_network(monkeypatch):
    captured = {}
    monkeypatch.setattr(run_eval, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        run_eval,
        "load_eval_cases",
        lambda: [
            run_eval.EvalCaseData(
                case_id="eval_1",
                query="刷单风险是什么",
                expected_output="刷单常见风险包括垫付和返利诱导。",
                scam_id="shuadan",
            )
        ],
    )
    monkeypatch.setattr(
        run_eval.rag,
        "retrieve",
        lambda query: [{"document": f"知识库上下文：{query}", "score": 0.9}],
    )

    result = run_eval.run_evaluation(_fake_bundle(captured))

    assert result == {"evaluated": 1}
    assert len(captured["metrics"]) == 4
    assert captured["test_cases"][0].kwargs == {
        "input": "刷单风险是什么",
        "actual_output": "知识库上下文：刷单风险是什么",
        "expected_output": "刷单常见风险包括垫付和返利诱导。",
        "retrieval_context": ["知识库上下文：刷单风险是什么"],
    }


def test_run_evaluation_requires_api_key_before_loading_deepeval(monkeypatch):
    monkeypatch.setattr(run_eval, "DEEPSEEK_API_KEY", "")

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        run_eval.run_evaluation({})


def test_run_evaluation_reports_missing_deepeval_dependency(monkeypatch):
    monkeypatch.setattr(run_eval, "DEEPSEEK_API_KEY", "test-key")

    def fail_load_deepeval():
        raise RuntimeError("DeepEval 依赖未安装，请先运行 pip install -r requirements.txt。")

    monkeypatch.setattr(run_eval, "_load_deepeval", fail_load_deepeval)

    with pytest.raises(RuntimeError, match="DeepEval"):
        run_eval.run_evaluation()


def test_build_test_case_uses_safe_empty_context_when_rag_fails(monkeypatch):
    def fail_retrieve(query):
        raise RuntimeError("/internal/chroma/path")

    monkeypatch.setattr(run_eval.rag, "retrieve", fail_retrieve)
    case = run_eval.EvalCaseData(
        case_id="eval_1",
        query="如何识别诈骗",
        expected_output="识别高风险信号。",
        scam_id="shuadan",
    )

    test_case = run_eval._build_test_case(FakeLLMTestCase, case)

    assert test_case.kwargs["actual_output"] == "未检索到可用反诈知识。"
    assert test_case.kwargs["retrieval_context"] == []
