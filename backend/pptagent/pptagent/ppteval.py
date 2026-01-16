import json
import os
from collections import defaultdict
from glob import glob
from os.path import dirname, exists, join

from jinja2 import Template
from tqdm.asyncio import tqdm

from .model_utils import ModelManager
from .presentation import Presentation
from .utils import Config, package_join, ppt_to_images_async

manager = ModelManager()
language_model = manager.language_model
vision_model = manager.vision_model

text_scorer = Template(
    open(
        package_join("prompts", "ppteval", "ppteval_content.txt"), encoding="utf-8"
    ).read()
)
vision_scorer = Template(
    open(
        package_join("prompts", "ppteval", "ppteval_style.txt"), encoding="utf-8"
    ).read()
)
style_descriptor = open(
    package_join("prompts", "ppteval", "ppteval_describe_style.txt"), encoding="utf-8"
).read()
content_descriptor = open(
    package_join("prompts", "ppteval", "ppteval_describe_content.txt"), encoding="utf-8"
).read()
ppt_extractor = Template(
    open(
        package_join("prompts", "ppteval", "ppteval_extract.txt"), encoding="utf-8"
    ).read()
)
logic_scorer = Template(
    open(
        package_join("prompts", "ppteval", "ppteval_coherence.txt"), encoding="utf-8"
    ).read()
)


def get_eval(prs_source: str):
    evals = defaultdict(dict)
    eval_file = join(dirname(prs_source), "evals.json")
    if exists(eval_file):
        with open(eval_file, encoding="utf-8") as f:
            evals |= json.load(f)
    return evals, eval_file


async def eval_slide(prs_source: str, slide_folder: str):
    evals, eval_file = get_eval(prs_source)
    for slide_image in glob(join(slide_folder, "slide_*.jpg")) + glob(
        join(slide_folder, "slide_images", "slide_*.jpg")
    ):
        slide_descr = slide_image.replace(".jpg", ".json")
        if not os.path.exists(slide_descr):
            style_descr = await vision_model(style_descriptor, slide_image)
            content_descr = await vision_model(content_descriptor, slide_image)
            with open(slide_descr, "w", encoding="utf-8") as f:
                json.dump(
                    {"content": content_descr, "style": style_descr},
                    f,
                    indent=2,
                )
        else:
            descr = json.load(open(slide_descr, encoding="utf-8"))
            style_descr = descr["style"]
            content_descr = descr["content"]
        if slide_image not in evals["vision"]:
            evals["vision"][slide_image] = await language_model(
                vision_scorer.render(descr=style_descr), return_json=True
            )
        if slide_image not in evals["content"]:
            evals["content"][slide_image] = await language_model(
                text_scorer.render(descr=content_descr), return_json=True
            )
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(evals, f, indent=2)


async def eval_coherence(prs_source: str):
    tmp_config = Config(dirname(prs_source))
    evals, eval_file = get_eval(prs_source)
    if "logic" in evals:
        return
    slide_descr = join(prs_source.replace(".pptx", ""), "extracted.json")
    if not exists(slide_descr):
        presentation = Presentation.from_file(prs_source, tmp_config).to_text()
        extracted = language_model(
            ppt_extractor.render(presentation=presentation),
            return_json=True,
        )
        with open(slide_descr, "w", encoding="utf-8") as f:
            json.dump(extracted, f, indent=2)
    else:
        extracted = json.load(open(slide_descr, encoding="utf-8"))
    evals["logic"] = await language_model(
        logic_scorer.render(
            presentation=extracted,
        ),
        return_json=True,
    )
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(evals, f, indent=2)


async def eval_ppt(prs_source: str):
    slide_folder = prs_source.replace(".pptx", "")
    if not exists(slide_folder):
        await ppt_to_images_async(prs_source, slide_folder)
    await eval_coherence(prs_source)
    await eval_slide(prs_source, slide_folder)
    return get_eval(prs_source)[0]


async def eval_parsed_ppts(prs_files: list[str], slide_folders: list[str]):
    await tqdm.gather(*[eval_coherence(prs_file) for prs_file in prs_files])
    await tqdm.gather(
        *[
            eval_slide(prs_file, slide_folder)
            for prs_file, slide_folder in zip(prs_files, slide_folders)
        ]
    )

    # Calculate average scores directly in this function
    all_scores = {"vision": [], "content": [], "logic": []}

    for prs_file in prs_files:
        evals, _ = get_eval(prs_file)

        # Vision scores
        vision_scores = [score.get("score", 0) for score in evals["vision"].values()]
        if vision_scores:
            all_scores["vision"].extend(vision_scores)

        # Content scores
        content_scores = [score.get("score", 0) for score in evals["content"].values()]
        if content_scores:
            all_scores["content"].extend(content_scores)

        # Logic score
        if "logic" in evals and "score" in evals["logic"]:
            all_scores["logic"].append(evals["logic"]["score"])

    # Calculate averages
    avg_scores = {}
    for category, scores in all_scores.items():
        if scores:
            avg_scores[category] = sum(scores) / len(scores)
        else:
            avg_scores[category] = 0

    # Display results
    print("\n=== Average Scores by Dimension ===")
    for category, score in avg_scores.items():
        print(f"{category.capitalize()}: {score:.2f}")

    # Calculate overall average
    if avg_scores:
        overall_avg = sum(avg_scores.values()) / len(avg_scores)
        print(f"Overall: {overall_avg:.2f}")

    return avg_scores
