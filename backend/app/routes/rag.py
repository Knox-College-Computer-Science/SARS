import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from models import Note
from app.rag.pipeline import ingest, query, list_course_files, delete_course_file, get_file_status
from app.rag.models import RAGFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


### AUTH HELPER ###

def _user_id(request: Request) -> str:
    user_id = request.session.get("nexus_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


### UPLOAD ###

@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    course_id: str = Form(...),
    db: Session = Depends(get_db),
):
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")

    user_id = _user_id(request)

    try:
        file_bytes = await file.read()

        result = ingest(
            db         = db,
            file_bytes = file_bytes,
            filename   = file.filename or "unknown",
            course_id  = course_id,
            user_id    = user_id,
        )

        if result.status == "duplicate":
            return {
                "status":   "duplicate",
                "filename": result.filename,
                "message":  "This file has already been indexed",
            }

        if result.status == "error":
            return {
                "status":   "error",
                "filename": result.filename,
                "error":    result.error or "Unknown error",
            }

        return {
            "status":           "success",
            "file_id":          result.file_id,
            "filename":         result.filename,
            "retrieval_chunks": result.retrieval_chunks,
            "parent_chunks":    result.parent_chunks,
            "text_chunks":      result.text_chunks,
            "table_chunks":     result.table_chunks,
            "image_chunks":     result.image_chunks,
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

    async def _run():
        if note.drive_file_id and access_token:
            from app.rag.modules.drive_fetcher import fetch_file_bytes
            file_bytes, _ = await fetch_file_bytes(note.drive_file_id, access_token)
        elif note.local_path:
            file_bytes = Path(note.local_path).read_bytes()
        else:
            raise ValueError("No file source available")

        ingest(
            db            = db,
            file_bytes    = file_bytes,
            filename      = note.filename,
            course_id     = course_id,
            user_id       = user_id,
            drive_file_id = note.drive_file_id,
        )

    background_tasks.add_task(_run)
    return {"status": "indexing_started", "note_id": note_id}

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

    if not rag_file.local_path:
        raise HTTPException(status_code=400, detail="No local file available to push")

    try:
        from app.services.google_oauth import (
            get_or_create_sars_folder,
            upload_file_to_drive,
        )
        file_bytes  = Path(rag_file.local_path).read_bytes()
        folder_id   = get_or_create_sars_folder(access_token=access_token)
        drive_result = upload_file_to_drive(
            access_token = access_token,
            file_bytes   = file_bytes,
            filename     = rag_file.filename,
            subject      = course_id,
            folder_id    = folder_id,
        )
        rag_file.drive_file_id = drive_result["drive_file_id"]
        db.commit()

        note = Note(
            course_id       = course_id,
            user_id         = user_id,
            filename        = rag_file.filename,
            drive_file_id   = drive_result["drive_file_id"],
            drive_view_link = drive_result["drive_view_link"],
        )
        db.add(note)
        db.commit()

        return {"status": "success", "drive_file_id": drive_result["drive_file_id"]}

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