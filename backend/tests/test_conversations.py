import pytest


### HELPERS ###

def create_conv(client, sender_id, recipient_id):
    return client.post(
        "/conversations",
        json={"sender_id": sender_id, "recipient_id": recipient_id},
    )


def send_dm(client, conv_id, sender_id, content):
    return client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": content, "sender_id": sender_id},
    )


### CREATE / GET CONVERSATION ###

def test_create_conversation_returns_id(client, users, alice_headers):
    res = create_conv(client, users["alice"].id, users["bob"].id)
    assert res.status_code == 200
    assert "conversation_id" in res.json()
    assert res.json()["recipient_name"] == "Bob Jones"


def test_create_conversation_is_idempotent(client, users, alice_headers):
    # Two calls with the same participants return the same conversation
    id1 = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
    id2 = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
    assert id1 == id2


### LIST CONVERSATIONS ###

def test_list_conversations_requires_auth(client):
    res = client.get("/conversations")
    assert res.status_code == 401


def test_list_conversations_returns_started_convs(client, users, alice_headers):
    create_conv(client, users["alice"].id, users["bob"].id)
    res = client.get("/conversations", headers=alice_headers)
    assert res.status_code == 200
    assert len(res.json()["conversations"]) >= 1


### SEND DM ###

def test_send_dm_returns_201(client, users):
    conv_id = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
    res = send_dm(client, conv_id, users["alice"].id, "Hey Bob!")
    assert res.status_code == 201
    assert res.json()["content"] == "Hey Bob!"
    assert res.json()["sender_name"] == "Alice Smith"


def test_send_dm_rejects_empty_content(client, users):
    conv_id = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
    res = send_dm(client, conv_id, users["alice"].id, "  ")
    assert res.status_code == 400


### GET DM MESSAGES ###

#def test_get_dm_messages_returns_sent(client, users):
 #   conv_id = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
  #  send_dm(client, conv_id, users["alice"].id, "First message")
   # send_dm(client, conv_id, users["bob"].id, "Second message")

    #res = client.get(f"/conversations/{conv_id}/messages")
   # assert res.status_code == 200
    #msgs = res.json()["messages"]
    #assert len(msgs) == 2
    #assert msgs[0]["content"] == "First message"
    #assert msgs[1]["content"] == "Second message"


### DM REACTIONS ###

def test_dm_react_adds_reaction(client, users):
    conv_id = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
    msg = send_dm(client, conv_id, users["alice"].id, "React to this").json()

    res = client.post(
        f"/conversations/{conv_id}/messages/{msg['id']}/react",
        json={"user_id": users["bob"].id, "emoji": "🔥"},
    )
    assert res.status_code == 200
    assert "🔥" in res.json()["reactions"]


def test_dm_react_toggles_off(client, users):
    conv_id = create_conv(client, users["alice"].id, users["bob"].id).json()["conversation_id"]
    msg = send_dm(client, conv_id, users["alice"].id, "Toggle me").json()
    url = f"/conversations/{conv_id}/messages/{msg['id']}/react"
    payload = {"user_id": users["bob"].id, "emoji": "⭐"}
    client.post(url, json=payload)
    res = client.post(url, json=payload)
    assert res.status_code == 200
    assert "⭐" not in res.json()["reactions"]
