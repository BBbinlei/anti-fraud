# docs/DATA.md
# 数据格式规范 · 数据库规范

> **何时读本文件：** 新建或修改任何数据结构、JSON 文件、数据库表之前。

---

## 一、全局枚举值（全项目统一，禁止自造新值）

**骗局类型 ID：**
```
shuadan       刷单返利诈骗
gongjianfa    冒充公检法诈骗
touzilicai    虚假投资理财诈骗
xiaoyuandai   校园贷陷阱
youxijiaoyi   游戏账号交易诈骗
```

**风险等级：**
```
critical  score=90  action=BLOCK    立即中断，红色警告，不调用 AI
high      score=70  action=WARN     插入橙色警告气泡
medium    score=40  action=HINT     显示蓝色提示
safe      score=0   action=PRAISE   绿色鼓励
normal    score=20  action=NONE     无动作
```

---

## 二、JSON 文件格式规范

### `data/scam_cards.json` — 骗局知识库（RAG 向量化的主要来源）
```json
{
  "scams": [
    {
      "id": "shuadan",
      "name": "刷单返利诈骗",
      "target": "在校学生",
      "tactics": ["先小额返利建立信任", "逐步提高垫付金额", "制造卡单借口"],
      "red_flags": ["刷单", "垫付", "返利", "日结"],
      "prevention": ["刷单本身违法", "任何要垫资的兼职都是诈骗"],
      "legal": "《刑法》第266条诈骗罪",
      "typical_case": "2024年武汉某大学生被刷单诈骗损失2万元"
    }
  ]
}
```

### `data/risk_rules.json` — 规则引擎规则定义
```json
{
  "rules": [
    {
      "level": "critical",
      "score": 90,
      "keywords": ["我转给你", "我打款", "汇款", "买点卡"],
      "action": "BLOCK",
      "message": "🚨 高危！您正准备转账，这是诈骗最后一步，请立即停止！"
    }
  ]
}
```
规则按 `score` 从高到低排列，匹配到第一条即返回，不继续检查。

### `data/script_templates.json` — 话术剧本模板
```json
{
  "templates": [
    {
      "scam_id": "shuadan",
      "difficulty": 1,
      "opener": "你好同学，我们公司招募兼职推广员，每单30元，日结，不需要垫付，感兴趣吗？",
      "persona": "热情、急于成交的'客服'",
      "escalation_steps": [
        "先给小额返利：已给你结了第一单50元，很简单吧",
        "提高金额：这单需要垫付200元，完成立刻返还加佣金",
        "制造借口：你的任务卡单了！需再垫付500元解除"
      ]
    }
  ]
}
```

### `data/eval_dataset.json` — DeepEval 测试集
```json
{
  "generation_cases": [
    {
      "id": "gen_001",
      "query": "刷单诈骗的常见套路是什么",
      "ground_truth": "刷单诈骗通常先给小额返利建立信任，再逐步要求垫付更大金额，最终以各种借口骗取资金"
    }
  ]
}
```

---

## 三、Pydantic 模型命名规范

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 请求体 | `XxxRequest` | `ChatRequest` |
| 响应体 | `XxxResponse` | `ChatResponse` |
| 内部数据类 | `XxxData` | `RiskData` |

**ID 格式：**
- `session_id`：UUID4 字符串，由前端生成，整个会话保持不变
- `request_id`：不再使用（Phoenix 自动生成 trace ID）

---

## 四、SQLite 表结构

### `sessions` 表
```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    scam_id      TEXT NOT NULL,
    started_at   TEXT,
    ended_at     TEXT,
    outcome      TEXT,     -- 'escaped' | 'fooled' | 'abandoned'
    final_score  INTEGER DEFAULT 0
);
```

### `messages` 表
```sql
CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL,   -- 'user' | 'scammer' | 'system'
    content      TEXT NOT NULL,
    risk_level   TEXT,
    risk_score   INTEGER,
    ts           TEXT
);
```

### `user_progress` 表
```sql
CREATE TABLE IF NOT EXISTS user_progress (
    user_id      TEXT PRIMARY KEY,
    total_score  INTEGER DEFAULT 0,
    streak       INTEGER DEFAULT 0,
    badges       TEXT DEFAULT '[]',    -- JSON 数组
    completed    TEXT DEFAULT '{}'     -- JSON 对象 {scam_id: count}
);
```

---

## 五、数据库操作规范

- 所有 SQLite 操作封装在 `services/db_service.py`，其他文件禁止直接 `import sqlite3`
- 连接用完立即关闭，禁止在模块级持久化 `connection` 对象
- 禁止字符串拼接 SQL，必须使用参数化查询：`cursor.execute("... WHERE id=?", (id,))`
- 用户输入存库前截断到 `config.MAX_USER_INPUT_DB` 个字符
