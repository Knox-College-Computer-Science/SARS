import time
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Channel, Course, CourseEnrollment, User
from security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

# In-memory OAuth state store (avoids cross-domain session cookie issues)
_oauth_states: dict[str, float] = {}       # state -> created_at
_session_handshakes: dict[str, dict] = {}  # token -> {data, ts}

def _store_oauth_state(state: str):
    _oauth_states[state] = time.time()
    cutoff = time.time() - 600
    for k in list(_oauth_states):
        if _oauth_states[k] < cutoff:
            del _oauth_states[k]

def _verify_oauth_state(state: str) -> bool:
    ts = _oauth_states.pop(state, None)
    return ts is not None and (time.time() - ts) < 600

def _create_handshake(data: dict) -> str:
    token = secrets.token_urlsafe(32)
    _session_handshakes[token] = {"data": data, "ts": time.time()}
    return token

def _consume_handshake(token: str):
    entry = _session_handshakes.pop(token, None)
    if entry is None or (time.time() - entry["ts"]) > 60:
        return None
    return entry["data"]

def _get_initials(name: str) -> str:
    parts = name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _upsert_user(db: Session, email: str, name: str) -> User:
    user = db.query(User).filter(User.school_email == email).first()
    if not user:
        user = User(
            school_email=email,
            display_name=name,
            initials=_get_initials(name),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _simplify_user(user_info: dict) -> dict:
    return {
        "name": user_info.get("name"),
        "email": user_info.get("email"),
    }


def _simplify_courses(courses_data: dict) -> list:
    raw_courses = courses_data.get("courses", [])
    result = []
    for course in raw_courses:
        result.append({
            "id": course.get("id"),
            "name": course.get("name"),
            "section": course.get("section"),
            "subject": course.get("subject"),
            "calendarId": course.get("calendarId"),
            "courseState": course.get("courseState"),
        })
    return result


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.display_name,
        "initials": user.initials,
        "email": user.school_email,
    }


def _serialize_course(course: Course) -> dict:
    return {
        "id": course.id,
        "school_course_id": course.school_course_id,
        "name": course.name,
        "course_code": course.course_code,
        "teacher_name": course.teacher_name,
        "term": course.term,
    }


@router.get("/google/login")
def google_login(request: Request):
    from app.config import GOOGLE_CLIENT_ID
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID in .env")

    from app.services.google_oauth import generate_state, build_google_auth_url
    state = generate_state()
    _store_oauth_state(state)
    auth_url = build_google_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    if not state or not _verify_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    from app.services.google_oauth import (
        exchange_code_for_tokens,
        get_user_info,
        get_classroom_courses,
    )

    token_data = exchange_code_for_tokens(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")

    user_info = get_user_info(access_token)

    try:
        courses_data = get_classroom_courses(access_token)
        cleaned_courses = _simplify_courses(courses_data)
    except Exception as exc:
        cleaned_courses = [{"error": str(exc)}]

    cleaned_user = _simplify_user(user_info)

    # Register this Google user in the chat database
    db_user = _upsert_user(db, email=cleaned_user["email"], name=cleaned_user["name"])
    nexus_token = create_access_token(db_user.id)

    from app.config import FRONTEND_URL
    handshake = _create_handshake({
        "user": cleaned_user,
        "access_token": access_token,
        "nexus_token": nexus_token,
        "nexus_user_id": db_user.id,
    })
    return RedirectResponse(url=f"{FRONTEND_URL}/connect?session_token={handshake}&connected=true")


@router.get("/session/restore")
def restore_session(request: Request, token: str):
    data = _consume_handshake(token)
    if not data:
        raise HTTPException(status_code=400, detail="Invalid or expired session token")
    request.session["user"] = data["user"]
    request.session["access_token"] = data["access_token"]
    request.session["nexus_token"] = data["nexus_token"]
    request.session["nexus_user_id"] = data["nexus_user_id"]
    return {"ok": True}


@router.get("/google/me")
def get_google_me(request: Request):
    user = request.session.get("user")
    access_token = request.session.get("access_token")

    if not user or not access_token:
        raise HTTPException(status_code=401, detail="Not connected to Google Classroom")

    return {
        "user": user,
        "has_access_token": True,
    }

class SchoolLaunchRequest(BaseModel):
    course_id: str
    token: str

@router.post("/google/disconnect")
def google_disconnect(request: Request):
    request.session.pop("user", None)
    request.session.pop("access_token", None)
    request.session.pop("courses", None)
    request.session.pop("nexus_token", None)
    request.session.pop("nexus_user_id", None)
    request.session.pop("oauth_state", None)

    return {
        "message": "Google Classroom disconnected successfully!"
    }


@router.post("/school-launch")
def school_launch(body: SchoolLaunchRequest, request: Request, db: Session = Depends(get_db)):
    # Prefer the OAuth-authenticated user if available
    session_user = request.session.get("user")
    if session_user:
        email = session_user.get("email", "demo.student@school.edu")
        name = session_user.get("name", "Test Student")
        initials = _get_initials(name)
    else:
        email = "demo.student@school.edu"
        name = "Test Student"
        initials = "TS"

    user = db.query(User).filter(User.school_email == email).first()
    if not user:
        user = User(school_email=email, display_name=name, initials=initials)
        db.add(user)
        db.flush()

    course = db.query(Course).filter(Course.school_course_id == body.course_id).first()
    if not course:
        course = Course(
            school_course_id=body.course_id,
            name="Introduction to Chemistry",
            course_code=body.course_id,
            teacher_name="Dr. Martinez",
            term="Spring 2026",
        )
        db.add(course)
        db.flush()

    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.user_id == user.id,
        )
        .first()
    )
    if not enrollment:
        db.add(CourseEnrollment(course_id=course.id, user_id=user.id, role="student"))

    db.commit()
    db.refresh(user)
    db.refresh(course)

    return {
        "token": create_access_token(user.id),
        "user": _serialize_user(user),
        "course": _serialize_course(course),
    }


