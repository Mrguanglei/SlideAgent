from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import uuid
from pathlib import Path
from pydantic import BaseModel

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
