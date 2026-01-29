"""
API endpoints for unified export service
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import io

from app.models.schemas import ExportRequest, ErrorResponse, HealthResponse
from app.services.export_service import export_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        supported_formats=["pdf", "png", "html", "pptx"]
    )


@router.post(
    "/pdf",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF file generated successfully"
        },
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def export_to_pdf(request: ExportRequest):
    """
    Export slides to PDF format
    
    - **slides_html**: List of HTML slides to export
    - **title**: Presentation title (used for filename)
    - **options**: Export options
    
    Returns a PDF file as a binary stream.
    """
    try:
        logger.info(f"Received PDF export request for {len(request.slides_html)} slides")
        
        if not request.slides_html:
            raise HTTPException(status_code=400, detail="slides_html cannot be empty")
        
        filepath, filename = await export_service.export_to_pdf(
            request.slides_html,
            request.title or "presentation"
        )
        
        logger.info(f"Returning PDF file: {filename}")
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post(
    "/png",
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "PNG images (ZIP) generated successfully"
        },
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def export_to_png(request: ExportRequest):
    """
    Export slides to PNG images (ZIP archive)
    
    - **slides_html**: List of HTML slides to export
    - **title**: Presentation title (used for filename)
    - **options**: Export options (includes image_format)
    
    Returns a ZIP file containing PNG images.
    """
    try:
        logger.info(f"Received PNG export request for {len(request.slides_html)} slides")
        
        if not request.slides_html:
            raise HTTPException(status_code=400, detail="slides_html cannot be empty")
        
        image_format = "png"
        if request.options and request.options.image_format:
            image_format = request.options.image_format
        
        filepath, filename = await export_service.export_to_png(
            request.slides_html,
            request.title or "presentation",
            image_format
        )
        
        logger.info(f"Returning ZIP file: {filename}")
        return FileResponse(
            filepath,
            media_type="application/zip",
            filename=filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PNG export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post(
    "/html",
    responses={
        200: {
            "content": {"text/html": {}},
            "description": "HTML file generated successfully"
        },
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def export_to_html(request: ExportRequest):
    """
    Export slides to standalone HTML file
    
    - **slides_html**: List of HTML slides to export
    - **title**: Presentation title (used for filename)
    - **options**: Export options
    
    Returns a standalone HTML file.
    """
    try:
        logger.info(f"Received HTML export request for {len(request.slides_html)} slides")
        
        if not request.slides_html:
            raise HTTPException(status_code=400, detail="slides_html cannot be empty")
        
        filepath, filename = await export_service.export_to_html(
            request.slides_html,
            request.title or "presentation"
        )
        
        logger.info(f"Returning HTML file: {filename}")
        return FileResponse(
            filepath,
            media_type="text/html",
            filename=filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HTML export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post(
    "/pptx",
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.presentationml.presentation": {}},
            "description": "PPTX file generated successfully"
        },
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def export_to_pptx(request: ExportRequest):
    """
    Export slides to editable PowerPoint (PPTX) file
    
    - **slides_html**: List of HTML slides to export
    - **title**: Presentation title (used for filename)
    - **options**: Export options (includes pptx-specific options)
    
    Returns a PPTX file as a binary stream.
    """
    try:
        logger.info(f"Received PPTX export request for {len(request.slides_html)} slides")
        
        if not request.slides_html:
            raise HTTPException(status_code=400, detail="slides_html cannot be empty")
        
        pptx_options = None
        if request.options and request.options.pptx:
            pptx_options = request.options.pptx
        
        filepath, filename = await export_service.export_to_pptx(
            request.slides_html,
            request.title or "presentation",
            pptx_options
        )
        
        logger.info(f"Returning PPTX file: {filename}")
        return FileResponse(
            filepath,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PPTX export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
