from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from database import engine, Base
from socket_manager import sio

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nexus API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routes import messages, channels, auth, conversations
app.include_router(auth.router,          prefix="/auth",         tags=["auth"])
app.include_router(channels.router,      prefix="/channels",     tags=["channels"])
app.include_router(messages.router,      prefix="",              tags=["messages"])
app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])

@app.get("/")
def root():
    return {"status": "Nexus API running"}

# Run with: uvicorn main:socket_app --reload --port 8000
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
