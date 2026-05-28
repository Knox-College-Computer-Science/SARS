from urllib.parse import urlencode
from datetime import date, datetime
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
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/drive.file",
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
    all_courses = []
    page_token = None

    while True:
        params = {
            "pageSize": 50,
            "courseStates": ["ACTIVE", "ARCHIVED"],
        }
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            "https://classroom.googleapis.com/v1/courses",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        all_courses.extend(data.get("courses", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return {"courses": all_courses}

def get_classroom_courses_for_upload_options(access_token: str) -> dict:
    """
    Returns all Google Classroom courses that can be used in the Upload Notes dropdown.

    This includes both ACTIVE and ARCHIVED courses so the backend can split them into:
    - current_courses
    - past_courses
    """
    return get_classroom_courses(access_token)

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
                        "alternateLink" : announcement.get("alternateLink"),
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

def parse_google_datetime(value: str):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_google_due_date(due_date: dict):
    if not due_date:
        return None

    try:
        return date(
            int(due_date["year"]),
            int(due_date["month"]),
            int(due_date["day"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def date_is_in_term(check_date, term_start: date, term_end: date) -> bool:
    return check_date is not None and term_start <= check_date <= term_end


def announcement_has_current_term_activity(
    announcement: dict,
    term_start: date,
    term_end: date,
) -> bool:
    creation_date = parse_google_datetime(announcement.get("creationTime"))
    update_date = parse_google_datetime(announcement.get("updateTime"))

    return (
        date_is_in_term(creation_date, term_start, term_end)
        or date_is_in_term(update_date, term_start, term_end)
    )


def assignment_has_current_term_activity(
    assignment: dict,
    term_start: date,
    term_end: date,
) -> bool:
    creation_date = parse_google_datetime(assignment.get("creationTime"))
    update_date = parse_google_datetime(assignment.get("updateTime"))
    due_date = parse_google_due_date(assignment.get("dueDate"))

    return (
        date_is_in_term(creation_date, term_start, term_end)
        or date_is_in_term(update_date, term_start, term_end)
        or date_is_in_term(due_date, term_start, term_end)
    )


def course_has_current_term_activity(
    access_token: str,
    course_id: str,
    term_start: date,
    term_end: date,
) -> bool:
    try:
        announcements_data = get_course_announcements(access_token, course_id)
        announcements = announcements_data.get("announcements", [])

        for announcement in announcements:
            if announcement_has_current_term_activity(
                announcement,
                term_start,
                term_end,
            ):
                return True

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise
    except Exception:
        pass

    try:
        coursework_data = get_course_coursework(access_token, course_id)
        assignments = coursework_data.get("courseWork", [])

        for assignment in assignments:
            if assignment_has_current_term_activity(
                assignment,
                term_start,
                term_end,
            ):
                return True

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise
    except Exception:
        pass

    return False

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


def get_course_materials(access_token: str, course_id: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"https://classroom.googleapis.com/v1/courses/{course_id}/courseWorkMaterials",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def get_all_materials_for_courses(access_token: str, courses: list) -> list:
    all_courses_materials = []

    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name")

        if not course_id:
            continue

        pdfs = []
        slides = []
        links = []

        try:
            response_data = get_course_materials(access_token, course_id)
            materials_list = response_data.get("courseWorkMaterial", [])

            for material_item in materials_list:
                for mat in material_item.get("materials", []):
                    drive_file_wrapper = mat.get("driveFile", {})
                    drive_file = drive_file_wrapper.get("driveFile", {}) if drive_file_wrapper else {}
                    link = mat.get("link", {})

                    if drive_file:
                        mime = drive_file.get("mimeType", "")
                        title = drive_file.get("title", "Untitled")
                        url = drive_file.get("alternateLink", "")

                        if "pdf" in mime.lower():
                            pdfs.append({"title": title, "url": url, "type": "pdf"})
                        elif "presentation" in mime.lower():
                            slides.append({"title": title, "url": url, "type": "slides"})
                        else:
                            links.append({"title": title, "url": url, "type": "drive"})

                    if link:
                        url = link.get("url", "")
                        title = link.get("title", url)
                        links.append({"title": title, "url": url, "type": "link"})

        except Exception as e:
            print(f"Failed to fetch materials for course {course_name} ({course_id}): {e}")

        all_courses_materials.append({
            "courseId": course_id,
            "courseName": course_name,
            "pdfs": pdfs,
            "slides": slides,
            "links": links,
        })

    return all_courses_materials

def get_or_create_sars_folder(access_token: str) -> str:
    """
    Returns the Drive folder ID for 'SARS App Notes'.
    Creates the folder if it doesn't exist yet.
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    creds = Credentials(token=access_token)
    service = build("drive", "v3", credentials=creds)

    FOLDER_NAME = "SARS App Notes"

    # Check if folder already exists so we don't create duplicates
    results = service.files().list(
        q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
        spaces="drive",
    ).execute()

    files = results.get("files", [])
    if files:
        return files[0]["id"]  # Folder already exists, reuse it

    # Create the folder
    folder_metadata = {
        "name": FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(
        body=folder_metadata,
        fields="id",
    ).execute()

    return folder["id"]


def upload_file_to_drive(
    access_token: str,
    file_bytes: bytes,
    filename: str,
    subject: str,
    folder_id: str = None,       # ← new param
) -> dict:
    import io
    import mimetypes
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2.credentials import Credentials

    creds = Credentials(token=access_token)
    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": filename,
        "description": f"Class notes - {subject}",
    }

    # Place inside the SARS folder if we have one
    if folder_id:
        file_metadata["parents"] = [folder_id]

    # Detect mimetype instead of hardcoding PDF
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()

    # Make viewable by anyone with the link
    service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return {
        "drive_file_id": uploaded["id"],
        "drive_view_link": uploaded["webViewLink"],
        "filename": uploaded["name"],
    }