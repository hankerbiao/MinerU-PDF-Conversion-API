from fastapi import APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os

from app.models.task import TaskStatus
from app.services.task_service import create_task, get_task, create_zip_archive
from app.services.pdf_service import tasks

router = APIRouter()

@router.post("/convert/", response_model=TaskStatus)
async def convert_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """上传PDF文件并开始转换任务"""
    return await create_task(file, background_tasks)

@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    return get_task(task_id)

@router.get("/download/{task_id}/{file_name}")
async def download_file(task_id: str, file_name: str):
    """下载特定任务的单个文件"""
    task = get_task(task_id)
        
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Task not completed"
        )
    
    if file_name not in task.files:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    
    from app.core.config import settings
    file_path = os.path.join(settings.OUTPUT_DIR, task_id, file_name)
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

@router.get("/download-zip/{task_id}")
async def download_zip(task_id: str):
    """下载任务的所有输出文件的ZIP压缩包"""
    zip_path, zip_filename = await create_zip_archive(task_id)
    
    return FileResponse(
        path=zip_path,
        filename=zip_filename,
        media_type='application/zip',
        background=BackgroundTasks().add_task(lambda: os.unlink(zip_path))  # 下载后删除临时文件
    )

@router.get("/files/{task_id}")
async def list_files(task_id: str):
    """列出任务的所有可用文件"""
    task = get_task(task_id)
        
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Task not completed"
        )
    
    return {"files": task.files} 