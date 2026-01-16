import asyncio
import os
import re
from contextlib import AsyncExitStack
from os.path import basename, exists, join

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, Field, create_model

from pptagent.agent import Agent
from pptagent.llms import AsyncLLM
from pptagent.model_utils import language_id
from pptagent.utils import (
    Language,
    get_logger,
    package_join,
)

from .doc_utils import (
    get_tree_structure,
    process_markdown_content,
    split_markdown_by_headings,
)
from .element import Media, Metadata, Section, SubSection, Table, link_medias

logger = get_logger(__name__)

env = Environment(undefined=StrictUndefined)

MERGE_METADATA_PROMPT = env.from_string(
    open(
        package_join("prompts", "document", "merge_metadata.txt"), encoding="utf-8"
    ).read()
)
LITERAL_CONSTRAINT = os.getenv("LITERAL_CONSTRAINT", "false").lower() == "true"


class Document(BaseModel):
    image_dir: str
    language: Language
    metadata: dict[str, str]
    sections: list[Section]

    def validate_medias(self, image_dir: str | None = None):
        """Validate and fix media file paths"""
        if image_dir is not None:
            self.image_dir = image_dir
        assert exists(self.image_dir), f"image directory is not found: {self.image_dir}"
        for media in self.iter_medias():
            if exists(media.path):
                continue
            base_name = basename(media.path)
            if exists(join(self.image_dir, base_name)):
                media.path = join(self.image_dir, base_name)
            else:
                raise FileNotFoundError(f"image file not found: {media.path}")

    def get_overview(self, include_summary: bool = False, include_image: bool = True):
        """Get document overview with sections and subsections"""
        overview = ""
        for section in self.sections:
            overview += f"<section>{section.title}</section>\n"
            if include_summary:
                overview += f"\tSummary: {section.summary}\n"
            for subsection in section.content:
                if isinstance(subsection, SubSection):
                    overview += f"\t<subsection>{subsection.title}</subsection>\n"
                elif include_image and isinstance(subsection, Media):
                    overview += (
                        f"\t<image>{subsection.path}</image>: {subsection.caption}\n"
                    )
            overview += "\n"
        return overview

    def iter_medias(self):
        """Iterate over all media items in the document"""
        for section in self.sections:
            yield from section.iter_medias()

    def find_media(self, caption: str | None = None, path: str | None = None):
        """Find media by caption or path"""
        for media in self.iter_medias():
            if caption is not None and media.caption == caption:
                return media
            if path is not None and media.path == path:
                return media
        raise ValueError(f"Image caption or path not found: {caption} or {path}")

    @classmethod
    async def _parse_chunk(
        cls,
        extractor: Agent,
        markdown_chunk: str,
        image_dir: str,
        language_model: AsyncLLM,
        vision_model: AsyncLLM,
        limiter: asyncio.Semaphore | AsyncExitStack,
    ):
        markdown, medias = process_markdown_content(
            markdown_chunk,
        )
        async with limiter:
            _, section = await extractor(
                markdown_document=markdown,
                response_format=Section.response_model(),
            )
            metadata = section.pop("metadata", {})
            section["content"] = section.pop("subsections")
            section = Section(**section, markdown_content=markdown_chunk)
            link_medias(medias, section)
            async with asyncio.TaskGroup() as tg:
                for media in section.iter_medias():
                    media.parse(image_dir)
                    if isinstance(media, Table):
                        tg.create_task(media.get_caption(language_model))
                    else:
                        tg.create_task(media.get_caption(vision_model))
        return metadata, section

    @classmethod
    async def from_markdown(
        cls,
        markdown_content: str,
        language_model: AsyncLLM,
        vision_model: AsyncLLM,
        image_dir: str,
        max_at_once: int | None = None,
    ):
        doc_extractor = Agent(
            "doc_extractor",
            llm_mapping={"language": language_model, "vision": vision_model},
        )
        document_tree = get_tree_structure(markdown_content)
        headings = re.findall(r"^#+\s+.*", markdown_content, re.MULTILINE)
        splited_chunks = await split_markdown_by_headings(
            markdown_content, headings, document_tree, language_model
        )

        metadata = []
        sections = []
        tasks = []

        limiter = (
            asyncio.Semaphore(max_at_once)
            if max_at_once is not None
            else AsyncExitStack()
        )
        async with asyncio.TaskGroup() as tg:
            for chunk in splited_chunks:
                tasks.append(
                    tg.create_task(
                        cls._parse_chunk(
                            doc_extractor,
                            chunk,
                            image_dir,
                            language_model,
                            vision_model,
                            limiter,
                        )
                    )
                )

        # Process results in order
        for task in tasks:
            meta, section = task.result()
            metadata.append(meta)
            sections.append(section)

        merged_metadata = await language_model(
            MERGE_METADATA_PROMPT.render(metadata=metadata),
            return_json=True,
            response_format=create_model(
                "MetadataList",
                metadata=(list[Metadata], Field(...)),
                __base__=BaseModel,
            ),
        )
        metadata = {meta["name"]: meta["value"] for meta in merged_metadata["metadata"]}
        return cls(
            image_dir=image_dir,
            language=language_id(markdown_content),
            metadata=metadata,
            sections=sections,
        )

    def index(self, target_item: SubSection | Media | Table):
        """Get the index position of a content item"""
        for i, (_, content) in enumerate(self):
            if content is target_item:
                return i
        raise ValueError("Item not found in document")

    def pop(self, index: int):
        """Remove and return content item at specified index position"""
        for idx, (section, content) in enumerate(self):
            if idx == index:
                return section.content.pop(section.content.index(content))
        raise IndexError("Index out of range")

    def insert(self, item: SubSection | Media | Table, target_index: int):
        """Insert content item after the specified index position"""
        for idx, (section, content) in enumerate(self):
            if idx == target_index:
                section.content.insert(section.content.index(content), item)
                return

        self.sections[-1].content.append(item)

    def remove(self, target_item: SubSection | Media | Table):
        """Remove content item from document"""
        for section, content in self:
            if content is target_item:
                section.content.remove(target_item)
                return
        raise ValueError("Item not found in document")

    def __contains__(self, key: str):
        for section in self.sections:
            if section.title == key:
                return True
        return False

    def __iter__(self):
        for section in self.sections:
            for content in section.content:
                yield section, content

    def __getitem__(self, key: int | slice | str):
        """Get content item by index, slice or section title"""
        if isinstance(key, slice):
            return [content for _, content in list(self)[key]]
        else:
            for i, (sec, content) in enumerate(self):
                if i == key:
                    return content
                elif sec.title == key:
                    return sec
            raise IndexError(f"Index out of range: {key}")

    @property
    def metainfo(self):
        return "\n".join([f"{k}: {v}" for k, v in self.metadata.items()])