@router.post("/sync-courses")
def sync_courses(request: Request, db: Session = Depends(get_db)):
    from app.routes.classroom import get_courses_from_google
    from app.services.knox_calendar import get_current_knox_term

    session_user = request.session.get("user")
    nexus_token = request.session.get("nexus_token")

    if not session_user:
        raise HTTPException(status_code=401, detail="Not connected to Google Classroom")

    user = db.query(User).filter(User.school_email == session_user.get("email")).first()
    if not user:
        user = User(
            school_email=session_user.get("email", ""),
            display_name=session_user.get("name", ""),
            initials=_get_initials(session_user.get("name", "")),
        )
        db.add(user)
        db.flush()

    user_id = user.id

    if not nexus_token:
        nexus_token = create_access_token(user_id)
        request.session["nexus_token"] = nexus_token
        request.session["nexus_user_id"] = user_id

    google_courses = get_courses_from_google(request)
    current_term = get_current_knox_term() or "Spring 2026"

    synced_courses = []
    for google_course in google_courses:
        google_course_id = google_course.get("id")
        course_name = google_course.get("name", "")
        section = google_course.get("section", "")
        creation_time = google_course.get("creationTime", "")

        # Use section as term label if set; otherwise fall back to creation year
        if section:
            term = section
        elif creation_time:
            term = creation_time[:4]
        else:
            term = current_term

        if not google_course_id:
            continue

        course = db.query(Course).filter(Course.school_course_id == google_course_id).first()
        if not course:
            course = Course(
                school_course_id=google_course_id,
                name=course_name,
                course_code=section or google_course_id,
                teacher_name="",
                term=term,
            )
            db.add(course)
            db.flush()
            db.add(Channel(course_id=course.id, name="general", channel_type="general", position=0))
            db.add(Channel(course_id=course.id, name="announcements", channel_type="announcements", position=1))
            db.flush()

        course_id = course.id
        course_data = _serialize_course(course)

        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.user_id == user_id,
            )
            .first()
        )
        if not enrollment:
            db.add(CourseEnrollment(course_id=course_id, user_id=user_id, role="student"))

        synced_courses.append(course_data)

    db.commit()

    serialized_user = {
        "id": user_id,
        "name": session_user.get("name", ""),
        "initials": _get_initials(session_user.get("name", "")),
        "email": session_user.get("email", ""),
    }

    return {
        "token": nexus_token,
        "user": serialized_user,
        "courses": synced_courses,
    }


@router.get("/session")
def get_session(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.school_course_id == course_id).first()
    if not course:
        return {"user": _serialize_user(current_user), "course": None}
    return {
        "user": _serialize_user(current_user),
        "course": _serialize_course(course),
    }