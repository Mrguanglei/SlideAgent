import asyncio
import json
from itertools import product
from pathlib import Path
from typing import Any

import json_repair
import yaml
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from openai.types.images_response import ImagesResponse
from pydantic import BaseModel, Field, PrivateAttr, ValidationError

from deeppresenter.utils.constants import (
    PACKAGE_DIR,
    PIXEL_MULTIPLE,
    RETRY_TIMES,
)
from deeppresenter.utils.log import debug, logging_openai_exceptions


def get_json_from_response(response: str) -> dict | list:
    """
    Extract JSON from a text response.

    Args:
        response (str): The response text.

    Returns:
        Dict|List: The extracted JSON.

    Raises:
        Exception: If JSON cannot be extracted from the response.
    """

    assert isinstance(response, str) and len(response) > 0, (
        "response must be a non-empty string"
    )
    response = response.strip()
    try:
        return json.loads(response)
    except:
        pass

    # Try to find JSON by looking for matching braces
    open_braces = []
    close_braces = []

    for i, char in enumerate(response):
        if char == "{" or char == "[":
            open_braces.append(i)
        elif char == "}" or char == "]":
            close_braces.append(i)

    for i, j in product(open_braces, reversed(close_braces)):
        if i > j:
            continue
        try:
            json_obj = json.loads(response[i : j + 1])
            if isinstance(json_obj, (dict, list)):
                return max(
                    json_obj, json_repair.loads(response), key=lambda x: len(str(x))
                )
        except Exception:
            pass

    return json_repair.loads(response)


