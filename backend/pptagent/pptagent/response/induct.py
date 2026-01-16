from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel

from pptagent.utils import edit_distance

_allowed_contents = ContextVar("allowed_contents")


class SlideElement(BaseModel):
    name: str
    data: list[str]
    type: Literal["text", "image"]

    def model_post_init(self, _):
        self.data = [
            max(_allowed_contents.get(), key=lambda x: edit_distance(x, d))
            for d in self.data
        ]


class SlideSchema(BaseModel):
    elements: list[SlideElement]

    @classmethod
    def response_model(cls, content_fields: list[str]) -> type[BaseModel]:
        _allowed_contents.set(content_fields)
        return cls
