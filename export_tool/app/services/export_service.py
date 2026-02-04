"""
Unified export service - supports PDF, PNG, HTML, and PPTX exports
"""
import zipfile
import logging
import asyncio
import shutil
from typing import List, Tuple
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from playwright.async_api import async_playwright

from app.utils.html_staticizer import batch_staticize_html
from app.services.pptx_service import generate_pptx_from_html
from app.models.schemas import ExportRequest, HtmlToPptxRequest, PptxOptions

logger = logging.getLogger(__name__)

# Export directory
EXPORT_DIR = Path("/tmp/ppt_exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class ExportService:
    """Unified export service for all formats"""
    
    def __init__(self):
        self.slide_width = 1280
        self.slide_height = 720
    
    def _extract_body_content(self, html: str) -> str:
        """Extract body content from HTML"""
        import re
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            return body_match.group(1)
        return html
    
    def _extract_style_content(self, html: str) -> str:
        """Extract style content from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        styles = []
        
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                styles.append(style_tag.string)
        
        return '\n'.join(styles)

    def _extract_body_attrs(self, html: str) -> Tuple[List[str], str, dict]:
        """Extract body classes/style/attributes from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.body
        if not body:
            return [], "", {}
        
        classes = body.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        style = body.get("style", "")
        attrs = {k: v for k, v in body.attrs.items() if k not in ("class", "style")}
        return classes, style, attrs
    
    def _scope_css(self, css: str, scope_class: str) -> str:
        """Add scoping to CSS to avoid conflicts - Enhanced version"""
        if not css or not css.strip():
            return ''
        
        lines = []
        in_media_query = False
        in_keyframes = False
        in_font_face = False
        brace_depth = 0
        
        for line in css.split('\n'):
            stripped = line.strip()
            
            # Handle @import and @charset - keep as-is
            if stripped.startswith('@import') or stripped.startswith('@charset'):
                lines.append(line)
                continue
            
            # Handle @media queries
            if stripped.startswith('@media'):
                in_media_query = True
                brace_depth = 0
                lines.append(line)
                continue
            
            # Handle @keyframes
            if stripped.startswith('@keyframes') or stripped.startswith('@-webkit-keyframes'):
                in_keyframes = True
                brace_depth = 0
                lines.append(line)
                continue
            
            # Handle @font-face
            if stripped.startswith('@font-face'):
                in_font_face = True
                brace_depth = 0
                lines.append(line)
                continue
            
            # Track brace depth for nested rules
            brace_depth += stripped.count('{') - stripped.count('}')
            
            # Exit special blocks when braces are balanced
            if brace_depth <= 0:
                if in_media_query:
                    in_media_query = False
                if in_keyframes:
                    in_keyframes = False
                if in_font_face:
                    in_font_face = False
            
            # Don't scope inside special blocks
            if in_media_query or in_keyframes or in_font_face:
                lines.append(line)
                continue
            
            # Scope regular CSS rules
            if '{' in stripped and not stripped.startswith('@') and not stripped.startswith('/*'):
                try:
                    selector_part = stripped[:stripped.index('{')].strip()
                    rest = stripped[stripped.index('{'):]
                    
                    selectors = [s.strip() for s in selector_part.split(',')]
                    scoped_selectors = []
                    
                    for sel in selectors:
                        if not sel:
                            continue
                        
                        # Handle pseudo-elements and pseudo-classes
                        if '::' in sel or sel.startswith(':'):
                            scoped_sel = f".{scope_class} {sel}"
                        elif sel.lower() in ('body', 'html', '*'):
                            scoped_sel = f".{scope_class}"
                        elif sel.lower().startswith('body ') or sel.lower().startswith('html '):
                            scoped_sel = f".{scope_class} " + sel.split(None, 1)[1]
                        else:
                            scoped_sel = f".{scope_class} {sel}"
                        
                        scoped_selectors.append(scoped_sel)
                    
                    scoped_line = ', '.join(scoped_selectors) + ' ' + rest
                    lines.append(' ' * (len(line) - len(line.lstrip())) + scoped_line)
                except Exception as e:
                    # If scoping fails, keep original line
                    logger.warning(f"Failed to scope CSS line: {line[:50]}... Error: {e}")
                    lines.append(line)
            else:
                lines.append(line)
        
        return '\n'.join(lines)
    
    def _merge_slides_html(self, slides_html: List[str]) -> str:
        """Merge multiple slides into a single HTML document"""
        all_contents = []
        all_styles = []
        
        for i, slide_html in enumerate(slides_html):
            body_content = self._extract_body_content(slide_html)
            style_content = self._extract_style_content(slide_html)
            
            scoped_style = self._scope_css(style_content, f"slide-{i+1}")
            all_styles.append(scoped_style)
            
            wrapped_content = f'''
            <div class="slide-page slide-{i+1}" id="slide-{i+1}">
                {body_content}
            </div>
            '''
            all_contents.append(wrapped_content)
        
        merged_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            background: white;
            font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
        }}
        .slide-page {{
            width: {self.slide_width}px;
            height: {self.slide_height}px;
            page-break-after: always;
            overflow: hidden;
            position: relative;
        }}
        .slide-page:last-child {{
            page-break-after: auto;
        }}
        {chr(10).join(all_styles)}
    </style>
