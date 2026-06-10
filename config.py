"""
config.py — 全局常量
所有模块从这里导入常量，禁止在其他任何文件硬编码路径、模型名、数值。
"""

import os
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
RISK_RULES_FILE = DATA_DIR / "risk_rules.json"
SCRIPT_TEMPLATES_FILE = DATA_DIR / "script_templates.json"
SCAM_CARDS_FILE = DATA_DIR / "scam_cards.json"
REVIEW_CARDS_FILE = DATA_DIR / "review_cards.json"
EVAL_DATASET_FILE = DATA_DIR / "eval_dataset.json"
CHROMA_DIR = BASE_DIR / "chroma_db"
LOGS_DIR  = BASE_DIR / "logs"
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_ASSETS_DIR = FRONTEND_DIR / "assets"
FRONTEND_INDEX_FILE = FRONTEND_DIR / "index.html"
FRONTEND_THEATER_FILE = FRONTEND_DIR / "theater.html"
FRONTEND_REVIEW_FILE = FRONTEND_DIR / "review.html"
FRONTEND_REPORT_FILE = FRONTEND_DIR / "report.html"
FRONTEND_PROFILE_FILE = FRONTEND_DIR / "profile.html"
FRONTEND_ASSETS_ROUTE = "/assets"
FRONTEND_INDEX_ROUTE = "/"
FRONTEND_THEATER_ROUTE = "/theater.html"
FRONTEND_REVIEW_ROUTE = "/review.html"
FRONTEND_REPORT_ROUTE = "/report.html"
FRONTEND_PROFILE_ROUTE = "/profile.html"
METRICS_DB = str(BASE_DIR / "metrics.db")
APP_DB     = str(BASE_DIR / "app.db")

# ── FastAPI / Observability ───────────────────────────────────
APP_NAME = "金融反诈剧场"
APP_VERSION = "0.1.0"
PHOENIX_PROJECT_NAME = "anti_fraud_theater"
HEALTH_STATUS_OK = "ok"

THEATER_ROUTER_PREFIX = "/theater"
REPORT_ROUTER_PREFIX = "/report"
USER_ROUTER_PREFIX = "/user"
THEATER_ROUTER_TAG = "theater"
REPORT_ROUTER_TAG = "report"
USER_ROUTER_TAG = "user"

# ── LLM ───────────────────────────────────────────────────────
LLM_MODEL            = "deepseek-chat"
MAX_TOKENS_SCAMMER   = 200    # 骗子角色扮演，回复要短
MAX_TOKENS_REVEAL    = 800    # 话术揭秘分析
MAX_TOKENS_REVIEW    = 600    # 复盘报告生成

# ── RAG / 向量库 ───────────────────────────────────────────────
EMBED_MODEL              = "BAAI/bge-small-zh-v1.5"
CHROMA_COLLECTION        = "scam_knowledge"
RAG_TOP_K                = 3
RAG_SIMILARITY_THRESHOLD = 0.3   # 低于此分数的检索结果丢弃
VECTORSTORE_SOURCE_FILES = ("scam_cards.json", "review_cards.json")
VECTORSTORE_FIELD_LABELS = {
    "name": "骗局名称",
    "title": "标题",
    "target": "目标人群",
    "tactics": "常见套路",
    "red_flags": "风险信号",
    "prevention": "防范建议",
    "legal": "法律依据",
    "typical_case": "典型案例",
    "content": "知识正文",
    "text": "文本",
}
VECTORSTORE_DEPENDENCY_ERROR_MESSAGE = "缺少向量库依赖，请先运行 pip install -r requirements.txt。"
DEEPEVAL_METRIC_THRESHOLD = 0.7
DEEPEVAL_MAX_CASES = 20
DEEPEVAL_API_KEY_MISSING_MESSAGE = "DEEPSEEK_API_KEY 未配置，无法运行 DeepEval 评估。"
DEEPEVAL_DEPENDENCY_ERROR_MESSAGE = "DeepEval 依赖未安装，请先运行 pip install -r requirements.txt。"
DEEPEVAL_NO_CASES_MESSAGE = "评估数据集为空，无法运行 DeepEval 评估。"

# ── 业务枚举（与 risk_rules.json / scam_cards.json 保持一致）─
FRAUD_TYPES = [
    "shuadan",       # 刷单返利
    "gongjianfa",    # 冒充公检法
    "touzilicai",    # 虚假投资理财
    "xiaoyuandai",   # 校园贷
    "youxijiaoyi",   # 游戏账号交易
]

RISK_LEVELS = ["critical", "high", "medium", "normal", "safe"]

