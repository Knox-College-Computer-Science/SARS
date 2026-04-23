from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import socketio

from app.config import SESSION_SECRET
from app.routes.auth import router as auth_router
from app.routes.classroom import router as classroom_router
from app.routes.channels import router as channels_router
from app.routes.messages import router as messages_router
from app.routes.conversations import router as conversations_router
from app.routes.notes import router as notes_router

from database import engine, Base, init_db
from socket_manager import sio

# Create all DB tables and seed demo data on startup
Base.metadata.create_all(bind=engine)
init_db()

app = FastAPI(title="SARS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


@app.get("/")
def root():
    return {"message": "SARS API running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# Wrap FastAPI with socket.io — run with:
# uvicorn app.main:socket_app --reload --port 8000
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
