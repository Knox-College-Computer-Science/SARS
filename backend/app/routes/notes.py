from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi import Depends
from pathlib import Path
import uuid

from database import get_db
from models import Note

router = APIRouter(tags=["Notes"])

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _safe_filename(filename: str) -> str:
    return Path(filename or "unknown").name.replace("\\", "_").replace("/", "_")


@router.post("/upload")
async def upload_note(
    request: Request,
    file: UploadFile = File(...),
    course_id: str = Form(...),
    subject: str = Form(...),
    db: Session = Depends(get_db),
):
    file_bytes   = await file.read()
    access_token = request.session.get("access_token")
    session_user = request.session.get("user")
    user_id      = request.session.get("nexus_user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    drive_file_id   = None
    drive_view_link = None
    safe_name       = _safe_filename(file.filename)
    dest            = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    with dest.open("wb") as buf:
        buf.write(file_bytes)
    local_path      = str(dest)

    if access_token:
        try:
            from app.services.google_oauth import (
                get_or_create_sars_folder,
                upload_file_to_drive,
            )
            folder_id = get_or_create_sars_folder(access_token=access_token)
            drive_result = upload_file_to_drive(
                access_token=access_token,
                file_bytes=file_bytes,
                filename=file.filename,
                subject=subject,
                folder_id=folder_id,
            )
            drive_file_id   = drive_result["drive_file_id"]
            drive_view_link = drive_result["drive_view_link"]
        except Exception as e:
            print(f"[Drive] Upload failed, falling back to local: {e}")

    note = Note(
        course_id       = course_id,
        user_id         = user_id,
        filename        = file.filename,
        subject=subject,
        drive_file_id   = drive_file_id,
        drive_view_link = drive_view_link,
        local_path      = local_path,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "message":        "Uploaded successfully",
        "note_id":        note.id,
        "filename":       note.filename,
        "drive_file_id":  drive_file_id,
        "drive_view_link": drive_view_link,
    }


@router.get("/notes")
def get_notes(
    course_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Note)
    if course_id:
        query = query.filter(Note.course_id == course_id)
    notes = query.order_by(Note.uploaded_at.desc()).all()
    return [
        {
            "id":              n.id,
            "course_id":       n.course_id,
            "filename":        n.filename,
            "subject":         n.subject,
            "drive_file_id":   n.drive_file_id,
            "drive_view_link": n.drive_view_link,
            "local_path":      n.local_path,
            "uploaded_at":     n.uploaded_at.isoformat() if n.uploaded_at else None,
        }
        for n in notes
    ]


@router.get("/files/{filename}")
def get_file(filename: str):
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        matches = list(UPLOAD_DIR.glob(f"*_{_safe_filename(filename)}"))
        if matches:
            filepath = matches[0]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(filepath))
