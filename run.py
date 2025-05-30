import uvicorn
import os
import sys

# 添加当前目录到路径，确保可以导入app包
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    # 启动FastAPI应用
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 