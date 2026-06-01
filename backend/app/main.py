from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.responses import JSONResponse

from app.config import SESSION_SECRET
from app.routes.auth import router as auth_router
from app.routes.classroom import router as classroom_router
from app.routes.channels import router as channels_router
from app.routes.messages import router as messages_router
from app.routes.conversations import router as conversations_router
from app.routes.notes import router as notes_router
from app.routes.rag import router as rag_router
from app.routes.todos import router as todos_router
from database import engine, Base, init_db, get_db

import socketio
from socket_manager import sio


# Create all DB tables and seed demo data on startup
Base.metadata.create_all(bind=engine)
init_db()

app = FastAPI(title="SARS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

app.include_router(auth_router)
app.include_router(classroom_router)
app.include_router(channels_router, prefix="/channels", tags=["channels"])
app.include_router(messages_router, tags=["messages"])
app.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
app.include_router(notes_router)
app.include_router(rag_router)
app.include_router(todos_router)

@app.get("/")
def root():
    return {"message": "SARS API running"}

@app.get("/health")
async def health(
    db: Session = Depends(get_db),
    deep: bool = False,
):
    checks = {}

    # Database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Gemini API
    google_key = os.getenv("GOOGLE_API_KEY")
    if not deep:
        checks["gemini"] = "ok" if google_key else "error: GOOGLE_API_KEY not set"
    else:
        try:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            genai.get_model("models/gemini-1.5-flash")
            checks["gemini"] = "ok"
        except Exception as e:
            checks["gemini"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ok" if all_ok else "degraded", "checks": checks}
    )

# Wrap FastAPI with socket.io — run with:
# uvicorn app.main:socket_app --reload --port 8000
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
