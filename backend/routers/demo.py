"""Demo PPT preview endpoints.

Provides list, preview generation (pptx -> images), and file/image serving.
"""

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from pptagent.utils import ppt_to_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_DIR = Path(os.getenv("PPT_DEMO_DIR", "/app/PPT_demo")).resolve()
CACHE_DIR = Path(os.getenv("PPT_DEMO_CACHE_DIR", "/tmp/ppt_demo_cache")).resolve()


def _ensure_demo_file(name: str) -> Path:
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="Invalid file name")
    if not name.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Only PPTX files are supported")
    file_path = (DEMO_DIR / name).resolve()
    if not str(file_path).startswith(str(DEMO_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PPTX file not found")
    return file_path


def _preview_dir(name: str) -> Path:
    cache_key = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    return (CACHE_DIR / cache_key).resolve()


@router.get("/list")
async def list_demo_files():
    if not DEMO_DIR.exists():
        return {"items": []}

    items = []
    for entry in sorted(DEMO_DIR.iterdir()):
        if not entry.is_file() or entry.suffix.lower() != ".pptx":
            continue
        stat = entry.stat()
        items.append({
            "name": entry.name,
            "size": stat.st_size,
            "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

    return {"items": items}


@router.get("/file")
async def get_demo_file(name: str = Query(...)):
    file_path = _ensure_demo_file(name)
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=name,
    )


@router.get("/preview")
async def get_demo_preview(name: str = Query(...)):
    file_path = _ensure_demo_file(name)
    output_dir = _preview_dir(name)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(output_dir.glob("slide_*.jpg"))
    if not images:
        try:
            ppt_to_images(str(file_path), str(output_dir))
        except Exception as exc:
            logger.error("Demo preview conversion failed", exc_info=exc)
            raise HTTPException(
                status_code=500,
                detail="Preview conversion failed. Ensure LibreOffice and poppler are installed.",
            )
        images = sorted(output_dir.glob("slide_*.jpg"))

    if not images:
        raise HTTPException(status_code=500, detail="Preview images not generated")

    encoded_name = quote(name)
    return {
        "name": name,
        "count": len(images),
        "images": [
            f"/api/demo/image?name={encoded_name}&file={quote(img.name)}" for img in images
        ],
        "downloadUrl": f"/api/demo/file?name={encoded_name}",
    }


@router.get("/image")
async def get_demo_image(name: str = Query(...), file: str = Query(...)):
    _ = _ensure_demo_file(name)
    if Path(file).name != file:
        raise HTTPException(status_code=400, detail="Invalid image name")
    if not file.startswith("slide_") or not file.lower().endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Invalid image file")

    output_dir = _preview_dir(name)
    image_path = (output_dir / file).resolve()
    if not str(image_path).startswith(str(output_dir)):
        raise HTTPException(status_code=400, detail="Invalid image path")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(image_path, media_type="image/jpeg")