</head>
<body>
    {''.join(all_contents)}
</body>
</html>'''
        
        return merged_html

    def _merge_slides_for_pptx(self, slides_html: List[str]) -> Tuple[str, str]:
        """Merge slides into HTML/CSS payload for dom-to-pptx conversion"""
        import html as html_module
        
        slide_blocks = []
        scoped_styles = []
        
        for i, slide_html in enumerate(slides_html):
            body_content = self._extract_body_content(slide_html)
            style_content = self._extract_style_content(slide_html)
            scoped_style = self._scope_css(style_content, f"slide-{i+1}")
            if scoped_style:
                scoped_styles.append(scoped_style)
            
            body_classes, body_style, body_attrs = self._extract_body_attrs(slide_html)
            class_list = ["ppt-slide", f"slide-{i+1}"] + body_classes
            attr_parts = [f'class="{html_module.escape(" ".join(class_list), quote=True)}"']
            
            if body_style:
                attr_parts.append(f'style="{html_module.escape(body_style, quote=True)}"')
            
            for key, value in body_attrs.items():
                attr_parts.append(f'{key}="{html_module.escape(str(value), quote=True)}"')
            
            slide_blocks.append(f'<div {" ".join(attr_parts)}>{body_content}</div>')
        
        base_css = f"""
        .ppt-slide {{
            width: {self.slide_width}px;
            height: {self.slide_height}px;
            position: relative;
            overflow: hidden;
        }}
        .ppt-slide * {{
            box-sizing: border-box;
        }}
        """
        combined_css = base_css + "\n" + "\n".join(scoped_styles)
        
        return "\n".join(slide_blocks), combined_css
    
    async def export_to_pdf(
        self,
        slides_html: List[str],
        title: str = "presentation"
    ) -> Tuple[str, str]:
        """Export slides to PDF"""
        try:
            filename = f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = EXPORT_DIR / filename
            
            logger.info(f"Staticizing {len(slides_html)} slides for PDF export...")
            slides_html = await batch_staticize_html(slides_html, timeout=30)
            logger.info("All slides staticized")
            
            pdf_html = self._merge_slides_html(slides_html)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                page = await browser.new_page()
                await page.set_content(pdf_html, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(3000)
                
                await page.pdf(
                    path=str(filepath),
                    width=f"{self.slide_width}px",
                    height=f"{self.slide_height}px",
                    print_background=True,
                    display_header_footer=False,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
                )
                
                await browser.close()
            
            logger.info(f"PDF exported: {filepath}")
            return str(filepath), filename
            
        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            raise
    
    async def export_to_png(
        self,
        slides_html: List[str],
        title: str = "presentation",
        image_format: str = "png"
    ) -> Tuple[str, str]:
        """Export slides to images (ZIP)"""
        try:
            logger.info(f"Staticizing {len(slides_html)} slides for image export...")
            slides_html = await batch_staticize_html(slides_html, timeout=30)
            logger.info("All slides staticized")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"{title}_{timestamp}_images.zip"
            zip_filepath = EXPORT_DIR / zip_filename
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                page = await browser.new_page(
                    viewport={'width': self.slide_width, 'height': self.slide_height}
                )
                
                with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for i, slide_html in enumerate(slides_html):
                        await page.set_content(slide_html)
                        await page.wait_for_load_state('networkidle')
                        await asyncio.sleep(0.5)
                        
                        await page.evaluate('''
                            () => {
                                return Promise.all(
                                    Array.from(document.images)
                                        .filter(img => !img.complete)
                                        .map(img => new Promise(resolve => {
                                            img.onload = img.onerror = resolve;
                                        }))
                                );
                            }
                        ''')
                        
                        screenshot = await page.screenshot(type=image_format, full_page=False)
                        
                        image_filename = f"slide_{i+1:02d}.{image_format}"
                        zipf.writestr(image_filename, screenshot)
                        
                        logger.info(f"Screenshot captured: {image_filename}")
                
                await browser.close()
            
            logger.info(f"Images exported: {zip_filepath}")
            return str(zip_filepath), zip_filename
            
        except Exception as e:
            logger.error(f"Failed to export images: {e}")
            raise
    
    async def export_to_html(
        self,
        slides_html: List[str],
        title: str = "presentation"
    ) -> Tuple[str, str]:
        """Export slides to standalone HTML file"""
        import html as html_module
        
        try:
            filename = f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filepath = EXPORT_DIR / filename
            
            slides_content = []
            for i, slide_html in enumerate(slides_html):
                full_slide_html = self._ensure_slide_dependencies(slide_html)
                escaped_html = html_module.escape(full_slide_html)
                
                slides_content.append(f'''
                    <div class="slide-wrapper" id="slide-{i+1}">
                        <iframe 
                            srcdoc="{escaped_html}"
                            class="slide-frame"
                            frameborder="0"
                            scrolling="no"
                            sandbox="allow-scripts allow-same-origin"
                        ></iframe>
                        <div class="slide-number">{i+1} / {len(slides_html)}</div>
                    </div>
                ''')
            
            full_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 演示文稿</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Microsoft YaHei', sans-serif;
            background-color: #1a1a2e;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 30px;
        }}
        .slide-wrapper {{
            position: relative;
            width: {self.slide_width}px;
            height: {self.slide_height}px;
            background: white;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            overflow: hidden;
            flex-shrink: 0;
        }}
        .slide-frame {{
            width: 100%;
            height: 100%;
            border: none;
            display: block;
        }}
        .slide-number {{
            position: absolute;
            bottom: 10px;
            right: 20px;
            background: rgba(0, 0, 0, 0.6);
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        .slide-wrapper:hover .slide-number {{
            opacity: 1;
        }}
    </style>
</head>
<body>
    {''.join(slides_content)}
</body>
</html>'''
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_html)
            
            logger.info(f"HTML exported: {filepath}")
            return str(filepath), filename
            
        except Exception as e:
            logger.error(f"Failed to export HTML: {e}")
            raise
    
    def _ensure_slide_dependencies(self, slide_html: str) -> str:
        """Ensure slide HTML includes necessary dependencies"""
        if '<head>' in slide_html.lower():
            deps = '''
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
'''
            return slide_html.replace('</head>', deps + '</head>')
        else:
            body = self._extract_body_content(slide_html)
            style = self._extract_style_content(slide_html)
            
            return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
        }}
        {style}
    </style>
