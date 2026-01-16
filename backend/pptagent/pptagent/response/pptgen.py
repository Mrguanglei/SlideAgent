from typing import Literal

from pydantic import BaseModel, Field, create_model


class SlideElement(BaseModel):
    name: str
    data: list[str]

    @classmethod
    def response_model(cls, elements: list[str]):
        return create_model(
            cls.__name__,
            name=(Literal[*elements], Field(...)),  # type: ignore
            data=(list[str], Field(...)),
            __base__=BaseModel,
        )


class EditorOutput(BaseModel):
    elements: list[SlideElement]

    @property
    def dict(self):
        return {element.name: element.data for element in self.elements}

    @classmethod
    def response_model(cls, elements: list[str]):
        return create_model(
            cls.__name__,
            elements=(list[SlideElement.response_model(elements)], Field(...)),
            __base__=BaseModel,
        )

    def __contains__(self, key: str):
        for element in self.elements:
            if element.name == key:
                return True
        return False

    def __getitem__(self, key: str):
        for element in self.elements:
            if element.name == key:
                return element
        raise KeyError(f"Element '{key}' not found")


class LayoutChoice(BaseModel):
    reasoning: str
    layout: str

    @classmethod
    def response_model(cls, layouts: list[str]):
        return create_model(
            cls.__name__,
            reasoning=(str, Field(...)),
            layout=(Literal[*layouts], Field(...)),  # type: ignore
            __base__=BaseModel,
        )


class TemplateChoice(BaseModel):
    reasoning: str
    template: str

    @classmethod
    def response_model(cls, templates: list[str]):
        return create_model(
            cls.__name__,
            reasoning=(str, Field(...)),
            template=(Literal[*templates], Field(...)),  # type: ignore
            __base__=BaseModel,
        )
