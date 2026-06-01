from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.services.google_oauth import get_all_announcements_for_courses
from app.services.google_oauth import get_all_assignments_for_courses
from app.services.google_oauth import get_all_materials_for_courses
from app.services.google_oauth import course_has_current_term_activity
from app.services.google_oauth import get_classroom_courses
from app.services.knox_calendar import get_current_knox_term_info
from database import get_db
from models import Course

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

def serialize_course(course: dict) -> dict:
    return {
        "id": course.get("id"),
        "name": course.get("name"),
        "section": course.get("section"),
        "subject": course.get("subject"),
        "calendarId": course.get("calendarId"),
        "courseState": course.get("courseState"),
    }

def serialize_db_course(course: Course) -> dict:
    return {
        "id": course.school_course_id,
        "school_course_id": course.school_course_id,
        "name": course.name,
        "section": course.course_code,
        "subject": None,
        "calendarId": None,
        "courseState": "ACTIVE" if course.is_active else "ARCHIVED",
        "term": course.term,
        "is_active": course.is_active,
        "is_current_term": course.is_active,
    }

def split_db_courses(db: Session):
    courses = db.query(Course).order_by(Course.name).all()
    current_courses = [serialize_db_course(c) for c in courses if c.is_active]
    past_courses = [serialize_db_course(c) for c in courses if not c.is_active]
    return current_courses, past_courses

def enrich_google_course(course: dict, db_course: Course | None, is_current: bool) -> dict:
    result = serialize_course(course)
    if db_course:
        result["school_course_id"] = db_course.school_course_id
        result["section"] = db_course.course_code or result.get("section")
        result["term"] = db_course.term
        result["is_active"] = db_course.is_active
        result["is_current_term"] = db_course.is_active
        return result

    result["school_course_id"] = result.get("id")
    result["is_active"] = is_current
    result["is_current_term"] = is_current
    return result

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

@router.get("/courses/upload-options")
def get_upload_course_options(
    request: Request,
    db: Session = Depends(get_db),
):
    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

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

        current_courses, past_courses = split_db_courses(db)
        return JSONResponse(content={
            "user": user,
            "current_courses": current_courses,
            "past_courses": past_courses,
            "source": "database",
            "warning": "Failed to fetch Google Classroom courses; using synced local courses.",
        })

    raw_courses = courses_data.get("courses", [])
    current_term, term_start, term_end = get_current_term_window()

    db_courses = {
        course.school_course_id: course
        for course in db.query(Course).all()
    }

    current_courses = []
    past_courses = []
    seen_course_ids = set()

    for course in raw_courses:
        course_id = course.get("id")

        if not course_id or course_id in seen_course_ids:
            continue

        seen_course_ids.add(course_id)

        db_course = db_courses.get(course_id)

        try:
            if db_course:
                is_current = db_course.is_active
            elif current_term and term_start and term_end:
                is_current = is_current_term_course(
                    course,
                    access_token,
                    current_term,
                    term_start,
                    term_end,
                )
            else:
                is_current = course.get("courseState") == "ACTIVE"

            serialized = enrich_google_course(course, db_course, is_current)
            if is_current:
                current_courses.append(serialized)
            else:
                past_courses.append(serialized)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                request.session.pop("access_token", None)

                raise HTTPException(
                    status_code=401,
                    detail="Google Classroom connection expired. Please reconnect."
                )

            serialized = enrich_google_course(course, db_course, False)
            past_courses.append(serialized)

    current_courses.sort(key=lambda course: course.get("name") or "")
    past_courses.sort(key=lambda course: course.get("name") or "")

    return JSONResponse(content={
        "user": user,
        "current_courses": current_courses,
        "past_courses": past_courses,
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

@router.get("/materials/all")
def get_all_course_materials(request: Request):
    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

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

    all_courses = []
    seen_course_ids = set()

    for course in raw_courses:
        course_id = course.get("id")

        if not course_id or course_id in seen_course_ids:
            continue

        seen_course_ids.add(course_id)
        all_courses.append(serialize_course(course))

    materials = get_all_materials_for_courses(access_token, all_courses)

    return JSONResponse(content={
        "user": user,
        "materials": materials,
    })

@router.get("/term-info")
def get_term_info():
    return get_current_knox_term_info()