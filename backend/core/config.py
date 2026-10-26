"""项目配置 —— 唯一入口。从 .env 读取，缺省与 .env.example 对齐。"""

import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.deepseek.com",
)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "deepseek-flash")
OPENAI_TIMEOUT_SECONDS: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "15"))
OPENAI_MAX_RETRIES: int = int(os.getenv("OPENAI_MAX_RETRIES", "1"))
AFVC_USE_LLM: str = os.getenv("AFVC_USE_LLM", "false")
AFVC_AGENT_GRAPH: str = os.getenv("AFVC_AGENT_GRAPH", "true")
AFVC_DATA_BACKEND: str = os.getenv("AFVC_DATA_BACKEND", "sql")
AFVC_DATA_PROFILE: str = os.getenv("AFVC_DATA_PROFILE", "production")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://afvc:afvc@localhost:5432/afvc",
)

LANGSMITH_TRACING: str = os.getenv("LANGSMITH_TRACING", "false")
LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "afvc")

# Session cookie gate (fixed accounts; no self-registration).
AFVC_SESSION_COOKIE: str = os.getenv("AFVC_SESSION_COOKIE", "afvc_session")
AFVC_SESSION_TTL_HOURS: float = float(os.getenv("AFVC_SESSION_TTL_HOURS", "168"))
AFVC_SESSION_SECURE: str = os.getenv("AFVC_SESSION_SECURE", "false")

PROJECT_NAME: str = "AFVC 检修安排闭环"
PROJECT_VERSION: str = "0.4.0"


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_llm_enabled() -> bool:
    """Return whether real LLM calls are enabled for this process."""
    return _flag(os.getenv("AFVC_USE_LLM", AFVC_USE_LLM))


def is_agent_graph_flag() -> bool:
    """Return the AFVC_AGENT_GRAPH switch (independent of LLM)."""
    return _flag(os.getenv("AFVC_AGENT_GRAPH", AFVC_AGENT_GRAPH))


def should_use_agent_graph() -> bool:
    """Main conversation path uses LangGraph only when LLM + graph are both on."""
    return is_agent_graph_flag() and is_llm_enabled()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", DATABASE_URL).strip()
    if get_data_profile() == "demo":
        parsed = urlparse(url)
        if (parsed.scheme not in {"postgresql", "postgres"}
                or parsed.hostname != "127.0.0.1"
                or parsed.port != 55433 or parsed.path != "/afvc_demo"):
            raise RuntimeError(
                "demo 模式只允许连接 127.0.0.1:55433/afvc_demo；请使用 docker-compose.demo.yml"
            )
    return url


def get_data_profile() -> str:
    profile = os.getenv("AFVC_DATA_PROFILE", AFVC_DATA_PROFILE).strip().lower()
    if profile not in {"demo", "production"}:
        raise RuntimeError("AFVC_DATA_PROFILE 必须是 demo 或 production")
    return profile


def is_sql_backend() -> bool:
    """Postgres is the workorder source of truth unless emergency file fallback is set."""
    backend = os.getenv("AFVC_DATA_BACKEND", AFVC_DATA_BACKEND).strip().lower()
    if get_data_profile() == "demo":
        if backend != "sql":
            raise RuntimeError("demo 模式必须使用独立 Postgres，AFVC_DATA_BACKEND=sql")
        return True
    return backend not in {"file", "excel", "raw"}


def get_openai_model() -> str:
    """Runtime chat model name (OpenAI-compatible provider)."""
    return os.getenv("OPENAI_MODEL", OPENAI_MODEL).strip() or OPENAI_MODEL


def has_usable_llm_key() -> bool:
    """True when OPENAI_API_KEY looks like a real provider key, not the example placeholder."""
    key = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY).strip()
    return bool(key) and "YOUR" not in key.upper()


def has_usable_langsmith_key() -> bool:
    """True when LANGSMITH_API_KEY looks real, not the example placeholder."""
    key = os.getenv("LANGSMITH_API_KEY", LANGSMITH_API_KEY).strip()
    return bool(key) and "your-langsmith" not in key.lower()


def get_session_cookie_name() -> str:
    name = os.getenv("AFVC_SESSION_COOKIE", AFVC_SESSION_COOKIE).strip()
    return name or AFVC_SESSION_COOKIE


def get_session_ttl_hours() -> float:
    raw = os.getenv("AFVC_SESSION_TTL_HOURS", str(AFVC_SESSION_TTL_HOURS))
    try:
        hours = float(raw)
    except ValueError as exc:
        raise RuntimeError("AFVC_SESSION_TTL_HOURS 必须是数字") from exc
    if hours <= 0:
        raise RuntimeError("AFVC_SESSION_TTL_HOURS 必须大于 0")
    return hours


def is_session_cookie_secure() -> bool:
    return _flag(os.getenv("AFVC_SESSION_SECURE", AFVC_SESSION_SECURE))
