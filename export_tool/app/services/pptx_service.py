"""
PPTX Generation Service using dom-to-pptx

This service handles the conversion of HTML slides to PPTX format using Playwright and dom-to-pptx library.
"""
import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
import tempfile

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.models.schemas import HtmlToPptxRequest, PptxOptions
from app.utils.browser import get_browser_pool
from app.utils.exceptions import PptxGenerationError

logger = logging.getLogger(__name__)

# Path to the converter HTML template
CONVERTER_HTML_PATH = Path(__file__).parent.parent.parent / "static" / "converter.html"


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
            # Load the converter page
            logger.info("Loading converter page...")
            converter_url = f"file://{CONVERTER_HTML_PATH.absolute()}"
            await page.goto(converter_url, wait_until="networkidle", timeout=30000)
            
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
            
            # Inject HTML content into the page with iframe extraction support
            logger.info("Injecting HTML content and extracting iframe slides...")
            await page.evaluate("""
                async (html) => {
                    const container = document.getElementById('slide-container');
                    if (!container) {
                        throw new Error('slide-container element not found');
                    }
                    
                    // First, inject the raw HTML
                    container.innerHTML = html;
                    
                    // Check if there are iframes with srcdoc (common in slide exports)
                    const iframes = container.querySelectorAll('iframe[srcdoc]');
                    
                    if (iframes.length > 0) {
                        console.log(`🔍 Found ${iframes.length} iframes with srcdoc, extracting slide content...`);
                        
                        // Store extracted slides
                        const extractedSlides = [];
                        
                        // Process each iframe
                        for (let i = 0; i < iframes.length; i++) {
                            const iframe = iframes[i];
                            const srcdoc = iframe.getAttribute('srcdoc');
                            
                            if (!srcdoc) {
                                console.warn(`⚠️ Iframe ${i} has no srcdoc attribute`);
                                continue;
                            }
                            
                            // Create a temporary container to parse the HTML
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = srcdoc;
                            
                            // Find the body content
                            const bodyMatch = srcdoc.match(/<body[^>]*>([\s\S]*)<\/body>/i);
                            const styleMatches = srcdoc.match(/<style[^>]*>([\s\S]*?)<\/style>/gi);
                            
                            if (bodyMatch) {
                                // Create a slide wrapper
                                const slideDiv = document.createElement('div');
                                slideDiv.className = 'ppt-slide';
                                slideDiv.style.cssText = 'width: 1280px; height: 720px; position: relative; overflow: hidden;';
                                
                                // Inject styles first
                                if (styleMatches) {
                                    styleMatches.forEach(styleTag => {
                                        slideDiv.innerHTML += styleTag;
                                    });
                                }
                                
                                // Inject body content
                                slideDiv.innerHTML += bodyMatch[1];
                                
                                extractedSlides.push(slideDiv);
                                console.log(`✅ Extracted slide ${i + 1}/${iframes.length}`);
                            } else {
                                console.warn(`⚠️ Could not extract body from iframe ${i}`);
                            }
                        }
                        
                        // Replace container content with extracted slides
                        if (extractedSlides.length > 0) {
                            container.innerHTML = '';
                            extractedSlides.forEach(slide => container.appendChild(slide));
                            console.log(`✅ Successfully extracted ${extractedSlides.length} slides from iframes`);
                        } else {
                            console.error('❌ Failed to extract any slides from iframes');
                        }
                    } else {
                        console.log('ℹ️ No iframes found, using HTML as-is');
                        
                        // If no iframes, ensure slides have .ppt-slide class
                        const potentialSlides = container.querySelectorAll('.slide-wrapper, [class*="slide"]');
                        if (potentialSlides.length > 0) {
                            potentialSlides.forEach(slide => {
                                if (!slide.classList.contains('ppt-slide')) {
                                    slide.classList.add('ppt-slide');
                                }
                            });
                            console.log(`✅ Added .ppt-slide class to ${potentialSlides.length} elements`);
                        }
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
            options = {
                "skipDownload": True,
                "autoEmbedFonts": request.options.autoEmbedFonts if request.options else False
            }
            
            if request.options and request.options.fonts:
                options["fonts"] = [
                    {"name": f.name, "url": f.url} 
                    for f in request.options.fonts
                ]
            
            if request.options and request.options.listConfig:
                options["listConfig"] = request.options.listConfig
            
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
                    async ({ autoEmbed }) => {
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
                        
                        const blob = await domToPptx.exportToPptx(slideArray, {
                            skipDownload: true,
                            autoEmbedFonts: autoEmbed
                        });
                        
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
                    {"autoEmbed": options["autoEmbedFonts"]}
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
