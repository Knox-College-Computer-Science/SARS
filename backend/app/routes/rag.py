from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.file_ingestion import save_uploaded_file

router = APIRouter(prefix="/rag", tags=["RAG"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    save_dict = save_uploaded_file(file)
    return{
        "file": save_dict,
    }

