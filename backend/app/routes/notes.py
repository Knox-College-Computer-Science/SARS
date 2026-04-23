import os
import shutil
import sqlite3
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(tags=["Notes"])

BASE_DIR    = Path(__file__).resolve().parent.parent.parent  # /backend/
UPLOAD_DIR  = BASE_DIR / "uploads"
NOTES_DB    = BASE_DIR / "notes.db"

UPLOAD_DIR.mkdir(exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(str(NOTES_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT,
            subject     TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


@router.post("/upload")
async def upload_note(file: UploadFile = File(...), subject: str = Form(...)):
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    conn = _get_conn()
    conn.execute("INSERT INTO notes (filename, subject) VALUES (?, ?)", (file.filename, subject))
    conn.commit()
    conn.close()

    return {"message": "Uploaded successfully", "filename": file.filename}


@router.get("/notes")
def get_notes():
    conn = _get_conn()
    rows = conn.execute("SELECT id, filename, subject, upload_time FROM notes").fetchall()
    conn.close()
    return [{"id": r[0], "filename": r[1], "subject": r[2], "upload_time": r[3]} for r in rows]


@router.get("/files/{filename}")
def get_file(filename: str):
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(filepath))
