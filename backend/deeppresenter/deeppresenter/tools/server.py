from pathlib import Path

from .appcore import mcp

from deeppresenter.utils.log import info, warning

if __name__ == "__main__":
    import os
    import sys
    import logging

    from deeppresenter.utils.log import set_logger

    assert len(sys.argv) == 2, "Usage: python deeppresenter/tools/server.py <workspace>"
    work_dir = Path(sys.argv[1])
    assert work_dir.exists(), f"Workspace {work_dir} does not exist."
    os.chdir(sys.argv[1])
    set_logger(
        f"deeppresenter-mcp-{work_dir.stem}",
        work_dir / "history" / "deeppresenter-mcp.log",
    )

    import os
    from . import any2markdown  # noqa: F401
    from . import fetch  # noqa: F401
    from . import research  # noqa: F401
    from . import richfile  # noqa: F401
    from . import task  # noqa: F401
    from . import tool_agents  # noqa: F401
    from . import html_tools  # noqa: F401

    if os.getenv("TAVILY_API_KEY", None):
        from . import search  # noqa: F401

    # 静默 MCP/FastMCP 的启动日志
    for name in ("mcp", "mcp.server", "mcp.client", "fastmcp"):
        logging.getLogger(name).setLevel(logging.ERROR)

    # 仅保留调试级别提示，避免控制台噪音
    from deeppresenter.utils.log import debug
    debug(f"Starting MCP server with workspace: {work_dir}")

    mcp.run(show_banner=False)