class LLM(BaseModel):
    """LLM Client Manager"""

    base_url: str = Field(description="API base URL")
    model: str = Field(description="Model name")
    api_key: str = Field(description="API key")
    identifier: str | None = Field(
        default=None,
        description="Optional identifier for the model instance, this will override property `model_name`",
    )
    is_multimodal: bool = Field(
        default=False, description="Whether the model is multimodal"
    )
    max_concurrent: int | None = Field(
        default=None, description="Maximum concurrency limit"
    )
    client_kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Client parameters"
    )
    sampling_parameters: dict[str, Any] = Field(
        default_factory=dict, description="Sampling parameters"
    )
    soft_response_parsing: bool = Field(
        default=False,
        description="Enable soft parsing: parse response content as JSON directly instead of using completion.parse",
    )
    min_image_size: int | None = Field(
        default=None,
        description="Minimum image size (width * height) for generation, smaller images will be resized proportionally",
    )

    # Fallback configuration
    fallback_base_url: str | None = Field(
        default=None, description="Fallback API base URL"
    )
    fallback_model: str | None = Field(default=None, description="Fallback model name")
    fallback_api_key: str | None = Field(default=None, description="Fallback API key")
    fallback_client_kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Fallback client parameters"
    )
    fallback_sampling_parameters: dict[str, Any] = Field(
        default_factory=dict, description="Fallback sampling parameters"
    )

    _semaphore: asyncio.Semaphore = PrivateAttr()
    _client: AsyncOpenAI = PrivateAttr()
    _fallback_client: AsyncOpenAI | None = PrivateAttr(default=None)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def model_name(self) -> str:
        return self.identifier or self.model.split("/")[-1].split(":")[0]

    @property
    def has_fallback(self) -> bool:
        """Check if fallback is configured"""
        return all(
            [
                self.fallback_base_url,
                self.fallback_model,
                self.fallback_api_key,
            ]
        )

    def model_post_init(self, _) -> None:
        """Initialize semaphore and clients"""
        self._semaphore = asyncio.Semaphore(self.max_concurrent or 10000)
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            **self.client_kwargs,
        )

        # 初始化 fallback client
        if self.has_fallback:
            self._fallback_client = AsyncOpenAI(
                api_key=self.fallback_api_key,
                base_url=self.fallback_base_url,
                **self.fallback_client_kwargs,
            )

        model_lower = self.model.lower()
        if not self.is_multimodal and any(
            word in model_lower for word in ("gpt", "claude", "gemini", "vl")
        ):
            self.is_multimodal = True
            debug(
                f"Model {self.model} is detected as multimodal model, setting `is_multimodal` to True"
            )

    def _prepare_messages(self, messages: list) -> list[dict[str, Any]]:
        """Convert ChatMessage objects to API-compatible dictionaries.
        
        This method handles the conversion of Pydantic ChatMessage objects to
        dictionaries that are compatible with the OpenAI/Zhipu API format.
        It specifically handles:
        - Empty content lists (which Zhipu API rejects)
        - Role enum conversion to strings
        - Tool calls serialization
        """
        prepared = []
        for msg in messages:
            if hasattr(msg, 'model_dump'):
                # It's a Pydantic model (ChatMessage)
                msg_dict = msg.model_dump(
                    exclude={'id', 'created_at', 'is_error', 'from_tool', 'extra_info', 'reasoning_content'}
                )
                
                # Handle content field - Zhipu API doesn't accept empty content
                content = msg_dict.get('content')
                if isinstance(content, list):
                    if len(content) == 0:
                        # Empty list - handle based on message type
                        if msg_dict.get('tool_calls'):
                            # For assistant messages with tool_calls, content can be None
                            msg_dict['content'] = None
                        else:
                            # For system/user messages, use a single space as placeholder
                            # This prevents the "messages[0].content is empty" error
                            msg_dict['content'] = " "
                    elif len(content) == 1 and content[0].get('type') == 'text':
                        # Single text block - convert to string for better compatibility
                        text_content = content[0].get('text', '')
                        msg_dict['content'] = text_content if text_content else " "
                    else:
                        # Multiple blocks or non-text content - keep as list but ensure non-empty
                        filtered_content = [b for b in content if b.get('type') == 'text' and b.get('text')]
                        if filtered_content:
                            msg_dict['content'] = filtered_content
                        else:
                            msg_dict['content'] = " "
                elif content is None or (isinstance(content, str) and not content.strip()):
                    # None or empty string
                    if msg_dict.get('tool_calls'):
                        msg_dict['content'] = None
                    else:
                        msg_dict['content'] = " "
                
                # Handle role enum - convert to string value
                role = msg_dict.get('role')
                if hasattr(role, 'value'):
                    msg_dict['role'] = role.value
                elif not isinstance(role, str):
                    msg_dict['role'] = str(role)
                
                # Handle tool_calls serialization
                if msg_dict.get('tool_calls'):
                    tool_calls = []
                    for tc in msg_dict['tool_calls']:
                        if hasattr(tc, 'model_dump'):
                            tool_calls.append(tc.model_dump())
                        elif isinstance(tc, dict):
                            tool_calls.append(tc)
                        else:
                            # Manual conversion for other types
                            tc_dict = {
                                'id': getattr(tc, 'id', ''),
                                'type': 'function',
                                'function': {
                                    'name': tc.function.name if hasattr(tc, 'function') else '',
                                    'arguments': tc.function.arguments if hasattr(tc, 'function') else '{}'
                                }
                            }
                            tool_calls.append(tc_dict)
                    msg_dict['tool_calls'] = tool_calls
                else:
                    # Remove tool_calls if None or empty
                    msg_dict.pop('tool_calls', None)
                
                # Remove tool_call_id if None
                if msg_dict.get('tool_call_id') is None:
                    msg_dict.pop('tool_call_id', None)
                
                prepared.append(msg_dict)
            elif isinstance(msg, dict):
                # Already a dict, but still validate content
                msg_copy = msg.copy()
                content = msg_copy.get('content')
                if content is None or content == '' or content == []:
                    if not msg_copy.get('tool_calls'):
                        msg_copy['content'] = " "
                prepared.append(msg_copy)
            else:
                # Unknown type, try to convert
                prepared.append({'role': 'user', 'content': str(msg)})
        
        return prepared

    async def _call(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict[str, Any]],
        sampling_params: dict[str, Any],
        response_format: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatCompletion:
        """Execute a chat or tool call using the specified client"""
        if tools is not None:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                **sampling_params,
            )
        elif not self.soft_response_parsing and response_format is not None:
            response: ChatCompletion = await client.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_format,
                **sampling_params,
            )
        else:
            response: ChatCompletion = await client.chat.completions.create(
                model=model,
                messages=messages,
                **sampling_params,
            )
        assert response.choices is not None and len(response.choices) > 0, (
            "No choices returned from the model"
        )
        message = response.choices[0].message
        if response_format is not None:
            message.content = response_format(
                **get_json_from_response(message.content)
            ).model_dump_json(indent=2)
        assert tools is None or len(message.tool_calls or []), (
            "No tool call returned from the model"
        )
        assert message.tool_calls or message.content, (
            "Empty content returned from the model"
        )
        return response

    async def run(
        self,
        messages: list[dict[str, Any]] | str,
        response_format: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
        retry_times: int = RETRY_TIMES,
    ) -> ChatCompletion:
        """Unified interface for chat and tool calls with alternating retry"""
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        else:
            # Prepare messages - convert ChatMessage objects to dicts
            # and ensure content fields are not empty (Zhipu API requirement)
            messages = self._prepare_messages(messages)

        clients = [(self._client, self.model, self.sampling_parameters)]
        if self._fallback_client is not None:
            clients.append(
                (
                    self._fallback_client,
                    self.fallback_model,
                    self.fallback_sampling_parameters,
                )
            )

        errors = []
        async with self._semaphore:
            for retry_idx in range(retry_times):
                client, model, sampling_params = clients[retry_idx % len(clients)]
                try:
                    return await self._call(
                        client, model, messages, sampling_params, response_format, tools
                    )
                except (AssertionError, ValidationError) as e:
                    errors.append(f"[{model}] {e}")
                except Exception as e:
                    errors.append(f"[{model}] {e}")
                    logging_openai_exceptions(model, e)
        raise ValueError(f"All models failed after {retry_times} retries:\n{errors}")

    async def generate_image(
        self,
        prompt: str,
        width: int,
        height: int,
        retry_times: int = RETRY_TIMES,
        pixel_multiple: int = PIXEL_MULTIPLE,
    ) -> ImagesResponse:
        """Unified interface for image generation"""
        if self.min_image_size is not None and (width * height) < int(
            self.min_image_size
        ):
            ratio = (int(self.min_image_size) / (width * height)) ** 0.5
            width = int(width * ratio)
            height = int(height * ratio)
        width = ((width + pixel_multiple - 1) // pixel_multiple) * pixel_multiple
        height = ((height + pixel_multiple - 1) // pixel_multiple) * pixel_multiple
        async with self._semaphore:
            errors = []
            for retry_idx in range(retry_times):
                await asyncio.sleep(retry_idx)
                try:
                    return await self._client.images.generate(
                        prompt=prompt,
                        model=self.model,
                        size=f"{width}x{height}",
                        **self.sampling_parameters,
                    )
                except Exception as e:
                    errors.append(e)
                    logging_openai_exceptions(self.model, e)
            raise ValueError(
                f"Model {self.model} failed after {retry_times} retries: {errors}"
            )

    async def validate(self):
        models = await self._client.models.list()
        # ? This for compatibility with google generative ai
        if not any(model.id.endswith(self.model) for model in models.data):
            raise Exception(
                f"Model {self.model} is not available at {self.base_url}, please check your apikey or {PACKAGE_DIR / 'config.yaml'}\n"
            )


class DeepPresenterConfig(BaseModel):
    """DeepPresenter Global Configuration"""

    file_path: str = Field(description="Configuration file path")
    mcp_config_file: str = Field(
        description="MCP configuration file", default=PACKAGE_DIR / "mcp.json"
    )
    research_agent: LLM = Field(description="Research agent model configuration")
    design_agent: LLM = Field(description="Design agent model configuration")
    long_context_model: LLM = Field(description="Long context model configuration")
    vision_model: LLM = Field(description="Vision model configuration")
    t2i_model: LLM = Field(description="Text-to-image model configuration")
    critic_agent: LLM | None = Field(
        default=None, description="Critic agent model configuration"
    )

    def model_post_init(self, context):
        assert self.critic_agent is None or self.critic_agent.is_multimodal, (
            "Critic agent must be a multimodal model, set `is_multimodal` to True if necessary"
        )
        return super().model_post_init(context)

    @classmethod
    def load_from_file(cls, config_path: str | None = None) -> "DeepPresenterConfig":
        """Load configuration from file"""
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = PACKAGE_DIR / "config.yaml"

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file {config_file} does not exist")
        config_data = {}
        with open(config_file, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        config_data["file_path"] = str(config_file.resolve())
        return cls(**config_data)

    async def validate_llms(self):
        # ? t2i endpoints might not support this api
        await asyncio.gather(
            self.research_agent.validate(),
            self.design_agent.validate(),
            self.long_context_model.validate(),
            self.vision_model.validate(),
            self.t2i_model.validate(),
        )

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


GLOBAL_CONFIG = DeepPresenterConfig.load_from_file()
