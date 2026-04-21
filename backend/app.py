from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import sqlite3
import os
import shutil

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ──────────────── DATABASE ────────────────
def init_db():
    conn = sqlite3.connect("notes.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            subject TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ──────────────── HOME ────────────────
@app.get("/")
def home():
    return {"message": "Backend is running!"}

# ──────────────── UPLOAD ────────────────
@app.post("/upload")
async def upload_note(file: UploadFile = File(...), subject: str = Form(...)):
    print(f"Received file: {file.filename}, subject: {subject}")

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = sqlite3.connect("notes.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notes (filename, subject) VALUES (?, ?)",
        (file.filename, subject)
    )
    conn.commit()
    conn.close()

    return {"message": "Uploaded successfully", "filename": file.filename}

# ──────────────── GET ALL NOTES ────────────────
@app.get("/notes")
def get_notes():
    try:
        conn = sqlite3.connect("notes.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, subject, upload_time FROM notes")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "filename": r[1], "subject": r[2], "upload_time": r[3]}
            for r in rows
        ]
    except Exception as e:
        print(f"ERROR: {e}")
        return {"error": str(e)}

# ──────────────── DOWNLOAD FILE ────────────────
@app.get("/files/{filename}")
def get_file(filename: str):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    return {"error": "File not found"}