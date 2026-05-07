from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.services.google_oauth import get_all_announcements_for_courses
from app.services.google_oauth import get_all_assignments_for_courses
from app.services.google_oauth import get_classroom_courses
from app.services.knox_calendar import get_current_knox_term
from app.services.knox_calendar import get_current_knox_term_info
import requests

router = APIRouter(prefix="/classroom", tags=["Classroom"])

def is_current_term_course(course: dict) -> bool:
    current_term = get_current_knox_term()

    if not current_term:
        return False

    name = course.get("name") or ""
    section = course.get("section") or ""

    return (
        course.get("courseState") == "ACTIVE"
        and (
            current_term.lower() in name.lower()
            or current_term.lower() in section.lower()
        )
    )

def get_courses_from_google(request: Request):
    access_token = request.session.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Google Classroom is not connected"
        )

    try:
        courses_data = get_classroom_courses(access_token)
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None

        request.session.pop("access_token", None)

        if status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Google Classroom connection expired. Please reconnect."
            )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch Google Classroom courses"
        )

    raw_courses = courses_data.get("courses", [])

    courses = []
    for course in raw_courses:
        if is_current_term_course(course):
            courses.append({
                "id": course.get("id"),
                "name": course.get("name"),
                "section": course.get("section"),
                "subject": course.get("subject"),
                "calendarId": course.get("calendarId"),
            })

    return courses

@router.get("/courses")
def get_courses(request: Request):
    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    courses = get_courses_from_google(request)

    return JSONResponse(content={
        "user": user,
        "courses": courses
    })

@router.get("/announcements")
def get_announcements(request: Request):
    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    courses = get_courses_from_google(request)
    access_token = request.session.get("access_token")
    announcements = get_all_announcements_for_courses(access_token, courses)

    return JSONResponse(content={
        "user": user,
        "announcements": announcements
    })

@router.get("/assignments")
def get_assignments(request: Request):
    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    courses = get_courses_from_google(request)
    access_token = request.session.get("access_token")
    assignments = get_all_assignments_for_courses(access_token, courses)

    return JSONResponse(content={
        "user": user,
        "assignments": assignments
    })

@router.get("/term-info")
def get_term_info():
    return get_current_knox_term_info()