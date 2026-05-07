from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User


TOKEN_PREFIX = "demo-token:"


def create_access_token(user_id: str) -> str:
    return f"{TOKEN_PREFIX}{user_id}"


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid authorization token")

    user_id = token.removeprefix(TOKEN_PREFIX)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found for token")

    return user
