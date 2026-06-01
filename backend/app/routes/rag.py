import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import SessionLocal, get_db
from models import Note
from app.rag.pipeline import ingest, query, list_course_files, delete_course_file, get_file_status
from app.rag.models import RAGFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAG_UPLOAD_DIR = BASE_DIR / "uploads" / "rag"
RAG_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


### AUTH HELPER ###

def _user_id(request: Request) -> str:
    user_id = request.session.get("nexus_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def _safe_filename(filename: str) -> str:
    return Path(filename or "unknown").name.replace("\\", "_").replace("/", "_")


def _save_rag_upload(file_bytes: bytes, filename: str) -> str:
    dest = RAG_UPLOAD_DIR / f"{uuid.uuid4().hex}_{_safe_filename(filename)}"
    dest.write_bytes(file_bytes)
    return str(dest)


async def _get_note_file_bytes(note: Note, access_token: Optional[str]) -> tuple[bytes, Optional[str]]:
    if note.local_path and Path(note.local_path).exists():
        return Path(note.local_path).read_bytes(), note.local_path

    if note.drive_file_id and access_token:
        from app.rag.modules.drive_fetcher import fetch_file_bytes
        file_bytes, _ = await fetch_file_bytes(note.drive_file_id, access_token)
        local_path = _save_rag_upload(file_bytes, note.filename)
        return file_bytes, local_path

    raise ValueError("No file source available")


def _create_processing_file(
    db: Session,
    *,
    file_id: str,
    course_id: str,
    user_id: str,
    filename: str,
    drive_file_id: Optional[str] = None,
    local_path: Optional[str] = None,
    file_size: Optional[int] = None,
    source_type: str = "uploaded",
) -> None:
    rag_file = RAGFile(
        id=file_id,
        course_id=course_id,
        user_id=user_id,
        filename=filename,
        source_type=source_type,
        drive_file_id=drive_file_id,
        local_path=local_path,
        file_size=file_size,
        indexing_status="processing",
    )
    db.add(rag_file)
    db.commit()


def _mark_processing_failed(file_id: str, error: str) -> None:
    with SessionLocal() as task_db:
        rag_file = task_db.query(RAGFile).filter(RAGFile.id == file_id).first()
        if rag_file:
            rag_file.indexing_status = "failed"
            rag_file.warnings = [error]
            task_db.commit()


def _index_bytes_in_background(
    *,
    file_id: str,
    file_bytes: bytes,
    filename: str,
    course_id: str,
    user_id: str,
    drive_file_id: Optional[str] = None,
    local_path: Optional[str] = None,
) -> None:
    with SessionLocal() as task_db:
        ingest(
            db=task_db,
            file_bytes=file_bytes,
            filename=filename,
            course_id=course_id,
            user_id=user_id,
            drive_file_id=drive_file_id,
            local_path=local_path,
            file_id=file_id,
        )


async def _index_note_in_background(
    *,
    file_id: str,
    note_id: str,
    course_id: str,
    user_id: str,
    access_token: Optional[str],
) -> None:
    try:
        with SessionLocal() as task_db:
            note = task_db.query(Note).filter(Note.id == note_id).first()
            if not note:
                raise ValueError("Note not found")

            if note.drive_file_id and access_token:
                from app.rag.modules.drive_fetcher import fetch_file_bytes
                file_bytes, _ = await fetch_file_bytes(note.drive_file_id, access_token)
                local_path = note.local_path
            elif note.local_path:
                file_bytes = Path(note.local_path).read_bytes()
                local_path = note.local_path
            else:
                raise ValueError("No file source available")

            ingest(
                db=task_db,
                file_bytes=file_bytes,
                filename=note.filename,
                course_id=course_id,
                user_id=user_id,
                drive_file_id=note.drive_file_id,
                local_path=local_path,
                file_id=file_id,
            )
    except Exception as exc:
        logger.error(f"Index from notes failed: {exc}", exc_info=True)
        _mark_processing_failed(file_id, str(exc))


### UPLOAD ###

@router.post("/upload")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    course_id: str = Form(...),
    db: Session = Depends(get_db),
):
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")

    user_id = _user_id(request)

    try:
        file_bytes = await file.read()
        filename = _safe_filename(file.filename or "unknown")
        file_id = str(uuid.uuid4())
        local_path = _save_rag_upload(file_bytes, filename)

        _create_processing_file(
            db=db,
            file_id=file_id,
            course_id=course_id,
            user_id=user_id,
            filename=filename,
            local_path=local_path,
            file_size=len(file_bytes),
        )

        background_tasks.add_task(
            _index_bytes_in_background,
            file_id=file_id,
            file_bytes=file_bytes,
            filename=filename,
            course_id=course_id,
            user_id=user_id,
            local_path=local_path,
        )

        return {
            "status": "indexing_started",
            "file_id": file_id,
            "filename": filename,
        }

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


### CHAT ###

