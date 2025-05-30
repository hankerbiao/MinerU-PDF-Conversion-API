import os
import shutil
import asyncio
import logging
from datetime import datetime
import uuid
from fastapi import UploadFile, HTTPException, BackgroundTasks
import zipfile
from tempfile import NamedTemporaryFile

from app.core.config import settings
from app.models.task import TaskStatus
from app.services.pdf_service import tasks, active_tasks, process_pdf

logger = logging.getLogger("mineru-api")

async def cleanup_expired_tasks():
    """定期清理过期的任务"""
    while True:
        now = datetime.now()
        expired_tasks = [task_id for task_id, task in tasks.items() 
                        if task.expires_at and now > task.expires_at]
        
        for task_id in expired_tasks:
            # 删除上传的文件
            task_upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
            if os.path.exists(task_upload_dir):
                shutil.rmtree(task_upload_dir)
            
            # 删除输出文件
            task_output_dir = os.path.join(settings.OUTPUT_DIR, task_id)
            if os.path.exists(task_output_dir):
                shutil.rmtree(task_output_dir)
            
            # 从任务列表中移除
            del tasks[task_id]
            logger.info(f"Cleaned up expired task {task_id}")
        
        # 每小时检查一次
        await asyncio.sleep(3600)

async def create_task(file: UploadFile, background_tasks: BackgroundTasks) -> TaskStatus:
    """创建新的PDF处理任务"""
    # 检查并发任务数
    if active_tasks >= settings.MAX_CONCURRENT_TASKS:
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
        
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE / (1024 * 1024)}MB"
            )
    
    # 创建任务ID
    task_id = str(uuid.uuid4())
    task_upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)
    task_output_dir = os.path.join(settings.OUTPUT_DIR, task_id)
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

def get_task(task_id: str) -> TaskStatus:
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    return tasks[task_id]

async def create_zip_archive(task_id: str) -> tuple:
    """为任务创建ZIP压缩包"""
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
            task_dir = os.path.join(settings.OUTPUT_DIR, task_id)
            
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
        original_files = [f for f in os.listdir(os.path.join(settings.UPLOAD_DIR, task_id)) if f.endswith('.pdf')]
        if original_files:
            original_name = original_files[0].rsplit('.', 1)[0]
            zip_filename = f"{original_name}_results.zip"
        else:
            zip_filename = f"mineru_results_{task_id}.zip"
        
        logger.info(f"Created ZIP archive for task {task_id}: {zip_filename}")
        
        return zip_path, zip_filename
    
    except Exception as e:
        # 如果出错，删除临时文件
        if os.path.exists(zip_path):
            os.unlink(zip_path)
        logger.error(f"Error creating ZIP for task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating ZIP file: {str(e)}"
        ) 