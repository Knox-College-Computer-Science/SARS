from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.services.google_oauth import get_all_announcements_for_courses
from app.services.google_oauth import get_all_assignments_for_courses
from app.services.google_oauth import get_classroom_courses
router = APIRouter(prefix="/classroom", tags=["Classroom"])


def get_courses_from_google(request: Request):
    access_token = request.session.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="No access token found in session")

    courses_data = get_classroom_courses(access_token)
    raw_courses = courses_data.get("courses", [])

    courses = []
    for course in raw_courses:
        if course.get("courseState") == "ACTIVE":
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
    access_token = request.session.get("access_token")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    if not access_token:
        raise HTTPException(status_code=401, detail="No access token found in session")

    courses_data = get_classroom_courses(access_token)

    raw_courses = courses_data.get("courses", [])
    courses = []

    for course in raw_courses:
        if course.get("courseState") == "ACTIVE":
            courses.append({
                "id": course.get("id"),
                "name": course.get("name"),
                "section": course.get("section"),
                "subject": course.get("subject"),
                "calendarId": course.get("calendarId"),
            })

    request.session["courses"] = courses

    return JSONResponse(content={
        "user": user,
        "courses": courses
    })


@router.get("/announcements")
def get_announcements(request: Request):
    user = request.session.get("user")
    access_token = request.session.get("access_token")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    courses = get_courses_from_google(request)

    announcements = get_all_announcements_for_courses(access_token, courses)

    return JSONResponse(content={
        "user": user,
        "announcements": announcements
    })

@router.get("/assignments")
def get_assignments(request: Request):
    user = request.session.get("user")
    access_token = request.session.get("access_token")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    courses = get_courses_from_google(request)

    assignments = get_all_assignments_for_courses(access_token, courses)

    return JSONResponse(content={
        "user": user,
        "assignments": assignments
    })