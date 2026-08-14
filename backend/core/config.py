"""项目配置 —— 唯一入口。从 .env 读取，缺省与 .env.example 对齐。"""

import os
from dotenv import load_dotenv

load_dotenv()


OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv(
    "OPENAI_BASE_URL",
    "https://open.bigmodel.cn/api/paas/v4/",
)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "glm-4-flash")
OPENAI_TIMEOUT_SECONDS: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "15"))
OPENAI_MAX_RETRIES: int = int(os.getenv("OPENAI_MAX_RETRIES", "1"))
AFVC_USE_LLM: str = os.getenv("AFVC_USE_LLM", "false")
AFVC_AGENT_GRAPH: str = os.getenv("AFVC_AGENT_GRAPH", "true")
AFVC_DATA_BACKEND: str = os.getenv("AFVC_DATA_BACKEND", "sql")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://afvc:afvc@localhost:5432/afvc",
)

LANGSMITH_TRACING: str = os.getenv("LANGSMITH_TRACING", "false")
LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "afvc")

PROJECT_NAME: str = "AFVC 诊断能力平台"
PROJECT_VERSION: str = "0.3.0"


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
    return os.getenv("DATABASE_URL", DATABASE_URL).strip()


def is_sql_backend() -> bool:
    """Postgres is the workorder source of truth unless emergency file fallback is set."""
    backend = os.getenv("AFVC_DATA_BACKEND", AFVC_DATA_BACKEND).strip().lower()
    return backend not in {"file", "excel", "raw"}
