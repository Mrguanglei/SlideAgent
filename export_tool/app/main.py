"""
FastAPI application entry point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import router
from app.utils.browser import cleanup_browser_pool, get_browser_pool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting HTML to PPTX API service...")
    
    # Initialize browser pool
    browser_pool = get_browser_pool(pool_size=3)
    await browser_pool.initialize()
    logger.info("Browser pool initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down HTML to PPTX API service...")
    await cleanup_browser_pool()
    logger.info("Browser pool cleaned up")


# Create FastAPI application
app = FastAPI(
    title="Export Tool API",
    description="Unified export service for PDF, PNG, HTML, and PPTX formats",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files mount removed (Pure Python NBLM)

# Include API router with new prefix
app.include_router(router, prefix="/api/export_tool")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Export Tool API Service",
        "version": "2.0.0",
        "supported_formats": ["pdf", "png", "html", "pptx"],
        "docs": "/docs"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
