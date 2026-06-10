# docs/BACKEND.md
# FastAPI 规范 · 安全规范 · 前端规范

> **何时读本文件：** 写 FastAPI 路由时、修改前端页面时、任意接口完成后做安全检查时。

---

## 一、FastAPI 路由规范

### 标准路由结构
```python
# routers/theater.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.rule_engine import analyze_risk
from services.ai_service import get_scammer_reply

router = APIRouter(prefix="/theater", tags=["theater"])

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[dict]     # [{"role": "user"/"assistant", "content": "..."}]
    scam_id: str

class ChatResponse(BaseModel):
    scammer_reply: str | None   # BLOCK 时为 None
    risk_level: str
    risk_score: int
    risk_message: str
    interrupted: bool

@router.post("/chat", response_model=ChatResponse)
async def theater_chat(req: ChatRequest):
    ...
```

### 禁止在路由文件中出现的代码

```python
# ❌ 禁止：直接调用 Chroma
collection.query(...)

# ❌ 禁止：直接调用 DeepSeek/OpenAI SDK
client.chat.completions.create(...)

# ❌ 禁止：直接连接数据库
sqlite3.connect(...)

# ❌ 禁止：路由函数体超过 25 行（必须抽到 services/）

# ❌ 禁止：硬编码任何字符串常量（URL、模型名、路径）
```

### 错误处理规范
- 用户侧错误：`raise HTTPException(status_code=400, detail="面向用户的说明")`
- 服务器错误：在 `services/` 层 try/except 后记录到 logger，向上抛出
- **禁止将内部异常信息（堆栈、路径、数据库错误）直接返回给前端**
- AI 调用失败：返回 fallback 文本，不中断整个请求流程

---

## 二、安全规范

### 输入处理
```python
from config import MAX_USER_INPUT_DB, MAX_USER_INPUT_LLM

# 存库前截断
content_for_db = user_input[:MAX_USER_INPUT_DB]

# 传给 LLM 前截断
content_for_llm = user_input[:MAX_USER_INPUT_LLM]
```

### 禁止事项（每个接口完成后对照检查）
- 禁止将 API key 的任何部分出现在响应、日志或前端代码中
- 禁止接受来自前端的 `model`、`max_tokens` 参数（模型参数只在后端 config.py 定义）
- 禁止在日志或响应中输出用户的真实姓名、手机号、身份证号
- 禁止接受并执行来自用户输入的代码或命令字符串
- 禁止在错误响应中包含文件路径、数据库结构、内部变量名

---

## 三、前端规范

### 背景
现有 `antiFraud_showcase.html` 是**设计原型**，供参考 UI 风格和配色，但它直接
调用 DeepSeek API（API Key 暴露在前端），不能直接用于正式版本。
新前端需要重新实现，所有 AI 调用改为请求本地 FastAPI 后端。

### 页面结构（对应 `frontend/` 目录）

| 文件 | 功能 | 对应后端接口 |
|------|------|-------------|
| `index.html` | 场景选择，展示5种骗局卡片 | `GET /theater/templates` |
| `theater.html` | 核心剧场，对话 + 实时风险提示 | `POST /theater/chat` |
| `review.html` | 话术揭秘 + 复盘报告 | `POST /theater/reveal` |
| `report.html` | 可疑内容/链接举报 | `POST /report/submit` |
| `profile.html` | 积分·徽章·完成进度 | `GET /user/progress` |

### `frontend/assets/api.js` — 统一 HTTP 客户端（必须存在）
```javascript
// 所有页面通过此文件调用后端，禁止在页面内直接写 fetch
const API_BASE = "http://localhost:8000";

async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiGet(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}
```

### UI 设计规范
- 配色沿用 `antiFraud_showcase.html` 的暗色主题（背景 `#060d1a`，强调色 `#00dfff`）
- 字体：`'PingFang SC', 'Microsoft YaHei', sans-serif`
- 风险等级颜色：critical=`#ff3a4e`，high=`#ffa502`，medium=`#00dfff`，safe=`#2ed573`
- 禁止在任何 HTML 页面的 `<script>` 内直接调用 DeepSeek API
- 禁止在前端代码中出现 DeepSeek API Key
