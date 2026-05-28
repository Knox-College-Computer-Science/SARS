from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import Todo

router = APIRouter(prefix="/todos", tags=["todos"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TodoCreate(BaseModel):
    text: str
    category: str = "Personal"

class TodoUpdate(BaseModel):
    done:     Optional[bool] = None
    text:     Optional[str]  = None
    category: Optional[str]  = None


# ── Helper ────────────────────────────────────────────────────────────────────

def require_user(request: Request) -> int:
    user_id = request.session.get("nexus_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def get_todos(
    request: Request,
    db:      Session = Depends(get_db),
):
    user_id = require_user(request)
    return db.query(Todo).filter(Todo.user_id == user_id).order_by(Todo.created_at).all()


@router.post("/")
def create_todo(
    request: Request,
    body:    TodoCreate,
    db:      Session = Depends(get_db),
):
    user_id = require_user(request)
    todo = Todo(text=body.text, category=body.category, user_id=user_id)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


@router.patch("/{todo_id}")
def update_todo(
    todo_id: int,
    request: Request,
    body:    TodoUpdate,
    db:      Session = Depends(get_db),
):
    user_id = require_user(request)
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    if todo.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your todo")

    if body.done     is not None: todo.done     = body.done
    if body.text     is not None: todo.text     = body.text
    if body.category is not None: todo.category = body.category
    db.commit()
    db.refresh(todo)
    return todo


@router.delete("/{todo_id}")
def delete_todo(
    todo_id: int,
    request: Request,
    db:      Session = Depends(get_db),
):
    user_id = require_user(request)
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    if todo.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your todo")

    db.delete(todo)
    db.commit()
    return {"ok": True}