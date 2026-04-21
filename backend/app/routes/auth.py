from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.services.google_oauth import (
    generate_state,
    build_google_auth_url,
    exchange_code_for_tokens,
    get_user_info,
    get_classroom_courses,
)

router = APIRouter(prefix="/auth/google", tags=["Google Auth"])


def simplify_user(user_info: dict) -> dict:
    return {
        "name": user_info.get("name"),
        "email": user_info.get("email"),
    }


def simplify_courses(courses_data: dict) -> list:
    raw_courses = courses_data.get("courses", [])
    active_courses = []

    for course in raw_courses:
        if course.get("courseState") != "ACTIVE":
            continue

        active_courses.append(
            {
                "id": course.get("id"),
                "name": course.get("name"),
                "section": course.get("section"),
                "subject": course.get("subject"),
                "calendarId": course.get("calendarId"),
            }
        )

    return active_courses


@router.get("/login")
def google_login(request: Request):
    state = generate_state()
    request.session["oauth_state"] = state

    auth_url = build_google_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/callback")
def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    saved_state = request.session.get("oauth_state")
    if not saved_state or state != saved_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_data = exchange_code_for_tokens(code)
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")

    user_info = get_user_info(access_token)

    try:
        courses_data = get_classroom_courses(access_token)
        cleaned_courses = simplify_courses(courses_data)
    except Exception as exc:
        cleaned_courses = [{"error": str(exc)}]

    cleaned_user = simplify_user(user_info)

    request.session["user"] = cleaned_user
    request.session["tokens"] = token_data
    request.session["courses"] = cleaned_courses

    return JSONResponse(
        content={
            "message": "Google login successful",
            "user": cleaned_user,
            "courses": cleaned_courses,
        }
    )