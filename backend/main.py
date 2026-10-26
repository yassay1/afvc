"""AFVC 检修安排闭环 —— FastAPI 入口。

启动方式：
    python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import PROJECT_NAME, PROJECT_VERSION, get_data_profile, get_database_url
from backend.core.tracing import configure_langsmith

# ── 日志 ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("afvc")

# ── LangSmith 初始化 ──────────────────────────────────────────

if configure_langsmith():
    logger.info("LangSmith tracing enabled")


# ── 应用生命周期 ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的操作。"""
    from backend.core.config import is_sql_backend

    profile = get_data_profile()
    if profile == "demo":
        get_database_url()  # Reject a production DB before migrations or seeding.
        from backend.infrastructure.demo_seed import validate_demo_dataset

        validate_demo_dataset()
    logger.info("AFVC v%s 启动，数据模式：%s", PROJECT_VERSION, profile)
    if is_sql_backend():
        from backend.infrastructure.db import init_db
        from backend.infrastructure.workorder_repo import seed_default_if_empty

        init_db(with_checkpointer=True)
        if profile == "demo":
            from backend.infrastructure.demo_seed import seed_demo_if_needed

            seeded = seed_demo_if_needed()
        else:
            seeded = seed_default_if_empty()
        if seeded:
            logger.info("seeded demo tasks: %s" if profile == "demo" else "seeded workorders: %s", seeded if profile == "demo" else seeded.get("row_count"))
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
        "预测驱动的 AFC 闸机检修安排闭环："
        "今日建议、可调整检修计划、执行反馈。"
        "/usecases/maintenance/* 为主路径；/interaction/* 为对话旁路。"
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
        "data_profile": get_data_profile(),
    }


# ── 注册路由 ──────────────────────────────────────────────────

from backend.api.auth_api import router as auth_router
from backend.api.upload_api import router as upload_router
from backend.api.usecases_api import router as usecases_router
from backend.api.interaction_api import router as interaction_router

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(usecases_router)
app.include_router(interaction_router)
