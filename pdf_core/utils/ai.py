import requests
import re

from utils.Logger import logger
from constant import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, DEFAULT_MAX_CHUNK_SIZE, DEFAULT_FORMAT_PROMPT


class AIProcessor:
    """AI文本处理类"""

    def __init__(self, base_url: str, model: str, max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE):
        self.base_url = base_url
        self.model = model
        self.max_chunk_size = max_chunk_size  # 每个chunk的最大字符数
        logger.info(f"初始化AI处理器: {base_url}, 模型: {model}, 最大chunk大小: {max_chunk_size}")

    def process_text(self, text: str, enter_text=None) -> str:
        """
        使用AI模型处理文本，如果文本过长则分块处理

        Args:
            text: 要处理的文本
            enter_text: 额外的文本输入（未使用，但保留接口一致性）

        Returns:
            处理后的文本
        """
        if not text or len(text.strip()) == 0:
            logger.warning("输入文本为空")
            return ""

        # 检查文本长度是否超过最大限制
        if len(text) > self.max_chunk_size:
            logger.info(f"文本长度({len(text)})超过最大限制({self.max_chunk_size})，将进行分块处理")
            return self._process_long_text(text, enter_text)
        else:
            return self._process_single_chunk(text, enter_text)

    def _process_long_text(self, text: str, enter_text=None) -> str:
        """
        处理长文本，将其分块并依次处理
        
        Args:
            text: 要处理的长文本
            enter_text: 额外的文本输入
            
        Returns:
            处理后的完整文本
        """
        chunks = self._split_text(text)
        logger.info(f"文本已分割为{len(chunks)}个块")
        
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            logger.info(f"开始处理第{i+1}/{len(chunks)}个块，长度: {len(chunk)}")
            # 只在最后一个块添加enter_text
            chunk_enter_text = enter_text if i == len(chunks) - 1 else None
            processed_chunk = self._process_single_chunk(chunk, chunk_enter_text)
            
            if processed_chunk.startswith("AI处理失败") or processed_chunk.startswith("处理文本时出错"):
                logger.error(f"第{i+1}个块处理失败: {processed_chunk}")
                # 如果块处理失败，返回原始块内容
                processed_chunks.append(chunk)
            else:
                processed_chunks.append(processed_chunk)
        
        # 合并所有处理后的块
        result = "\n\n".join(processed_chunks)
        logger.info(f"所有块处理完成，合并后长度: {len(result)}")
        return result
    
    def _split_text(self, text: str) -> list:
        """
        将长文本分割成多个块
        
        Args:
            text: 要分割的长文本
            
        Returns:
            文本块列表
        """
        chunks = []
        remaining_text = text
        
        while len(remaining_text) > self.max_chunk_size:
            # 在最大块大小范围内寻找最后一个段落结束位置
            split_pos = remaining_text[:self.max_chunk_size].rfind("</p>")
            
            if split_pos == -1:
                # 如果找不到</p>标签，尝试寻找其他自然分割点如段落结束
                split_pos = remaining_text[:self.max_chunk_size].rfind("\n\n")
                
            if split_pos == -1:
                # 如果仍找不到，尝试寻找句号作为分割点
                split_pos = remaining_text[:self.max_chunk_size].rfind("。")
                
            if split_pos == -1:
                # 如果仍找不到适合的分割点，就在最大大小处截断
                split_pos = self.max_chunk_size
            else:
                # 调整分割位置到包含分隔符
                split_pos += 4 if remaining_text[split_pos:split_pos+4] == "</p>" else 1
            
            # 切分文本
            chunk = remaining_text[:split_pos]
            chunks.append(chunk)
            remaining_text = remaining_text[split_pos:]
        
        # 添加剩余文本作为最后一个块
        if remaining_text:
            chunks.append(remaining_text)
        
        return chunks

    def _process_single_chunk(self, text: str, enter_text=None) -> str:
        """
        处理单个文本块
        
        Args:
            text: 要处理的文本块
            enter_text: 额外的文本输入
            
        Returns:
            处理后的文本块
        """
        try:
            prompt = f"{DEFAULT_FORMAT_PROMPT}\n{text}"

            if enter_text:
                prompt += f"\n\n下面内容为重要的链接信息，追加到正文后面：\n{enter_text}"

            logger.debug(f"AI处理提示词: {prompt[:200]}...")

            # 构建API请求
            headers = {
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": DEFAULT_TEMPERATURE,
                "max_tokens": DEFAULT_MAX_TOKENS
            }

            logger.info(f"发送请求到AI模型: {self.model}")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=300
            )

            # 检查响应
            if response.status_code == 200:
                result = response.json()
                processed_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(f"AI处理成功，输出长度: {len(processed_text)}")
                return processed_text
            else:
                logger.error(f"AI处理失败: HTTP {response.status_code}, {response.text}")
                return f"AI处理失败: {response.status_code}"

        except Exception as e:
            logger.exception(f"AI处理异常: {str(e)}")
            return f"处理文本时出错: {str(e)}"
