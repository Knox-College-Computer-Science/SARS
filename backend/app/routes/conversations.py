from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from database import get_db
from models import Conversation, ConversationParticipant, DirectMessage, User
from security import get_current_user
from socket_manager import sio

router = APIRouter()


def _serialize_msg(m: DirectMessage, sender: User) -> dict:
    return {
        "id":              m.id,
        "conversation_id": m.conversation_id,
        "sender_id":       m.sender_id,
        "sender_name":     sender.display_name if sender else "Unknown",
        "sender_initials": sender.initials     if sender else "??",
        "content":         m.content,
        "sent_at":         m.sent_at.isoformat() if m.sent_at else None,
    }


@router.get("")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participant_rows = (
        db.query(ConversationParticipant)
        .filter(ConversationParticipant.user_id == current_user.id)
        .all()
    )

    result = []
    for p in participant_rows:
        conv = db.query(Conversation).filter(Conversation.id == p.conversation_id).first()
        if not conv:
            continue

        other = (
            db.query(ConversationParticipant)
            .filter(
                ConversationParticipant.conversation_id == p.conversation_id,
                ConversationParticipant.user_id != current_user.id,
            )
            .first()
        )
        if not other:
            continue

        other_user = db.query(User).filter(User.id == other.user_id).first()
        if not other_user:
            continue

        last_msg = (
            db.query(DirectMessage)
            .filter(
                DirectMessage.conversation_id == conv.id,
                DirectMessage.deleted_at == None,
            )
            .order_by(desc(DirectMessage.sent_at))
            .first()
        )

        result.append({
            "id": conv.id,
            "recipient": {
                "id":       other_user.id,
                "name":     other_user.display_name,
                "initials": other_user.initials,
            },
            "last_message":    last_msg.content[:60] if last_msg else None,
            "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        })

    result.sort(key=lambda x: x["last_message_at"] or "", reverse=True)
    return {"conversations": result}


class StartConversation(BaseModel):
    sender_id:    str
    recipient_id: str


@router.post("")
def get_or_create_conversation(body: StartConversation, db: Session = Depends(get_db)):
    sender_convs = (
        db.query(ConversationParticipant.conversation_id)
        .filter(ConversationParticipant.user_id == body.sender_id)
        .subquery()
    )
    shared = (
        db.query(ConversationParticipant.conversation_id)
        .filter(
            ConversationParticipant.user_id == body.recipient_id,
            ConversationParticipant.conversation_id.in_(sender_convs),
        )
        .first()
    )

    if shared:
        conv = db.query(Conversation).filter(Conversation.id == shared[0]).first()
    else:
        conv = Conversation()
        db.add(conv)
        db.flush()
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=body.sender_id))
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=body.recipient_id))
        db.commit()
        db.refresh(conv)

    recipient = db.query(User).filter(User.id == body.recipient_id).first()
    return {
        "conversation_id":    conv.id,
        "recipient_name":     recipient.display_name if recipient else "Unknown",
        "recipient_initials": recipient.initials     if recipient else "??",
        "recipient_id":       body.recipient_id,
    }


@router.get("/{conversation_id}/messages")
def get_dm_messages(conversation_id: str, limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.deleted_at == None,
        )
        .order_by(desc(DirectMessage.sent_at))
        .limit(limit)
        .all()
    )
    rows.reverse()

    result = []
    for m in rows:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        result.append(_serialize_msg(m, sender))

    return {"messages": result}


class SendDM(BaseModel):
    content:   str
    sender_id: str


@router.post("/{conversation_id}/messages", status_code=201)
async def send_dm(conversation_id: str, body: SendDM, db: Session = Depends(get_db)):
    if not body.content.strip():
        raise HTTPException(400, "Empty message")

    sender = db.query(User).filter(User.id == body.sender_id).first()
    if not sender:
        raise HTTPException(404, "User not found")

    msg = DirectMessage(
        conversation_id=conversation_id,
        sender_id=body.sender_id,
        content=body.content.strip(),
    )
    db.add(msg)

    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.last_message_at = msg.sent_at

    db.commit()
    db.refresh(msg)

    payload = _serialize_msg(msg, sender)
    await sio.emit("new_dm", payload, room=f"conversation:{conversation_id}")
    return payload
