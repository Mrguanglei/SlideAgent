from dataclasses import asdict, dataclass
from functools import partial
from math import ceil

import yaml
from jinja2 import Environment, StrictUndefined, Template
from PIL import Image
from pydantic import BaseModel

from pptagent.llms import AsyncLLM
from pptagent.utils import get_json_from_response, package_join

RETRY_TEMPLATE = Template(
    """The previous output is invalid, please carefully analyze the traceback and feedback information, correct errors happened before.
            feedback:
            {{feedback}}
            traceback:
            {{traceback}}
            Give your corrected output in the same format without including the previous output:
            """
)


@dataclass
class Turn:
    """
    A class to represent a turn in a conversation.
    """

    id: int
    prompt: str
    response: str
    message: list
    retry: int = -1
    images: list[str] = None
    input_chars: int = 0
    output_chars: int = 0

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if k != "embedding"}

    def calc_token(self):
        """
        Calculate the number of tokens for the turn.
        """
        if self.images is not None:
            self.input_chars += calc_image_tokens(self.images)
        self.input_chars += len(self.prompt)
        self.output_chars = len(self.response)

    def __eq__(self, other):
        return self is other


class Agent:
    """
    An agent, defined by its instruction template and model.
    """

    def __init__(
        self,
        name: str,
        llm_mapping: dict[str, AsyncLLM],
        record_cost: bool = False,
        config: dict | None = None,
        env: Environment | None = None,
    ):
        """
        Initialize the Agent.

        Args:
            name (str): The name of the role.
        llm_mapping (dict): The mapping of the language model.
            record_cost (bool): Whether to record the token cost.
            llm (LLM): The language model.
            config (dict): The configuration.
            env (Environment): The Jinja2 environment.
        """
        self.name = name
        self.config = config
        if self.config is None:
            with open(package_join("roles", f"{name}.yaml"), encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
                assert isinstance(self.config, dict), "Agent config must be a dict"
        self.llm_mapping = llm_mapping
        self.llm = self.llm_mapping[self.config["use_model"]]
        self.model = self.llm.model
        self.record_cost = record_cost
        self.return_json = self.config.get("return_json", False)
        self.system_message = self.config["system_prompt"]
        self.prompt_args = set(self.config["jinja_args"])
        self.env = env
        if self.env is None:
            self.env = Environment(undefined=StrictUndefined)
        self.template = self.env.from_string(self.config["template"])
        self.input_tokens = 0
        self.output_tokens = 0
        self._history: list[Turn] = []
        run_args = self.config.get("run_args", {})
        self.llm.__call__ = partial(self.llm.__call__, **run_args)
        self.system_tokens = len(self.system_message)

    def calc_cost(self, turns: list[Turn]):
        """
        Calculate the cost of a list of turns.
        """
        for turn in turns[:-1]:
            self.input_tokens += turn.input_chars
            self.input_tokens += turn.output_chars
        self.input_tokens += turns[-1].input_chars
        self.output_tokens += turns[-1].output_chars
        self.input_tokens += self.system_tokens

    @property
    def next_turn_id(self):
        if len(self._history) == 0:
            return 0
        return max(t.id for t in self._history) + 1

    @property
    def history(self):
        return sorted(self._history, key=lambda x: (x.id, x.retry))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, model={self.model})"

    async def retry(
        self,
        feedback: str,
        traceback: str,
        turn_id: int,
        error_idx: int,
        response_format: BaseModel | None = None,
        **client_kwargs,
    ):
        """
        Retry a failed turn with feedback and traceback.
        """
        assert error_idx > 0, "error_idx must be greater than 0"
        prompt = RETRY_TEMPLATE.render(feedback=feedback, traceback=traceback)
        history = [t for t in self._history if t.id == turn_id]
        history_msg = []
        for turn in history:
            history_msg.extend(turn.message)
        response, message = await self.llm(
            prompt,
            history=history_msg,
            return_message=True,
            response_format=response_format,
            **client_kwargs,
        )
        turn = Turn(
            id=turn_id,
            prompt=prompt,
            response=response,
            message=message,
            retry=error_idx,
        )
        return await self.__post_process__(response, history, turn)

    async def __call__(
        self,
        images: list[str] = None,
        recent: int = 0,
        response_format: BaseModel | None = None,
        client_kwargs: dict | None = None,
        **jinja_args,
    ):
        """
        Call the agent with prompt arguments.

        Args:
            images (list[str]): A list of image file paths.
            recent (int): The number of recent turns to include.
            similar (int): The number of similar turns to include.
            **jinja_args: Additional arguments for the Jinja2 template.

        Returns:
            The response from the role.
        """
        if isinstance(images, str):
            images = [images]
        assert self.prompt_args == set(jinja_args.keys()), (
            f"Invalid arguments, expected: {self.prompt_args}, got: {jinja_args.keys()}"
        )
        prompt = self.template.render(**jinja_args)
        history = await self.get_history(recent)
        history_msg = []
        for turn in history:
            history_msg.extend(turn.message)

        if client_kwargs is None:
            client_kwargs = {}
        response, message = await self.llm(
            prompt,
            system_message=self.system_message,
            history=history_msg,
            images=images,
            return_message=True,
            response_format=response_format,
            **client_kwargs,
        )
        turn = Turn(
            id=self.next_turn_id,
            prompt=prompt,
            response=response,
            message=message,
            images=images,
        )
        return turn.id, await self.__post_process__(response, history, turn)

    async def get_history(self, recent: int):
        """
        Get the conversation history.
        """
        history = self._history[-recent:] if recent > 0 else []
        history.sort(key=lambda x: x.id)
        return history

    async def __post_process__(
        self, response: str, history: list[Turn], turn: Turn
    ) -> str | dict:
        """
        Post-process the response from the agent.
        """
        self._history.append(turn)
        if self.record_cost:
            turn.calc_token()
            self.calc_cost(history + [turn])
        if self.return_json:
            response = get_json_from_response(response)
        return response


def calc_image_tokens(images: list[str]):
    """
    Calculate the number of tokens for a list of images.
    """
    tokens = 0
    for image in images:
        with open(image, "rb") as f:
            width, height = Image.open(f).size
        if width > 1024 or height > 1024:
            if width > height:
                height = int(height * 1024 / width)
                width = 1024
            else:
                width = int(width * 1024 / height)
                height = 1024
        h = ceil(height / 512)
        w = ceil(width / 512)
        tokens += 85 + 170 * h * w
    return tokens
