from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/classroom", tags=["Classroom"])


@router.get("/courses")
def get_courses(request: Request):
    user = request.session.get("user")
    courses = request.session.get("courses")

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User is not logged in"
        )

    if courses is None:
        raise HTTPException(
            status_code=404,
            detail="No courses found in session"
        )

    return JSONResponse(
        content={
            "user": user,
            "courses": courses
        }
    )