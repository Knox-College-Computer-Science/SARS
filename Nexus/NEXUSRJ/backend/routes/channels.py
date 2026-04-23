from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Channel, ChannelMessage, Course, CourseEnrollment, User
from security import get_current_user

router = APIRouter()


# ------------------------------------------------------------------
# GET /channels/courses/{course_id}/channels
# ------------------------------------------------------------------
@router.get("/courses/{course_id}/channels")
def get_course_channels(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.school_course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.user_id == current_user.id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    channels = (
        db.query(Channel)
        .filter(Channel.course_id == course.id, Channel.is_archived == False)
        .order_by(Channel.position)
        .all()
    )

    member_count = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.course_id == course.id)
        .count()
    )

    serialized = []
    for ch in channels:
        unread_count = (
            db.query(ChannelMessage)
            .filter(
                ChannelMessage.channel_id == ch.id,
                ChannelMessage.sender_id != current_user.id,
                ChannelMessage.deleted_at == None,
            )
            .count()
            if ch.channel_type == "announcements"
            else 0
        )
        serialized.append({
            "id":           ch.id,
            "name":         ch.name,
            "type":         ch.channel_type,
            "member_count": member_count,
            "unread_count": unread_count,
        })

    return {
        "course": {
            "id":               course.id,
            "school_course_id": course.school_course_id,
            "name":             course.name,
            "course_code":      course.course_code,
            "teacher_name":     course.teacher_name,
            "term":             course.term,
            "member_count":     member_count,
        },
        "channels": serialized,
    }


# ------------------------------------------------------------------
# GET /channels/courses/{course_id}/members
# ------------------------------------------------------------------
@router.get("/courses/{course_id}/members")
def get_course_members(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.school_course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollments = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.course_id == course.id)
        .all()
    )

    members = []
    for e in enrollments:
        user = db.query(User).filter(User.id == e.user_id).first()
        if user and user.id != current_user.id:
            members.append({
                "id":       user.id,
                "name":     user.display_name,
                "initials": user.initials,
                "email":    user.school_email,
                "role":     e.role,
            })

    return {"members": members}


# ------------------------------------------------------------------
# POST /channels/courses/{course_id}/channels  — create a channel
# ------------------------------------------------------------------
class CreateChannel(BaseModel):
    name: str
    channel_type: str = "custom"


@router.post("/courses/{course_id}/channels", status_code=201)
def create_channel(
    course_id: str,
    body: CreateChannel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.school_course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    name = body.name.strip().lower().replace(" ", "-")
    if not name:
        raise HTTPException(status_code=400, detail="Channel name required")

    existing = (
        db.query(Channel)
        .filter(Channel.course_id == course.id, Channel.name == name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Channel already exists")

    max_pos = db.query(Channel).filter(Channel.course_id == course.id).count()
    ch = Channel(
        course_id=course.id,
        name=name,
        channel_type=body.channel_type,
        position=max_pos,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)

    member_count = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.course_id == course.id)
        .count()
    )

    return {
        "id":           ch.id,
        "name":         ch.name,
        "type":         ch.channel_type,
        "member_count": member_count,
        "unread_count": 0,
    }


# ------------------------------------------------------------------
# GET /channels/{channel_id}/messages  — in messages.py
# ------------------------------------------------------------------
