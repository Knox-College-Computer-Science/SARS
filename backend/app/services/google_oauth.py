from urllib.parse import urlencode
import secrets
import requests

from app.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
]


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def build_google_auth_url(state: str) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=20)
    response.raise_for_status()
    return response.json()


def get_user_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


def get_classroom_courses(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        "https://classroom.googleapis.com/v1/courses",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()

def get_course_announcements(access_token: str, course_id: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"https://classroom.googleapis.com/v1/courses/{course_id}/announcements",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def get_all_announcements_for_courses(access_token: str, courses: list) -> list:
    all_announcements = []

    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name")

        if not course_id:
            continue

        try:
            response_data = get_course_announcements(access_token, course_id)
            announcements = response_data.get("announcements", [])

            for announcement in announcements:
                all_announcements.append(
                    {
                        "courseId": course_id,
                        "courseName": course_name,
                        "id": announcement.get("id"),
                        "text": announcement.get("text"),
                        "creationTime": announcement.get("creationTime"),
                        "updateTime": announcement.get("updateTime"),
                    }
                )
        except Exception:
            continue

    return all_announcements

def get_course_coursework(access_token: str, course_id: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"https://classroom.googleapis.com/v1/courses/{course_id}/courseWork",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def format_due_datetime(due_date: dict, due_time: dict) -> dict:
    return {
        "dueDate": due_date if due_date else None,
        "dueTime": due_time if due_time else None,
    }


def get_all_assignments_for_courses(access_token: str, courses: list) -> list:
    all_assignments = []

    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name")

        if not course_id:
            continue

        try:
            response_data = get_course_coursework(access_token, course_id)
            assignments = response_data.get("courseWork", [])

            for assignment in assignments:
                due_info = format_due_datetime(
                    assignment.get("dueDate"),
                    assignment.get("dueTime"),
                )

                all_assignments.append(
                    {
                        "courseId": course_id,
                        "courseName": course_name,
                        "id": assignment.get("id"),
                        "title": assignment.get("title"),
                        "description": assignment.get("description"),
                        "workType": assignment.get("workType"),
                        "state": assignment.get("state"),
                        "creationTime": assignment.get("creationTime"),
                        "updateTime": assignment.get("updateTime"),
                        "dueDate": due_info["dueDate"],
                        "dueTime": due_info["dueTime"],
                        "alternateLink": assignment.get("alternateLink"),
                    }
                )
        except Exception as e:
            print(f"Failed for course {course_name} ({course_id}): {e}")
            continue

    return all_assignments