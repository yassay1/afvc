"""统一 LLM 封装。

对话叙述走 get_conversation_llm()；连通性脚本走 get_llm()。
旧八节点的 parse/report 专用实例已删除。
"""

import logging
from langchain_openai import ChatOpenAI
from backend.core.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS,
    is_llm_enabled,
)

logger = logging.getLogger(__name__)

_CONVERSATION_LLM: ChatOpenAI | None = None


def _create_chat_openai(temperature: float) -> ChatOpenAI:
    """创建 ChatOpenAI 实例，统一校验 API Key 与开关。"""
    if not is_llm_enabled():
        raise RuntimeError(
            "LLM calls are disabled. Set AFVC_USE_LLM=true to enable real model calls."
        )
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY 未配置，请在 .env 文件中设置，"
            "可参考 .env.example 文件。"
        )

    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=temperature,
        timeout=OPENAI_TIMEOUT_SECONDS,
        max_retries=OPENAI_MAX_RETRIES,
    )


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """获取一次性 LLM 实例（连通性检查 / 非对话路径）。"""
    return _create_chat_openai(temperature=temperature)


def get_agent_llm() -> ChatOpenAI:
    """Main Agent 工具调用用 LLM（略低温度，与叙述单例分离）。"""
    logger.info("初始化 LLM Agent 实例（model=%s）", OPENAI_MODEL)
    return _create_chat_openai(temperature=0.2)


def get_conversation_llm() -> ChatOpenAI:
    """对话叙述用 LLM（懒加载单例）。"""
    global _CONVERSATION_LLM
    if _CONVERSATION_LLM is None:
        logger.info("初始化 LLM 对话实例（model=%s）", OPENAI_MODEL)
        _CONVERSATION_LLM = _create_chat_openai(temperature=0.5)
    return _CONVERSATION_LLM
