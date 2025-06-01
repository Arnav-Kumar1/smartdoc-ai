from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.database import get_db
from app.models.document import Document
from sqlmodel import Session
from app.config import UPLOAD_DIR
from app.utils.unique import get_unique_filename
from app.routes.auth import get_current_user
from app.models.user import User
import shutil
import os
import hashlib
import traceback
from datetime import datetime, timezone

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Update upload directory path to use config path
    user_upload_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_upload_dir, exist_ok=True)

    # Read file bytes to calculate hash
    file_bytes = await file.read()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    # Check if user already uploaded a document with this hash
    existing_doc = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.file_hash == file_hash
    ).first()
    print(f"DEBUG: existing_doc for hash {file_hash}: {existing_doc}")
    # In your backend upload route, when detecting a duplicate:
    if existing_doc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Duplicate document",
                "existing_filename": existing_doc.filename,
                "attempted_filename": file.filename
            }
        )

    # Reset file pointer for saving
    file.file.seek(0)

    unique_filename = get_unique_filename(file.filename, user_upload_dir)
    file_location = os.path.join(user_upload_dir, unique_filename)

    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        print("[ERROR] File saving failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    # Create document with explicit UTC time
    document = Document(
        filename=unique_filename,
        file_type=file.content_type,
        upload_time=datetime.now(timezone.utc),  # Store as UTC
        path=file_location,
        user_id=current_user.id,
        file_hash=file_hash  # Save the hash
    )

    try:
        db.add(document)
        db.commit()
        print("[INFO] Document committed.")
        db.refresh(document)
        print("[INFO] Document refreshed.")
    except Exception as e:
        db.rollback()
        print("[ERROR] Database commit or refresh failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database commit failed: {str(e)}")

    return JSONResponse(
        content={
            "id": str(document.id),
            "filename": document.filename,
            "file_type": document.file_type,
            "upload_time": document.upload_time.isoformat(),
            "path": document.path,
            "summary": document.summary
        },
        status_code=201
    )
