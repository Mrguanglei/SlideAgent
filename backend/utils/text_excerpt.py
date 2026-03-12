"""
文本节选工具

用于从超长文本中抽取均衡分布的片段，避免只取开头导致信息不完整。
"""

from __future__ import annotations

from typing import List


def _snap_to_newline(text: str, start: int, end: int, window: int = 200) -> tuple[int, int]:
    """在给定窗口内尽量对齐到换行符，减少截断感。"""
    if not text:
        return start, end

    # 向前找最近的换行
    left = max(0, start - window)
    newline_before = text.rfind("\n", left, start)
    if newline_before != -1:
        start = newline_before + 1

    # 向后找最近的换行
    right = min(len(text), end + window)
    newline_after = text.find("\n", end, right)
    if newline_after != -1:
        end = newline_after

    return start, end


def build_balanced_excerpt(text: str, max_chars: int = 4000, segments: int = 5) -> str:
    """
    从长文本中抽取均衡分布的片段，覆盖前中后内容。

    Args:
        text: 原始文本
        max_chars: 最大输出字符数
        segments: 片段数量（均匀分布）

    Returns:
        节选文本（可能带分段标记）
    """
    if not text:
        return ""

    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    if max_chars <= 0:
        return ""

    # 保证 segments 合理
    segments = max(1, int(segments))
    if max_chars < segments * 120:
        segments = max(1, max_chars // 120)

    if segments <= 1:
        return cleaned[:max_chars]

    segment_len = max(200, max_chars // segments)
    total_len = len(cleaned)
    max_start = max(0, total_len - segment_len)
    step = max(1, max_start // (segments - 1))

    excerpts: List[str] = []
    for i in range(segments):
        start = min(max_start, i * step)
        end = min(total_len, start + segment_len)
        start, end = _snap_to_newline(cleaned, start, end)
        part = cleaned[start:end].strip()
        if part:
            excerpts.append(f"【节选 {i + 1}/{segments}】\n{part}")

    if not excerpts:
        return cleaned[:max_chars]

    return "\n\n".join(excerpts)


def build_prompt_context(
    text: str,
    max_chars: int = 4000,
    segments: int = 5,
    full_threshold: int = 12000,
) -> str:
    """
    生成用于提示词的文本上下文。
    当前策略：始终返回全文（不做截断或节选）。
    说明：保留参数以便将来可配置为节选策略。
    """
    if not text:
        return ""
    return text.strip()
