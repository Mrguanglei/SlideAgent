"""
HTML staticization utility - converts dynamic content to static
"""
import logging
import asyncio
from typing import List
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def staticize_html(html: str, timeout: int = 30) -> str:
    """
    静态化单个 HTML 幻灯片
    - 将 Canvas 转换为图片
    - 将 CSSOM 样式固化到 DOM
    - 移除脚本标签
    
    Args:
        html: HTML 内容
        timeout: 超时时间（秒）
        
    Returns:
        静态化后的 HTML
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.new_page()
            
            # 设置内容
            await page.set_content(html, wait_until="domcontentloaded", timeout=timeout * 1000)
            
            # 等待渲染
            await page.wait_for_timeout(2000)
            
            # 执行静态化脚本
            await page.evaluate("""
                () => {
                    // 1. 固化 CSSOM 样式
                    try {
                        for (const sheet of document.styleSheets) {
                            try {
                                if (!sheet.href && sheet.ownerNode && sheet.ownerNode.tagName === 'STYLE') {
                                    if (sheet.cssRules) {
                                        let css = '';
                                        for (const rule of sheet.cssRules) {
                                            css += rule.cssText + '\\n';
                                        }
                                        if (css) {
                                            sheet.ownerNode.textContent = css;
                                        }
                                    }
                                }
                            } catch (e) {
                                // 忽略跨域样式表访问错误
                            }
                        }
                    } catch (e) {
                        console.error('CSS Materialization failed:', e);
                    }

                    // 2. Canvas -> Image
                    document.querySelectorAll('canvas').forEach(canvas => {
                        try {
                            const img = document.createElement('img');
                            img.src = canvas.toDataURL('image/png');
                            img.style.cssText = canvas.style.cssText;
                            img.className = canvas.className;
                            img.style.width = canvas.width + 'px';
                            img.style.height = canvas.height + 'px';
                            if (canvas.parentNode) {
                                canvas.parentNode.replaceChild(img, canvas);
                            }
                        } catch (e) {
                            console.error('Canvas to Image failed:', e);
                        }
                    });
                    
                    // 3. 移除脚本
                    document.querySelectorAll('script').forEach(el => el.remove());
                    
                    // 4. 移除 contenteditable
                    document.querySelectorAll('[contenteditable]').forEach(el => {
                        el.removeAttribute('contenteditable');
                    });
                }
            """)
            
            # 获取静态化后的 HTML
            staticized_html = await page.content()
            
            await browser.close()
            
            logger.info("HTML staticized successfully")
            return staticized_html
            
    except Exception as e:
        logger.error(f"Failed to staticize HTML: {e}")
        # 失败时返回原始 HTML
        return html


async def batch_staticize_html(slides_html: List[str], timeout: int = 30) -> List[str]:
    """
    批量静态化多个 HTML 幻灯片
    
    Args:
        slides_html: HTML 幻灯片列表
        timeout: 每个幻灯片的超时时间（秒）
        
    Returns:
        静态化后的 HTML 列表
    """
    logger.info(f"Staticizing {len(slides_html)} slides...")
    
    # 并发处理多个幻灯片
    tasks = [staticize_html(html, timeout) for html in slides_html]
    staticized_slides = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理异常情况
    result = []
    for i, slide in enumerate(staticized_slides):
        if isinstance(slide, Exception):
            logger.error(f"Failed to staticize slide {i+1}: {slide}")
            result.append(slides_html[i])  # 使用原始 HTML
        else:
            result.append(slide)
    
    logger.info(f"Staticization completed: {len(result)} slides")
    return result
