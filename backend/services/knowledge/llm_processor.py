"""
LLM 处理服务 - 关键字提取和向量嵌入

功能：
- 使用 LLM 提取文档关键字和摘要
- 使用嵌入模型生成文本向量
- 支持配置化的模型设置（从 .env 读取）
"""

import json
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import httpx
from utils.env_config import env_config


@dataclass
class LLMConfig:
    """LLM 配置"""
    base_url: str
    api_key: str
    model_name: str
    embedding_model: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从统一配置加载（由 .env 驱动）"""
        env_config.load()
        return cls(
            base_url=env_config.KNOWLEDGE_LLM_BASE_URL or env_config.PPTAGENT_API_BASE or "https://open.bigmodel.cn/api/paas/v4/",
            api_key=env_config.KNOWLEDGE_LLM_API_KEY or env_config.PPTAGENT_API_KEY or "",
            model_name=env_config.KNOWLEDGE_LLM_MODEL or env_config.PPTAGENT_MODEL,
            embedding_model=env_config.KNOWLEDGE_EMBEDDING_MODEL or "embedding-3",
        )


class LLMProcessor:
    """LLM 处理器 - 关键字提取和文本处理"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 LLM 处理器
        
        Args:
            config: LLM 配置，如果为 None 则从环境变量加载
        """
        self.config = config or LLMConfig.from_env()
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        使用 LLM 提取文档关键字
        
        Args:
            text: 文档文本（可以是摘要或完整内容）
            max_keywords: 最大关键字数量
            
        Returns:
            关键字列表
        """
        if not text or not text.strip():
            return []
        
        # 截取前 2000 字符用于提取关键字
        text_sample = text[:2000] if len(text) > 2000 else text
        
        prompt = f"""请从以下文本中提取最重要的关键字（最多 {max_keywords} 个）。

要求：
1. 关键字应该是文档的核心概念、主题词或重要术语
2. 优先提取专有名词、技术术语、核心概念
3. 关键字应该简洁，通常是 1-4 个词
4. 按重要性排序

文本内容：
{text_sample}

请以 JSON 数组格式返回关键字，例如：["关键字1", "关键字2", "关键字3"]
只返回 JSON 数组，不要其他内容。"""

        try:
            response = await self._call_llm(prompt)
            
            # 解析 JSON 响应
            # 尝试提取 JSON 数组
            import re
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                keywords = json.loads(json_match.group())
                return keywords[:max_keywords]
            
            return []
            
        except Exception as e:
            print(f"关键字提取失败: {e}")
            return []
    
    async def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        使用 LLM 生成文档摘要
        
        Args:
            text: 文档文本
            max_length: 摘要最大长度（字符）
            
        Returns:
            文档摘要
        """
        if not text or not text.strip():
            return ""
        
        # 截取前 4000 字符用于生成摘要
        text_sample = text[:4000] if len(text) > 4000 else text
        
        prompt = f"""请为以下文档生成一个简洁的摘要（不超过 {max_length} 字）。

要求：
1. 摘要应该概括文档的主要内容和核心观点
2. 语言简洁、准确
3. 保持客观，不添加主观评价

文档内容：
{text_sample}

请直接返回摘要内容，不要其他说明。"""

        try:
            response = await self._call_llm(prompt)
            return response.strip()[:max_length]
        except Exception as e:
            print(f"摘要生成失败: {e}")
            return ""
    
    async def clean_and_enhance_text(self, text: str) -> str:
        """
        使用 LLM 清洗和增强文本
        
        Args:
            text: 原始文本
            
        Returns:
            清洗后的文本
        """
        if not text or not text.strip():
            return ""
        
        # 如果文本较短，直接返回
        if len(text) < 100:
            return text
        
        # 截取前 3000 字符进行处理
        text_sample = text[:3000] if len(text) > 3000 else text
        
        prompt = f"""请对以下文本进行清洗和格式化处理：

要求：
1. 修正明显的 OCR 错误或乱码
2. 统一标点符号格式
3. 去除无意义的重复内容
4. 保持原文的核心信息不变
5. 如果文本已经很清晰，则保持原样

原始文本：
{text_sample}

请直接返回处理后的文本，不要其他说明。"""

        try:
            response = await self._call_llm(prompt)
            return response.strip()
        except Exception as e:
            print(f"文本清洗失败: {e}")
            return text
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        if not self.config.api_key:
            raise ValueError("LLM API Key 未配置")
        
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": self.config.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }
        
        response = await self.client.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


class EmbeddingProcessor:
    """向量嵌入处理器"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化嵌入处理器
        
        Args:
            config: LLM 配置
        """
        self.config = config or LLMConfig.from_env()
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def embed_text(self, text: str) -> List[float]:
        """
        生成单个文本的向量嵌入
        
        Args:
            text: 文本内容
            
        Returns:
            向量列表
        """
        if not text or not text.strip():
            return []
        
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文本的向量嵌入
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表的列表
        """
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []
        
        if not self.config.api_key:
            raise ValueError("Embedding API Key 未配置")
        
        url = f"{self.config.base_url.rstrip('/')}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": self.config.embedding_model or "embedding-3",
            "input": valid_texts,
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            embeddings = [item["embedding"] for item in result["data"]]
            return embeddings
            
        except Exception as e:
            print(f"向量嵌入失败: {e}")
            return []
    
    async def embed_chunks(
        self, 
        chunks: List[Dict[str, Any]], 
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        批量为文本块生成向量嵌入
        
        Args:
            chunks: 文本块列表，每个块包含 'content' 字段
            batch_size: 每批处理的数量
            
        Returns:
            添加了 'embedding' 字段的文本块列表
        """
        if not chunks:
            return []
        
        result_chunks = []
        
        # 分批处理
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk.get('content', '') for chunk in batch]
            
            embeddings = await self.embed_texts(texts)
            
            for j, chunk in enumerate(batch):
                chunk_copy = chunk.copy()
                if j < len(embeddings):
                    chunk_copy['embedding'] = embeddings[j]
                else:
                    chunk_copy['embedding'] = []
                result_chunks.append(chunk_copy)
            
            # 避免请求过快
            if i + batch_size < len(chunks):
                await asyncio.sleep(0.5)
        
        return result_chunks


# 便捷函数
async def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """提取关键字的便捷函数"""
    processor = LLMProcessor()
    try:
        return await processor.extract_keywords(text, max_keywords)
    finally:
        await processor.close()


async def generate_summary(text: str, max_length: int = 200) -> str:
    """生成摘要的便捷函数"""
    processor = LLMProcessor()
    try:
        return await processor.generate_summary(text, max_length)
    finally:
        await processor.close()


async def embed_text(text: str) -> List[float]:
    """生成向量嵌入的便捷函数"""
    processor = EmbeddingProcessor()
    try:
        return await processor.embed_text(text)
    finally:
        await processor.close()
