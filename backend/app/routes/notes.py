import io
import sqlite3
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(tags=["Notes"])

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
NOTES_DB   = BASE_DIR / "notes.db"

UPLOAD_DIR.mkdir(exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(str(NOTES_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT,
            subject         TEXT,
            upload_time     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by     TEXT,
            drive_file_id   TEXT,
            drive_view_link TEXT
        )
    """)
<<<<<<< HEAD
=======
    # Migrate old DB: add new columns if they don't exist
>>>>>>> 97deffec916b457fba0141528ee0b719faa08a49
    for col, col_type in [
        ("uploaded_by",     "TEXT"),
        ("drive_file_id",   "TEXT"),
        ("drive_view_link", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
<<<<<<< HEAD
            pass
=======
            pass  # column already exists, skip
>>>>>>> 97deffec916b457fba0141528ee0b719faa08a49
    conn.commit()
    return conn


@router.post("/upload")
async def upload_note(
    request: Request,
    file: UploadFile = File(...),
    subject: str = Form(...),
):
    file_bytes = await file.read()
    access_token = request.session.get("access_token")
    session_user = request.session.get("user")
    uploaded_by = session_user.get("email") if session_user else "anonymous"

    drive_file_id = None
    drive_view_link = None
<<<<<<< HEAD

    if access_token:
        try:
            from app.services.google_oauth import upload_file_to_drive
            drive_result = upload_file_to_drive(
                access_token=access_token,
                file_bytes=file_bytes,
                filename=file.filename,
                subject=subject,
            )
            drive_file_id   = drive_result["drive_file_id"]
            drive_view_link = drive_result["drive_view_link"]
        except Exception as e:
            print(f"[Drive] Upload failed, falling back to local: {e}")

    if not drive_file_id:
        dest = UPLOAD_DIR / file.filename
        with dest.open("wb") as buf:
            buf.write(file_bytes)
=======
>>>>>>> 97deffec916b457fba0141528ee0b719faa08a49

    # ── Try Google Drive upload if user is logged in ──
    if access_token:
        try:
            from app.services.google_oauth import upload_file_to_drive
            drive_result = upload_file_to_drive(
                access_token=access_token,
                file_bytes=file_bytes,
                filename=file.filename,
                subject=subject,
            )
            drive_file_id   = drive_result["drive_file_id"]
            drive_view_link = drive_result["drive_view_link"]
        except Exception as e:
            print(f"[Drive] Upload failed, falling back to local: {e}")

    # ── Fall back to local storage if Drive upload failed / not logged in ──
    if not drive_file_id:
        dest = UPLOAD_DIR / file.filename
        with dest.open("wb") as buf:
            buf.write(file_bytes)

    # ── Save to DB ──
    conn = _get_conn()
    conn.execute(
        "INSERT INTO notes (filename, subject, uploaded_by, drive_file_id, drive_view_link) VALUES (?, ?, ?, ?, ?)",
        (file.filename, subject, uploaded_by, drive_file_id, drive_view_link),
    )
    conn.commit()
    conn.close()

<<<<<<< HEAD
=======
    # ── RAG indexing ──
>>>>>>> 97deffec916b457fba0141528ee0b719faa08a49
    rag_indexed = False
    if file.filename.lower().endswith(".pdf"):
        try:
            from app.rag.rag_pipeline import index_pdf
            index_pdf(file_bytes, file.filename)
            rag_indexed = True
        except Exception as e:
            print(f"[RAG] Auto-index failed (non-fatal): {e}")

    return {
        "message": "Uploaded successfully",
        "filename": file.filename,
        "rag_indexed": rag_indexed,
        "drive_file_id": drive_file_id,
        "drive_view_link": drive_view_link,
    }


@router.get("/notes")
def get_notes():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, filename, subject, upload_time, uploaded_by, drive_file_id, drive_view_link FROM notes"
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "filename": r[1],
            "subject": r[2],
            "upload_time": r[3],
            "uploaded_by": r[4],
            "drive_file_id": r[5],
            "drive_view_link": r[6],
        }
        for r in rows
    ]


@router.get("/files/{filename}")
def get_file(filename: str):
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(filepath))