</head>
<body>
    {body}
</body>
</html>'''
    
    async def export_to_pptx(
        self,
        slides_html: List[str],
        title: str = "presentation",
        options: PptxOptions = None
    ) -> Tuple[str, str]:
        """Export slides to PPTX using dom-to-pptx"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            requested_filename = options.fileName if options and options.fileName else ""
            pptx_filename = requested_filename or f"{title}_{timestamp}.pptx"
            safe_filename = Path(pptx_filename).name or f"{title}_{timestamp}.pptx"
            pptx_filepath = EXPORT_DIR / safe_filename
            
            logger.info(f"Generating PPTX via dom-to-pptx for {len(slides_html)} slides...")
            
            logger.info("Staticizing slides for PPTX export...")
            slides_html = await batch_staticize_html(slides_html, timeout=30)
            
            pptx_html, pptx_css = self._merge_slides_for_pptx(slides_html)
            
            if options:
                pptx_options = options.copy()
                pptx_options.fileName = safe_filename
            else:
                pptx_options = PptxOptions(fileName=safe_filename)
            
            request = HtmlToPptxRequest(
                html=pptx_html,
                css=pptx_css,
                options=pptx_options
            )
            
            temp_path, _ = await generate_pptx_from_html(request)
            temp_path = Path(temp_path)
            
            if temp_path != pptx_filepath:
                pptx_filepath.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(pptx_filepath))
            
            # Verify file
            if not pptx_filepath.exists():
                raise Exception(f"PPTX file not generated: {pptx_filepath}")
            
            file_size = pptx_filepath.stat().st_size
            if file_size < 1000:
                raise Exception(f"PPTX file may be corrupted, size: {file_size} bytes")
            
            logger.info(f"✅ PPTX exported successfully: {pptx_filepath} ({file_size:,} bytes)")
            return str(pptx_filepath), safe_filename
            
        except Exception as e:
            logger.error(f"❌ Failed to export PPTX: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise


# Singleton instance
export_service = ExportService()
