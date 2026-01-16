import hashlib
import re
from os.path import exists, join

from jinja2 import Environment, StrictUndefined
from PIL import Image
from pydantic import BaseModel, Field, create_model

from pptagent.llms import AsyncLLM
from pptagent.utils import (
    edit_distance,
    get_html_table_image,
    get_logger,
    package_join,
)

from .doc_utils import parse_table_with_merges

env = Environment(undefined=StrictUndefined)

IMAGE_PARSING_REGEX = re.compile(r"\((.*?)\)")
TABLE_CAPTION_PROMPT = env.from_string(
    open(
        package_join("prompts", "document", "markdown_table_caption.txt"),
        encoding="utf-8",
    ).read()
)
IMAGE_CAPTION_PROMPT = env.from_string(
    open(
        package_join("prompts", "document", "markdown_image_caption.txt"),
        encoding="utf-8",
    ).read()
)

logger = get_logger(__name__)


class Media(BaseModel):
    markdown_content: str
    near_chunks: tuple[str, str]
    path: str | None = None
    caption: str | None = None

    @property
    def size(self):
        assert self.path is not None, "Path is required to get size"
        return Image.open(self.path).size

    def parse(self, image_dir: str):
        """
        Parse the markdown content to extract image path and alt text.
        Format expected: ![alt text](image.png)
        """
        match = IMAGE_PARSING_REGEX.search(self.markdown_content)
        if match is None:
            raise ValueError("No image found in the markdown content")
        image_path = match.group(1)
        if not exists(image_path):
            image_path = join(image_dir, image_path)
        assert exists(image_path), f"image file not found: {image_path}"
        self.path = image_path

    async def get_caption(self, vision_model: AsyncLLM):
        assert self.path is not None, "Path is required to get caption"
        if self.caption is None:
            self.caption = await vision_model(
                IMAGE_CAPTION_PROMPT.render(
                    markdown_caption=self.near_chunks,
                ),
                self.path,
            )
            logger.debug(f"Caption: {self.caption}")


class Table(Media):
    cells: list[list[str]] | None = None
    merge_area: list[tuple[int, int, int, int]] | None = None

    def parse(self, image_dir: str):
        cells, merges = parse_table_with_merges(self.markdown_content)
        self.cells = cells
        self.merge_area = merges

        if self.path is None:
            self.path = join(
                image_dir,
                f"table_{hashlib.md5(str(self.cells).encode()).hexdigest()[:4]}.png",
            )
        get_html_table_image(self.markdown_content, self.path)

    async def get_caption(self, language_model: AsyncLLM):
        if self.caption is None:
            self.caption = await language_model(
                TABLE_CAPTION_PROMPT.render(
                    markdown_content=self.markdown_content,
                    markdown_caption=self.near_chunks,
                )
            )
            logger.debug(f"Caption: {self.caption}")


class SubSection(BaseModel):
    title: str
    content: str


class Metadata(BaseModel):
    name: str
    value: str


class Section(BaseModel):
    title: str
    summary: str
    content: list[SubSection | Media | Table]
    markdown_content: str | None = None

    def iter_medias(self):
        for block in self.content:
            if isinstance(block, Media):
                yield block

    @classmethod
    def response_model(cls):
        # Create a new model with only SubSection blocks and metadata
        return create_model(
            cls.__name__,
            title=(str, Field(...)),
            summary=(str, Field(...)),
            subsections=(list[SubSection], Field(...)),
            metadata=(list[Metadata], Field(default_factory=list)),
            __base__=BaseModel,
        )

    def __getitem__(self, key: str):
        for block in self.content:
            if isinstance(block, SubSection) and block.title == key:
                return block
            elif isinstance(block, Media) and (
                block.path == key or block.caption == key
            ):
                return block
        raise KeyError(f"No subsection or media with title {key} found")


def link_medias(
    medias: list[dict],
    section: Section,
    max_chunk_size: int = 256,
):
    """
    Link media elements to the section by inserting them into the blocks list at appropriate positions.

    Args:
        medias: List of media dictionaries (tables, images)
        section: Section object to insert medias into
        max_chunk_size: Maximum size of text chunk to consider for matching
    """
    if not medias:
        return

    # Convert media dictionaries to Media instances
    media_instances = []
    for media_dict in medias:
        if media_dict.get("type") == "table":
            media_instances.append(Table(**media_dict))
        else:
            media_instances.append(Media(**media_dict))

    # Find the best insertion position for each media
    for media in media_instances:
        if len(media.near_chunks[0]) < max_chunk_size:
            # If context is small, insert at the beginning
            section.content.insert(0, media)
        else:
            # Find the most similar SubSection based on content
            best_match_idx = 0
            best_similarity = 0

            for i, block in enumerate(section.content):
                if isinstance(block, SubSection):
                    similarity = edit_distance(media.near_chunks[0], block.content)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_idx = i

            section.content.insert(best_match_idx + 1, media)
