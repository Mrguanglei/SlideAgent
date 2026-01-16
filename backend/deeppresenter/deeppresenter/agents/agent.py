import asyncio
import json
import re
from abc import abstractmethod
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Literal

import jsonlines
import yaml
from jinja2 import Template
from jinja2.runtime import StrictUndefined
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageFunctionToolCall as ToolCall,
)
from pydantic import BaseModel

from deeppresenter.agents.env import AgentEnv
from deeppresenter.utils.config import (
    LLM,
    DeepPresenterConfig,
    get_json_from_response,
)
from deeppresenter.utils.constants import (
    AGENT_PROMPT,
    CONTEXT_LENGTH_LIMIT,
    MAX_LOGGING_LENGTH,
    PACKAGE_DIR,
)
from deeppresenter.utils.log import (
    debug,
    info,
    timer,
    warning,
)
from deeppresenter.utils.typings import (
    ChatMessage,
    Cost,
    InputRequest,
    Role,
    RoleConfig,
)

HALF_NOTICE_MESSAGE = {
    "text": "<NOTICE>You have used about half of your working budget. Now focused on the core task and skipping unnecessary steps or explorations.</NOTICE>",
    "type": "text",
}
URGENT_NOTICE_MESSAGE = {
    "text": "<URGENT>Working budget nearly exhausted. You must finish the core task and call `finalize` now, or your work will fail. Skip extras like inspection and validation.</URGENT>",
    "type": "text",
}
REASON_TOOLS = ["inspect_slide", "inspect_manuscript", "thinking"]