RISK_ACTION_BLOCK = "BLOCK"
RISK_ACTION_WARN = "WARN"
RISK_ACTION_HINT = "HINT"
RISK_ACTION_PRAISE = "PRAISE"
RISK_ACTION_NONE = "NONE"
RISK_ACTIONS = [
    RISK_ACTION_BLOCK,
    RISK_ACTION_WARN,
    RISK_ACTION_HINT,
    RISK_ACTION_PRAISE,
    RISK_ACTION_NONE,
]

DEFAULT_RISK_LEVEL = "normal"
DEFAULT_RISK_SCORE = 20
DEFAULT_RISK_ACTION = RISK_ACTION_NONE
DEFAULT_RISK_MESSAGE = "暂未发现明显风险，请继续保持警惕。"
DEFAULT_MATCHED_KEYWORD = ""
CHAT_FALLBACK_REPLY = "我需要再核实一下信息，我们先暂停这一步。"
TEMPLATE_LOAD_ERROR_MESSAGE = "剧场场景暂时无法读取，请稍后再试。"
SCAM_CARD_LOAD_ERROR_MESSAGE = "反诈知识暂时无法读取，请稍后再试。"
REVIEW_GENERATE_ERROR_MESSAGE = "复盘报告暂时无法生成，请稍后再试。"
SESSION_ID_EMPTY_ERROR_MESSAGE = "session_id 不能为空"
SCAMMER_REPLY_MAX_CHARS = 80
SCAMMER_FALLBACK_HISTORY_STEP_SIZE = 2
SCAMMER_STAGE_SEPARATORS = ("：", ":")

# ── 输入长度限制 ───────────────────────────────────────────────
MAX_USER_INPUT_DB  = 1000   # 存库前截断
MAX_USER_INPUT_LLM = 500    # 传给 LLM 前截断
MAX_LOG_TEXT_LEN   = 120    # 写入日志的最大字符数
MAX_REPORT_CONTENT_LEN = 1000
MAX_REPORT_URL_LEN = 500
MAX_SESSION_ID_LEN = 64
MAX_USER_ID_LEN = 64
MAX_SCAM_ID_LEN = 32

# ── 举报接口文案 ───────────────────────────────────────────────
REPORT_STATUS_RECEIVED = "received"
REPORT_SUBMIT_SUCCESS_MESSAGE = "举报已提交，我们会用于后续反诈分析。"
REPORT_EMPTY_ERROR_MESSAGE = "举报内容或链接至少填写一项。"
REPORT_SAVE_ERROR_MESSAGE = "举报暂时无法提交，请稍后再试。"
REPORT_RISK_LEVEL_INVALID_ERROR_MESSAGE = "risk_level 不在支持的风险等级中"

# ── 游戏化积分 ─────────────────────────────────────────────────
DEFAULT_USER_PROGRESS_SCORE = 0
DEFAULT_USER_PROGRESS_STREAK = 0
DEFAULT_SCAM_COMPLETION_COUNT = 0
GAMIFICATION_POINTS_PER_COMPLETION = 10
GAMIFICATION_STREAK_INCREMENT = 1
GAMIFICATION_STATUS_COMPLETED = "completed"
GAMIFICATION_STATUS_ALREADY_CLAIMED = "already_claimed"
GAMIFICATION_COMPLETE_SUCCESS_MESSAGE = "学习进度已更新。"
GAMIFICATION_ALREADY_CLAIMED_MESSAGE = "本次学习已经领取过积分。"
USER_ID_EMPTY_ERROR_MESSAGE = "user_id 不能为空"
SCAM_ID_EMPTY_ERROR_MESSAGE = "scam_id 不能为空"
SCAM_ID_INVALID_ERROR_MESSAGE = "scam_id 不在支持的骗局类型中"
USER_PROGRESS_LOAD_ERROR_MESSAGE = "用户进度暂时无法读取，请稍后再试。"
USER_PROGRESS_SAVE_ERROR_MESSAGE = "用户进度暂时无法更新，请稍后再试。"
GAMIFICATION_BADGES = [
    {
        "id": "first_guard",
        "name": "反诈新手",
        "min_score": 10,
        "min_completed_total": 1,
        "min_unique_scam_types": 1,
    },
    {
        "id": "steady_learner",
        "name": "稳健学习者",
        "min_score": 30,
        "min_completed_total": 3,
        "min_unique_scam_types": 2,
    },
    {
        "id": "scenario_master",
        "name": "全场景守护者",
        "min_score": 50,
        "min_completed_total": 5,
        "min_unique_scam_types": len(FRAUD_TYPES),
    },
]

# ── API Key（从环境变量读取，禁止硬编码）────────────────────────
DEEPSEEK_API_KEY  = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
