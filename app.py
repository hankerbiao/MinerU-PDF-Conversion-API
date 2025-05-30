from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import shutil
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import magic_pdf.data.data_reader_writer as drw
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
import config
from datetime import datetime, timedelta
import logging
from contextlib import asynccontextmanager
import zipfile
from tempfile import NamedTemporaryFile

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mineru-api")

# 活跃任务计数
active_tasks = 0
tasks = {}

# 任务清理函数
async def cleanup_expired_tasks():
    while True:
        now = datetime.now()
        expired_tasks = [task_id for task_id, task in tasks.items() 
                        if task.expires_at and now > task.expires_at]
        
        for task_id in expired_tasks:
            # 删除上传的文件
            task_upload_dir = os.path.join(config.UPLOAD_DIR, task_id)
            if os.path.exists(task_upload_dir):
                shutil.rmtree(task_upload_dir)
            
            # 删除输出文件
            task_output_dir = os.path.join(config.OUTPUT_DIR, task_id)
            if os.path.exists(task_output_dir):
                shutil.rmtree(task_output_dir)
            
            # 从任务列表中移除
            del tasks[task_id]
            logger.info(f"Cleaned up expired task {task_id}")
        
        # 每小时检查一次
        await asyncio.sleep(3600)

# 使用lifespan上下文管理器替代on_event
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
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description=config.APP_DESCRIPTION,
    lifespan=lifespan
)

# 配置存储路径
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 任务状态跟踪
class TaskStatus(BaseModel):
    task_id: str
    status: str  # "pending", "processing", "completed", "failed"
    files: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: datetime = datetime.now()
    expires_at: Optional[datetime] = None

async def process_pdf(task_id: str, pdf_path: str):
    global active_tasks
    try:
        active_tasks += 1
        tasks[task_id].status = "processing"
        logger.info(f"Processing task {task_id}, file: {pdf_path}")
        
        # 创建输出目录
        task_output_dir = os.path.join(config.OUTPUT_DIR, task_id)
        local_image_dir = os.path.join(task_output_dir, "images")
        os.makedirs(local_image_dir, exist_ok=True)
        
        # 准备环境
        image_dir = "images"
        image_writer = drw.FileBasedDataWriter(local_image_dir)
        md_writer = drw.FileBasedDataWriter(task_output_dir)
        
        # 读取PDF内容
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        # 处理PDF
        name_without_suff = os.path.basename(pdf_path).split(".")[0]
        
        # 创建数据集实例
        ds = PymuDocDataset(pdf_bytes)
        
        # 推理
        if ds.classify() == SupportedPdfParseMethod.OCR:
            logger.info(f"Task {task_id}: Using OCR mode")
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            logger.info(f"Task {task_id}: Using text mode")
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)
        
        # 绘制模型结果
        model_path = os.path.join(task_output_dir, f"{name_without_suff}_model.pdf")
        infer_result.draw_model(model_path)
        
        # 获取模型推理结果
        model_inference_result = infer_result.get_infer_res()
        
        # 绘制布局结果
        layout_path = os.path.join(task_output_dir, f"{name_without_suff}_layout.pdf")
        pipe_result.draw_layout(layout_path)
        
        # 绘制spans结果
        spans_path = os.path.join(task_output_dir, f"{name_without_suff}_spans.pdf")
        pipe_result.draw_span(spans_path)
        
        # 获取并保存Markdown内容
        md_content = pipe_result.get_markdown(image_dir)
        md_path = f"{name_without_suff}.md"
        pipe_result.dump_md(md_writer, md_path, image_dir)
        
        # 获取并保存内容列表
        content_list_path = f"{name_without_suff}_content_list.json"
        pipe_result.dump_content_list(md_writer, content_list_path, image_dir)
        
        # 获取并保存中间JSON
        middle_json_path = f"{name_without_suff}_middle.json"
        pipe_result.dump_middle_json(md_writer, middle_json_path)
        
        # 更新任务状态
        tasks[task_id].status = "completed"
        tasks[task_id].files = [
            f"{name_without_suff}_model.pdf",
            f"{name_without_suff}_layout.pdf",
            f"{name_without_suff}_spans.pdf",
            f"{name_without_suff}.md",
            f"{name_without_suff}_content_list.json",
            f"{name_without_suff}_middle.json"
        ]
        # 设置过期时间
        tasks[task_id].expires_at = datetime.now() + timedelta(hours=config.TASK_EXPIRY_HOURS)
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        tasks[task_id].status = "failed"
        tasks[task_id].error = str(e)
        tasks[task_id].expires_at = datetime.now() + timedelta(hours=1)  # 失败任务保留1小时
    finally:
        active_tasks -= 1

