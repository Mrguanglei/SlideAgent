"""
Browser management utilities for Playwright
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Browser, Playwright, async_playwright
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class BrowserPool:
    """Simple browser pool manager"""
    
    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the browser pool"""
        if self._initialized:
            return
        
        logger.info("Initializing browser pool...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',  # Allow CORS for fonts
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        self._semaphore = asyncio.Semaphore(self.pool_size)
        self._initialized = True
        logger.info(f"Browser pool initialized with size {self.pool_size}")
    
    async def cleanup(self):
        """Cleanup browser resources"""
        if not self._initialized:
            return
        
        logger.info("Cleaning up browser pool...")
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        logger.info("Browser pool cleaned up")
    
    @asynccontextmanager
    async def get_page(self):
        """Get a new browser page (context manager)"""
        if not self._initialized:
            await self.initialize()
        
        async with self._semaphore:
            context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                device_scale_factor=2,  # Higher DPI for better quality
                ignore_https_errors=True,  # Ignore SSL errors for external resources
                java_script_enabled=True
            )
            page = await context.new_page()
            
            try:
                yield page
            finally:
                await page.close()
                await context.close()


# Global browser pool instance
_browser_pool: Optional[BrowserPool] = None


def get_browser_pool(pool_size: int = 3) -> BrowserPool:
    """Get or create the global browser pool"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(pool_size=pool_size)
    return _browser_pool


async def cleanup_browser_pool():
    """Cleanup the global browser pool"""
    global _browser_pool
    if _browser_pool:
        await _browser_pool.cleanup()
        _browser_pool = None
