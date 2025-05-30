import gradio as gr
import requests
import time
import os
import tempfile
import shutil
import json
from datetime import datetime

# API配置
API_URL = "http://123.157.247.187:31000"  # 可以根据需要修改为实际API地址

def format_time(timestamp_str):
    """格式化时间戳字符串为易读格式"""
    if not timestamp_str:
        return ""
    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def upload_and_convert_pdf(pdf_file, progress=gr.Progress()):
    """上传PDF文件到API并等待转换完成"""
    if not pdf_file:
        return {"error": "请选择PDF文件"}, None
    
    try:
        # 准备上传文件
        progress(0.1, desc="准备上传文件...")
        files = {"file": (os.path.basename(pdf_file.name), open(pdf_file.name, "rb"), "application/pdf")}
        
        # 发送请求
        progress(0.2, desc="上传文件中...")
        response = requests.post(f"{API_URL}/convert/", files=files)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        task_id = result["task_id"]
        
        # 等待任务完成
        progress(0.3, desc="文件已上传，正在转换中...")
        status = "pending"
        start_time = time.time()
        timeout = 600  # 10分钟超时
        
        while status in ["pending", "processing"]:
            # 检查任务状态
            response = requests.get(f"{API_URL}/status/{task_id}")
            response.raise_for_status()
            result = response.json()
            status = result["status"]
            
            # 如果任务完成或失败，退出循环
            if status not in ["pending", "processing"]:
                break
            
            # 检查是否超时
            if time.time() - start_time > timeout:
                return {"error": "转换超时，请稍后检查结果"}, None
            
            # 更新进度
            elapsed = time.time() - start_time
            progress_value = min(0.3 + (elapsed / timeout) * 0.6, 0.9)
            progress(progress_value, desc="正在转换中，请耐心等待...")
            
            # 等待一段时间再次检查
            time.sleep(3)
        
        # 处理任务结果
        if status == "completed":
            progress(0.95, desc="转换完成，准备下载结果...")
            
            # 创建临时目录存储下载的文件
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"{os.path.basename(pdf_file.name).split('.')[0]}_results.zip")
            
            # 下载ZIP文件
            response = requests.get(f"{API_URL}/download-zip/{task_id}", stream=True)
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            progress(1.0, desc="转换完成！")
            return {
                "status": "成功",
                "message": "PDF转换成功！",
                "task_id": task_id,
                "文件数量": len(result.get("files", [])) if result.get("files") else 0
            }, output_path
        else:
            return {"error": f"转换失败: {result.get('error', '未知错误')}"}, None
            
    except Exception as e:
        return {"error": f"处理失败: {str(e)}"}, None

# 自定义CSS样式
custom_css = """
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
"""

def create_ui():
    """创建简化版Gradio UI"""
    with gr.Blocks(title="测试中心内部PDF转换工具", css=custom_css) as demo:
        with gr.Column(elem_classes=["container"]):
            # 标题和说明
            with gr.Column(elem_classes=["header"]):
                gr.Markdown("# 测试中心内部PDF转换工具")
                gr.Markdown("将PDF文档转换为Markdown，支持提取文本、表格和图片。")
            
            # 上传区域
            with gr.Column(elem_classes=["upload-section"]):
                gr.Markdown("## 上传PDF文件")
                pdf_file = gr.File(label="选择PDF文件", file_types=[".pdf"], elem_id="pdf-upload")
                upload_button = gr.Button("上传并开始转换", variant="primary", size="lg")
                result_json = gr.JSON(label="转换结果")
            
            # 下载区域
            with gr.Column(elem_classes=["download-section"]):
                gr.Markdown("## 下载转换结果")
                zip_output = gr.File(label="ZIP压缩包")
            
            # 页脚
            with gr.Column(elem_classes=["footer"]):
                gr.Markdown("© 2025 测试中心内部PDF转换工具 | 基于[MinerU](https://github.com/opendatalab/MinerU)开发")
        
        # 事件处理
        upload_button.click(
            fn=upload_and_convert_pdf,
            inputs=[pdf_file],
            outputs=[result_json, zip_output]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.queue()
    demo.launch(share=False) 