class Agent:
    def __init__(
        self,
        config: DeepPresenterConfig,
        agent_env: AgentEnv,
        workspace: Path,
        language: Literal["zh", "en"],
        allow_reflection: bool,
        config_file: str | None = None,
        keep_reasoning: bool = True,
        context_window: int = CONTEXT_LENGTH_LIMIT,
    ):
        self.name = self.__class__.__name__
        self.cost = Cost()
        self.context_length = 0
        self.context_warning = 0
        self.workspace = workspace
        self.agent_env = agent_env
        self.language = language
        self.keep_reasoning = keep_reasoning
        self.context_window = context_window
        config_file = (
            Path(config_file)
            if config_file
            else PACKAGE_DIR / "roles" / f"{self.name}.yaml"
        )
        if not config_file.exists():
            raise FileNotFoundError(f"Cannot found role config file at: {config_file} ")

        with open(config_file, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        role_config = RoleConfig(**config_data)
        self.llm: LLM = config[role_config.use_model]
        self.model = self.llm.model
        self.prompt: Template = Template(
            role_config.instruction, undefined=StrictUndefined
        )

        if role_config.include_tool_servers == "all":
            role_config.include_tool_servers = list(agent_env._server_tools)
        for server in (
            role_config.include_tool_servers + role_config.exclude_tool_servers
        ):
            assert server in agent_env._server_tools, (
                f"Server {server} is not available"
            )
        for tool in role_config.include_tools + role_config.exclude_tools:
            assert tool in agent_env._tools_dict, f"Tool {tool} is not available"
        self.tools = []
        for server in role_config.include_tool_servers:
            if server not in role_config.exclude_tool_servers:
                for tool in agent_env._server_tools[server]:
                    if tool not in role_config.exclude_tools:
                        self.tools.append(agent_env._tools_dict[tool])
        for tool_name, tool in agent_env._tools_dict.items():
            if tool_name in role_config.include_tools:
                self.tools.append(tool)
        if language not in role_config.system:
            raise ValueError(f"Language '{language}' not found in system prompts")
        self.system = role_config.system[language]
        if not allow_reflection:
            self.system = re.sub(
                r"<REFLECTION>.*?</REFLECTION>", "", self.system, flags=re.DOTALL
            )
            self.tools = [
                t
                for t in self.tools
                if not t["function"]["name"].startswith(("think", "inspect"))
            ]

        # ? for those agents equipped with sandbox only
        if any(t["function"]["name"] == "execute_command" for t in self.tools):
            self.system += AGENT_PROMPT.format(
                workspace=self.workspace,
                cutoff_len=self.agent_env.cutoff_len,
                time=datetime.now().strftime("%Y-%m-%d"),
            )

        self.chat_history: list[ChatMessage] = [
            ChatMessage(role=Role.SYSTEM, content=self.system)
        ]
        info(f"{self.name} Agent got {len(self.tools)} tools")
        available_tools = [tool["function"]["name"] for tool in self.tools]
        debug(f"Available tools: {', '.join(available_tools)}")

    async def chat(
        self,
        message: ChatMessage,
        response_format: type[BaseModel] | None = None,
        **chat_kwargs,
    ) -> ChatMessage:
        if len(self.chat_history) == 1:
            self.chat_history.append(
                ChatMessage(role=Role.USER, content=self.prompt.render(**chat_kwargs))
            )
            self.log_message(self.chat_history[-1])
        self.chat_history.append(message)
        self.log_message(self.chat_history[-1])
        with timer(f"{self.name} Agent LLM chat"):
            response = await self.llm.run(
                messages=self.chat_history,
                response_format=response_format,
            )
            if response.usage is not None:
                self.cost += response.usage
                self.context_length = response.usage.total_tokens
            self.chat_history.append(
                ChatMessage(
                    role=response.choices[0].message.role,
                    content=response.choices[0].message.content,
                    reasoning_content=getattr(
                        response.choices[0].message, "reasoning_content", None
                    ),
                )
            )
            self.log_message(self.chat_history[-1])
            return self.chat_history[-1]

    async def action(
        self,
        **chat_kwargs,
    ):
        """Tool calling interface"""

        if len(self.chat_history) == 1:
            self.chat_history.append(
                ChatMessage(
                    role=Role.USER,
                    content=self.prompt.render(**chat_kwargs),
                )
            )
            self.log_message(self.chat_history[-1])

        with timer(f"{self.name} Agent LLM call"):
            response = await self.llm.run(
                messages=self.chat_history,
                tools=self.tools,
            )
            if response.usage is not None:
                self.cost += response.usage
                self.context_length = response.usage.total_tokens
            agent_message: ChatCompletionMessage = response.choices[0].message
        if self.keep_reasoning and hasattr(agent_message, "reasoning_content"):
            reasoning = agent_message.reasoning_content
        else:
            reasoning = None
        self.chat_history.append(
            ChatMessage(
                role=agent_message.role,
                content=agent_message.content,
                tool_calls=agent_message.tool_calls,
                reasoning_content=reasoning,
            )
        )
        self.log_message(self.chat_history[-1])
        return self.chat_history[-1]

    @abstractmethod
    async def loop(
        self, req: InputRequest, *args, **kwargs
    ) -> AsyncGenerator[str | ChatMessage, None]:
        """
        Loop interface, return the message or the outcome filepath of the agent.
        """

    @abstractmethod
    async def finish(self, result: str):
        """This function defines when and how should an agent finish their tasks, combined with outcome check"""

    async def execute(self, tool_calls: list[ToolCall]) -> str | list[ChatMessage]:
        coros = []
        observations: list[ChatMessage] = []
        used_tools = set()
        finish_id = None
        outcome = None
        for t in tool_calls:
            arguments = t.function.arguments
            if len(arguments) == 0:
                arguments = None
            else:
                try:
                    arguments = get_json_from_response(t.function.arguments)
                    if t.function.name == "finalize":
                        arguments["agent_name"] = self.name
                        finish_id = t.id
                        # 尝试从参数中获取outcome，如果没有则稍后从工具返回结果中提取
                        outcome = arguments.get("outcome")
                    elif t.function.name in REASON_TOOLS:
                        assert len(tool_calls) == 1, (
                            "When using reasoning tools, only one tool call is allowed"
                        )
                    assert isinstance(arguments, dict), (
                        f"Tool call arguments must be a dict or empty, while {arguments} is given"
                    )
                    t.function.arguments = json.dumps(arguments, ensure_ascii=False)
                except AssertionError as e:
                    observations.append(
                        ChatMessage(
                            role=Role.TOOL,
                            content=str(e),
                            tool_call_id=t.id,
                        )
                    )
                    warning(f"Tool call `{t.function}` encountered error: {e}")
                    continue
            used_tools.add(t.function.name)
            coros.append(self.agent_env.tool_execute(t))

        observations.extend(await asyncio.gather(*coros))
        for obs in observations:
            if obs.has_image:
                if "gemini" in self.llm.model.lower():
                    obs.role = Role.USER
                if "claude" in self.llm.model.lower():
                    oai_b64 = obs.content[0]["image_url"]["url"]
                    obs.content = [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": oai_b64.split(";")[0].split(":")[1],
                                "data": oai_b64.split(",")[1],
                            },
                        }
                    ]

        self.chat_history.extend(observations)

        if finish_id is not None:
            for obs in observations:
                if obs.tool_call_id == finish_id:
                    # 如果outcome为None，尝试从工具返回结果中提取
                    if outcome is None:
                        try:
                            result = json.loads(obs.text) if isinstance(obs.text, str) else obs.text
                            if isinstance(result, dict) and "outcome" in result:
                                outcome = result["outcome"]
                            elif isinstance(result, dict) and "workspace" in result:
                                # 如果没有outcome字段，使用workspace字段
                                outcome = result["workspace"]
                        except:
                            pass

                    # 如果找到了outcome，返回它；否则返回整个返回值
                    if outcome and obs.text == outcome:
                        info(f"{self.name} Agent finished with result: {obs.text}")
                        return obs.text
                    elif outcome:
                        info(f"{self.name} Agent finished with result: {outcome}")
                        return outcome
                    else:
                        info(f"{self.name} Agent finished with result: {obs.text}")
                        return obs.text

        if (
            self.context_warning == 0
            and self.context_length > self.context_window * 0.5
        ):
            self.context_warning += 1
            observations[0].content.insert(0, HALF_NOTICE_MESSAGE)
        elif (
            self.context_warning == 1
            and self.context_length > self.context_window * 0.8
        ):
            observations[0].content.insert(0, URGENT_NOTICE_MESSAGE)
            self.context_warning = 2

        for obs in observations:
            self.log_message(obs)

        if self.context_length > self.context_window:
            raise RuntimeError(
                f"{self.name} agent exceeded context window: {self.context_length}/{self.context_window}"
            )

        return observations

    def log_message(self, msg: ChatMessage):
        if len(msg.text) < MAX_LOGGING_LENGTH:
            info(f"{self.name}: {msg.text}")
        else:
            info(f"{self.name}: {msg.text[:MAX_LOGGING_LENGTH]}...")

    def save_history(self, dir: Path | None = None):
        dir = dir or self.workspace / "history"
        dir.mkdir(parents=True, exist_ok=True)

        history_file = dir / f"{self.name}-history.jsonl"
        with jsonlines.open(history_file, mode="w") as writer:
            for message in self.chat_history:
                writer.write(message.model_dump())

        config_file = dir / f"{self.name}-config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": self.name,
                    "model": self.model,
                    "context_window": self.context_length,
                    "cost": self.cost.model_dump(),
                    "tools": self.tools,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        error_history = []
        for idx, msg in enumerate(self.chat_history):
            if msg.is_error:
                error_history.append(self.chat_history[idx - 1 : idx + 2])

        if error_history:
            error_file = dir / f"{self.name}-errors.jsonl"
            with jsonlines.open(error_file, mode="w") as writer:
                for context in error_history:
                    writer.write([msg.model_dump() for msg in context])

        info(
            f"{self.name} done | cost:{self.cost} ctx:{self.context_length} | history:{history_file.name} config:{config_file.name}"
        )
