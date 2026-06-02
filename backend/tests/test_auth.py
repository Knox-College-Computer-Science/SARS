import pytest


### SCHOOL LAUNCH ###

def test_school_launch_creates_user_and_returns_token(client, db):
    res = client.post("/auth/school-launch", json={"course_id": "CHEM101", "token": "x"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["token"].startswith("demo-token:")
    assert data["user"]["email"] == "demo.student@school.edu"


def test_school_launch_creates_course_if_not_exists(client, db):
    res = client.post("/auth/school-launch", json={"course_id": "NEW999", "token": "x"})
    assert res.status_code == 200
    assert res.json()["course"]["school_course_id"] == "NEW999"


def test_school_launch_is_idempotent(client, db):
    # Calling twice with the same course_id should not fail or duplicate
    client.post("/auth/school-launch", json={"course_id": "CHEM101", "token": "x"})
    res = client.post("/auth/school-launch", json={"course_id": "CHEM101", "token": "x"})
    assert res.status_code == 200


### SESSION ###

def test_get_session_returns_user_and_course(client, users, course, alice_headers):
    res = client.get(
        f"/auth/session?course_id={course['course'].school_course_id}",
        headers=alice_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == "alice@test.edu"
    assert data["course"]["school_course_id"] == "CS101"


def test_get_session_returns_null_course_for_unknown_id(client, users, alice_headers):
    res = client.get("/auth/session?course_id=DOESNOTEXIST", headers=alice_headers)
    assert res.status_code == 200
    assert res.json()["course"] is None


def test_get_session_requires_auth(client):
    res = client.get("/auth/session?course_id=CS101")
    assert res.status_code == 401


### GOOGLE DISCONNECT ###

def test_disconnect_clears_session(client):
    res = client.post("/auth/google/disconnect")
    assert res.status_code == 200
    assert "disconnected" in res.json()["message"].lower()


### GOOGLE ME ###

def test_google_me_returns_401_when_not_connected(client):
    res = client.get("/auth/google/me")
    assert res.status_code == 401
