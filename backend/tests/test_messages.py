import pytest
import models


### HELPERS ###

def send_msg(client, channel_id, sender_id, content, headers=None):
    return client.post(
        f"/channels/{channel_id}/messages",
        json={"content": content, "sender_id": sender_id},
        headers=headers or {},
    )


### GET MESSAGES ###

def test_get_messages_empty_channel(client, users, course):
    res = client.get(f"/channels/{course['general'].id}/messages")
    assert res.status_code == 200
    assert res.json()["messages"] == []


def test_get_messages_returns_sent_messages(client, users, course):
    send_msg(client, course["general"].id, users["alice"].id, "Hello world")
    res = client.get(f"/channels/{course['general'].id}/messages")
    assert res.status_code == 200
    msgs = res.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hello world"
    assert msgs[0]["sender_name"] == "Alice Smith"


def test_get_messages_returns_404_for_unknown_channel(client):
    res = client.get("/channels/nonexistent-id/messages")
    assert res.status_code == 404


### SEND MESSAGE ###

def test_send_message_returns_201(client, users, course):
    res = send_msg(client, course["general"].id, users["alice"].id, "Hi!")
    assert res.status_code == 201
    assert res.json()["content"] == "Hi!"


def test_send_message_rejects_empty_content(client, users, course):
    res = send_msg(client, course["general"].id, users["alice"].id, "   ")
    assert res.status_code == 400


def test_send_message_rejects_too_long(client, users, course):
    res = send_msg(client, course["general"].id, users["alice"].id, "x" * 2001)
    assert res.status_code == 400


### EDIT MESSAGE ###

def test_edit_message_updates_content(client, users, course):
    msg = send_msg(client, course["general"].id, users["alice"].id, "Original").json()
    res = client.patch(
        f"/channels/{course['general'].id}/messages/{msg['id']}",
        json={"content": "Edited", "sender_id": users["alice"].id},
    )
    assert res.status_code == 200
    assert res.json()["content"] == "Edited"
    assert res.json()["edited_at"] is not None


def test_edit_message_forbidden_for_other_user(client, users, course):
    msg = send_msg(client, course["general"].id, users["alice"].id, "Alice's msg").json()
    res = client.patch(
        f"/channels/{course['general'].id}/messages/{msg['id']}",
        json={"content": "Hack", "sender_id": users["bob"].id},
    )
    assert res.status_code == 403


### DELETE MESSAGE ###

def test_delete_message_soft_deletes(client, users, course):
    msg = send_msg(client, course["general"].id, users["alice"].id, "Delete me").json()
    res = client.request(
        "DELETE",
        f"/channels/{course['general'].id}/messages/{msg['id']}",
        json={"sender_id": users["alice"].id},
    )
    assert res.status_code == 204

    # Message should no longer appear in the channel
    msgs = client.get(f"/channels/{course['general'].id}/messages").json()["messages"]
    assert all(m["id"] != msg["id"] for m in msgs)


def test_delete_message_forbidden_for_other_user(client, users, course):
    msg = send_msg(client, course["general"].id, users["alice"].id, "Mine").json()
    res = client.request(
        "DELETE",
        f"/channels/{course['general'].id}/messages/{msg['id']}",
        json={"sender_id": users["bob"].id},
    )
    assert res.status_code == 403


### REACTIONS ###

def test_react_adds_reaction(client, users, course):
    msg = send_msg(client, course["general"].id, users["alice"].id, "React to me").json()
    res = client.post(
        f"/channels/{course['general'].id}/messages/{msg['id']}/react",
        json={"user_id": users["bob"].id, "emoji": "👍"},
    )
    assert res.status_code == 200
    assert "👍" in res.json()["reactions"]


def test_react_twice_removes_reaction(client, users, course):
    msg = send_msg(client, course["general"].id, users["alice"].id, "Toggle").json()
    url = f"/channels/{course['general'].id}/messages/{msg['id']}/react"
    payload = {"user_id": users["bob"].id, "emoji": "❤️"}
    client.post(url, json=payload)
    res = client.post(url, json=payload)
    assert res.status_code == 200
    assert "❤️" not in res.json()["reactions"]
