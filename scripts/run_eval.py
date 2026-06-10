"""Manual DeepEval entrypoint for the anti-fraud RAG pipeline."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPEVAL_API_KEY_MISSING_MESSAGE,
    DEEPEVAL_DEPENDENCY_ERROR_MESSAGE,
    DEEPEVAL_MAX_CASES,
    DEEPEVAL_METRIC_THRESHOLD,
    DEEPEVAL_NO_CASES_MESSAGE,
    EVAL_DATASET_FILE,
    LLM_MODEL,
)
from services import rag

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvalCaseData:
    case_id: str
    query: str
    expected_output: str
    scam_id: str


def load_eval_cases(dataset_file: Path = EVAL_DATASET_FILE) -> list[EvalCaseData]:
    with open(dataset_file, encoding="utf-8") as f:
        payload = json.load(f)

    raw_cases = payload.get("generation_cases", [])
    if not isinstance(raw_cases, list):
        return []

    cases = []
    for raw_case in raw_cases[:DEEPEVAL_MAX_CASES]:
        if not isinstance(raw_case, dict):
            continue
        query = str(raw_case.get("query", "")).strip()
        expected_output = str(raw_case.get("ground_truth", "")).strip()
        if not query or not expected_output:
            continue
        cases.append(
            EvalCaseData(
                case_id=str(raw_case.get("id", "")).strip(),
                query=query,
                expected_output=expected_output,
                scam_id=str(raw_case.get("scam_id", "")).strip(),
            )
        )
    return cases


def run_evaluation(deepeval_bundle: dict[str, Any] | None = None):
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(DEEPEVAL_API_KEY_MISSING_MESSAGE)

    bundle = deepeval_bundle or _load_deepeval()
    cases = load_eval_cases()
    if not cases:
        raise RuntimeError(DEEPEVAL_NO_CASES_MESSAGE)

    judge = bundle["OpenAIModel"](
        model=LLM_MODEL,
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
    )
    metrics = [
        bundle["FaithfulnessMetric"](threshold=DEEPEVAL_METRIC_THRESHOLD, model=judge),
        bundle["AnswerRelevancyMetric"](threshold=DEEPEVAL_METRIC_THRESHOLD, model=judge),
        bundle["ContextualPrecisionMetric"](threshold=DEEPEVAL_METRIC_THRESHOLD, model=judge),
        bundle["ContextualRecallMetric"](threshold=DEEPEVAL_METRIC_THRESHOLD, model=judge),
    ]
    test_cases = [_build_test_case(bundle["LLMTestCase"], case) for case in cases]
    return bundle["evaluate"](test_cases, metrics)


def _load_deepeval() -> dict[str, Any]:
    try:
        from deepeval import evaluate
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            FaithfulnessMetric,
        )
        from deepeval.models import OpenAIModel
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        raise RuntimeError(DEEPEVAL_DEPENDENCY_ERROR_MESSAGE) from exc

    return {
        "evaluate": evaluate,
        "FaithfulnessMetric": FaithfulnessMetric,
        "AnswerRelevancyMetric": AnswerRelevancyMetric,
        "ContextualPrecisionMetric": ContextualPrecisionMetric,
        "ContextualRecallMetric": ContextualRecallMetric,
        "LLMTestCase": LLMTestCase,
        "OpenAIModel": OpenAIModel,
    }


def _build_test_case(llm_test_case_class, case: EvalCaseData):
    contexts = _retrieve_contexts(case.query)
    retrieval_context = [
        str(context.get("document", "")).strip()
        for context in contexts
        if str(context.get("document", "")).strip()
    ]
    return llm_test_case_class(
        input=case.query,
        actual_output=_build_actual_output(retrieval_context),
        expected_output=case.expected_output,
        retrieval_context=retrieval_context,
    )


def _retrieve_contexts(query: str) -> list[dict]:
    try:
        return rag.retrieve(query)
    except Exception as exc:
        logger.warning("Eval RAG retrieval failed: %s", type(exc).__name__)
        return []


def _build_actual_output(retrieval_context: list[str]) -> str:
    if not retrieval_context:
        return "未检索到可用反诈知识。"
    return "\n".join(retrieval_context)


def main() -> int:
    try:
        run_evaluation()
    except RuntimeError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
