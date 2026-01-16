import asyncio
import json
import os
from glob import glob
from os.path import join

from pptagent.induct import SlideInducter
from pptagent.model_utils import ModelManager
from pptagent.multimodal import ImageLabler
from pptagent.presentation import Presentation
from pptagent.utils import Config, ppt_to_images_async

pr_folders = glob("data/*/pptx/*")

model_manager = ModelManager()


async def test_induct(pr_folder: str, sem: asyncio.Semaphore):
    config = Config(pr_folder)
    prs = Presentation.from_file(join(pr_folder, "original.pptx"), config)
    prs.save(join(pr_folder, "source.pptx"))
    async with sem:
        if len(glob(join(pr_folder, "slide_images", "*"))) == 0:
            await ppt_to_images_async(
                join(pr_folder, "source.pptx"),
                join(pr_folder, "slide_images"),
            )
        if len(glob(join(pr_folder, "template_images", "*"))) == 0:
            prs.save(join(pr_folder, "template.pptx"), layout_only=True)
            await ppt_to_images_async(
                join(pr_folder, "template.pptx"), join(pr_folder, "template_images")
            )
        prs = Presentation.from_file(join(pr_folder, "source.pptx"), config)
        labler = ImageLabler(prs, config)
        try:
            labler.apply_stats(
                json.load(open(join(pr_folder, "image_stats.json"), encoding="utf-8"))
            )
        except:  # noqa: E722
            caption = await labler.caption_images_async(model_manager.vision_model)
            with open(join(pr_folder, "image_stats.json"), "w", encoding="utf-8") as f:
                json.dump(caption, f, indent=4, ensure_ascii=False)
            labler.apply_stats(
                json.load(open(join(pr_folder, "image_stats.json"), encoding="utf-8"))
            )
        if not os.path.exists(join(pr_folder, "slide_induction.json")):
            inducter = SlideInducter(
                prs,
                join(pr_folder, "slide_images"),
                join(pr_folder, "template_images"),
                config,
                model_manager.image_model,
                model_manager.language_model,
                model_manager.vision_model,
            )
            reference = await inducter.content_induct(await inducter.layout_induct())
            with open(
                join(pr_folder, "slide_induction.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(reference, f, indent=4, ensure_ascii=False)
        print(pr_folder, "done")


async def main():
    sem = asyncio.Semaphore(16)
    async with asyncio.TaskGroup() as tg:
        for pr_folder in pr_folders:
            tg.create_task(test_induct(pr_folder, sem))


if __name__ == "__main__":
    asyncio.run(main())
