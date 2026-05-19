from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.services.google_oauth import get_all_announcements_for_courses
from app.services.google_oauth import get_all_assignments_for_courses
from app.services.google_oauth import get_all_materials_for_courses
from app.services.google_oauth import course_has_current_term_activity
from app.services.google_oauth import get_classroom_courses
from app.services.knox_calendar import get_current_knox_term
from app.services.knox_calendar import get_current_knox_term_info

import requests
import re
from datetime import datetime

router = APIRouter(prefix="/classroom", tags=["Classroom"])

def get_current_term_window():
    term_info = get_current_knox_term_info()

    term_name = term_info.get("term")
    start = term_info.get("start")
    end = term_info.get("end")

    if not term_name or not start or not end:
        return None, None, None

    term_start = datetime.strptime(start, "%Y-%m-%d").date()
    term_end = datetime.strptime(end, "%Y-%m-%d").date()

    return term_name, term_start, term_end


def course_matches_current_term(text: str, current_term: str) -> bool:
    season, year = current_term.split()

    patterns = [
        rf"\b{season}\s+{year}\b",
        rf"\b{season}\s+Term\s+{year}\b",
        rf"\b{year}\s+{season}\b",
    ]

    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def course_mentions_any_term(text: str) -> bool:
    patterns = [
        r"\b(Fall|Winter|Spring)\s+(Term\s+)?20\d{2}\b",
        r"\b20\d{2}\s+(Fall|Winter|Spring)\b",
    ]

    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def is_current_term_course(
    course: dict,
    access_token: str,
    current_term: str,
    term_start,
    term_end,
) -> bool:
    if course.get("courseState") != "ACTIVE":
        return False

    course_id = course.get("id")
    if not course_id:
        return False

    name = course.get("name") or ""
    section = course.get("section") or ""
    text = f"{name} {section}"

    if course_matches_current_term(text, current_term):
        return True

    if course_mentions_any_term(text):
        return False

    return course_has_current_term_activity(
        access_token,
        course_id,
        term_start,
        term_end,
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
    current_term, term_start, term_end = get_current_term_window()

    if not current_term or not term_start or not term_end:
        return []

    courses = []
    for course in raw_courses:
        try:
            if is_current_term_course(
                course,
                access_token,
                current_term,
                term_start,
                term_end,
            ):
                courses.append({
                    "id": course.get("id"),
                    "name": course.get("name"),
                    "section": course.get("section"),
                    "subject": course.get("subject"),
                    "calendarId": course.get("calendarId"),
                })

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                request.session.pop("access_token", None)

                raise HTTPException(
                    status_code=401,
                    detail="Google Classroom connection expired. Please reconnect."
                )

            continue

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

@router.get("/materials")
def get_materials(request: Request):
    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    courses = get_courses_from_google(request)
    access_token = request.session.get("access_token")
    materials = get_all_materials_for_courses(access_token, courses)

    return JSONResponse(content={
        "user": user,
        "materials": materials,
    })


@router.get("/term-info")
def get_term_info():
    return get_current_knox_term_info()