# 金融反诈剧场 · AGENTS.md
# 2026 睿抗机器人开发者大赛 · 方向三

> 本文件是项目入口。**开始任何任务前必须完整读完本文件，然后按第五节导航表找到对应文档再动手。**

---

## 一、项目定位

面向在校学生的反诈教育对话系统。用户扮演"潜在受害者"与 AI 骗子角色扮演，
系统实时检测风险并插入劝阻，结束后生成话术揭秘报告。

**赛题评分直接对应的四个功能（缺一必扣分）：**
反诈知识库 · 规则引擎 · 风险劝阻+举报 · 游戏化积分系统

---

## 二、技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | — |
| Web 框架 | FastAPI + uvicorn | 所有路由必须 async |
| LLM | DeepSeek API（OpenAI 兼容） | 常量见 `config.py` |
| Embedding | sentence-transformers | `bge-small-zh-v1.5`，本地运行 |
| 向量库 | ChromaDB PersistentClient | 路径见 `config.CHROMA_DIR` |
| 普通数据库 | SQLite（标准库 sqlite3） | 禁止使用 ORM |
| 可观测性 | Arize Phoenix | `main.py` 启动时初始化，自动追踪所有 LLM 调用 |
| RAG 评估 | DeepEval | `scripts/run_eval.py` 手动触发，LLM-as-judge |
| 常量管理 | `config.py` | 禁止在其他文件硬编码路径/模型名/数值 |

**禁止引入：** Django、Flask、SQLAlchemy、Pydantic v1、任何前端框架（React/Vue）。

---

## 三、目录结构

```
anti_fraud/
├── AGENTS.md
├── config.py                       ← 全局常量，所有模块从此导入
├── main.py                         ← router 挂载 + Phoenix 初始化，不写业务逻辑
├── requirements.txt
├── .env.example
│
├── routers/                        ← 路由层：只做请求解析和响应组装
│   ├── theater.py
│   ├── report.py
│   └── user.py
│
├── services/                       ← 业务逻辑层
│   ├── rule_engine.py              ← 纯同步，无 IO，无外部依赖
│   ├── ai_service.py               ← 构建 prompt + 调用 DeepSeek API
│   ├── rag.py                      ← Chroma 检索，含手动 Phoenix span
│   ├── db_service.py               ← SQLite 所有读写，禁止在其他文件直连数据库
│   └── gamification.py             ← 积分 / 徽章 / 进度计算
│
├── frontend/                       ← 原生 HTML/CSS/JS，无构建步骤
│   ├── index.html                  ← 主入口（场景选择）
│   ├── theater.html                ← 剧场互动页
│   ├── review.html                 ← 复盘报告页
│   ├── report.html                 ← 举报入口页
│   ├── profile.html                ← 学习成长页
│   └── assets/
│       ├── style.css
│       └── api.js                  ← 统一封装所有 fetch 请求，禁止在页面内直接调用
│
├── data/                           ← 运行时只读，禁止服务代码写入
│   ├── scam_cards.json
│   ├── script_templates.json
│   ├── risk_rules.json
│   ├── review_cards.json
│   └── eval_dataset.json
│
├── scripts/
│   ├── build_vectorstore.py        ← 一次性，修改 data/ 后需重跑
│   └── run_eval.py                 ← DeepEval 评估入口，手动触发
│
├── docs/                           ← Claude Code 规则文档
│   ├── WORKFLOW.md
│   ├── DATA.md
│   ├── AI_PIPELINE.md
│   ├── BACKEND.md
│   ├── architecture.html           ← 系统架构图（只读）
│   └── competition_rules.pdf       ← 赛题规则（只读）
│
├── logs/           ← gitignore
├── chroma_db/      ← gitignore
└── app.db          ← gitignore
```

---

## 四、赛题评分项

| 评分项 | 分值 | 验收标准 |
|--------|------|----------|
| 完成度 | 20 分 | 知识库·规则引擎·劝阻举报·游戏化，**各 5 分，缺项直接扣** |
| 创新性 | 20 分 | AI 对话剧场 + RAG 增强 + 多骗局场景覆盖 |
| 实用性 | 20 分 | 前后端完整联通，可现场流畅演示 |
| 成熟度 | 20 分 | 系统稳定、代码规范、Phoenix 有真实监控数据 |
| 安全性 | 20 分 | 无硬编码密钥、输入截断、无内部报错泄露给前端 |
| 团队表现 | +10 分 | 答辩加分项 |

**开发优先级：** 完成度 → 实用性 → 成熟度 → 安全性 → 创新性

---

## 五、文档导航

**每次新任务开始前，先读** `docs/WORKFLOW.md`。

| 任务类型 | 必读文档 |
|----------|----------|
| 新建 / 修改任何数据结构或数据库表 | `docs/DATA.md` |
| 实现 AI 相关接口（theater/chat 等） | `docs/AI_PIPELINE.md` |
| 编写 FastAPI 路由 | `docs/BACKEND.md` |
| 修改前端页面 | `docs/BACKEND.md`（第四节） |
| 完成任何接口后做安全检查 | `docs/BACKEND.md`（第三节） |
| 不确定读哪个 | `docs/WORKFLOW.md` 第六节快速参考 |

---

## 六、外部参考文件

| 文件 | 用途 |
|------|------|
| `docs/architecture.html` | 查看完整系统分层架构图 |
| `docs/competition_rules.pdf` | 查看赛题原文和完整评分细则 |
