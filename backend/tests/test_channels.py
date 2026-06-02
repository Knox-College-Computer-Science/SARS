import pytest


### GET CHANNELS ###
#
#def test_get_channels_returns_list(client, users, course, alice_headers):
 #   res = client.get(
  #      f"/courses/{course['course'].school_course_id}/channels",
   #     headers=alice_headers,
    #)
    #assert res.status_code == 200
    #data = res.json()
    #assert "channels" in data
    #names = [ch["name"] for ch in data["channels"]]
    #assert "general" in names
    #assert "announcements" in names


#def test_get_channels_returns_course_info(client, users, course, alice_headers):
 #   res = client.get(
  #      f"/courses/{course['course'].school_course_id}/channels",
#     headers=alice_headers,
 #   )
  #  assert res.status_code == 200
   # assert res.json()["course"]["name"] == "Intro to CS"


#def test_get_channels_requires_auth(client, course):
 #   res = client.get(f"/courses/{course['course'].school_course_id}/channels")
  #  assert res.status_code == 401


def test_get_channels_returns_404_for_unknown_course(client, alice_headers):
    res = client.get("/courses/DOESNOTEXIST/channels", headers=alice_headers)
    assert res.status_code == 404


#def test_get_channels_returns_403_when_not_enrolled(client, db, course):
 #   import models
  #  from security import create_access_token
   # outsider = models.User(school_email="outsider@test.edu", display_name="Out Sider", initials="OS")
    #db.add(outsider)
    #db.flush()
    #headers = {"Authorization": f"Bearer {create_access_token(outsider.id)}"}
    #res = client.get(
     #   f"/courses/{course['course'].school_course_id}/channels",
      #  headers=headers,
    #)
    #assert res.status_code == 403


### CREATE CHANNEL ###

#def test_create_channel_returns_new_channel(client, users, course, alice_headers):
 #   res = client.post(
  #      f"/courses/{course['course'].school_course_id}/channels",
   #     json={"name": "study-group"},
    #    headers=alice_headers,
    #)
    #assert res.status_code == 201
    #assert res.json()["name"] == "study-group"


#def test_create_channel_normalises_name(client, users, course, alice_headers):
 #   res = client.post(
  #      f"/courses/{course['course'].school_course_id}/channels",
   #     json={"name": "Study Group"},
    #    headers=alice_headers,
    #)
    #assert res.status_code == 201
    #assert res.json()["name"] == "study-group"


#def test_create_channel_rejects_duplicate(client, users, course, alice_headers):
 #   client.post(
  #      f"/courses/{course['course'].school_course_id}/channels",
   #     json={"name": "duplicate"},
    #    headers=alice_headers,
    #)
    #res = client.post(
     #   f"/courses/{course['course'].school_course_id}/channels",
      #  json={"name": "duplicate"},
       # headers=alice_headers,
    #)
    #assert res.status_code == 409


### GET MEMBERS ###

#def test_get_members_excludes_requesting_user(client, users, course, alice_headers):
 #   res = client.get(
  #      f"/courses/{course['course'].school_course_id}/members",
   #     headers=alice_headers,
    #)
    #assert res.status_code == 200
    #emails = [m["email"] for m in res.json()["members"]]
    #assert "alice@test.edu" not in emails
    #assert "bob@test.edu" in emails
