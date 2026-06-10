# docs/AI_PIPELINE.md
# AI 流程规范 · Phoenix 可观测性 · LLM 调用 · DeepEval 评估

> **何时读本文件：** 实现任何涉及 AI 调用的接口时（theater/chat、复盘报告、话术揭秘等）。

---

## 一、`/theater/chat` 处理顺序（强制，不得更改）

```
1. 解析请求，校验 session_id 非空
2. 规则引擎分析用户输入 → risk_result（纯同步，约 1ms）
3. ── 若 risk_result.action == "BLOCK" ──
   → 直接返回 ChatResponse(interrupted=True)，不调用 AI，不查向量库
4. rag.retrieve(user_input) → contexts
   （在 Phoenix span "chroma_retrieval" 内执行，见第二节）
5. 过滤 score < config.RAG_SIMILARITY_THRESHOLD 的结果
6. ai_service.get_scammer_reply(history, user_input, contexts, template)
   （DeepSeek API 调用，Phoenix 自动追踪）
7. db_service.save_message(session_id, "user", user_input, risk_result)
8. db_service.save_message(session_id, "scammer", reply, None)
9. 返回 ChatResponse
```

**规则引擎永远在 AI 之前运行，这是强制约束。**

---

## 二、Phoenix 可观测性

Phoenix 在 `main.py` 启动时已全局初始化，**OpenAI SDK 的所有调用自动被追踪**（DeepSeek 使用 OpenAI 兼容接口），
无需在每个函数里手动添加日志。

```python
# main.py（已写好，不要修改这部分）
import phoenix as px
from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor

px.launch_app()
tracer_provider = register(
    project_name="anti_fraud_theater",
    auto_instrument=True
)
```

**唯一需要手动添加 span 的地方是 Chroma 检索**（Phoenix 没有 Chroma 自动埋点）：

```python
# services/rag.py
from opentelemetry import trace
from config import RAG_TOP_K, RAG_SIMILARITY_THRESHOLD

tracer = trace.get_tracer(__name__)

def retrieve(query: str, embedding: list) -> list[dict]:
    with tracer.start_as_current_span("chroma_retrieval") as span:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=RAG_TOP_K
        )
        top_score = results["distances"][0][0] if results["distances"] else 0
        span.set_attribute("retrieval.top_k", RAG_TOP_K)
        span.set_attribute("retrieval.top1_score", round(top_score, 4))
        span.set_attribute("retrieval.query_len", len(query))
        # 过滤低相关性结果
        return [
            {"id": mid, "document": doc, "score": 1 - dist}
            for mid, doc, dist in zip(
                results["ids"][0],
                results["documents"][0],
                results["distances"][0]
            )
            if (1 - dist) >= RAG_SIMILARITY_THRESHOLD
        ]
```

Phoenix dashboard 访问 `localhost:6006`，可看到每次请求的完整 trace、
延迟分布、token 消耗、prompt/response 内容。

---

## 三、LLM 调用规范

所有常量从 `config.py` 导入，禁止硬编码。

```python
from config import LLM_MODEL, MAX_TOKENS_SCAMMER, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from openai import OpenAI

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
```

**各场景 max_tokens 限制：**

| 场景 | 常量 | 说明 |
|------|------|------|
| 骗子角色扮演 | `MAX_TOKENS_SCAMMER = 200` | 回复要短，不超过80字 |
| 话术揭秘分析 | `MAX_TOKENS_REVEAL = 800` | 详细分析 |
| 复盘报告生成 | `MAX_TOKENS_REVIEW = 600` | 结构化报告 |

**Prompt 构建规则：**
- 骗子 system prompt 从 `script_templates.json` 动态拼装，禁止硬编码话术内容
- 所有 prompt 必须包含"这是反诈教育角色扮演"的明确声明
- RAG 检索结果用 `---参考知识---` 和 `---` 包裹后注入 prompt
- 传给 LLM 的用户输入截断到 `config.MAX_USER_INPUT_LLM` 个字符

---

## 四、DeepEval 评估规范

评估只在以下情况手动触发，**不在请求路径中运行**：
- 修改了 `data/scam_cards.json` 或 `data/risk_rules.json` 后
- 调整了 RAG 参数（`top_k`、`embedding_model`、`similarity_threshold`）后
- 正式提交前做最终验收

```python
# scripts/run_eval.py 的核心结构
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric, AnswerRelevancyMetric,
    ContextualPrecisionMetric, ContextualRecallMetric,
)
from deepeval.test_case import LLMTestCase
import os
from deepeval.models import OpenAIModel

# 用 DeepSeek 做评估 judge（成本低、OpenAI 兼容接口）
judge = OpenAIModel(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
)

metrics = [
    FaithfulnessMetric(threshold=0.7, model=judge),
    AnswerRelevancyMetric(threshold=0.7, model=judge),
    ContextualPrecisionMetric(threshold=0.7, model=judge),
    ContextualRecallMetric(threshold=0.7, model=judge),
]
```

**构建 `LLMTestCase` 的必填字段：**

| 字段 | 来源 |
|------|------|
| `input` | `eval_dataset.json` 里的 `query` |
| `actual_output` | 调用真实 RAG pipeline 生成的回答 |
| `expected_output` | `eval_dataset.json` 里的 `ground_truth` |
| `retrieval_context` | Chroma 检索到的文档列表（字符串列表）|

测试集控制在 **20 条以内**，避免评估 token 消耗过大。
