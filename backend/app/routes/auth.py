from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Course, CourseEnrollment, User
from security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

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
    active_courses = []
    for course in raw_courses:
        if course.get("courseState") != "ACTIVE":
            continue
        active_courses.append({
            "id": course.get("id"),
            "name": course.get("name"),
            "section": course.get("section"),
            "subject": course.get("subject"),
            "calendarId": course.get("calendarId"),
        })
    return active_courses


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
    from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID in .env")

    from app.services.google_oauth import generate_state, build_google_auth_url
    state = generate_state()
    request.session["oauth_state"] = state
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

    saved_state = request.session.get("oauth_state")
    if not saved_state or state != saved_state:
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

    request.session["user"] = cleaned_user
    request.session["access_token"] = access_token
    request.session["nexus_token"] = nexus_token
    request.session["nexus_user_id"] = db_user.id

    return RedirectResponse(url="http://localhost:3000/connect?connected=true")


@router.get("/google/me")
def get_google_me(request: Request):
    return {
        "user": request.session.get("user"),
        "has_access_token": request.session.get("access_token") is not None,
        "courses": request.session.get("courses"),
    }

class SchoolLaunchRequest(BaseModel):
    course_id: str
    token: str


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
