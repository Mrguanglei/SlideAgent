"""
资源内联工具模块

用于将 HTML 中的外部资源（图片、字体等）转换为内联的 Base64 格式，
避免导出时依赖外部网络资源，提高导出速度和稳定性。
"""

import re
import base64
import logging
import asyncio
from typing import Optional
from urllib.parse import urlparse
import aiohttp

logger = logging.getLogger(__name__)


async def inline_images_in_html(html: str, timeout: int = 30) -> str:
    """
    将 HTML 中的外部图片 URL 转换为 Base64 内联格式
    
    Args:
        html: HTML 内容
        timeout: 下载超时时间（秒）
        
    Returns:
        处理后的 HTML 内容
    """
    # 匹配 <img src="http://..." 或 <img src='http://...'
    img_pattern = re.compile(r'<img\s+([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>', re.IGNORECASE)
    
    async def replace_img(match):
        """替换单个图片标签"""
        before_src = match.group(1)
        img_url = match.group(2)
        after_src = match.group(3)
        
        # 跳过已经是 Base64 的图片
        if img_url.startswith('data:'):
            return match.group(0)
        
        # 下载并转换为 Base64
        base64_data = await download_and_encode(img_url, timeout)
        
        if base64_data:
            # 检测图片类型
            mime_type = detect_mime_type(img_url, base64_data)
            new_src = f'data:{mime_type};base64,{base64_data}'
            return f'<img {before_src}src="{new_src}"{after_src}>'
        else:
            # 下载失败，保留原 URL
            logger.warning(f"Failed to inline image: {img_url}")
            return match.group(0)
    
    # 查找所有图片标签
    img_matches = list(img_pattern.finditer(html))
    
    if not img_matches:
        return html
    
    logger.info(f"Found {len(img_matches)} images to inline")
    
    # 并发下载所有图片
    tasks = []
    for match in img_matches:
        tasks.append(replace_img(match))
    
    # 等待所有下载完成
    replacements = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 替换 HTML 中的图片标签
    result = html
    for i, match in enumerate(img_matches):
        if isinstance(replacements[i], str):
            result = result.replace(match.group(0), replacements[i], 1)
        else:
            logger.error(f"Error processing image: {replacements[i]}")
    
    logger.info(f"Inlined {len(img_matches)} images")
    return result


async def download_and_encode(url: str, timeout: int = 30) -> Optional[str]:
    """
    下载图片并转换为 Base64
    
    Args:
        url: 图片 URL
        timeout: 超时时间（秒）
        
    Returns:
        Base64 编码的图片数据，失败返回 None
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    image_data = await response.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    return base64_data
                else:
                    logger.warning(f"Failed to download image: {url}, status: {response.status}")
                    return None
    except asyncio.TimeoutError:
        logger.warning(f"Timeout downloading image: {url}")
        return None
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return None


def detect_mime_type(url: str, base64_data: str) -> str:
    """
    检测图片的 MIME 类型
    
    Args:
        url: 图片 URL
        base64_data: Base64 编码的图片数据
        
    Returns:
        MIME 类型字符串
    """
    # 从 URL 扩展名推断
    url_lower = url.lower()
    if url_lower.endswith('.png'):
        return 'image/png'
    elif url_lower.endswith('.jpg') or url_lower.endswith('.jpeg'):
        return 'image/jpeg'
    elif url_lower.endswith('.gif'):
        return 'image/gif'
    elif url_lower.endswith('.svg'):
        return 'image/svg+xml'
    elif url_lower.endswith('.webp'):
        return 'image/webp'
    
    # 从 Base64 数据头部推断（魔术数字）
    try:
        # 解码前几个字节
        data = base64.b64decode(base64_data[:100])
        
        # PNG: 89 50 4E 47
        if data.startswith(b'\x89PNG'):
            return 'image/png'
        # JPEG: FF D8 FF
        elif data.startswith(b'\xFF\xD8\xFF'):
            return 'image/jpeg'
        # GIF: 47 49 46
        elif data.startswith(b'GIF'):
            return 'image/gif'
        # WebP: 52 49 46 46 ... 57 45 42 50
        elif data.startswith(b'RIFF') and b'WEBP' in data[:20]:
            return 'image/webp'
    except Exception:
        pass
    
    # 默认返回 PNG
    return 'image/png'


async def inline_css_backgrounds(html: str, timeout: int = 30) -> str:
    """
    将 CSS 中的背景图片 URL 转换为 Base64 内联格式
    
    Args:
        html: HTML 内容
        timeout: 下载超时时间（秒）
        
    Returns:
        处理后的 HTML 内容
    """
    # 匹配 background-image: url(http://...) 或 background: url(http://...)
    bg_pattern = re.compile(r'(background(?:-image)?:\s*url\(["\']?)([^"\')\s]+)(["\']?\))', re.IGNORECASE)
    
    async def replace_bg(match):
        """替换单个背景图片"""
        before_url = match.group(1)
        img_url = match.group(2)
        after_url = match.group(3)
        
        # 跳过已经是 Base64 的图片
        if img_url.startswith('data:'):
            return match.group(0)
        
        # 下载并转换为 Base64
        base64_data = await download_and_encode(img_url, timeout)
        
        if base64_data:
            mime_type = detect_mime_type(img_url, base64_data)
            new_url = f'data:{mime_type};base64,{base64_data}'
            return f'{before_url}{new_url}{after_url}'
        else:
            logger.warning(f"Failed to inline background image: {img_url}")
            return match.group(0)
    
    # 查找所有背景图片
    bg_matches = list(bg_pattern.finditer(html))
    
    if not bg_matches:
        return html
    
    logger.info(f"Found {len(bg_matches)} background images to inline")
    
    # 并发下载所有图片
    tasks = []
    for match in bg_matches:
        tasks.append(replace_bg(match))
    
    # 等待所有下载完成
    replacements = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 替换 HTML 中的背景图片
    result = html
    for i, match in enumerate(bg_matches):
        if isinstance(replacements[i], str):
            result = result.replace(match.group(0), replacements[i], 1)
        else:
            logger.error(f"Error processing background image: {replacements[i]}")
    
    logger.info(f"Inlined {len(bg_matches)} background images")
    return result


async def inline_all_resources(html: str, timeout: int = 30) -> str:
    """
    内联 HTML 中的所有外部资源（图片、背景图片等）
    
    Args:
        html: HTML 内容
        timeout: 下载超时时间（秒）
        
    Returns:
        处理后的 HTML 内容
    """
    logger.info("Starting resource inlining...")
    
    # 1. 内联 <img> 标签中的图片
    html = await inline_images_in_html(html, timeout)
    
    # 2. 内联 CSS 背景图片
    html = await inline_css_backgrounds(html, timeout)
    
    logger.info("Resource inlining completed")
    return html
