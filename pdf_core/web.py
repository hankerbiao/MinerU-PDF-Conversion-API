import gradio as gr
import requests
import time
import os
import tempfile
import shutil
import zipfile
from constant import API_URL, CUSTOM_CSS, DEFAULT_AI_MODEL, DEFAULT_MAX_CHUNK_SIZE, DEFAULT_KB_ID
from utils.Logger import logger
from utils.public import process_all_markdown_files, extract_and_find_markdown_files, upload_to_knowledge_base, \
    create_new_zip_with_processed_files, process_all_markdown_files_with_ai


def process_html_file(html_file, upload_to_kb_flag, kb_id, use_ai_flag=True, ai_model=DEFAULT_AI_MODEL,
                       max_chunk_size=DEFAULT_MAX_CHUNK_SIZE, progress=gr.Progress()):
    """处理HTML文件，直接转换为Markdown并处理"""
    if not html_file:
        return {"error": "❌ 请选择HTML文件"}, None

    try:
        # 创建临时目录
        progress(0.1, desc="📋 准备处理HTML文件...")
        logger.info(f"准备处理HTML文件: {html_file.name}")
        temp_dir = tempfile.mkdtemp()
        
        # 创建保存HTML的临时路径
        html_temp_path = os.path.join(temp_dir, os.path.basename(html_file.name))
        
        # 复制HTML文件到临时目录
        shutil.copyfile(html_file.name, html_temp_path)
        
        # 创建Markdown转换目录
        markdown_dir = os.path.join(temp_dir, "markdown")
        os.makedirs(markdown_dir, exist_ok=True)
        
        # 创建images目录
        images_dir = os.path.join(markdown_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        # 使用html2text转换HTML到Markdown
        progress(0.3, desc="🔄 正在转换HTML到Markdown...")
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.escape_snob = True
            h.unicode_snob = True
            
            with open(html_temp_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            markdown_content = h.handle(html_content)
            
            # 保存Markdown文件
            markdown_file_path = os.path.join(markdown_dir, f"{os.path.splitext(os.path.basename(html_file.name))[0]}.md")
            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            logger.info(f"HTML已转换为Markdown: {markdown_file_path}")
            
            # 创建Markdown文件列表
            markdown_files = [markdown_file_path]
            
        except ImportError:
            logger.error("未安装html2text模块，无法转换HTML")
            return {"error": "❌ 处理失败: 未安装html2text模块"}, None
        except Exception as e:
            logger.error(f"转换HTML到Markdown失败: {str(e)}")
            return {"error": f"❌ 转换失败: {str(e)}"}, None
        
        # 处理额外的上传选项和图片处理
        extra_info = {}
        extra_info["找到的Markdown文件"] = len(markdown_files)
        extra_info["找到的images目录"] = 1  # 我们创建了一个images目录
        
        # 最终输出路径（默认为ZIP文件）
        output_path = os.path.join(temp_dir, f"{os.path.splitext(os.path.basename(html_file.name))[0]}_results.zip")
        
        # AI 大模型清洗
        ai_success_count = 0
        ai_fail_count = 0
        if use_ai_flag:
            progress(0.6, desc="🧠 正在使用AI优化文档...")
            logger.info(f"开始使用AI大模型清洗文档，模型: {ai_model}，最大块大小: {max_chunk_size}")
            ai_success_count, ai_fail_count = process_all_markdown_files_with_ai(markdown_files,
                                                                                 ai_model=ai_model,
                                                                                 max_chunk_size=max_chunk_size)
            extra_info[
                "AI优化"] = f"✅ 成功: {ai_success_count} 个文件" if ai_fail_count == 0 else f"⚠️ 部分成功: {ai_success_count} 成功, {ai_fail_count} 失败"
        else:
            logger.info("跳过AI优化文档")
            extra_info["AI优化"] = "⏭️ 已跳过"
        
        # 创建包含所有文件的ZIP
        progress(0.8, desc="📦 正在创建ZIP文件...")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加所有文件
            for root, _, files in os.walk(markdown_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 计算相对路径，保持目录结构
                    rel_path = os.path.relpath(file_path, markdown_dir)
                    logger.info(f"添加文件到ZIP: {rel_path}")
                    zipf.write(file_path, rel_path)
        
        final_output_path = output_path
            
        # 如果选择了上传知识库
        if upload_to_kb_flag:
            if not kb_id:
                logger.warning("未提供知识库ID，无法上传")
                extra_info["知识库上传"] = "❌ 失败: 未提供知识库ID"
            else:
                progress(0.9, desc="📚 正在上传到知识库...")
                logger.info(f"开始上传到知识库 {kb_id}")

                try:
                    # 上传Markdown文件到知识库
                    upload_success, upload_result = upload_to_knowledge_base(markdown_dir, kb_id)
                    if upload_success:
                        extra_info["知识库上传"] = f"✅ 成功 (知识库ID: {kb_id})"
                        extra_info["知识库上传结果"] = upload_result
                        logger.info(f"上传到知识库成功: {kb_id}")
                    else:
                        extra_info["知识库上传"] = f"❌ 失败: {upload_result.get('错误', '未知错误')}"
                        extra_info["知识库上传结果"] = upload_result
                        logger.warning(f"上传到知识库失败: {upload_result}")
                except Exception as e:
                    logger.error(f"上传到知识库失败: {str(e)}")
                    extra_info["知识库上传"] = f"❌ 失败: {str(e)}"
        
        progress(1.0, desc="🎉 处理完成！")
        result_info = {
            "status": "✅ 成功",
            "message": "🎉 HTML处理成功！",
            "文件数量": len(markdown_files),
            **extra_info
        }
        logger.info(f"处理完成: {result_info}")
        return result_info, final_output_path
        
    except Exception as e:
        logger.exception(f"处理出错: {str(e)}")
        return {"error": f"❌ 处理失败: {str(e)}"}, None


def upload_and_convert_pdf(pdf_file, upload_to_kb_flag, kb_id, use_ai_flag=True, ai_model=DEFAULT_AI_MODEL,
                           max_chunk_size=DEFAULT_MAX_CHUNK_SIZE, progress=gr.Progress()):
    """上传PDF/HTML文件并处理"""
    if not pdf_file:
        return {"error": "❌ 请选择文件"}, None
    
    # 检查文件类型
    file_extension = os.path.splitext(pdf_file.name)[1].lower()
    
    # 如果是HTML文件，使用HTML处理流程
    if file_extension == '.html':
        logger.info(f"检测到HTML文件: {pdf_file.name}，使用HTML处理流程")
        return process_html_file(pdf_file, upload_to_kb_flag, kb_id, use_ai_flag, ai_model, max_chunk_size, progress)
    
    # 否则按照原PDF处理流程处理
    try:
        # 准备上传文件
        progress(0.1, desc="📋 准备上传文件...")
        logger.info(f"准备上传文件: {pdf_file.name}")
        files = {"file": (os.path.basename(pdf_file.name), open(pdf_file.name, "rb"), "application/pdf")}

        # 发送请求
        progress(0.2, desc="📤 正在上传文件...")
        response = requests.post(f"{API_URL}/convert/", files=files)
        response.raise_for_status()

        # 解析响应
        result = response.json()
        task_id = result["task_id"]

        # 等待任务完成
        progress(0.3, desc="🔄 文件已上传，正在转换中...")
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
                return {"error": "⏱️ 转换超时，请稍后检查结果或尝试重新上传"}, None

            # 更新进度
            elapsed = time.time() - start_time
            progress_value = min(0.3 + (elapsed / timeout) * 0.6, 0.9)
            progress(progress_value, desc=f"🔄 正在转换中，已用时 {int(elapsed)}秒，请耐心等待...")

            # 等待一段时间再次检查
            time.sleep(3)

        # 处理任务结果
        if status == "completed":
            progress(0.95, desc="✅ 转换完成，准备下载结果...")
            logger.info(f"转换完成，任务ID: {task_id}")

            # 创建临时目录存储下载的文件
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"{os.path.basename(pdf_file.name).split('.')[0]}_results.zip")

            # 下载ZIP文件
            logger.info(f"下载结果文件到: {output_path}")
            response = requests.get(f"{API_URL}/download-zip/{task_id}", stream=True)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 处理额外的上传选项和图片处理
            extra_info = {}
            final_output_path = output_path  # 默认使用原始输出路径

            # 解压并查找Markdown文件和images目录
            progress(0.96, desc="📄 正在解析转换结果...")
            extract_dir, markdown_files, images_dirs = extract_and_find_markdown_files(output_path)

            # 添加找到的文件信息到结果中
            extra_info["找到的Markdown文件"] = len(markdown_files)
            extra_info["找到的images目录"] = len(images_dirs)

            # 处理所有Markdown文件中的图片链接
            if markdown_files:
                progress(0.97, desc="🖼️ 正在处理图片链接...")
                logger.info("开始处理所有Markdown文件中的图片链接")
                success, stats = process_all_markdown_files(extract_dir, markdown_files)

                # AI 大模型清洗
                ai_success_count = 0
                ai_fail_count = 0
                if use_ai_flag:
                    progress(0.98, desc="🧠 正在使用AI优化文档...")
                    logger.info(f"开始使用AI大模型清洗文档，模型: {ai_model}，最大块大小: {max_chunk_size}")
                    ai_success_count, ai_fail_count = process_all_markdown_files_with_ai(markdown_files,
                                                                                         ai_model=ai_model,
                                                                                         max_chunk_size=max_chunk_size)
                    extra_info[
                        "AI优化"] = f"✅ 成功: {ai_success_count} 个文件" if ai_fail_count == 0 else f"⚠️ 部分成功: {ai_success_count} 成功, {ai_fail_count} 失败"
                else:
                    logger.info("跳过AI优化文档")
                    extra_info["AI优化"] = "⏭️ 已跳过"

                # 创建包含处理后文件的新ZIP
                progress(0.99, desc="📦 正在创建新的ZIP文件...")
                final_output_path = create_new_zip_with_processed_files(output_path, extract_dir)

                # 添加处理统计信息
                extra_info["图片处理"] = "✅ 成功" if success else "⚠️ 部分成功"
                extra_info["处理统计"] = stats

            # 如果选择了上传知识库
            if upload_to_kb_flag:
                if not kb_id:
                    logger.warning("未提供知识库ID，无法上传")
                    extra_info["知识库上传"] = "❌ 失败: 未提供知识库ID"
                else:
                    progress(0.99, desc="📚 正在上传到知识库...")
                    logger.info(f"开始上传到知识库 {kb_id}")

                    try:
                        # 使用已经处理过图片的文件进行上传
                        upload_success, upload_result = upload_to_knowledge_base(extract_dir, kb_id)
                        if upload_success:
                            extra_info["知识库上传"] = f"✅ 成功 (知识库ID: {kb_id})"
                            extra_info["知识库上传结果"] = upload_result
                            logger.info(f"上传到知识库成功: {kb_id}")
                        else:
                            extra_info["知识库上传"] = f"❌ 失败: {upload_result.get('错误', '未知错误')}"
                            extra_info["知识库上传结果"] = upload_result
                            logger.warning(f"上传到知识库失败: {upload_result}")
                    except Exception as e:
                        logger.error(f"上传到知识库失败: {str(e)}")
                        extra_info["知识库上传"] = f"❌ 失败: {str(e)}"

            progress(1.0, desc="🎉 转换完成！")
            result_info = {
                "status": "✅ 成功",
                "message": "🎉 PDF转换成功！",
                "task_id": task_id,
                "文件数量": len(result.get("files", [])) if result.get("files") else 0,
                **extra_info
            }
            logger.info(f"处理完成: {result_info}")
            return result_info, final_output_path
        else:
            error_msg = result.get('error', '未知错误')
            logger.error(f"转换失败: {error_msg}")
            return {"error": f"❌ 转换失败: {error_msg}"}, None

    except Exception as e:
        logger.exception(f"处理出错: {str(e)}")
        return {"error": f"❌ 处理失败: {str(e)}"}, None


def show_kb_id_input(upload_to_kb):
    """根据是否选择上传知识库来显示或隐藏知识库ID输入框"""
    return gr.update(visible=upload_to_kb)


def process_multiple_files(pdf_files, upload_to_kb_flag, kb_id, use_ai_flag=True, ai_model=DEFAULT_AI_MODEL,
                           max_chunk_size=DEFAULT_MAX_CHUNK_SIZE, progress=gr.Progress()):
    """处理多个PDF/HTML文件"""
    if not pdf_files:
        return {"error": "❌ 请选择至少一个文件"}, None
    
    # 如果只有一个文件，直接调用单文件处理函数
    if len(pdf_files) == 1:
        pdf_file = pdf_files[0]
        file_extension = os.path.splitext(pdf_file.name)[1].lower()
        
        if file_extension == '.html':
            return process_html_file(pdf_file, upload_to_kb_flag, kb_id, use_ai_flag, ai_model, max_chunk_size, progress)
        else:
            return upload_and_convert_pdf(pdf_file, upload_to_kb_flag, kb_id, use_ai_flag, ai_model, max_chunk_size, progress)
    
    # 创建临时目录来存储所有处理结果
    main_temp_dir = tempfile.mkdtemp()
    main_output_path = os.path.join(main_temp_dir, "combined_results.zip")
    
    # 用于存储所有处理结果
    all_results = {}
    all_extract_dirs = []
    success_count = 0
    fail_count = 0
    
    # 总步骤数 = 文件数
    total_files = len(pdf_files)
    
    try:
        # 处理每个文件
        for i, pdf_file in enumerate(pdf_files):
            file_name = os.path.basename(pdf_file.name)
            file_progress_base = i / total_files
            file_progress_step = 1 / total_files
            
            # 更新进度条
            progress(file_progress_base, desc=f"📄 处理文件 {i+1}/{total_files}: {file_name}")
            logger.info(f"开始处理文件 {i+1}/{total_files}: {file_name}")
            
            # 根据文件类型调用相应的处理函数
            file_extension = os.path.splitext(file_name)[1].lower()
            
            # 创建一个子进度条函数
            def sub_progress(value, desc=""):
                # 将子进度映射到总进度的对应部分
                overall_value = file_progress_base + (value * file_progress_step)
                progress(min(overall_value, 0.99), desc=f"📄 {file_name}: {desc}")
            
            try:
                if file_extension == '.html':
                    # 处理HTML文件
                    result, output_path = process_html_file(
                        pdf_file, upload_to_kb_flag, kb_id, use_ai_flag, ai_model, max_chunk_size, 
                        gr.Progress(lambda v, d: sub_progress(v, d))
                    )
                else:
                    # 处理PDF文件
                    result, output_path = upload_and_convert_pdf(
                        pdf_file, upload_to_kb_flag, kb_id, use_ai_flag, ai_model, max_chunk_size, 
                        gr.Progress(lambda v, d: sub_progress(v, d))
                    )
                
                if "error" not in result:
                    success_count += 1
                    all_results[file_name] = result
                    
                    # 如果有输出路径，解压它以便合并
                    if output_path and os.path.exists(output_path):
                        extract_dir, _, _ = extract_and_find_markdown_files(output_path)
                        all_extract_dirs.append((file_name, extract_dir))
                else:
                    fail_count += 1
                    all_results[file_name] = result
            except Exception as e:
                logger.exception(f"处理文件 {file_name} 时出错: {e}")
                fail_count += 1
                all_results[file_name] = {"error": f"❌ 处理失败: {str(e)}"}
        
        # 创建合并的ZIP文件
        progress(0.95, desc="📦 正在创建合并的ZIP文件...")
        with zipfile.ZipFile(main_output_path, 'w', zipfile.ZIP_DEFLATED) as main_zip:
            # 添加每个处理好的目录到ZIP中
            for file_name, extract_dir in all_extract_dirs:
                base_name = os.path.splitext(file_name)[0]
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算相对路径，并添加文件名前缀以区分不同文件的结果
                        rel_path = os.path.relpath(file_path, extract_dir)
                        zip_path = os.path.join(base_name, rel_path)
                        logger.info(f"添加文件到合并ZIP: {zip_path}")
                        main_zip.write(file_path, zip_path)
        
        # 总结处理结果
        progress(1.0, desc="🎉 所有文件处理完成！")
        summary = {
            "status": "✅ 成功" if fail_count == 0 else "⚠️ 部分成功",
            "message": f"🎉 文件处理完成！成功: {success_count}，失败: {fail_count}",
            "总文件数": total_files,
            "成功数": success_count,
            "失败数": fail_count,
            "文件详情": all_results
        }
        logger.info(f"所有文件处理完成: {summary}")
        return summary, main_output_path
    
    except Exception as e:
        logger.exception(f"批量处理过程中发生错误: {e}")
        return {"error": f"❌ 批量处理失败: {str(e)}"}, None


def create_ui():
    """创建简化版Gradio UI"""
    with gr.Blocks(title="NC 测试中心内部PDF/HTML转换工具", css=CUSTOM_CSS) as demo:
        with gr.Column(elem_classes=["container"]):
            # 标题和说明
            with gr.Column(elem_classes=["header"]):
                gr.Markdown("# 📄 测试中心内部PDF/HTML转换工具")
                gr.Markdown("基于GPDF转换、知识库上传、AI大模型清洗等功能，支持批量处理上传PDF和HTML文件。")

            # 上传区域
            with gr.Column(elem_classes=["upload-section"]):
                gr.Markdown("## 📤 上传PDF/HTML文件")
                pdf_files = gr.File(label="选择PDF/HTML文件", file_types=[".pdf", ".html"], elem_id="pdf-upload", file_count="multiple")

                # 添加转换选项
                gr.Markdown("🔄 转换后处理选项")
                with gr.Row(elem_classes=["options-row"]):
                    upload_to_kb_flag = gr.Checkbox(label="📚 上传知识库", value=True)
                    kb_id_input = gr.Dropdown(
                        label="知识库ID（TODO:自动获取知识库列表，显示格式为：知识库的名称）",
                        choices=[DEFAULT_KB_ID],
                        value=DEFAULT_KB_ID
                    )
                with gr.Row(elem_classes=["options-row"]):
                    use_ai_flag = gr.Checkbox(label="🧠 AI优化文档", value=True)
                    ai_model_input = gr.Dropdown(
                        label="AI模型",
                        choices=[DEFAULT_AI_MODEL],
                        value=DEFAULT_AI_MODEL
                    )
                with gr.Row(elem_classes=["options-row"]):
                    max_chunk_size = gr.Slider(
                        label="文本块最大大小（字符数）",
                        minimum=10000,
                        maximum=200000,
                        value=DEFAULT_MAX_CHUNK_SIZE,
                        step=10000,
                        info="处理长文档时的分块大小，过大可能导致AI处理失败"
                    )

                upload_button = gr.Button("📤 上传并开始转换", variant="primary", size="lg")
                result_info = gr.JSON(label="转换信息", visible=False)

            # 下载区域
            with gr.Column(elem_classes=["download-section"]):
                gr.Markdown("## 📥 下载转换结果")
                zip_output = gr.File(label="ZIP压缩包")

            # 页脚
            with gr.Column(elem_classes=["footer"]):
                gr.Markdown(
                    "© 2025 测试中心内部PDF/HTML转换工具 | 基于[MinerU](https://github.com/opendatalab/MinerU)开发 | 💬 使用问题联系libiao1")

        # 事件处理
        upload_button.click(
            fn=process_multiple_files,
            inputs=[pdf_files, upload_to_kb_flag, kb_id_input, use_ai_flag, ai_model_input, max_chunk_size],
            outputs=[result_info, zip_output],
            show_progress=True  # 显示Gradio内置进度条
        )

        # 当上传知识库复选框状态变化时，显示或隐藏知识库ID输入框
        upload_to_kb_flag.change(
            fn=show_kb_id_input,
            inputs=[upload_to_kb_flag],
            outputs=[kb_id_input]
        )

    return demo


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("启动PDF转换Web应用")
    logger.info("=" * 50)
    demo = create_ui()
    demo.queue()
    demo.launch(share=False, server_name='0.0.0.0')
