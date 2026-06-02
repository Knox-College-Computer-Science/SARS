import io
import pytest
import models


### HELPERS ###

def upload_note(client, course_id, user_id, filename="test.txt", content=b"Hello notes", cookies=None):
    return client.post(
        "/upload",
        data={"course_id": course_id, "subject": "Test Subject"},
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        cookies=cookies or {},
    )


### UPLOAD ###

def test_upload_note_requires_auth(client, course):
    res = upload_note(client, course["course"].id, "nobody")
    assert res.status_code == 401


def test_upload_note_succeeds_with_session(client, users, course, alice_cookies):
    res = upload_note(client, course["course"].id, users["alice"].id, cookies=alice_cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "test.txt"
    assert "note_id" in data


def test_upload_note_saves_to_db(client, users, course, alice_cookies, db):
    upload_note(client, course["course"].id, users["alice"].id, cookies=alice_cookies)
    count = db.query(models.Note).filter(models.Note.course_id == course["course"].id).count()
    assert count == 1


### GET NOTES ###

def test_get_notes_returns_empty_initially(client, course):
    res = client.get(f"/notes?course_id={course['course'].id}")
    assert res.status_code == 200
    assert res.json() == []


def test_get_notes_returns_uploaded_note(client, users, course, alice_cookies):
    upload_note(client, course["course"].id, users["alice"].id, cookies=alice_cookies)
    res = client.get(f"/notes?course_id={course['course'].id}")
    assert res.status_code == 200
    notes = res.json()
    assert len(notes) == 1
    assert notes[0]["filename"] == "test.txt"
    assert notes[0]["subject"] == "Test Subject"


def test_get_notes_filters_by_course(client, users, db, alice_cookies):
    # Create two courses, upload one note to each
    c1 = models.Course(school_course_id="C1", name="Course 1", course_code="C1", teacher_name="T")
    c2 = models.Course(school_course_id="C2", name="Course 2", course_code="C2", teacher_name="T")
    db.add_all([c1, c2])
    db.flush()

    upload_note(client, c1.id, users["alice"].id, filename="note1.txt", cookies=alice_cookies)
    upload_note(client, c2.id, users["alice"].id, filename="note2.txt", cookies=alice_cookies)

    res = client.get(f"/notes?course_id={c1.id}")
    notes = res.json()
    assert all(n["course_id"] == c1.id for n in notes)
    assert len(notes) == 1
