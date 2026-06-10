# docs/WORKFLOW.md
# 工作流规则 · 快速参考 · 启动顺序

> **何时读本文件：** 每次开始新任务前必读。

---

## 一、任务开始检查清单

开始写任何代码前，逐项确认：

- [ ] 已完整读完 `CLAUDE.md`
- [ ] 已根据任务类型找到并读完对应的 `docs/*.md`
- [ ] 已用 `view` 查看要修改的现有文件
- [ ] 已确认要用到的常量在 `config.py` 里已定义（没有则先补充）
- [ ] 已输出实现计划（列出要创建/修改哪些文件），等待确认后再写代码

---

## 二、修改现有文件前

- 必须先 `view` 完整内容，再动手
- 只改需要改的部分，不重写无关代码
- 修改 `data/scam_cards.json` 或 `data/review_cards.json`（RAG 知识库文件）后，必须重新运行 `scripts/build_vectorstore.py`；修改 `risk_rules.json`、`script_templates.json`、`eval_dataset.json` 等配置/模板文件**无需**重跑
- 新增骗局类型，必须同时更新：`scam_cards.json`、`script_templates.json`、`risk_rules.json`

---

## 三、完成任务后

- 检查是否有字符串应改成 `config.py` 里的常量
- 对照 `docs/BACKEND.md` 第三节安全规范逐项检查
- 新接口必须有对应的 Pydantic 请求/响应模型

---

## 四、首次启动顺序（必须按序执行）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入：DEEPSEEK_API_KEY=sk-...

# 3. 构建 Chroma 向量库（只需一次，修改 data/scam_cards.json 后需重跑）
python scripts/build_vectorstore.py

# 4. 初始化 SQLite 数据库
python -c "from services.db_service import init_db; init_db()"

# 5. 启动后端（Phoenix 面板在 main.py 内自动启动）
uvicorn main:app --reload --port 8000
```

启动成功后：
- API 文档：`http://localhost:8000/docs`
- Phoenix 监控面板：`http://localhost:6006`
- 前端入口：`http://localhost:8000`

---

## 五、日常运行命令

```bash
# 启动服务
uvicorn main:app --reload --port 8000

# 手动触发 DeepEval 评估（修改知识库或 RAG 参数后运行）
python scripts/run_eval.py

# 重建向量库
python scripts/build_vectorstore.py
```

---

## 六、快速参考：模块职责一览

| 文件 | 职责 | 被谁调用 |
|------|------|----------|
| `config.py` | 全局常量 | 所有模块 |
| `services/rule_engine.py` | 关键词匹配，返回风险等级 | `routers/theater.py` |
| `services/rag.py` | Chroma 向量检索，含 Phoenix span | `services/ai_service.py` |
| `services/ai_service.py` | 构建 prompt + 调用 DeepSeek API | `routers/theater.py` |
| `services/db_service.py` | SQLite 所有读写 | `routers/*` |
| `services/gamification.py` | 积分、徽章、进度计算 | `routers/user.py` |
| `scripts/build_vectorstore.py` | 一次性构建向量库 | 手动运行 |
| `scripts/run_eval.py` | DeepEval 评估入口 | 手动运行 |
| Phoenix `localhost:6006` | LLM 调用追踪、延迟、token 监控 | `main.py` 初始化后自动生效 |

---

## 七、新建文件时的位置规则

| 文件类型 | 放在哪里 |
|----------|----------|
| FastAPI 路由 | `routers/` |
| 业务逻辑 / 服务 | `services/` |
| 知识库 / 规则 / 测试集 | `data/` |
| 一次性脚本 | `scripts/` |
| 前端页面 | `frontend/` |
| **禁止** 在 `main.py` 写业务逻辑 | — |
| **禁止** 在 `routers/` 直接调用 Chroma 或 DeepSeek/OpenAI SDK | — |
