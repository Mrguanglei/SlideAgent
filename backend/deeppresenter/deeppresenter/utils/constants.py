"""deeppresenter 全局常量定义"""

import logging
import os
from pathlib import Path

from platformdirs import user_cache_dir

# ============ Path ============
PACKAGE_DIR = Path(__file__).parent.parent

# ============ Logging ===========
LOGGING_LEVEL = int(os.getenv("DEEPPRESENTER_LOG_LEVEL", logging.WARNING))
MAX_LOGGING_LENGTH = int(os.getenv("DEEPPRESENTER_MAX_LOGGING_LENGTH", 1024))

# ============ Agent  ============
RETRY_TIMES = int(os.getenv("RETRY_TIMES", 6))
MAX_RETRY_INTERVAL = int(os.getenv("MAX_RETRY_INTERVAL", 60))
# count in chars, this is about the first 4 page of a dual-column paper
TOOL_CUTOFF_LEN = int(os.getenv("TOOL_CUTOFF_LEN", 4192))
# count in tokens
CONTEXT_LENGTH_LIMIT = int(os.getenv("CONTEXT_LENGTH_LIMIT", 64_000))
CUTOFF_WARNING = "NOTE: Output truncated (showing {line} lines). Use `read_file` with `offset` parameter to continue reading from {resource_id}."
AGENT_PROMPT = """
<Environment>
Current time: {time}
Working directory: {workspace}
Platform: Debian Linux container

Pre-installed tools:
- Python 3.13, Node.js, imagemagic, mmdc, curl, wget, and other common utilities
- python-pptx, matplotlib, plotly, and other common packages
You can freely install any required tools, packages, or command-line utilities to complete the task
</Environment>

<Task Guidelines>
- Exploration Principle: A warning is issued at 10% remaining computation budget, Until then, explore thoroughly and give your best effort.
- Max Length: Tool Call Output exceeding {cutoff_len} characters will be truncated at the preceding line break. Full content is saved locally and accessible via `read_file` with `offset`.
- Response Format: Every response must include reasoning content and a valid tool call.
</Task Guidelines>
"""

# ============ Environment ============
PIXEL_MULTIPLE = int(os.getenv("PIXEL_MULTIPLE", 16))
MCP_CONNECT_TIMEOUT = int(os.getenv("MCP_CONNECT_TIMEOUT", 120))
MCP_CALL_TIMEOUT = int(os.getenv("MCP_CALL_TIMEOUT", 600))
WORKSPACE_BASE = Path(
    os.getenv("DEEPPRESENTER_WORKSPACE_BASE", user_cache_dir("deeppresenter"))
)
TOOL_CACHE = PACKAGE_DIR / ".tools.json"

GLOBAL_ENV_LIST = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "all_proxy",
]

# ============ Webview ============
PDF_OPTIONS = {
    "print_background": True,
    "landscape": False,
    "margin": {"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
    "prefer_css_page_size": False,
    "display_header_footer": False,
    "scale": 1,
    "page_ranges": "1",
}
