import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "MinerU PDF Conversion API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "A FastAPI service for converting PDFs using MinerU"
    
    # 存储路径配置
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # 任务配置
    TASK_EXPIRY_HOURS: int = 24  # 任务结果保留时间（小时）
    MAX_CONCURRENT_TASKS: int = 5  # 最大并发任务数
    
    class Config:
        env_file = ".env"

# 创建全局设置实例
settings = Settings()

# 确保目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True) 