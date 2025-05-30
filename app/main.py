from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
import logging

from app.api import api_router
from app.core.config import settings
from app.utils.logger import setup_logger
from app.services.task_service import cleanup_expired_tasks

logger = setup_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    cleanup_task = asyncio.create_task(cleanup_expired_tasks())
    logger.info("MinerU PDF Conversion API started")
    
    yield  # 这里是应用程序运行的地方
    
    # 关闭时执行
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("Cleanup task cancelled")
    logger.info("MinerU PDF Conversion API shutdown")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan
)

app.include_router(api_router) 