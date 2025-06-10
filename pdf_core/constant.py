# 服务器URL相关常量
API_URL = "http://123.157.247.187:31000"  # MinerU 服务地址
IMAGES_API_URL = "http://123.157.247.187:31002/api/images/upload"  # 图片上传服务地址
KB_API_BASE_URL = "http://123.157.247.187:27100/api/v1"  # 知识库服务基础地址
AI_API_BASE_URL = "http://123.157.247.187:18084/v1"  # AI服务基础地址

# 认证相关常量
DEFAULT_API_KEY = "ragflow-BlNGFjOWZlMzQ2ODExZjA4N2I0ZDY1YW"  # 默认API密钥

# 知识库相关常量
DEFAULT_KB_ID = "120f1dca405b11f090bed65ac74b6c9e"  # 默认知识库ID

# AI模型相关常量
DEFAULT_AI_MODEL = "Qwen3-32B"  # 默认AI模型
DEFAULT_MAX_CHUNK_SIZE = 102400  # 默认文本块最大字符数
DEFAULT_TEMPERATURE = 0.3  # 默认温度参数
DEFAULT_MAX_TOKENS = 1024 * 100  # 默认最大生成token数

# UI相关常量
# 自定义CSS样式
CUSTOM_CSS = """
.container {
    max-width: 800px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
.header {
    text-align: center !important;
    margin-bottom: 2rem !important;
}
.header h1 {
    font-size: 2.5rem !important;
    margin-bottom: 0.5rem !important;
}
.header p {
    font-size: 1.1rem !important;
    color: #666 !important;
}
.upload-section {
    background-color: #f8f9fa !important;
    border-radius: 10px !important;
    padding: 1.5rem !important;
    margin-bottom: 1.5rem !important;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
}
.download-section {
    background-color: #f0f8ff !important;
    border-radius: 10px !important;
    padding: 1.5rem !important;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
}
.footer {
    text-align: center !important;
    margin-top: 2rem !important;
    font-size: 0.9rem !important;
    color: #666 !important;
}
.options-row {
    margin-top: 1rem !important;
    margin-bottom: 1rem !important;
}
"""

# AI提示词相关常量
DEFAULT_FORMAT_PROMPT = """
请根据以下要求和参考示例，优化所提供文本的格式。

**核心要求：**
1.  **保留原文内容**：除了明确指示需要移除的内容外，不要用你自身的知识修改，不得修改文本的原始语句。
2.  **优化排版与可读性**：重点在于调整各级标题、段落结构和列表格式，使其清晰、规范、易读。

**必须移除的内容 (不应出现在最终输出中)：**
1.  **页码标识**：例如 "第 n 页"、"第n页 共n页" 或任何类似的页码信息。
2.  **文档元数据/辅助信息**：例如 "变更记录"、"修订历史"、"制定日期"、"生效日期"、"版本号"等部分。如果这些信息作为独立的章节或段落出现，请直接删除。

**格式优化细节 (请严格参考提供的示例)：**
1.  **层级标题**：确保各级标题（如 `### 1.` 和 `#### 1.1.`）结构清晰，层级分明。
2.  **段落划分**：合理划分段落，确保每个段落讨论一个核心点。
3.  **列表项**：
    * 主要列表项使用 `- **加粗文本**` 的格式。
    * 次级列表项（如对主要列表项的解释或示例）使用 `o 普通文本` 并进行适当缩进。


请开始处理以下文本：
"""
