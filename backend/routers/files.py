from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import uuid
from pathlib import Path
from pydantic import BaseModel

from services.chat_file_service import ensure_chat_file_parsed

router = APIRouter(prefix="/api/files", tags=["files"])

# Use the same upload directory logic as knowledge, or a dedicated one.
# For simplicity, we'll use a 'chat_uploads' directory in the same temp location.
UPLOAD_DIR = os.getenv("CHAT_UPLOAD_DIR", "/tmp/chat_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class UploadResponse(BaseModel):
    id: str
    filename: str
    file_path: str
    content_type: str
    size: int


class ParseRequest(BaseModel):
    file_path: str
    filename: str | None = None


class ParseResponse(BaseModel):
    parse_status: str
    parse_message: str
    file_type: str | None = None
    content_length: int = 0


def _ensure_upload_path(file_path: str) -> str:
    resolved = Path(file_path).resolve()
    upload_root = Path(UPLOAD_DIR).resolve()
    if upload_root != resolved and upload_root not in resolved.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return str(resolved)

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    try:
        # Generate unique ID and filename
        file_id = str(uuid.uuid4())
        file_ext = Path(file.filename).suffix
        stored_filename = f"{file_id}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, stored_filename)

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(file_path)

        return UploadResponse(
            id=file_id,
            filename=file.filename,
            file_path=file_path,
            content_type=file.content_type or "application/octet-stream",
            size=file_size
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse", response_model=ParseResponse)
async def parse_file(data: ParseRequest):
    file_path = _ensure_upload_path(data.file_path)
    result = await ensure_chat_file_parsed(file_path, filename=data.filename)
    return ParseResponse(
        parse_status=result.get("parse_status", "failed"),
        parse_message=result.get("parse_message", "解析失败"),
        file_type=result.get("file_type"),
        content_length=int(result.get("content_length") or 0),
    )
