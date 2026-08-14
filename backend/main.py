"""AFVC 诊断能力平台 —— FastAPI 入口。

启动方式：
    python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    LANGSMITH_TRACING,
    LANGSMITH_API_KEY,
    LANGSMITH_PROJECT,
)

# ── 日志 ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("afvc")

# ── LangSmith 初始化 ──────────────────────────────────────────

if LANGSMITH_TRACING.lower() == "true" and LANGSMITH_API_KEY:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT


# ── 应用生命周期 ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的操作。"""
    from pathlib import Path

    from backend.core.config import is_sql_backend

    raw_dir = Path(__file__).parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    logger.info("AFVC v%s 启动，数据目录：%s", PROJECT_VERSION, raw_dir)
    if is_sql_backend():
        from backend.infrastructure.db import init_db
        from backend.infrastructure.workorder_repo import seed_default_if_empty

        init_db(with_checkpointer=True)
        seeded = seed_default_if_empty()
        if seeded:
            logger.info("seeded workorders: %s rows", seeded.get("row_count"))
        else:
            logger.info("workorders table already has data")
    else:
        logger.warning("AFVC_DATA_BACKEND=file：工单仍读 raw 文件（紧急回退）")
    yield
    logger.info("AFVC 关闭")


# ── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(
    title=PROJECT_NAME,
    description=(
        "面向地铁 AFC 闸机维修工单数据的诊断能力平台。"
        "通过 /usecases/* 暴露业务用例；/interaction/turn 在 LLM+Graph 开启时走 LangGraph 主 Agent。"
    ),
    version=PROJECT_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查 ──────────────────────────────────────────────────

@app.get("/health", tags=["健康检查"])
def health_check():
    return {
        "status": "ok",
        "message": "AFVC 后端运行正常",
        "version": PROJECT_VERSION,
    }


# ── 注册路由 ──────────────────────────────────────────────────

from backend.api.upload_api import router as upload_router
from backend.api.usecases_api import router as usecases_router
from backend.api.interaction_api import router as interaction_router

app.include_router(upload_router)
app.include_router(usecases_router)
app.include_router(interaction_router)
