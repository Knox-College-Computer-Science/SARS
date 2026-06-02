import pytest


def course_channels_url(course_id):
    return f"/channels/courses/{course_id}/channels"


def course_members_url(course_id):
    return f"/channels/courses/{course_id}/members"


### GET CHANNELS ###

def test_get_channels_returns_list(client, users, course, alice_headers):
    res = client.get(
        course_channels_url(course["course"].school_course_id),
        headers=alice_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "channels" in data
    names = [ch["name"] for ch in data["channels"]]
    assert "general" in names
    assert "announcements" in names


def test_get_channels_returns_course_info(client, users, course, alice_headers):
    res = client.get(
        course_channels_url(course["course"].school_course_id),
        headers=alice_headers,
    )
    assert res.status_code == 200
    assert res.json()["course"]["name"] == "Intro to CS"


def test_get_channels_requires_auth(client, course):
    res = client.get(course_channels_url(course["course"].school_course_id))
    assert res.status_code == 401


def test_get_channels_returns_404_for_unknown_course(client, alice_headers):
    res = client.get(course_channels_url("DOESNOTEXIST"), headers=alice_headers)
    assert res.status_code == 404


def test_get_channels_returns_403_when_not_enrolled(client, db, course):
    import models
    from security import create_access_token
    outsider = models.User(school_email="outsider@test.edu", display_name="Out Sider", initials="OS")
    db.add(outsider)
    db.flush()
    headers = {"Authorization": f"Bearer {create_access_token(outsider.id)}"}
    res = client.get(
        course_channels_url(course["course"].school_course_id),
        headers=headers,
    )
    assert res.status_code == 403


### CREATE CHANNEL ###

def test_create_channel_returns_new_channel(client, users, course, alice_headers):
    res = client.post(
        course_channels_url(course["course"].school_course_id),
        json={"name": "study-group"},
        headers=alice_headers,
    )
    assert res.status_code == 201
    assert res.json()["name"] == "study-group"


def test_create_channel_normalises_name(client, users, course, alice_headers):
    res = client.post(
        course_channels_url(course["course"].school_course_id),
        json={"name": "Study Group"},
        headers=alice_headers,
    )
    assert res.status_code == 201
    assert res.json()["name"] == "study-group"


def test_create_channel_rejects_duplicate(client, users, course, alice_headers):
    client.post(
        course_channels_url(course["course"].school_course_id),
        json={"name": "duplicate"},
        headers=alice_headers,
    )
    res = client.post(
        course_channels_url(course["course"].school_course_id),
        json={"name": "duplicate"},
        headers=alice_headers,
    )
    assert res.status_code == 409


### GET MEMBERS ###

def test_get_members_excludes_requesting_user(client, users, course, alice_headers):
    res = client.get(
        course_members_url(course["course"].school_course_id),
        headers=alice_headers,
    )
    assert res.status_code == 200
    emails = [m["email"] for m in res.json()["members"]]
    assert "alice@test.edu" not in emails
    assert "bob@test.edu" in emails
