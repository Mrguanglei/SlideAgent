from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel, Field, create_model

from pptagent.document import Document, SubSection
from pptagent.utils import get_logger

_empty_images = ContextVar(
    "_empty_images",
)

logger = get_logger(__name__)


class DocumentIndex(BaseModel):
    section: str
    subsections: list[str]

    @classmethod
    def response_model(cls, section_fields: list[str], subsection_fields: list[str]):
        return create_model(
            cls.__name__,
            section=(Literal[*section_fields], Field(...)),  # type: ignore
            subsections=(list[Literal[*subsection_fields]], Field(...)),  # type: ignore
            __base__=BaseModel,
        )


class OutlineItem(BaseModel):
    purpose: str
    topic: str
    indexes: list[DocumentIndex] | list[str]
    images: list[str] = Field(default_factory=list)

    def model_post_init(self, _) -> None:
        if self.images and not _empty_images.get():
            self.images.clear()

    def retrieve(self, slide_idx: int, document: Document):
        subsections = []
        for index in self.indexes:
            for subsection in index.subsections:
                subsections.append(document[index.section][subsection])
        header = f"Current Slide: {self.purpose}\n"
        header += f"This is the {slide_idx + 1} slide of the presentation.\n"
        content = ""
        for subsection in subsections:
            content += f"Paragraph: {subsection.title}\nContent: {subsection.content}\n"
        images = [
            f"<image>{path}</image>: {document.find_media(path=path).caption}"
            for path in self.images
        ]
        return header, content, images

    @classmethod
    def response_model(cls, document: Document):
        sections = []
        subsections = []
        for sec in document.sections:
            sections.append(sec.title)
            for subsec in sec.content:
                if isinstance(subsec, SubSection):
                    subsections.append(subsec.title)
        allowed_images = [m.path for m in document.iter_medias()]
        if allowed_images:
            literal_image = Literal[*allowed_images]  # type: ignore
            _empty_images.set(True)
        else:
            _empty_images.set(False)
            literal_image = str

        return create_model(
            cls.__name__,
            purpose=(str, Field(...)),
            topic=(str, Field(...)),
            indexes=(
                list[DocumentIndex.response_model(sections, subsections)],
                Field(...),
            ),
            images=(list[literal_image], Field(default_factory=list)),
            __base__=BaseModel,
        )


class Outline(BaseModel):
    outline: list[OutlineItem]

    @classmethod
    def response_model(cls, document: Document):
        return create_model(
            cls.__name__,
            outline=(
                list[OutlineItem.response_model(document)],
                Field(...),
            ),
            __base__=BaseModel,
        )
