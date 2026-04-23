from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import ChannelMessage, MessageReaction, Channel, User
from socket_manager import sio

router = APIRouter()


def _serialize_message(m: ChannelMessage, db: Session) -> dict:
    sender = db.query(User).filter(User.id == m.sender_id).first()

    reaction_map: dict[str, dict] = {}
    for r in m.reactions:
        if r.emoji not in reaction_map:
            reaction_map[r.emoji] = {"count": 0, "users": []}
        reaction_map[r.emoji]["count"] += 1
        reaction_map[r.emoji]["users"].append(r.user_id)

    return {
        "id":              m.id,
        "channel_id":      m.channel_id,
        "sender_id":       m.sender_id,
        "sender_name":     sender.display_name if sender else "Unknown",
        "sender_initials": sender.initials     if sender else "??",
        "content":         m.content,
        "sent_at":         m.sent_at.isoformat() if m.sent_at else None,
        "edited_at":       m.edited_at.isoformat() if m.edited_at else None,
        "reply_to_id":     m.reply_to_id,
        "reactions":       reaction_map,
    }


@router.get("/channels/{channel_id}/messages")
def get_messages(channel_id: str, limit: int = 50, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")

    rows = (
        db.query(ChannelMessage)
        .filter(ChannelMessage.channel_id == channel_id, ChannelMessage.deleted_at == None)
        .order_by(desc(ChannelMessage.sent_at))
        .limit(limit)
        .all()
    )
    rows.reverse()

    return {
        "messages": [_serialize_message(m, db) for m in rows],
        "has_more": len(rows) == limit,
    }


class SendMsg(BaseModel):
    content:     str
    sender_id:   str
    reply_to_id: Optional[str] = None


@router.post("/channels/{channel_id}/messages", status_code=201)
async def send_message(channel_id: str, body: SendMsg, db: Session = Depends(get_db)):
    if not body.content.strip():
        raise HTTPException(400, "Empty message")
    if len(body.content) > 2000:
        raise HTTPException(400, "Message too long")

    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")

    sender = db.query(User).filter(User.id == body.sender_id).first()
    if not sender:
        raise HTTPException(404, "User not found")

    msg = ChannelMessage(
        channel_id=channel_id,
        sender_id=body.sender_id,
        content=body.content.strip(),
        reply_to_id=body.reply_to_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    payload = _serialize_message(msg, db)
    await sio.emit("new_channel_message", payload, room=f"channel:{channel_id}")
    return payload


class EditMsg(BaseModel):
    content:   str
    sender_id: str


@router.patch("/channels/{channel_id}/messages/{message_id}")
async def edit_message(
    channel_id: str,
    message_id: str,
    body: EditMsg,
    db: Session = Depends(get_db),
):
    msg = db.query(ChannelMessage).filter(
        ChannelMessage.id == message_id,
        ChannelMessage.channel_id == channel_id,
        ChannelMessage.deleted_at == None,
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.sender_id != body.sender_id:
        raise HTTPException(403, "Cannot edit another user's message")

    new_content = body.content.strip()
    if not new_content:
        raise HTTPException(400, "Empty content")

    msg.content = new_content
    msg.edited_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    payload = _serialize_message(msg, db)
    await sio.emit("message_edited", payload, room=f"channel:{channel_id}")
    return payload


class DeleteMsg(BaseModel):
    sender_id: str


@router.delete("/channels/{channel_id}/messages/{message_id}", status_code=204)
async def delete_message(
    channel_id: str,
    message_id: str,
    body: DeleteMsg,
    db: Session = Depends(get_db),
):
    msg = db.query(ChannelMessage).filter(
        ChannelMessage.id == message_id,
        ChannelMessage.channel_id == channel_id,
        ChannelMessage.deleted_at == None,
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.sender_id != body.sender_id:
        raise HTTPException(403, "Cannot delete another user's message")

    msg.deleted_at = datetime.now(timezone.utc)
    db.commit()

    await sio.emit(
        "message_deleted",
        {"message_id": message_id, "channel_id": channel_id},
        room=f"channel:{channel_id}",
    )


class ReactMsg(BaseModel):
    user_id: str
    emoji:   str


@router.post("/channels/{channel_id}/messages/{message_id}/react")
async def react_to_message(
    channel_id: str,
    message_id: str,
    body: ReactMsg,
    db: Session = Depends(get_db),
):
    msg = db.query(ChannelMessage).filter(
        ChannelMessage.id == message_id,
        ChannelMessage.channel_id == channel_id,
        ChannelMessage.deleted_at == None,
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")

    existing = db.query(MessageReaction).filter(
        MessageReaction.message_id == message_id,
        MessageReaction.user_id == body.user_id,
        MessageReaction.emoji == body.emoji,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
    else:
        db.add(MessageReaction(
            message_id=message_id,
            user_id=body.user_id,
            emoji=body.emoji,
        ))
        db.commit()

    db.refresh(msg)
    payload = _serialize_message(msg, db)
    await sio.emit("message_reacted", payload, room=f"channel:{channel_id}")
    return payload
