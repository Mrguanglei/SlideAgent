"""
文本分块器 - TokenTextSplitter

将长文本分割成较小的块，以便进行向量化处理。

分块策略：
- 按 token 数量分块（默认 512 tokens）
- 保留重叠（默认 50 tokens）以保持上下文连贯性
- 支持按段落、句子智能分割
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

# Token 计数
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


@dataclass
class TextChunk:
    """文本块数据类"""
    index: int  # 块索引
    content: str  # 块内容
    token_count: int  # token 数量
    char_count: int  # 字符数量
    metadata: Dict[str, Any]  # 元数据


class TokenTextSplitter:
    """
    基于 Token 的文本分块器
    
    特点：
    - 使用 tiktoken 进行准确的 token 计数
    - 智能分割：优先在段落、句子边界分割
    - 支持重叠以保持上下文
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",  # GPT-4 使用的编码
        separators: Optional[List[str]] = None,
    ):
        """
        初始化分块器
        
        Args:
            chunk_size: 每个块的最大 token 数量
            chunk_overlap: 块之间的重叠 token 数量
            encoding_name: tiktoken 编码名称
            separators: 分隔符列表，按优先级排序
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name
        
        # 默认分隔符（按优先级）
        self.separators = separators or [
            "\n\n",  # 段落
            "\n",    # 换行
            "。",    # 中文句号
            "！",    # 中文感叹号
            "？",    # 中文问号
            ".",     # 英文句号
            "!",     # 英文感叹号
            "?",     # 英文问号
            "；",    # 中文分号
            ";",     # 英文分号
            "，",    # 中文逗号
            ",",     # 英文逗号
            " ",     # 空格
        ]
        
        # 初始化 tiktoken 编码器
        if HAS_TIKTOKEN:
            try:
                self.encoder = tiktoken.get_encoding(encoding_name)
            except Exception:
                try:
                    self.encoder = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    # 在离线环境或编码下载失败时回退到估算模式
                    self.encoder = None
        else:
            self.encoder = None
    
    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        if self.encoder:
            return len(self.encoder.encode(text))
        else:
            # 简单估算：中文约 1.5 字符/token，英文约 4 字符/token
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 1.5 + other_chars / 4)
    
    def split(self, text: str) -> List[TextChunk]:
        """
        将文本分割成块
        
        Args:
            text: 要分割的文本
            
        Returns:
            TextChunk 列表
        """
        if not text or not text.strip():
            return []
        
        # 预处理文本
        text = text.strip()
        
        # 如果文本足够短，直接返回
        total_tokens = self.count_tokens(text)
        if total_tokens <= self.chunk_size:
            return [TextChunk(
                index=0,
                content=text,
                token_count=total_tokens,
                char_count=len(text),
                metadata={}
            )]
        
        # 递归分割
        chunks = self._split_recursive(text, self.separators)
        
        # 合并小块
        merged_chunks = self._merge_chunks(chunks)
        
        # 创建 TextChunk 对象
        result = []
        for i, chunk_text in enumerate(merged_chunks):
            result.append(TextChunk(
                index=i,
                content=chunk_text,
                token_count=self.count_tokens(chunk_text),
                char_count=len(chunk_text),
                metadata={}
            ))
        
        return result
    
    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        """递归分割文本"""
        if not separators:
            # 没有分隔符了，强制按字符分割
            return self._split_by_chars(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        # 按当前分隔符分割
        if separator in text:
            parts = text.split(separator)
        else:
            # 当前分隔符不存在，尝试下一个
            return self._split_recursive(text, remaining_separators)
        
        chunks = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            part_tokens = self.count_tokens(part)
            
            if part_tokens <= self.chunk_size:
                chunks.append(part)
            else:
                # 继续递归分割
                sub_chunks = self._split_recursive(part, remaining_separators)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_by_chars(self, text: str) -> List[str]:
        """按字符强制分割（最后手段）"""
        chunks = []
        current_chunk = ""
        
        for char in text:
            test_chunk = current_chunk + char
            if self.count_tokens(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = char
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _merge_chunks(self, chunks: List[str]) -> List[str]:
        """合并小块并添加重叠"""
        if not chunks:
            return []
        
        merged = []
        current_chunk = ""
        current_tokens = 0
        
        for chunk in chunks:
            chunk_tokens = self.count_tokens(chunk)
            
            # 检查是否可以合并
            if current_tokens + chunk_tokens <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + chunk
                else:
                    current_chunk = chunk
                current_tokens = self.count_tokens(current_chunk)
            else:
                # 保存当前块
                if current_chunk:
                    merged.append(current_chunk)
                
                # 添加重叠
                if merged and self.chunk_overlap > 0:
                    overlap_text = self._get_overlap_text(merged[-1])
                    current_chunk = overlap_text + "\n\n" + chunk if overlap_text else chunk
                else:
                    current_chunk = chunk
                
                current_tokens = self.count_tokens(current_chunk)
        
        # 添加最后一个块
        if current_chunk:
            merged.append(current_chunk)
        
        return merged
    
    def _get_overlap_text(self, text: str) -> str:
        """获取重叠文本（从末尾截取）"""
        if not text or self.chunk_overlap <= 0:
            return ""
        
        # 从末尾开始，找到合适的重叠点
        words = text.split()
        overlap_words = []
        overlap_tokens = 0
        
        for word in reversed(words):
            word_tokens = self.count_tokens(word)
            if overlap_tokens + word_tokens <= self.chunk_overlap:
                overlap_words.insert(0, word)
                overlap_tokens += word_tokens
            else:
                break
        
        return " ".join(overlap_words)


class SentenceSplitter:
    """
    基于句子的文本分块器
    
    特点：
    - 保持句子完整性
    - 适合需要语义完整性的场景
    """
    
    # 句子结束标记
    SENTENCE_ENDINGS = re.compile(r'([。！？.!?]+)')
    
    def __init__(
        self,
        max_sentences: int = 10,
        min_sentences: int = 3,
    ):
        """
        初始化分块器
        
        Args:
            max_sentences: 每个块的最大句子数
            min_sentences: 每个块的最小句子数
        """
        self.max_sentences = max_sentences
        self.min_sentences = min_sentences
    
    def split_into_sentences(self, text: str) -> List[str]:
        """将文本分割成句子"""
        # 使用正则表达式分割
        parts = self.SENTENCE_ENDINGS.split(text)
        
        sentences = []
        current = ""
        
        for i, part in enumerate(parts):
            if self.SENTENCE_ENDINGS.match(part):
                current += part
                if current.strip():
                    sentences.append(current.strip())
                current = ""
            else:
                current += part
        
        if current.strip():
            sentences.append(current.strip())
        
        return sentences
    
    def split(self, text: str) -> List[str]:
        """将文本分割成块"""
        sentences = self.split_into_sentences(text)
        
        if len(sentences) <= self.max_sentences:
            return [text]
        
        chunks = []
        current_chunk = []
        
        for sentence in sentences:
            current_chunk.append(sentence)
            
            if len(current_chunk) >= self.max_sentences:
                chunks.append(" ".join(current_chunk))
                # 保留一些句子作为重叠
                overlap = max(1, self.min_sentences // 2)
                current_chunk = current_chunk[-overlap:]
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
