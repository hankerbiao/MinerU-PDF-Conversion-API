import os
import logging
from datetime import datetime, timedelta
import magic_pdf.data.data_reader_writer as drw
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod

from app.core.config import settings
from app.models.task import TaskStatus

logger = logging.getLogger("mineru-api")

# 全局任务状态存储
tasks = {}
active_tasks = 0

async def process_pdf(task_id: str, pdf_path: str):
    global active_tasks
    try:
        active_tasks += 1
        tasks[task_id].status = "processing"
        logger.info(f"Processing task {task_id}, file: {pdf_path}")
        
        # 创建输出目录
        task_output_dir = os.path.join(settings.OUTPUT_DIR, task_id)
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
        tasks[task_id].expires_at = datetime.now() + timedelta(hours=settings.TASK_EXPIRY_HOURS)
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        tasks[task_id].status = "failed"
        tasks[task_id].error = str(e)
        tasks[task_id].expires_at = datetime.now() + timedelta(hours=1)  # 失败任务保留1小时
    finally:
        active_tasks -= 1 