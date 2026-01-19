"""
HTML 验证器
用于检查生成的 HTML 是否符合导出要求

更新日志：
- 2026-01-17: 初始版本，支持样式完整性检查、Tailwind检测、尺寸检查等
"""

import re
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HtmlValidator:
    """HTML 验证器"""
    
    def __init__(self):
        self.required_width = 1280
        self.required_height = 720
    
    def validate(self, html: str) -> Dict[str, Any]:
        """
        验证 HTML 是否符合导出要求
        
        Args:
            html: HTML 内容
            
        Returns:
            验证结果字典 {
                "passed": bool,
                "issues": List[str],
                "warnings": List[str],
                "external_resources": List[str]
            }
        """
        issues = []
        warnings = []
        
        # 1. 检查是否有 <style> 标签
        if not self._has_style_tag(html):
            issues.append("缺少 <style> 标签，所有样式必须在 <style> 中定义")
        
        # 2. 检查是否使用了 Tailwind 动态加载
        if self._uses_tailwind_script(html):
            warnings.append("使用了 Tailwind 动态脚本，建议使用 CDN CSS 文件")
        
        # 3. 检查是否有未加载的 Tailwind utility classes
        tailwind_classes = self._find_tailwind_classes(html)
        if tailwind_classes and not self._has_tailwind_css(html):
            issues.append(f"使用了 Tailwind utility classes 但未加载 Tailwind CSS: {', '.join(list(tailwind_classes)[:5])}")
        
        # 4. 检查尺寸设置
        size_issues = self._check_size(html)
        if size_issues:
            warnings.extend(size_issues)
        
        # 5. 检查外部资源
        external_resources = self._find_external_resources(html)
        if external_resources:
            warnings.append(f"使用了 {len(external_resources)} 个外部资源，可能影响导出速度")
        
        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "external_resources": external_resources
        }
    
    def _has_style_tag(self, html: str) -> bool:
        """检查是否有 <style> 标签"""
        return bool(re.search(r'<style[^>]*>.*?</style>', html, re.DOTALL | re.IGNORECASE))
    
    def _uses_tailwind_script(self, html: str) -> bool:
        """检查是否使用了 Tailwind 动态脚本"""
        return 'tailwindcss.com' in html.lower() and '<script' in html.lower()
    
    def _has_tailwind_css(self, html: str) -> bool:
        """检查是否加载了 Tailwind CSS"""
        return 'tailwindcss' in html.lower() and ('<link' in html or 'cdn.jsdelivr.net' in html)
    
    def _find_tailwind_classes(self, html: str) -> set:
        """查找可能的 Tailwind utility classes"""
        # 常见的 Tailwind classes
        tailwind_patterns = [
            r'\bflex\b', r'\bgrid\b', r'\bhidden\b', r'\bblock\b',
            r'\bw-\d+', r'\bh-\d+', r'\bp-\d+', r'\bm-\d+',
            r'\btext-\w+', r'\bbg-\w+', r'\bborder-\w+',
            r'\brounded-\w+', r'\bshadow-\w+'
        ]
        
        found_classes = set()
        for pattern in tailwind_patterns:
            matches = re.findall(pattern, html)
            found_classes.update(matches)
        
        return found_classes
    
    def _check_size(self, html: str) -> List[str]:
        """检查尺寸设置"""
        issues = []
        
        # 检查是否有固定尺寸
        if f'width: {self.required_width}px' not in html and f'width:{self.required_width}px' not in html:
            issues.append(f"未找到固定宽度 {self.required_width}px")
        
        if f'height: {self.required_height}px' not in html and f'height:{self.required_height}px' not in html:
            issues.append(f"未找到固定高度 {self.required_height}px")
        
        return issues
    
    def _find_external_resources(self, html: str) -> List[str]:
        """查找外部资源"""
        resources = []
        
        # 查找外部 CSS
        css_links = re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        resources.extend([url for url in css_links if url.startswith('http')])
        
        # 查找外部图片
        img_srcs = re.findall(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        resources.extend([url for url in img_srcs if url.startswith('http')])
        
        # 查找 background-image
        bg_images = re.findall(r'background-image:\s*url\(["\']?([^"\')\s]+)["\']?\)', html, re.IGNORECASE)
        resources.extend([url for url in bg_images if url.startswith('http')])
        
        return resources


# 单例实例
validator = HtmlValidator()


def validate_html(html: str) -> Dict[str, Any]:
    """验证 HTML"""
    return validator.validate(html)
