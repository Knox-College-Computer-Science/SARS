import pytest


### GET TODOS ###

def test_get_todos_returns_empty_list_initially(client, users, alice_cookies):
    res = client.get("/todos/", cookies=alice_cookies)
    assert res.status_code == 200
    assert res.json() == []


def test_get_todos_requires_auth(client):
    res = client.get("/todos/")
    assert res.status_code == 401


### CREATE TODO ###

def test_create_todo_returns_created_item(client, users, alice_cookies):
    res = client.post(
        "/todos/",
        json={"text": "Read chapter 5", "category": "Academic"},
        cookies=alice_cookies,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "Read chapter 5"
    assert data["category"] == "Academic"
    assert data["done"] is False


def test_create_todo_defaults_category_to_personal(client, users, alice_cookies):
    res = client.post("/todos/", json={"text": "Buy groceries"}, cookies=alice_cookies)
    assert res.status_code == 200
    assert res.json()["category"] == "Personal"


def test_create_todo_requires_auth(client):
    res = client.post("/todos/", json={"text": "No auth"})
    assert res.status_code == 401


### UPDATE TODO ###

def test_update_todo_marks_done(client, users, alice_cookies):
    todo = client.post("/todos/", json={"text": "Finish homework"}, cookies=alice_cookies).json()
    res  = client.patch(f"/todos/{todo['id']}", json={"done": True}, cookies=alice_cookies)
    assert res.status_code == 200
    assert res.json()["done"] is True


def test_update_todo_changes_text(client, users, alice_cookies):
    todo = client.post("/todos/", json={"text": "Old text"}, cookies=alice_cookies).json()
    res  = client.patch(f"/todos/{todo['id']}", json={"text": "New text"}, cookies=alice_cookies)
    assert res.status_code == 200
    assert res.json()["text"] == "New text"


def test_update_todo_returns_404_for_missing(client, users, alice_cookies):
    res = client.patch("/todos/99999", json={"done": True}, cookies=alice_cookies)
    assert res.status_code == 404

### ISOLATION ###

#def test_todos_are_user_scoped(client, users, alice_cookies):
 #   from conftest import make_session_cookie
  #  bob_cookies = {"session": make_session_cookie({"nexus_user_id": users["bob"].id})}
#
 #   client.post("/todos/", json={"text": "Alice's private task"}, cookies=alice_cookies)
  #  bob_todos = client.get("/todos/", cookies=bob_cookies).json()
   # assert all(t["text"] != "Alice's private task" for t in bob_todos)
