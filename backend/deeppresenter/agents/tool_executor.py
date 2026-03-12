import asyncio
import inspect
import json
import uuid
from collections import defaultdict
from pathlib import Path

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageFunctionToolCall as ToolCall,
)

from deeppresenter.utils.config import GLOBAL_CONFIG, DeepPresenterConfig
from deeppresenter.utils.constants import (
    CUTOFF_WARNING,
    TOOL_CUTOFF_LEN,
)
from deeppresenter.utils.log import (
    debug,
    info,
    timer,
    warning,
)
from deeppresenter.utils.typings import ChatMessage, Role


class AgentEnv:
    def __init__(
        self,
        workspace: Path,
        config: DeepPresenterConfig = GLOBAL_CONFIG,
        cutoff_len: int = TOOL_CUTOFF_LEN,
    ):
        if isinstance(workspace, str):
            workspace = Path(workspace)
        self.workspace = workspace.absolute()
        self.cutoff_len = cutoff_len

        self._tools_dict: dict[str, dict] = {}
        self._server_tools = defaultdict(list)
        self._tool_to_server = {}
        self._tool_callables: dict[str, callable] = {}
        self.tool_history: list[tuple[ToolCall, ChatMessage]] = []
        self.tool_history_file = self.workspace / "history" / "tool_history.jsonl"

    def _register_tools(self):
        """注册工具（直接 Python 调用，无需 MCP）"""
        from deeppresenter.tools.html_tools import (
            TOOL_REGISTRY as HTML_REGISTRY,
            TOOL_SCHEMAS as HTML_SCHEMAS,
            set_workspace,
        )
        from deeppresenter.tools.richfile import (
            TOOL_REGISTRY as RICH_REGISTRY,
            TOOL_SCHEMAS as RICH_SCHEMAS,
        )

        # 设置工作目录
        set_workspace(str(self.workspace))

        server_name = "deeppresenter"
        all_schemas = HTML_SCHEMAS + RICH_SCHEMAS
        all_registry = {**HTML_REGISTRY, **RICH_REGISTRY}

        # 如果配置了 Tavily，注册搜索工具
        import os
        if os.getenv("TAVILY_API_KEY"):
            from deeppresenter.tools.search import (
                TOOL_REGISTRY as SEARCH_REGISTRY,
                TOOL_SCHEMAS as SEARCH_SCHEMAS,
            )
            all_schemas = all_schemas + SEARCH_SCHEMAS
            all_registry = {**all_registry, **SEARCH_REGISTRY}

        for schema in all_schemas:
            tool_name = schema["function"]["name"]
            self._tools_dict[tool_name] = schema
            self._server_tools[server_name].append(tool_name)
            self._tool_to_server[tool_name] = server_name
            self._tool_callables[tool_name] = all_registry[tool_name]

        info(f"Registered {len(all_schemas)} tools directly (no MCP)")

    async def tool_execute(self, tool_call: ToolCall) -> ChatMessage:
        tool_name = tool_call.function.name
        try:
            arguments = {}
            if tool_call.function.arguments:
                arguments = json.loads(tool_call.function.arguments)

            if tool_name not in self._tool_callables:
                raise KeyError(f"Tool `{tool_name}` not found.")

            with timer(f"Tool `{tool_name}` execution"):
                fn = self._tool_callables[tool_name]
                if inspect.iscoroutinefunction(fn):
                    result = await (fn(**arguments) if arguments else fn())
                else:
                    result = fn(**arguments) if arguments else fn()

            # 序列化结果
            if isinstance(result, (dict, list)):
                result_text = json.dumps(result, ensure_ascii=False)
            else:
                result_text = str(result)

            is_error = isinstance(result, dict) and "error" in result
            if is_error:
                warning(f"Tool `{tool_name}` returned error: {result_text}")

        except KeyError as e:
            result_text = str(e)
            is_error = True
        except Exception as e:
            result_text = f"Tool `{tool_name}` execution failed: {e}"
            is_error = True
            warning(result_text)

        # 截断过长输出
        if len(result_text) > self.cutoff_len:
            truncated = result_text[: self.cutoff_len]
            truncated = truncated[: truncated.rfind("\n")] if "\n" in truncated else truncated
            hash_id = uuid.uuid4().hex[:4]
            local_file = self.workspace / f"{tool_name}_{hash_id}.txt"
            local_file.write_text(result_text)
            truncated += CUTOFF_WARNING.format(
                line=truncated.count("\n") + 1, resource_id=str(local_file)
            )
            result_text = truncated

        content = [{"type": "text", "text": result_text}]
        msg = ChatMessage(
            role=Role.TOOL,
            content=content,
            from_tool=tool_call.function,
            tool_call_id=tool_call.id,
            is_error=is_error,
        )
        self.tool_history.append((tool_call, msg))
        return msg

    async def __aenter__(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._register_tools()

        debug(f"AgentEnv ready, tools: {', '.join(self._tools_dict.keys())}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.tool_history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tool_history_file, "a", encoding="utf-8") as f:
            for tool_call, msg in self.tool_history:
                f.write(
                    json.dumps([tool_call.model_dump(), msg.text], ensure_ascii=False) + "\n"
                )
        debug(f"AgentEnv exited, history saved to: {self.tool_history_file}")

    def get_server_tools(self, server_id: str):
        return [self._tools_dict[t] for t in self._server_tools[server_id]]
