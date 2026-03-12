import os
import re
import shutil
import uuid
from datetime import datetime
from enum import StrEnum
from hashlib import md5
from pathlib import Path
from typing import Any, Literal

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, Field

from deeppresenter.utils.constants import GLOBAL_ENV_LIST
from deeppresenter.utils.log import debug, warning


class MCPServer(BaseModel):
    """MCP server config model, matches each entry in mcp.json"""

    name: str
    description: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    header: dict[str, str] | None = None
    keep_tools: list[str] | None = None
    exclude_tools: list[str] | None = Field(default_factory=list)

    def _process_escape(self):
        """Process escape characters in args, url, env"""
        for proxy_env in GLOBAL_ENV_LIST:
            if proxy_env in os.environ:
                self.env[proxy_env] = os.environ[proxy_env]
                debug(
                    f"Global proxy detected at {self.name}, set {proxy_env} to {os.environ[proxy_env]}"
                )
        self.args = [self._process_text(arg) for arg in self.args]
        for k, v in self.env.items():
            # Process if the value contains env variable references (starts with $)
            if v.startswith("$"):
                self.env[k] = self._process_text(v)
        if self.url:
            self.url = self._process_text(self.url)

    def _process_text(self, text: str) -> dict:
        """Process environment variables in config"""
        match = re.findall(r"\$([A-Z][A-Z_]*[A-Z])", text)
        for m in match:
            if m in os.environ:
                text = text.replace(f"${m}", os.environ[m])
                debug(f"Escaping {m} to {os.environ[m]}")
            elif m in self.env:
                text = text.replace(f"${m}", self.env[m])
                debug(f"Escaping {m} to {self.env[m]}")
            else:
                raise ValueError(f"Environment variable {m} declared but not found")
        return text


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """Chat message model"""

    role: Role
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: None | str | list[dict]
    reasoning_content: None | str = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    # This attribute mark if function call failed to execute
    is_error: bool = False
    from_tool: Function | None = None
    tool_call_id: str | None = None
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None = None
    extra_info: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, _):
        if not isinstance(self.content, list):
            content = []
            if self.content is not None and self.content.strip():
                content.append({"type": "text", "text": self.content})
            self.content = content

        for block in self.content:
            if block["type"] == "text":
                block["text"] = block["text"].strip()

    @property
    def text(self):
        texts = []
        if isinstance(self.content, str) and self.content.strip():
            texts.append(self.content)
        elif isinstance(self.content, list) and len(self.content):
            for block in self.content:
                if block["type"] == "text":
                    texts.append(block["text"])
                elif block["type"] == "image_url":
                    texts.append("<image>")
        elif len(self.tool_calls or []):
            for t in self.tool_calls:
                texts.append(t.function.model_dump_json())

        texts.extend([t.function for t in self.tool_calls or []])
        if len(texts) == 0:
            return ""
        elif len(texts) == 1:
            return texts[0]
        else:
            return str(texts)

    @property
    def has_image(self) -> bool:
        for block in self.content:
            if block["type"] == "image_url":
                return True
        return False


class RoleConfig(BaseModel):
    """Role configuration model"""

    system: dict[str, str]
    instruction: str
    use_model: str
    include_tool_servers: list[str] | Literal["all"] = "all"
    exclude_tool_servers: list[str] = []
    include_tools: list[str] = []
    exclude_tools: list[str] = []


class Cost(BaseModel):
    prompt: int = 0
    completion: int = 0
    total: int = 0

    def __add__(self, other: CompletionUsage):
        self.prompt += other.prompt_tokens
        self.completion += other.completion_tokens
        self.total += other.total_tokens
        return self

    def __repr__(self):
        return f"{self.prompt / 1000:.1f}K prompt tokens and {self.completion / 1000:.1f}K completion tokens"


class ConvertType(StrEnum):
    DEEPPRESENTER = "deeppresenter"
    PPTAGENT = "pptagent"
    DESIGN = "design"
    SLIDE_DESIGN = "slide_design"  # HTML幻灯片生成
    # NANOBANANA = "nanobanana"


class PowerPointType(StrEnum):
    WIDE_SCREEN = "16:9 Widescreen"
    STANDARD_SCREEN = "4:3 Standard"
    POSTER = "A1 Poster (Single Page)"


class InputRequest(BaseModel):
    instruction: str
    attachments: list[str] = []
    num_pages: str | None = None
    template: str | None = None
    powerpoint_type: PowerPointType = PowerPointType.WIDE_SCREEN
    convert_type: ConvertType = ConvertType.DEEPPRESENTER
    extra_info: dict[str, Any] = {}

    def copy_to_workspace(self, workspace: Path):
        """Copy attachments to workspace"""
        if not self.attachments:
            return
        (workspace / "attachments").mkdir(parents=True, exist_ok=True)
        new_attachments = []
        for att in self.attachments:
            assert os.path.exists(att), f"Attachment {att} does not exist"
            dest_path = workspace / "attachments" / Path(att).name
            if dest_path.exists():
                warning(f"Attachment {att} already exists in workspace")
            shutil.copy(att, str(dest_path))
            new_attachments.append(str(dest_path))
        self.attachments = new_attachments

    @property
    def task_id(self):
        task = self.instruction + "".join(self.attachments)
        return md5(task.encode()).hexdigest()[:8]

    @property
    def deepresearch_prompt(self):
        prompt = [self.instruction]
        if self.num_pages is not None and self.num_pages not in self.instruction:
            prompt.append("Number of pages: " + self.num_pages)
        if self.attachments and not all(
            a in self.instruction for a in self.attachments
        ):
            prompt.append("Attachments: " + ", ".join(self.attachments))
        if (
            self.powerpoint_type is not None
            and self.powerpoint_type.value not in self.instruction
        ):
            prompt.append("PPT format: " + self.powerpoint_type.value)
        return "\n".join(prompt)

    @property
    def pptagent_prompt(self):
        prompt = [self.instruction]
        if self.template is not None and self.template not in self.instruction:
            prompt.append("PPT Template: " + self.template)
        if self.num_pages is not None and self.num_pages not in self.instruction:
            prompt.append("Number of pages: " + self.num_pages)
        return "\n".join(prompt)

    @property
    def webagent_prompt(self):
        prompt = [self.instruction]
        if (
            self.powerpoint_type is not None
            and self.powerpoint_type.value not in self.instruction
        ):
            prompt.append("PPT format: " + self.powerpoint_type.value)
        return "\n".join(prompt)

    @property
    def aspect_ratio(self):
        if self.powerpoint_type == PowerPointType.STANDARD_SCREEN:
            return "normal"
        elif self.powerpoint_type == PowerPointType.POSTER:
            return "A1"
        elif self.powerpoint_type == PowerPointType.WIDE_SCREEN:
            return "widescreen"
        else:
            raise ValueError("Unknow powerpoint type")
