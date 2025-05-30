# MinerU PDF Conversion API

基于[MinerU](https://github.com/opendatalab/MinerU)的PDF转换API服务，使用FastAPI框架实现。

## 功能特点

- 将PDF文档转换为Markdown和JSON格式
- 支持异步处理大型PDF文件
- 提供RESTful API接口
- 任务状态跟踪和文件管理
- 自动清理过期任务
- 支持打包下载所有输出文件

## 安装

1. 克隆本仓库
   ```bash
   git clone https://github.com/hankerbiao/MinerU-PDF-Conversion-API.git
   cd mineru-api
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

3. 运行服务
   ```bash
   python run.py
   ```

   或者指定主机和端口：
   ```bash
   python run.py --host 127.0.0.1 --port 8080
   ```

## API接口

### 上传PDF并开始转换

**请求**:
```
POST /convert/
```

表单参数:
- `file`: PDF文件

**响应**:
```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "files": null,
  "error": null,
  "created_at": "2023-01-01T12:00:00",
  "expires_at": null
}
```

### 获取任务状态

**请求**:
```
GET /status/{task_id}
```

**响应**:
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "files": [
    "document_model.pdf",
    "document_layout.pdf",
    "document_spans.pdf",
    "document.md",
    "document_content_list.json",
    "document_middle.json"
  ],
  "error": null,
  "created_at": "2023-01-01T12:00:00",
  "expires_at": "2023-01-02T12:00:00"
}
```

### 获取文件列表

**请求**:
```
GET /files/{task_id}
```

**响应**:
```json
{
  "files": [
    "document_model.pdf",
    "document_layout.pdf",
    "document_spans.pdf",
    "document.md",
    "document_content_list.json",
    "document_middle.json"
  ]
}
```

### 下载单个文件

**请求**:
```
GET /download/{task_id}/{file_name}
```

**响应**: 文件内容（二进制）

### 下载所有文件（ZIP压缩包）

**请求**:
```
GET /download-zip/{task_id}
```

**响应**: ZIP压缩包（二进制），包含所有输出文件和图像

## 配置

可以在`config.py`文件中修改以下配置参数：

- `UPLOAD_DIR`: 上传文件存储目录
- `OUTPUT_DIR`: 输出文件存储目录
- `MAX_FILE_SIZE`: 最大文件大小（字节）
- `TASK_EXPIRY_HOURS`: 任务结果保留时间（小时）
- `MAX_CONCURRENT_TASKS`: 最大并发任务数

## 示例

### 使用curl上传PDF

```bash
curl -X POST "http://localhost:8000/convert/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

### 使用curl下载ZIP压缩包

```bash
# 获取任务ID
TASK_ID=$(curl -s -X POST "http://localhost:8000/convert/" -H "Content-Type: multipart/form-data" -F "file=@document.pdf" | jq -r '.task_id')

# 等待处理完成
while true; do
  STATUS=$(curl -s "http://localhost:8000/status/$TASK_ID" | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ]; then
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "Task failed"
    exit 1
  fi
  sleep 5
done

# 下载ZIP压缩包
curl -o results.zip "http://localhost:8000/download-zip/$TASK_ID"
```

### 使用Python客户端

```python
import requests

# 上传PDF文件
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/convert/',
        files={'file': f}
    )
    
task_id = response.json()['task_id']
print(f"Task ID: {task_id}")

# 检查任务状态
status_response = requests.get(f'http://localhost:8000/status/{task_id}')
print(f"Status: {status_response.json()['status']}")

# 如果任务完成，下载ZIP压缩包
if status_response.json()['status'] == 'completed':
    # 下载所有文件的ZIP压缩包
    with open('results.zip', 'wb') as f:
        response = requests.get(f'http://localhost:8000/download-zip/{task_id}', stream=True)
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("Downloaded ZIP archive")
```

### 使用提供的客户端脚本

```bash
# 上传PDF并等待处理完成，然后下载所有文件
python client_example.py document.pdf --wait

# 上传PDF并等待处理完成，然后下载ZIP压缩包
python client_example.py document.pdf --wait --zip
```

## 许可证

与MinerU相同，本项目采用AGPL-3.0许可证。 