"""
Export Tool HTTP Client

用于从 backend 调用 export_tool 服务的 HTTP 客户端
"""
import logging
import httpx
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Export tool service URL
EXPORT_TOOL_URL = "http://export_tool:8017/api/export_tool"
# Fallback to localhost for development
EXPORT_TOOL_URL_DEV = "http://localhost:8017/api/export_tool"

# Timeout settings (in seconds)
EXPORT_TIMEOUT = 300  # 5 minutes for export operations
EXPORT_TIMEOUT_PPTX = 600  # 10 minutes for PPTX (more complex)


class ExportToolClient:
    """HTTP client for export_tool service"""
    
    def __init__(self, base_url: str = EXPORT_TOOL_URL):
        self.base_url = base_url
        self.timeout = httpx.Timeout(EXPORT_TIMEOUT, connect=10.0)
        self.timeout_pptx = httpx.Timeout(EXPORT_TIMEOUT_PPTX, connect=10.0)
    
    async def export(
        self,
        slides_html: List[str],
        format: str,
        title: str = "presentation"
    ) -> Tuple[bytes, str]:
        """
        导出 PPT 到指定格式
        
        Args:
            slides_html: HTML 幻灯片列表
            format: 导出格式 (pdf/png/html/pptx)
            title: 文件标题
            
        Returns:
            (文件字节, 文件名)
        """
        try:
            url = f"{self.base_url}/{format}"
            
            payload = {
                "slides_html": slides_html,
                "title": title,
                "options": {}
            }
            
            logger.info(f"Calling export_tool service: {url}")
            logger.info(f"Exporting {len(slides_html)} slides to {format}")
            
            # Use longer timeout for PPTX
            timeout = self.timeout_pptx if format == 'pptx' else self.timeout
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                # 从 Content-Disposition header 获取文件名
                content_disposition = response.headers.get("content-disposition", "")
                filename = self._extract_filename(content_disposition, format)
                
                logger.info(f"Export successful: {filename}")
                return response.content, filename
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Export failed with status {e.response.status_code}: {e.response.text}")
            raise Exception(f"Export service error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Export request failed: {e}")
            raise Exception(f"Failed to connect to export service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during export: {e}")
            raise
    
    def _extract_filename(self, content_disposition: str, format: str) -> str:
        """从 Content-Disposition header 提取文件名"""
        if "filename=" in content_disposition:
            # 尝试提取 filename
            parts = content_disposition.split("filename=")
            if len(parts) > 1:
                filename = parts[1].strip('"').strip("'")
                return filename
        
        # 默认文件名
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        extensions = {
            "pdf": "pdf",
            "png": "zip",
            "html": "html",
            "pptx": "pptx"
        }
        
        ext = extensions.get(format, "bin")
        return f"presentation_{timestamp}.{ext}"
    
    async def health_check(self) -> bool:
        """检查 export_tool 服务健康状态"""
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("status") == "healthy"
        except Exception as e:
            logger.warning(f"Export tool health check failed: {e}")
            return False


# Singleton instance
export_client = ExportToolClient()
