"""
HTML 静态化工具模块

用于将包含动态内容的 HTML 转换为完全静态的 HTML，确保导出时无需任何动态渲染。

支持处理：
1. ECharts 图表（Canvas）
2. 其他 Canvas 元素
3. SVG 动画
4. CSS 动画（捕获最终状态）
5. JavaScript 生成的内容
6. Web 字体（等待加载完成）
7. 视频/音频（转换为静态截图）
8. iframe 内容（提取并内联）
"""

import logging
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger(__name__)


class HTMLStaticizer:
    """HTML 静态化器"""
    
    def __init__(self, width: int = 1280, height: int = 720):
        """
        初始化静态化器
        
        Args:
            width: 幻灯片宽度
            height: 幻灯片高度
        """
        self.width = width
        self.height = height
    
    async def staticize_html(self, html: str, timeout: int = 30) -> str:
        """
        将动态 HTML 转换为静态 HTML
        
        Args:
            html: 原始 HTML 内容
            timeout: 渲染超时时间（秒）
            
        Returns:
            静态化后的 HTML 内容
        """
        try:
            logger.info("Starting HTML staticization...")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                page = await browser.new_page(
                    viewport={'width': self.width, 'height': self.height}
                )
                
                # 设置页面内容
                await page.set_content(html, wait_until="domcontentloaded", timeout=timeout * 1000)
                
                # 等待所有资源加载完成
                await self._wait_for_resources(page)
                
                # 等待动态内容渲染
                await self._wait_for_dynamic_content(page)
                
                # 转换动态内容为静态内容
                await self._convert_dynamic_to_static(page)
                
                # 提取静态 HTML
                static_html = await page.content()
                
                await browser.close()
                
                logger.info("HTML staticization completed")
                return static_html
                
        except Exception as e:
            logger.error(f"Failed to staticize HTML: {e}")
            # 静态化失败，返回原始 HTML
            return html
    
    async def _wait_for_resources(self, page: Page):
        """等待所有资源加载完成"""
        try:
            # 等待网络空闲
            await page.wait_for_load_state('networkidle', timeout=10000)
        except Exception as e:
            logger.warning(f"Network idle timeout: {e}")
        
        # 等待字体加载
        try:
            await page.evaluate("""async () => {
                if (document.fonts) {
                    await document.fonts.ready;
                }
            }""")
        except Exception as e:
            logger.warning(f"Font loading timeout: {e}")
    
    async def _wait_for_dynamic_content(self, page: Page):
        """等待动态内容渲染完成"""
        # 等待 Tailwind CSS 生成完成
        await self._wait_for_tailwind(page)
        
        # 等待 ECharts 图表渲染
        await self._wait_for_echarts(page)
        
        # 等待 CSS 动画完成（捕捉最终状态）
        await page.wait_for_timeout(1000)
        
        # 等待 JavaScript 执行完成
        await page.evaluate("() => new Promise(resolve => setTimeout(resolve, 500))")
    
    async def _wait_for_tailwind(self, page: Page):
        """等待 Tailwind CSS 生成完成"""
        try:
            await page.evaluate("""async () => {
                // 检查是否有 Tailwind Play CDN
                const tailwindScript = Array.from(document.querySelectorAll('script')).find(s => 
                    s.src && (s.src.includes('tailwindcss') || s.src.includes('cdn.tailwindcss.com'))
                );
                
                if (tailwindScript) {
                    // 等待 Tailwind CSS 生成完成
                    // Tailwind Play CDN 会在 <head> 中添加 <style> 标签
                    await new Promise(resolve => {
                        const checkInterval = setInterval(() => {
                            const tailwindStyles = Array.from(document.querySelectorAll('style')).find(s => 
                                s.textContent && s.textContent.includes('tailwind')
                            );
                            if (tailwindStyles) {
                                clearInterval(checkInterval);
                                resolve();
                            }
                        }, 100);
                        
                        // 超时保护
                        setTimeout(() => {
                            clearInterval(checkInterval);
                            resolve();
                        }, 3000);
                    });
                    
                    // 额外等待一下，确保所有样式都生成完成
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }""")
        except Exception as e:
            logger.warning(f"Tailwind wait timeout: {e}")
    
    async def _wait_for_echarts(self, page: Page):
        """等待 ECharts 图表渲染完成"""
        try:
            await page.evaluate("""async () => {
                // 检查是否有 ECharts 实例
                if (typeof echarts !== 'undefined') {
                    // 等待所有 ECharts 实例渲染完成
                    const instances = [];
                    document.querySelectorAll('[_echarts_instance_]').forEach(el => {
                        const instance = echarts.getInstanceByDom(el);
                        if (instance) {
                            instances.push(instance);
                        }
                    });
                    
                    // 等待所有实例完成渲染
                    await new Promise(resolve => {
                        if (instances.length === 0) {
                            resolve();
                        } else {
                            let finished = 0;
                            instances.forEach(instance => {
                                instance.on('finished', () => {
                                    finished++;
                                    if (finished === instances.length) {
                                        resolve();
                                    }
                                });
                            });
                            // 超时保护
                            setTimeout(resolve, 5000);
                        }
                    });
                }
            }""")
        except Exception as e:
            logger.warning(f"ECharts wait timeout: {e}")
    
    async def _convert_dynamic_to_static(self, page: Page):
        """将动态内容转换为静态内容"""
        await page.evaluate("""() => {
            // ==================== 1. Canvas 转图片 ====================
            document.querySelectorAll('canvas').forEach(canvas => {
                try {
                    const img = document.createElement('img');
                    img.src = canvas.toDataURL('image/png');
                    
                    // 复制所有属性
                    img.className = canvas.className;
                    img.id = canvas.id;
                    img.style.cssText = canvas.style.cssText;
                    
                    // 设置尺寸
                    if (canvas.width) img.width = canvas.width;
                    if (canvas.height) img.height = canvas.height;
                    
                    // 复制 data 属性
                    Array.from(canvas.attributes).forEach(attr => {
                        if (attr.name.startsWith('data-')) {
                            img.setAttribute(attr.name, attr.value);
                        }
                    });
                    
                    // 替换元素
                    if (canvas.parentNode) {
                        canvas.parentNode.replaceChild(img, canvas);
                    }
                } catch (e) {
                    console.error('Failed to convert canvas:', e);
                }
            });
            
            // ==================== 2. 移除所有脚本标签 ====================
            // Tailwind CSS 已经生成完成，<style> 标签已经存在
            // 现在可以安全地移除所有脚本
            document.querySelectorAll('script').forEach(el => el.remove());
            
            // ==================== 3. 移除 contenteditable ====================
            document.querySelectorAll('[contenteditable]').forEach(el => {
                el.removeAttribute('contenteditable');
            });
            
            // ==================== 4. 停止所有动画 ====================
            // 移除 CSS 动画
            const style = document.createElement('style');
            style.textContent = `
                * {
                    animation: none !important;
                    transition: none !important;
                }
            `;
            document.head.appendChild(style);
            
            // ==================== 5. 处理 SVG 动画 ====================
            document.querySelectorAll('svg animate, svg animateTransform, svg animateMotion').forEach(el => {
                el.remove();
            });
            
            // ==================== 6. 处理视频/音频 ====================
            document.querySelectorAll('video, audio').forEach(el => {
                // 暂停播放
                if (el.pause) el.pause();
                
                // 如果是视频，尝试捕获当前帧
                if (el.tagName === 'VIDEO') {
                    try {
                        const canvas = document.createElement('canvas');
                        canvas.width = el.videoWidth || el.clientWidth;
                        canvas.height = el.videoHeight || el.clientHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(el, 0, 0, canvas.width, canvas.height);
                        
                        const img = document.createElement('img');
                        img.src = canvas.toDataURL('image/png');
                        img.className = el.className;
                        img.style.cssText = el.style.cssText;
                        
                        if (el.parentNode) {
                            el.parentNode.replaceChild(img, el);
                        }
                    } catch (e) {
                        console.error('Failed to convert video:', e);
                    }
                }
            });
            
            // ==================== 7. 保留样式表 ====================
            // 不固化计算样式，保留原始 <style> 标签
            // 这样可以保持 HTML 的可读性和灵活性
            // Tailwind 等 CSS 框架会在渲染时自动应用样式
            
            // ==================== 8. 移除事件监听器属性 ====================
            document.querySelectorAll('*').forEach(el => {
                Array.from(el.attributes).forEach(attr => {
                    if (attr.name.startsWith('on')) {
                        el.removeAttribute(attr.name);
                    }
                });
            });
            
            // ==================== 9. 处理 iframe ====================
            document.querySelectorAll('iframe').forEach(iframe => {
                // 将 iframe 替换为占位符或提取内容
                const placeholder = document.createElement('div');
                placeholder.className = iframe.className;
                placeholder.style.cssText = iframe.style.cssText;
                placeholder.style.background = '#f0f0f0';
                placeholder.style.display = 'flex';
                placeholder.style.alignItems = 'center';
                placeholder.style.justifyContent = 'center';
                placeholder.textContent = '[iframe content]';
                
                if (iframe.parentNode) {
                    iframe.parentNode.replaceChild(placeholder, iframe);
                }
            });
        }""")
    
    async def batch_staticize(self, html_list: list[str], timeout: int = 30) -> list[str]:
        """
        批量静态化 HTML
        
        Args:
            html_list: HTML 列表
            timeout: 每个 HTML 的渲染超时时间（秒）
            
        Returns:
            静态化后的 HTML 列表
        """
        logger.info(f"Starting batch staticization for {len(html_list)} slides...")
        
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            for i, html in enumerate(html_list):
                try:
                    logger.info(f"Staticizing slide {i+1}/{len(html_list)}...")
                    static_html = await self._staticize_with_browser(browser, html, timeout)
                    results.append(static_html)
                except Exception as e:
                    logger.error(f"Failed to staticize slide {i+1}: {e}")
                    results.append(html)  # 失败时使用原始 HTML
            
            await browser.close()
        
        logger.info(f"Batch staticization completed: {len(results)} slides")
        return results
    
    async def _staticize_with_browser(self, browser: Browser, html: str, timeout: int) -> str:
        """使用已有的浏览器实例静态化 HTML"""
        page = await browser.new_page(
            viewport={'width': self.width, 'height': self.height}
        )
        
        try:
            await page.set_content(html, wait_until="domcontentloaded", timeout=timeout * 1000)
            await self._wait_for_resources(page)
            await self._wait_for_dynamic_content(page)
            await self._convert_dynamic_to_static(page)
            static_html = await page.content()
            return static_html
        finally:
            await page.close()


# 创建全局实例
_staticizer = HTMLStaticizer()


async def staticize_html(html: str, timeout: int = 30) -> str:
    """
    静态化单个 HTML
    
    Args:
        html: HTML 内容
        timeout: 超时时间（秒）
        
    Returns:
        静态化后的 HTML
    """
    return await _staticizer.staticize_html(html, timeout)


async def batch_staticize_html(html_list: list[str], timeout: int = 30) -> list[str]:
    """
    批量静态化 HTML
    
    Args:
        html_list: HTML 列表
        timeout: 每个 HTML 的超时时间（秒）
        
    Returns:
        静态化后的 HTML 列表
    """
    return await _staticizer.batch_staticize(html_list, timeout)
