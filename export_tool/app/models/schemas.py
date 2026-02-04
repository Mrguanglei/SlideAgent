"""
Unified export request/response schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FontConfig(BaseModel):
    """Font configuration for embedding"""
    name: str = Field(..., description="Font family name, e.g., 'Roboto'")
    url: str = Field(..., description="URL to the font file (TTF, WOFF, or OTF)")


class PptxOptions(BaseModel):
    """Options for PPTX generation"""
    fileName: Optional[str] = Field(default="output.pptx", description="Output file name")
    autoEmbedFonts: Optional[bool] = Field(default=True, description="Automatically detect and embed fonts")
    fonts: Optional[List[FontConfig]] = Field(default=None, description="Manual font configurations")
    listConfig: Optional[Dict[str, Any]] = Field(default=None, description="List styling configuration")
    iconMode: Optional[str] = Field(
        default=None,
        description="Icon render mode: 'image' or 'text'"
    )
    iconBaseUrl: Optional[str] = Field(
        default=None,
        description="Base URL for icon images (used with iconPathTemplate)"
    )
    iconExt: Optional[str] = Field(
        default=None,
        description="Icon file extension (used with iconBaseUrl)"
    )
    iconPathTemplate: Optional[str] = Field(
        default=None,
        description="Icon URL template, supports {base} {name} {ext}"
    )
    textBoxExpandPx: Optional[float] = Field(
        default=None,
        description="Extra width in px added to text boxes to avoid last-character wrapping"
    )
    textBoxExpandMode: Optional[str] = Field(
        default=None,
        description="Text box expand mode: 'auto' or 'fixed'"
    )
    textBoxExpandCjkFactor: Optional[float] = Field(
        default=None,
        description="Auto-expand factor for CJK text (multiplier of font size in px)"
    )
    textBoxExpandLatinFactor: Optional[float] = Field(
        default=None,
        description="Auto-expand factor for Latin text (multiplier of font size in px)"
    )


class ExportOptions(BaseModel):
    """Common options for all export formats"""
    # PPTX specific options
    pptx: Optional[PptxOptions] = Field(default=None, description="PPTX-specific options")
    
    # PDF specific options
    wait_time: Optional[int] = Field(default=3000, description="Wait time for rendering (ms)")
    
    # PNG specific options
    image_format: Optional[str] = Field(default="png", description="Image format: png or jpg")


class ExportRequest(BaseModel):
    """Unified request model for all export formats"""
    slides_html: List[str] = Field(..., description="List of HTML slides to export", min_length=1)
    title: Optional[str] = Field(default="presentation", description="Presentation title for filename")
    options: Optional[ExportOptions] = Field(default_factory=ExportOptions, description="Format-specific options")
    
    class Config:
        json_schema_extra = {
            "example": {
                "slides_html": [
                    "<div style='width:1280px;height:720px;background:#667eea'><h1>Slide 1</h1></div>",
                    "<div style='width:1280px;height:720px;background:#f093fb'><h1>Slide 2</h1></div>"
                ],
                "title": "my_presentation",
                "options": {
                    "pptx": {
                        "fileName": "presentation.pptx",
                        "autoEmbedFonts": True
                    }
                }
            }
        }


class HtmlToPptxRequest(BaseModel):
    """Legacy request model for HTML to PPTX conversion (for backward compatibility)"""
    html: str = Field(..., description="HTML content to convert", min_length=1)
    css: Optional[str] = Field(default="", description="Additional CSS styles")
    options: Optional[PptxOptions] = Field(default_factory=PptxOptions, description="Conversion options")
    
    class Config:
        json_schema_extra = {
            "example": {
                "html": "<div style='width:1920px;height:1080px;background:#667eea'><h1>Hello World</h1></div>",
                "css": ".slide { font-family: 'Roboto', sans-serif; }",
                "options": {
                    "fileName": "presentation.pptx",
                    "autoEmbedFonts": True
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(default="healthy")
    version: str = Field(default="2.0.0")
    supported_formats: List[str] = Field(default=["pdf", "png", "html", "pptx"])
