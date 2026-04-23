from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.services.google_oauth import get_all_announcements_for_courses
from app.services.google_oauth import get_all_assignments_for_courses

router = APIRouter(prefix="/classroom", tags=["Classroom"])


@router.get("/courses")
def get_courses(request: Request):
    user = request.session.get("user")
    courses = request.session.get("courses")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    if courses is None:
        raise HTTPException(status_code=404, detail="No courses found in session")

    return JSONResponse(
        content={
            "user": user,
            "courses": courses
        }
    )


@router.get("/announcements")
def get_announcements(request: Request):
    user = request.session.get("user")
    courses = request.session.get("courses")
    access_token = request.session.get("access_token")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    if not courses:
        raise HTTPException(status_code=404, detail="No courses found in session")

    if not access_token:
        raise HTTPException(status_code=401, detail="No access token found in session")

    announcements = get_all_announcements_for_courses(access_token, courses)

    return JSONResponse(
        content={
            "user": user,
            "announcements": announcements
        }
    )

@router.get("/assignments")
def get_assignments(request: Request):
    user = request.session.get("user")
    courses = request.session.get("courses")
    access_token = request.session.get("access_token")

    if not user:
        raise HTTPException(status_code=401, detail="User is not logged in")

    if not courses:
        raise HTTPException(status_code=404, detail="No courses found in session")

    if not access_token:
        raise HTTPException(status_code=401, detail="No access token found in session")

    assignments = get_all_assignments_for_courses(access_token, courses)

    return JSONResponse(
        content={
            "user": user,
            "assignments": assignments
        }
    )