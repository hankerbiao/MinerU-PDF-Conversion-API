import os

# 应用配置
APP_NAME = "MinerU PDF Conversion API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "A FastAPI service for converting PDFs using MinerU"

# 存储路径配置
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 任务配置
TASK_EXPIRY_HOURS = 24  # 任务结果保留时间（小时）
MAX_CONCURRENT_TASKS = 5  # 最大并发任务数

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True) 