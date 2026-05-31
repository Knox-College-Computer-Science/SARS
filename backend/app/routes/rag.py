import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from app.rag.pipeline import ingest, query, list_course_files, delete_course_file, get_file_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


### AUTH HELPER ###

def _user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
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
async def health(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection failed")