"""
Custom exceptions for export services
"""


class PptxGenerationError(Exception):
    """Exception raised when PPTX generation fails"""
    pass


class ExportError(Exception):
    """Base exception for export operations"""
    pass


class BrowserError(Exception):
    """Exception raised when browser operations fail"""
    pass