@app.post("/convert/", response_model=TaskStatus)
async def convert_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    global active_tasks
    
    # 检查并发任务数
    if active_tasks >= config.MAX_CONCURRENT_TASKS:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent tasks. Please try again later."
        )
    
    # 验证文件是PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # 检查文件大小
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB
    chunks = []
    
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        file_size += len(chunk)
        chunks.append(chunk)
        
        if file_size > config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {config.MAX_FILE_SIZE / (1024 * 1024)}MB"
            )
    
    # 创建任务ID
    task_id = str(uuid.uuid4())
    task_upload_dir = os.path.join(config.UPLOAD_DIR, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)
    task_output_dir = os.path.join(config.OUTPUT_DIR, task_id)
    os.makedirs(task_output_dir, exist_ok=True)
    
    # 保存上传的文件
    file_path = os.path.join(task_upload_dir, file.filename)
    with open(file_path, "wb") as f:
        for chunk in chunks:
            f.write(chunk)
    
    logger.info(f"File uploaded: {file.filename}, task ID: {task_id}")
    
    # 创建任务状态
    tasks[task_id] = TaskStatus(
        task_id=task_id,
        status="pending",
        created_at=datetime.now()
    )
    
    # 在后台处理PDF
    background_tasks.add_task(process_pdf, task_id, file_path)
    
    return tasks[task_id]

@app.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    return tasks[task_id]

@app.get("/download/{task_id}/{file_name}")
async def download_file(task_id: str, file_name: str):
    if task_id not in tasks:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
        
    if tasks[task_id].status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Task not completed"
        )
    
    if file_name not in tasks[task_id].files:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    
    file_path = os.path.join(config.OUTPUT_DIR, task_id, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found on server"
        )
        
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type='application/octet-stream'
    )

@app.get("/download-zip/{task_id}")
async def download_zip(task_id: str):
    """下载任务的所有输出文件的ZIP压缩包"""
    if task_id not in tasks:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
        
    if tasks[task_id].status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Task not completed"
        )
    
    if not tasks[task_id].files:
        raise HTTPException(
            status_code=400,
            detail="No files available for download"
        )
    
    # 创建一个临时文件来存储ZIP
    with NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
        zip_path = tmp_file.name
    
    # 创建ZIP文件
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            task_dir = os.path.join(config.OUTPUT_DIR, task_id)
            
            # 添加所有文件到ZIP
            for file_name in tasks[task_id].files:
                file_path = os.path.join(task_dir, file_name)
                if os.path.exists(file_path):
                    zipf.write(file_path, file_name)
            
            # 添加图片目录（如果存在）
            images_dir = os.path.join(task_dir, "images")
            if os.path.exists(images_dir) and os.path.isdir(images_dir):
                for root, _, files in os.walk(images_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算相对于task_dir的路径
                        rel_path = os.path.relpath(file_path, task_dir)
                        zipf.write(file_path, rel_path)
        
        # 获取原始PDF文件名（不含扩展名）作为ZIP文件名的一部分
        original_files = [f for f in os.listdir(os.path.join(config.UPLOAD_DIR, task_id)) if f.endswith('.pdf')]
        if original_files:
            original_name = original_files[0].rsplit('.', 1)[0]
            zip_filename = f"{original_name}_results.zip"
        else:
            zip_filename = f"mineru_results_{task_id}.zip"
        
        logger.info(f"Created ZIP archive for task {task_id}: {zip_filename}")
        
        # 返回ZIP文件
        return FileResponse(
            path=zip_path,
            filename=zip_filename,
            media_type='application/zip',
            background=BackgroundTasks().add_task(lambda: os.unlink(zip_path))  # 下载后删除临时文件
        )
    
    except Exception as e:
        # 如果出错，删除临时文件
        if os.path.exists(zip_path):
            os.unlink(zip_path)
        logger.error(f"Error creating ZIP for task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating ZIP file: {str(e)}"
        )

@app.get("/files/{task_id}")
async def list_files(task_id: str):
    if task_id not in tasks:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
        
    if tasks[task_id].status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Task not completed"
        )
    
    return {"files": tasks[task_id].files} 