@router.post("/chat")
async def chat(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
):
    user_id     = _user_id(request)
    query_text  = body.get("query", "").strip()
    course_id   = body.get("course_id", "").strip()
    course_name = body.get("course_name", "Unknown Course")
    history     = body.get("history", [])

    if not query_text:
        raise HTTPException(status_code=400, detail="query required")
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")

    async def event_stream():
        try:
            async for event in query(
                db          = db,
                user_query  = query_text,
                course_id   = course_id,
                user_id     = user_id,
                course_name = course_name,
                history     = history,
            ):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error(f"Chat stream failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


### FILE MANAGEMENT ###

@router.get("/files")
async def list_files(
    request: Request,
    course_id: str = None,
    db: Session = Depends(get_db),
):
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")

    _user_id(request)

    try:
        files = list_course_files(db, course_id)
        return {"status": "success", "files": files}
    except Exception as e:
        logger.error(f"List files failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    request: Request,
    course_id: str = None,
    db: Session = Depends(get_db),
):
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")

    _user_id(request)

    try:
        deleted = delete_course_file(db, file_id, course_id)
        return {
            "status":         "success",
            "file_id":        file_id,
            "deleted_chunks": deleted,
        }
    except Exception as e:
        logger.error(f"Delete file failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}/status")
async def file_status(
    file_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _user_id(request)

    try:
        status = get_file_status(db, file_id)
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="File not found")
        return {"status": "success", "file": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File status failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


### HEALTH ###

@router.get("/health")
async def rag_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT COUNT(*) FROM rag_files"))
        return {"status": "ok", "rag": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

# Returns notes for this course that haven't been indexed into RAG yet.
@router.get("/notes-available")
async def notes_available_for_rag(
    request: Request,
    course_id: str,
    db: Session = Depends(get_db),
):
    user_id = _user_id(request)

    notes = (
        db.query(Note)
        .filter(Note.course_id == course_id)
        .all()
    )

    indexed_drive_ids = {
        f.drive_file_id
        for f in db.query(RAGFile).filter(
            RAGFile.course_id == course_id,
            RAGFile.drive_file_id.isnot(None),
        ).all()
    }

    return [
        {
            "note_id":        n.id,
            "filename":       n.filename,
            "drive_file_id":  n.drive_file_id,
            "drive_view_link": n.drive_view_link,
            "already_indexed": n.drive_file_id in indexed_drive_ids,
        }
        for n in notes
        if n.drive_file_id not in indexed_drive_ids
    ]

# Index a file that already exists in the Notes feature into RAG.
@router.post("/index-from-notes")
async def index_from_notes(
    request: Request,
    body: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user_id      = _user_id(request)
    note_id      = body.get("note_id")
    course_id    = body.get("course_id")
    access_token = request.session.get("access_token")

    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    try:
        file_bytes, local_path = await _get_note_file_bytes(note, access_token)
    except Exception as exc:
        logger.error(f"Could not load note file for indexing: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Could not load note file: {exc}")

    if local_path and note.local_path != local_path:
        note.local_path = local_path
        db.commit()

    file_id = str(uuid.uuid4())
    _create_processing_file(
        db=db,
        file_id=file_id,
        course_id=course_id,
        user_id=user_id,
        filename=note.filename,
        drive_file_id=note.drive_file_id,
        local_path=local_path,
        file_size=len(file_bytes),
        source_type="notes",
    )

    background_tasks.add_task(
        _index_bytes_in_background,
        file_id=file_id,
        file_bytes=file_bytes,
        filename=note.filename,
        course_id=course_id,
        user_id=user_id,
        drive_file_id=note.drive_file_id,
        local_path=local_path,
    )
    return {"status": "indexing_started", "note_id": note_id, "file_id": file_id}

# Push a locally-uploaded RAG file into the Notes feature.
@router.post("/send-to-notes")
async def send_to_notes(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
):
    user_id      = _user_id(request)
    file_id      = body.get("file_id")
    course_id    = body.get("course_id")
    access_token = request.session.get("access_token")

    rag_file = db.query(RAGFile).filter(
        RAGFile.id == file_id,
        RAGFile.course_id == course_id,
    ).first()
    if not rag_file:
        raise HTTPException(status_code=404, detail="RAG file not found")
    if rag_file.drive_file_id:
        return {"status": "already_in_notes", "drive_file_id": rag_file.drive_file_id}

    try:
        drive_result = None
        local_path = rag_file.local_path

        if local_path and access_token:
            from app.services.google_oauth import (
                get_or_create_sars_folder,
                upload_file_to_drive,
            )
            file_bytes = Path(local_path).read_bytes()
            folder_id = get_or_create_sars_folder(access_token=access_token)
            drive_result = upload_file_to_drive(
                access_token=access_token,
                file_bytes=file_bytes,
                filename=rag_file.filename,
                subject=course_id,
                folder_id=folder_id,
            )
            rag_file.drive_file_id = drive_result["drive_file_id"]
            db.commit()
        elif not local_path:
            raise HTTPException(
                status_code=400,
                detail="This older RAG file has no saved original file. Re-upload it once, then Add to Notes will work.",
            )

        note = Note(
            course_id       = course_id,
            user_id         = user_id,
            filename        = rag_file.filename,
            drive_file_id   = drive_result["drive_file_id"] if drive_result else None,
            drive_view_link = drive_result["drive_view_link"] if drive_result else None,
            local_path      = local_path if not drive_result else None,
        )
        db.add(note)
        db.commit()

        return {
            "status": "success",
            "drive_file_id": drive_result["drive_file_id"] if drive_result else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Update labels on a RAG file.
@router.patch("/files/{file_id}/labels")
async def update_labels(
    file_id: str,
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
):
    _user_id(request)
    labels = body.get("labels", [])

    rag_file = db.query(RAGFile).filter(RAGFile.id == file_id).first()
    if not rag_file:
        raise HTTPException(status_code=404, detail="File not found")

    rag_file.labels = labels
    db.commit()
    return {"status": "success", "labels": labels}
