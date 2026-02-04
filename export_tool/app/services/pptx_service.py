"""
PPTX Generation Service using dom-to-pptx

This service handles the conversion of HTML slides to PPTX format using Playwright and dom-to-pptx library.
"""
import asyncio
import base64
import json
import logging
import os
from typing import Tuple
from pathlib import Path
import tempfile

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.models.schemas import HtmlToPptxRequest
from app.utils.browser import get_browser_pool
from app.utils.exceptions import PptxGenerationError
from app.utils.icon_assets import get_material_symbols_base_url
from app.utils.font_assets import resolve_font_configs

logger = logging.getLogger(__name__)

def _get_dom_to_pptx_bundle_location() -> str:
    env_url = os.getenv("DOM_TO_PPTX_BUNDLE_URL")
    if env_url:
        return env_url

    env_path = os.getenv("DOM_TO_PPTX_BUNDLE_PATH")
    if env_path:
        return env_path

    default_path = Path(__file__).resolve().parents[2] / "dom-to-pptx" / "dist" / "dom-to-pptx.bundle.js"
    return str(default_path)


def _build_converter_html() -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>dom-to-pptx runtime</title>
  </head>
  <body>
    <div id="slide-container"></div>
  </body>
</html>"""


async def generate_pptx_from_html(
    request: HtmlToPptxRequest,
    timeout: int = 60  # Increased timeout for complex slides
) -> Tuple[str, str]:
    """
    Generate PPTX from HTML using dom-to-pptx library via Playwright
    
    Args:
        request: HtmlToPptxRequest containing HTML, CSS, and options
        timeout: Timeout in seconds for PPTX generation
        
    Returns:
        Tuple of (file_path, filename)
        
    Raises:
        PptxGenerationError: If PPTX generation fails
    """
    browser_pool = get_browser_pool()
    
    # Capture console logs for debugging
    console_logs = []
    
    async with browser_pool.get_page() as page:
        # Set up console log capture
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[ERROR] {err}"))
        
        try:
            # Load converter shell
            bundle_location = _get_dom_to_pptx_bundle_location()
            logger.info(f"Loading dom-to-pptx bundle: {bundle_location}")
            await page.set_content(
                _build_converter_html(),
                wait_until="load",
                timeout=30000
            )

            if bundle_location.startswith("http://") or bundle_location.startswith("https://") or bundle_location.startswith("file://"):
                await page.add_script_tag(url=bundle_location)
            else:
                bundle_path = Path(bundle_location).expanduser().resolve()
                if not bundle_path.exists():
                    raise PptxGenerationError(
                        f"dom-to-pptx bundle not found: {bundle_path}. "
                        "Run `pnpm install && pnpm build` in export_tool/dom-to-pptx "
                        "or set DOM_TO_PPTX_BUNDLE_URL."
                    )
                await page.add_script_tag(path=str(bundle_path))
            
            # Wait for dom-to-pptx to be available
            logger.info("Waiting for dom-to-pptx library...")
            await page.wait_for_function(
                "typeof domToPptx !== 'undefined' && typeof domToPptx.exportToPptx === 'function'",
                timeout=10000
            )
            
            # Check dom-to-pptx version
            dom_info = await page.evaluate("""
                () => {
                    return {
                        loaded: typeof domToPptx !== 'undefined',
                        hasExport: typeof domToPptx?.exportToPptx === 'function',
                        version: domToPptx?.version || 'unknown'
                    };
                }
            """)
            logger.info(f"dom-to-pptx library loaded: {json.dumps(dom_info)}")
            
            if not dom_info.get('hasExport'):
                raise PptxGenerationError("dom-to-pptx.exportToPptx function not found")
            
            # Inject HTML content into the page
            logger.info("Injecting HTML content...")
            await page.evaluate("""
                (html) => {
                    const container = document.getElementById('slide-container');
                    if (!container) {
                        throw new Error('slide-container element not found');
                    }
                    container.innerHTML = html;
                    const slides = container.querySelectorAll('.ppt-slide');
                    if (!slides.length) {
                        Array.from(container.children).forEach((node) => {
                            if (node && node.classList) node.classList.add('ppt-slide');
                        });
                    }
                }
            """, request.html)
            
            # Wait for content to settle
            await page.wait_for_timeout(500)
            
            # Inject CSS if provided
            if request.css:
                logger.info("Injecting CSS styles...")
                await page.evaluate("""
                    (css) => {
                        const style = document.createElement('style');
                        style.textContent = css;
                        document.head.appendChild(style);
                    }
                """, request.css)
            
            # Inject global CSS to ensure text elements are on top layer in PPTX
            logger.info("Injecting text layer z-index fix...")
            await page.evaluate("""
                () => {
                    const textLayerStyle = document.createElement('style');
                    textLayerStyle.textContent = `
                        /* Auto-injected: Ensure text elements are on top layer for PPTX editing */
                        h1, h2, h3, h4, h5, h6, p, span, a, li, ul, ol, td, th,
                        div[class*="title"], div[class*="text"], div[class*="desc"],
                        div[class*="label"], div[class*="badge"] {
                            position: relative !important;
                            z-index: 999 !important;
                        }
                    `;
                    document.head.appendChild(textLayerStyle);
                }
            """)
            
            # Enhance styles for better PPTX preservation
            logger.info("Enhancing styles for PPTX compatibility...")
            await page.evaluate("""
                () => {
                    const styleEnhancement = document.createElement('style');
                    styleEnhancement.textContent = `
                        /* Auto-injected: Enhance style preservation in PPTX */
                        
                        /* Preserve gradients */
                        [style*="linear-gradient"], [style*="radial-gradient"] {
                            background-size: 100% 100% !important;
                        }
                        
                        /* Enhance shadows for better visibility */
                        [style*="box-shadow"] {
                            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
                        }
                        
                        /* Ensure border-radius is preserved */
                        [style*="border-radius"] {
                            -webkit-border-radius: inherit;
                            -moz-border-radius: inherit;
                        }
                        
                        /* Make table styles more robust */
                        table {
                            border-collapse: collapse !important;
                            width: 100% !important;
                        }
                        
                        table th {
                            font-weight: 700 !important;
                        }
                        
                        /* Ensure opacity values are preserved */
                        [style*="opacity"] {
                            -webkit-opacity: inherit;
                        }
                        
                        /* Fix for images */
                        img {
                            max-width: 100%;
                            height: auto;
                        }
                        
                        /* Optimized text wrapping strategy */
                        * {
                            /* Keep Chinese words intact, only break when necessary */
                            word-break: keep-all !important;
                            overflow-wrap: break-word !important;
                            white-space: normal !important;
                        }
                        
                        /* Specific fixes for text containers */
                        .item-text, .card-title, .card-content, .catalog-item, 
                        p, div, span, h1, h2, h3, h4, h5, h6 {
                            word-break: keep-all !important;
                            overflow-wrap: break-word !important;
                            white-space: normal !important;
                        }
                        
                        /* Allow breaking for very long words or URLs */
                        a, .url, .long-text {
                            word-break: break-all !important;
                        }
                        
                        /* Preserve pre and code blocks */
                        pre, code {
                            white-space: pre-wrap !important;
                            word-break: keep-all !important;
                            overflow-wrap: break-word !important;
                        }
                        
                        /* Fix text layer z-index and positioning */
                        .text-layer, .subtitle, .main-title, .page-title {
                            position: relative !important;
                            z-index: 10 !important;
                        }
                        
                        /* Ensure proper spacing and prevent overlap */
                        .subtitle {
                            margin-top: 20px !important;
                            clear: both !important;
                        }
                        
                        /* Fix flex and grid layouts */
                        .catalog-item, .card {
                            display: flex !important;
                            flex-wrap: wrap !important;
                            align-items: flex-start !important;
                        }
                    `;
                    document.head.appendChild(styleEnhancement);
                    console.log('✅ Style enhancements applied');
                }
            """)
            
            # Wait for images and resources to load
            logger.info("Waiting for resources to load...")
            await page.evaluate("""
                () => {
                    return Promise.all(
                        Array.from(document.images)
                            .filter(img => !img.complete)
                            .map(img => new Promise(resolve => {
                                img.onload = img.onerror = resolve;
                            }))
                    );
                }
            """)
            await asyncio.sleep(1)  # Additional wait for rendering
            
            # Build options object for dom-to-pptx
            auto_embed = request.options.autoEmbedFonts if request.options else False
            options = {
                "skipDownload": True,
                "autoEmbedFonts": auto_embed,
            }

            if request.options and request.options.fonts:
                options["fonts"] = [{"name": f.name, "url": f.url} for f in request.options.fonts]
            else:
                auto_fonts = resolve_font_configs(request.html, request.css or "")
                if auto_fonts:
                    options["fonts"] = auto_fonts

            if request.options and request.options.listConfig:
                options["listConfig"] = request.options.listConfig

            if request.options and request.options.iconMode:
                options["iconMode"] = request.options.iconMode
            if request.options and request.options.iconBaseUrl:
                options["iconBaseUrl"] = request.options.iconBaseUrl
            if request.options and request.options.iconExt:
                options["iconExt"] = request.options.iconExt
            if request.options and request.options.iconPathTemplate:
                options["iconPathTemplate"] = request.options.iconPathTemplate
            if request.options and request.options.textBoxExpandPx is not None:
                options["textBoxExpandPx"] = request.options.textBoxExpandPx
            if request.options and request.options.textBoxExpandMode:
                options["textBoxExpandMode"] = request.options.textBoxExpandMode
            if request.options and request.options.textBoxExpandCjkFactor is not None:
                options["textBoxExpandCjkFactor"] = request.options.textBoxExpandCjkFactor
            if request.options and request.options.textBoxExpandLatinFactor is not None:
                options["textBoxExpandLatinFactor"] = request.options.textBoxExpandLatinFactor

            # If explicit fonts provided, merge any auto-resolved ones not already set.
            if request.options and request.options.fonts:
                auto_fonts = resolve_font_configs(request.html, request.css or "")
                if auto_fonts:
                    existing = {f["name"] for f in options.get("fonts", [])}
                    for font in auto_fonts:
                        if font["name"] not in existing:
                            options.setdefault("fonts", []).append(font)

            # Inject @font-face rules to align browser layout with embedded fonts
            if options.get("fonts"):
                def _font_format(url: str) -> str:
                    lower = url.lower().split("?")[0].split("#")[0]
                    if lower.endswith(".otf"):
                        return "opentype"
                    if lower.endswith(".woff"):
                        return "woff"
                    return "truetype"

                def _font_weight(url: str) -> str:
                    lower = url.lower()
                    if "variable" in lower or "vf" in lower:
                        return "100 900"
                    return "400"

                font_faces = []
                for font in options["fonts"]:
                    name = font.get("name")
                    url = font.get("url")
                    if not name or not url:
                        continue
                    fmt = _font_format(url)
                    weight = _font_weight(url)
                    font_faces.append(
                        "@font-face { "
                        f"font-family: '{name}'; "
                        f"src: url('{url}') format('{fmt}'); "
                        f"font-weight: {weight}; "
                        "font-style: normal; "
                        "font-display: swap; "
                        "}"
                    )

                if font_faces:
                    await page.evaluate(
                        """
                        (css) => {
                            const style = document.createElement('style');
                            style.textContent = css;
                            document.head.appendChild(style);
                        }
                        """,
                        "\n".join(font_faces),
                    )

            # Default Material Icons/Symbols handling (SVG fallback)
            if "iconBaseUrl" not in options:
                haystack = f"{request.html}\n{request.css}".lower()
                if "material-icons" in haystack or "material-symbols" in haystack:
                    base_url = get_material_symbols_base_url()
                    if base_url:
                        options.setdefault("iconMode", "image")
                        options.setdefault("iconBaseUrl", base_url)
                        options.setdefault(
                            "iconPathTemplate",
                            "{base}/{name}/materialsymbolsoutlined/{name}_24px.svg",
                        )

            if "textBoxExpandMode" not in options:
                options["textBoxExpandMode"] = "auto"
            if "textBoxExpandPx" not in options:
                options["textBoxExpandPx"] = 1
            
            logger.info("Starting PPTX generation...")
            
            # Check slide detection
            slide_info = await page.evaluate("""
                () => {
                    const container = document.getElementById('slide-container');
                    if (!container) {
                        return { error: 'Container not found', count: 0 };
                    }
                    
                    const slides = container.querySelectorAll('.ppt-slide');
                    return {
                        count: slides.length,
                        containerChildren: container.children.length,
                        slides: Array.from(slides).map((s, i) => ({
                            index: i,
                            width: s.offsetWidth,
                            height: s.offsetHeight,
                            className: s.className,
                            hasContent: s.innerHTML.length > 100,
                            childCount: s.children.length
                        }))
                    };
                }
            """)
            logger.info(f"Slide detection result: {json.dumps(slide_info, indent=2)}")
            
            if slide_info.get('count', 0) == 0:
                logger.warning("No .ppt-slide elements found after extraction!")
                logger.info(f"Container has {slide_info.get('containerChildren', 0)} children")
            
            # Call dom-to-pptx with proper parameters
            try:
                # Set a longer timeout for the page
                page.set_default_timeout(timeout * 1000)
                
                pptx_blob = await page.evaluate(
                        """
                        async ({ exportOptions }) => {
                            const container = document.getElementById('slide-container');
                            if (!container) throw new Error('Container not found');
                            
                            const slides = container.querySelectorAll('.ppt-slide');
                            if (slides.length === 0) {
                                console.error('❌ No .ppt-slide elements found for conversion');
                                throw new Error('No slides found for conversion');
                            }
                            
                            console.log(`🚀 Converting ${slides.length} slides to PPTX...`);
                            
                            const slideArray = Array.from(slides);
                            console.log('Slide details:', slideArray.map((s, i) => ({
                                index: i,
                                width: s.offsetWidth,
                                height: s.offsetHeight,
                                hasContent: s.innerHTML.length > 100
                            })));
                            
                            const blob = await domToPptx.exportToPptx(slideArray, exportOptions);
                            
                            console.log('✅ PPTX blob generated, size:', blob.size);
                            
                            // Convert blob to base64
                            return new Promise((resolve, reject) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                reader.onerror = reject;
                                reader.readAsDataURL(blob);
                            });
                        }
                        """,
                        {"exportOptions": options}
                    )
            except PlaywrightTimeoutError:
                logger.error(f"PPTX generation timed out after {timeout} seconds")
                logger.error(f"Recent console logs: {console_logs[-10:]}")
                raise PptxGenerationError(f"PPTX generation timed out after {timeout} seconds")
            except Exception as e:
                logger.error(f"Error during PPTX generation: {e}")
                logger.error(f"Console logs: {console_logs[-10:]}")
                raise PptxGenerationError(f"Failed to generate PPTX: {str(e)}")
            
            # Decode base64 to bytes
            try:
                pptx_bytes = base64.b64decode(pptx_blob)
            except Exception as e:
                logger.error(f"Failed to decode PPTX blob: {e}")
                raise PptxGenerationError(f"Failed to decode PPTX data: {str(e)}")
            
            # Validate PPTX file (check for ZIP signature)
            if not pptx_bytes.startswith(b'PK\x03\x04'):
                logger.error("Generated file is not a valid PPTX (missing ZIP signature)")
                logger.error(f"First 20 bytes: {pptx_bytes[:20]}")
                raise PptxGenerationError("Generated file is not a valid PPTX format")
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pptx",
                prefix="presentation_"
            )
            temp_file.write(pptx_bytes)
            temp_file.close()
            
            filename = request.options.fileName if request.options and request.options.fileName else "presentation.pptx"
            
            logger.info(f"PPTX exported successfully: {temp_file.name} ({len(pptx_bytes)} bytes)")
            logger.info(f"Slide count: {slide_info.get('count', 0)}")
            
            return temp_file.name, filename
            
        except Exception as e:
            logger.error(f"Error generating PPTX: {e}")
            logger.error(f"Console logs: {console_logs}")
            raise PptxGenerationError(f"Failed to generate PPTX: {str(e)}")
