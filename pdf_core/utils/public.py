import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

import requests

from utils.Logger import logger
from utils.ai import AIProcessor
from constant import IMAGES_API_URL, KB_API_BASE_URL, DEFAULT_API_KEY, AI_API_BASE_URL, DEFAULT_AI_MODEL, DEFAULT_MAX_CHUNK_SIZE


def extract_image_links(markdown_content):
    """
    从Markdown内容中提取图片链接

    Args:
        markdown_content: Markdown文本内容

    Returns:
        list: 图片链接列表
    """
    # 使用正则表达式匹配Markdown格式的图片链接
    # 格式为: ![可选的alt文本](图片链接)
    image_pattern = r'!\[.*?\]\((.*?)\)'
    return re.findall(image_pattern, markdown_content)


def extract_image_links_by_line(file_path):
    """
    逐行读取Markdown文件并提取每行中的图片链接

    Args:
        file_path: Markdown文件的路径

    Returns:
        list: 包含行号和图片链接的元组列表 [(行号, 图片链接, 原始行内容), ...]
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    image_links = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(file, 1):
            links = extract_image_links(line)
            for link in links:
                image_links.append((line_num, link, line))

    return image_links


def upload_image_to_server(image_path):
    """
    上传图片到图床服务

    Args:
        image_path: 图片文件路径

    Returns:
        dict: 上传结果，包含URL等信息
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    # 获取图片类型
    file_ext = os.path.splitext(image_path)[1][1:].lower()
    if not file_ext:
        file_ext = 'jpg'  # 默认类型

    # 构建curl命令
    cmd = [
        'curl', '-X', 'POST',
        IMAGES_API_URL,
        '-H', 'accept: application/json',
        '-H', 'Content-Type: multipart/form-data',
        '-F', f'file=@{image_path};type=image/{file_ext}',
        '-F', 'description='
    ]

    try:
        # 执行curl命令
        logger.info(f"执行上传命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # 记录原始响应
        logger.info(f"图床API原始响应: {result.stdout}")

        # 解析JSON响应
        response = json.loads(result.stdout)

        # 验证响应格式
        if 'url' in response:
            # 确保URL使用正斜杠
            response['url'] = response['url'].replace('\\', '/')
            logger.info(f"成功获取图床URL: {response['url']}")
        else:
            logger.warning(f"图床API响应缺少URL字段: {response}")

        return response
    except subprocess.CalledProcessError as e:
        logger.error(f"上传图片失败: {e}")
        logger.error(f"错误输出: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"解析响应失败: {e}")
        logger.error(f"原始响应: {result.stdout}")
        return None
    except Exception as e:
        logger.exception(f"上传图片时发生未知错误: {e}")
        return None


def replace_image_links_in_file(file_path, replacements):
    """
    替换Markdown文件中的图片链接

    Args:
        file_path: Markdown文件路径
        replacements: 替换映射 {原始链接: 新链接}

    Returns:
        bool: 是否成功替换
    """
    # 首先创建备份文件
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # 替换所有图片链接
        for old_link, new_link in replacements.items():
            # 处理新链接中的反斜杠，将Windows路径格式转换为URL格式
            new_link_fixed = new_link.replace('\\', '/')
            logger.info(f"替换链接: {old_link} -> {new_link_fixed}")

            # 使用正则表达式确保只替换图片链接部分
            pattern = r'!\[(.*?)\]\(' + re.escape(old_link) + r'\)'
            replacement = r'![\1](' + new_link_fixed + r')'
            content = re.sub(pattern, replacement, content)

        # 写入替换后的内容
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        return True
    except Exception as e:
        logger.error(f"替换图片链接失败: {e}")
        logger.exception("详细错误信息")
        # 恢复备份
        shutil.copy2(backup_path, file_path)
        return False
    finally:
        # 保留备份文件，以防需要手动恢复
        pass


def process_markdown_images(markdown_file, extract_dir):
    """
    处理Markdown文件中的图片，上传到图床并替换链接

    Args:
        markdown_file: Markdown文件路径
        extract_dir: 解压目录路径

    Returns:
        tuple: (success, stats)
            success: 是否成功
            stats: 处理统计信息
    """
    logger.info(f"处理Markdown文件中的图片: {markdown_file}")

    try:
        # 提取图片链接
        image_links_by_line = extract_image_links_by_line(markdown_file)

        if not image_links_by_line:
            logger.info("未找到图片链接")
            return True, {"图片链接": 0, "上传成功": 0, "上传失败": 0}

        logger.info(f"找到 {len(image_links_by_line)} 个图片链接")

        # 上传图片并记录新的URL
        replacements = {}  # {原始链接: 新链接}
        success_count = 0
        fail_count = 0

        for line_num, link, line in image_links_by_line:
            logger.info(f"处理行 {line_num} 中的图片: {link}")

            # 构建完整的图片路径
            markdown_dir = os.path.dirname(markdown_file)

            if link.startswith('images/'):
                # 相对于Markdown文件的images目录
                image_path = os.path.join(markdown_dir, link)
            else:
                # 尝试在同级的images目录中查找
                image_path = os.path.join(markdown_dir, 'images', os.path.basename(link))
                if not os.path.exists(image_path):
                    # 尝试在解压目录的根级images目录中查找
                    image_path = os.path.join(extract_dir, 'images', os.path.basename(link))

            # 检查图片是否存在
            if not os.path.exists(image_path):
                logger.warning(f"图片文件不存在: {image_path}")
                fail_count += 1
                continue

            logger.info(f"上传图片: {image_path}")

            # 上传图片
            response = upload_image_to_server(image_path)

            # 记录完整响应以便调试
            logger.info(f"图床API响应: {response}")

            if response and 'url' in response:
                new_url = response['url']
                logger.info(f"上传成功! 新URL: {new_url}")

                # 检查URL格式，确保使用正斜杠
                if '\\' in new_url:
                    logger.info(f"URL中包含反斜杠，进行替换: {new_url}")
                    new_url = new_url.replace('\\', '/')
                    logger.info(f"替换后的URL: {new_url}")

                replacements[link] = new_url
                success_count += 1
            else:
                logger.error(f"上传失败或返回格式异常: {response}")
                fail_count += 1

        # 替换原始文件中的图片链接
        if replacements:
            logger.info(f"开始替换文件中的 {len(replacements)} 个图片链接...")

            # 记录所有替换项以便调试
            for old_link, new_link in replacements.items():
                logger.info(f"准备替换: {old_link} -> {new_link}")

            success = replace_image_links_in_file(markdown_file, replacements)

            if success:
                logger.info("替换完成! 原文件已备份为 .bak 文件")
            else:
                logger.error("替换失败! 已恢复原文件")
                return False, {"图片链接": len(image_links_by_line), "上传成功": success_count, "上传失败": fail_count}

            # 显示替换结果
            for old_link, new_link in replacements.items():
                logger.info(f"已替换: {old_link} -> {new_link}")

        return True, {"图片链接": len(image_links_by_line), "上传成功": success_count, "上传失败": fail_count}

    except Exception as e:
        logger.exception(f"处理出错: {e}")
        return False, {"错误": str(e)}


def process_all_markdown_files(extract_dir, markdown_files):
    """
    处理所有Markdown文件中的图片链接

    Args:
        extract_dir: 解压目录
        markdown_files: Markdown文件列表

    Returns:
        tuple: (success, stats)
            success: 是否全部成功
            stats: 处理统计信息
    """
    total_stats = {
        "处理的文件": len(markdown_files),
        "成功处理": 0,
        "失败处理": 0,
        "总图片链接": 0,
        "总上传成功": 0,
        "总上传失败": 0
    }

    all_success = True

    for md_file in markdown_files:
        logger.info(f"开始处理文件: {md_file}")
        success, stats = process_markdown_images(md_file, extract_dir)

        if success:
            total_stats["成功处理"] += 1
        else:
            total_stats["失败处理"] += 1
            all_success = False

        total_stats["总图片链接"] += stats.get("图片链接", 0)
        total_stats["总上传成功"] += stats.get("上传成功", 0)
        total_stats["总上传失败"] += stats.get("上传失败", 0)

    logger.info(f"所有Markdown文件处理完成，统计信息: {total_stats}")
    return all_success, total_stats


def extract_and_find_markdown_files(zip_path):
    """
    解压ZIP文件并查找其中的Markdown文件和images目录

    Args:
        zip_path: ZIP文件路径

    Returns:
        tuple: (temp_extract_dir, markdown_files, images_dirs)
            temp_extract_dir: 临时解压目录
            markdown_files: Markdown文件路径列表
            images_dirs: images目录路径列表
    """
    # 创建临时目录用于解压
    temp_extract_dir = tempfile.mkdtemp()

    try:
        # 解压ZIP文件
        logger.info(f"正在解压文件: {zip_path}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)

        # 查找所有Markdown文件
        markdown_files = []
        for root, _, files in os.walk(temp_extract_dir):
            for file in files:
                if file.lower().endswith('.md'):
                    markdown_files.append(os.path.join(root, file))

        # 查找所有images目录
        images_dirs = []
        for root, dirs, _ in os.walk(temp_extract_dir):
            for dir_name in dirs:
                if dir_name.lower() == 'images':
                    images_dirs.append(os.path.join(root, dir_name))

        logger.info(f"解压完成，找到 {len(markdown_files)} 个Markdown文件和 {len(images_dirs)} 个images目录")
        return temp_extract_dir, markdown_files, images_dirs
    except Exception as e:
        logger.error(f"解压或查找文件时出错: {e}")
        return temp_extract_dir, [], []


def create_new_zip_with_processed_files(original_zip_path, processed_dir):
    """
    创建一个新的ZIP文件，包含处理过的文件

    Args:
        original_zip_path: 原始ZIP文件路径
        processed_dir: 处理后的文件目录

    Returns:
        str: 新ZIP文件路径
    """
    # 创建新的ZIP文件路径
    new_zip_path = original_zip_path.replace('.zip', '_processed.zip')
    logger.info(f"创建新的ZIP文件: {new_zip_path}")

    # 创建新的ZIP文件
    file_count = 0
    with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加处理目录中的所有文件
        for root, dirs, files in os.walk(processed_dir):
            for file in files:
                # 跳过备份文件
                if file.endswith('.bak'):
                    continue

                file_path = os.path.join(root, file)
                # 计算相对路径，保持目录结构
                rel_path = os.path.relpath(file_path, processed_dir)
                logger.info(f"添加文件到ZIP: {rel_path}")
                zipf.write(file_path, rel_path)
                file_count += 1

    logger.info(f"新ZIP文件创建完成: {new_zip_path}，包含 {file_count} 个文件")

    # 验证新ZIP文件
    try:
        with zipfile.ZipFile(new_zip_path, 'r') as zipf:
            # 列出ZIP文件内容
            file_list = zipf.namelist()
            logger.info(f"ZIP文件内容验证: 包含 {len(file_list)} 个文件")

            # 检查是否包含Markdown文件
            md_files = [f for f in file_list if f.lower().endswith('.md')]
            logger.info(f"ZIP文件中包含 {len(md_files)} 个Markdown文件")

            if len(md_files) == 0:
                logger.warning("警告: ZIP文件中不包含Markdown文件!")
    except Exception as e:
        logger.error(f"验证ZIP文件时出错: {e}")

    return new_zip_path


def upload_files_to_dataset(file_paths, dataset_id, api_key=None):
    """
    向指定的数据集上传多个文件并解析

    Args:
        file_paths: 要上传的文件路径列表
        dataset_id: 数据集ID
        api_key: API密钥，默认使用预设值

    Returns:
        tuple: (success, response_data)
            success: 是否成功
            response_data: 响应数据
    """
    if not api_key:
        api_key = DEFAULT_API_KEY  # 使用常量中的默认API密钥

    url = f"{KB_API_BASE_URL}/datasets/{dataset_id}/documents"

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # 准备文件
    logger.info(f"准备上传 {len(file_paths)} 个文件到数据集 {dataset_id}")
    files = []
    for path in file_paths:
        try:
            file_name = os.path.basename(path)
            files.append(('file', (file_name, open(path, 'rb'))))
            logger.info(f"添加文件: {file_name}")
        except Exception as e:
            logger.error(f"准备文件 {path} 时出错: {e}")

    if not files:
        logger.error("没有有效的文件可上传")
        return False, {"error": "没有有效的文件可上传"}

    try:
        with requests.Session() as session:
            # 上传文件
            logger.info(f"正在上传文件到 {url}")
            upload_response = session.post(url, headers=headers, files=files)

            if upload_response.status_code != 200:
                logger.error(f"上传文件失败: {upload_response.text}")
                return False, {"error": f"上传文件失败: {upload_response.text}"}

            upload_data = upload_response.json()
            logger.info(f"文件上传成功: {upload_data}")

            # 获取文档ID
            doc_ids = [doc['id'] for doc in upload_data.get('data', [])]
            if not doc_ids:
                logger.error("上传成功但未返回文档ID")
                return False, {"error": "上传成功但未返回文档ID"}

            logger.info(f"获取到文档ID: {doc_ids}")

            # 解析文档
            url_chunks = f"{KB_API_BASE_URL}/datasets/{dataset_id}/chunks"
            data = {
                'document_ids': doc_ids,
            }

            logger.info(f"开始解析文档: {doc_ids}")
            chunks_response = session.post(url_chunks, headers=headers, json=data)

            if chunks_response.status_code != 200:
                logger.error(f"解析文档失败: {chunks_response.text}")
                return False, {"error": f"解析文档失败: {chunks_response.text}"}

            chunks_data = chunks_response.json()
            logger.info(f"文档解析成功: {chunks_data}")

            return True, {
                "upload": upload_data,
                "chunks": chunks_data,
                "document_ids": doc_ids
            }
    except Exception as e:
        logger.exception(f"上传或解析过程中发生异常: {e}")
        return False, {"error": f"请求过程中发生异常: {str(e)}"}
    finally:
        # 关闭所有打开的文件
        for _, file_tuple in files:
            try:
                file_tuple[1].close()
            except:
                pass


def upload_to_knowledge_base(extract_dir, kb_id=None):
    """上传到知识库功能"""
    logger.info(f"准备上传到知识库: {extract_dir}, 知识库ID: {kb_id}")

    # 查找所有Markdown文件（排除备份文件）
    markdown_files = []
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith('.md') and not file.endswith('.bak') and not file.endswith('.original'):
                markdown_files.append(os.path.join(root, file))

    # 查找所有images目录
    images_dirs = []
    for root, dirs, _ in os.walk(extract_dir):
        for dir_name in dirs:
            if dir_name.lower() == 'images':
                images_dirs.append(os.path.join(root, dir_name))

    logger.info(f"找到 {len(markdown_files)} 个Markdown文件:")
    for md_file in markdown_files:
        logger.info(f"  - {md_file}")

    logger.info(f"找到 {len(images_dirs)} 个images目录:")
    for img_dir in images_dirs:
        logger.info(f"  - {img_dir}")
        # 列出目录中的图片文件
        image_files = glob.glob(os.path.join(img_dir, "*.*"))
        logger.info(f"    包含 {len(image_files)} 个文件")
        for img_file in image_files[:5]:  # 只打印前5个文件，避免输出过多
            logger.info(f"    - {os.path.basename(img_file)}")
        if len(image_files) > 5:
            logger.info(f"    - ... 等 {len(image_files) - 5} 个文件")

    # 上传处理后的Markdown文件到知识库
    if markdown_files:
        logger.info(f"开始上传 {len(markdown_files)} 个Markdown文件到知识库 {kb_id}")
        success, response_data = upload_files_to_dataset(markdown_files, kb_id)

        if success:
            logger.info(f"上传到知识库成功: {response_data}")
            return True, {
                "上传文件数": len(markdown_files),
                "文档IDs": response_data.get("document_ids", []),
                "状态": "成功"
            }
        else:
            logger.error(f"上传到知识库失败: {response_data}")
            return False, {
                "上传文件数": len(markdown_files),
                "错误": response_data.get("error", "未知错误"),
                "状态": "失败"
            }
    else:
        logger.warning("没有找到Markdown文件，无法上传到知识库")
        return False, {"错误": "没有找到Markdown文件，无法上传到知识库"}


def process_markdown_with_ai(markdown_file, ai_processor):
    """
    使用AI处理Markdown文件内容

    Args:
        markdown_file: Markdown文件路径
        ai_processor: AI处理器实例

    Returns:
        bool: 是否成功处理
    """
    try:
        logger.info(f"使用AI处理Markdown文件: {markdown_file}")

        # 读取Markdown文件内容
        with open(markdown_file, 'r', encoding='utf-8') as file:
            content = file.read()

        # 创建备份
        backup_path = f"{markdown_file}.original"
        if not os.path.exists(backup_path):
            logger.info(f"创建原始文件备份: {backup_path}")
            shutil.copy2(markdown_file, backup_path)

        # 使用AI处理内容
        logger.info(f"开始AI处理，原始内容长度: {len(content)}")
        processed_content = ai_processor.process_text(content)

        if processed_content and not processed_content.startswith("AI处理失败") and not processed_content.startswith(
                "处理文本时出错"):
            # 写入处理后的内容
            with open(markdown_file, 'w', encoding='utf-8') as file:
                file.write(processed_content)
            logger.info(f"AI处理完成，新内容长度: {len(processed_content)}")
            return True
        else:
            logger.error(f"AI处理未返回有效内容: {processed_content[:100]}...")
            return False

    except Exception as e:
        logger.exception(f"AI处理Markdown文件时出错: {e}")
        return False


def process_all_markdown_files_with_ai(markdown_files, ai_base_url=AI_API_BASE_URL,
                                       ai_model=DEFAULT_AI_MODEL, max_chunk_size=DEFAULT_MAX_CHUNK_SIZE):
    """
    使用AI处理所有Markdown文件

    Args:
        markdown_files: Markdown文件路径列表
        ai_base_url: AI服务基础URL
        ai_model: AI模型名称
        max_chunk_size: 每个文本块的最大字符数

    Returns:
        tuple: (success_count, fail_count)
    """
    # 初始化AI处理器
    ai_processor = AIProcessor(ai_base_url, ai_model, max_chunk_size)

    success_count = 0
    fail_count = 0

    for md_file in markdown_files:
        logger.info(f"开始AI处理文件: {md_file}")
        success = process_markdown_with_ai(md_file, ai_processor)

        if success:
            success_count += 1
            logger.info(f"AI处理成功: {md_file}")
        else:
            fail_count += 1
            logger.error(f"AI处理失败: {md_file}")

    logger.info(f"AI处理完成，成功: {success_count}，失败: {fail_count}")
    return success_count, fail_count
