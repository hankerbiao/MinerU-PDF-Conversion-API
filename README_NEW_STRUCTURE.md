# MinerU PDF Conversion API - 重构版

这是MinerU PDF转换API的重构版本，采用了更加模块化和可维护的项目结构。

## 项目结构

```
MineruClient/
├── app/                        # 主应用包
│   ├── api/                    # API相关模块
│   │   ├── endpoints/          # API端点定义
│   │   │   ├── __init__.py
│   │   │   └── pdf.py          # PDF相关API端点
│   │   └── __init__.py         # API路由注册
│   ├── core/                   # 核心配置
│   │   └── config.py           # 应用配置
│   ├── models/                 # 数据模型
│   │   └── task.py             # 任务模型
│   ├── services/               # 业务逻辑服务
│   │   ├── pdf_service.py      # PDF处理服务
│   │   └── task_service.py     # 任务管理服务
│   ├── utils/                  # 工具函数
│   │   └── logger.py           # 日志配置
│   └── main.py                 # FastAPI应用实例
├── uploads/                    # 上传文件存储目录
├── outputs/                    # 输出文件存储目录
├── requirements.txt            # 项目依赖
└── run.py                      # 应用启动脚本
```

## 重构说明

1. **模块化设计**:
   - 将单一的app.py文件拆分为多个模块，每个模块负责特定功能
   - 采用分层架构，分离API、业务逻辑和数据模型

2. **配置管理**:
   - 使用pydantic_settings进行配置管理，支持环境变量和.env文件
   - 集中管理所有配置项

3. **API路由组织**:
   - 使用FastAPI的APIRouter组织API端点
   - 按功能将API端点分组

4. **服务层**:
   - 将业务逻辑封装在服务层中
   - 分离PDF处理和任务管理逻辑

5. **数据模型**:
   - 使用Pydantic模型定义数据结构
   - 集中管理所有数据模型

## 运行应用

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python run.py
```

应用将在 http://localhost:8000 上运行，API文档可在 http://localhost:8000/docs 访问。

## 环境变量

可以通过环境变量或.env文件覆盖默认配置:

```
APP_NAME=自定义应用名称
UPLOAD_DIR=自定义上传目录
OUTPUT_DIR=自定义输出目录
MAX_FILE_SIZE=104857600  # 100MB
TASK_EXPIRY_HOURS=24
MAX_CONCURRENT_TASKS=5
``` 