from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Course, CourseEnrollment, User
from security import create_access_token, get_current_user

router = APIRouter()


class SchoolLaunchRequest(BaseModel):
    course_id: str
    token: str


def serialize_user(user: User):
    return {
        "id": user.id,
        "name": user.display_name,
        "initials": user.initials,
        "email": user.school_email,
    }


def serialize_course(course: Course):
    return {
        "id": course.id,
        "school_course_id": course.school_course_id,
        "name": course.name,
        "course_code": course.course_code,
        "teacher_name": course.teacher_name,
        "term": course.term,
    }


@router.post("/school-launch")
def school_launch(body: SchoolLaunchRequest, db: Session = Depends(get_db)):
    demo_identity = {
        "school_email": "demo.student@school.edu",
        "display_name": "Test Student",
        "initials": "TS",
    }

    user = db.query(User).filter(User.school_email == demo_identity["school_email"]).first()

    if not user:
        user = User(
            school_email=demo_identity["school_email"],
            display_name=demo_identity["display_name"],
            initials=demo_identity["initials"],
        )
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
        db.add(
            CourseEnrollment(
                course_id=course.id,
                user_id=user.id,
                role="student",
            )
        )

    db.commit()
    db.refresh(user)
    db.refresh(course)

    return {
        "token": create_access_token(user.id),
        "user": serialize_user(user),
        "course": serialize_course(course),
    }


@router.get("/session")
def get_session(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.school_course_id == course_id).first()
    if not course:
        return {"user": serialize_user(current_user), "course": None}

    return {
        "user": serialize_user(current_user),
        "course": serialize_course(course),
    }
