import socketio

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# Maps user_id -> sid and sid -> user_id for presence tracking
online_users: dict[str, str] = {}   # user_id -> sid
sid_to_user:  dict[str, str] = {}   # sid -> user_id
user_statuses: dict[str, str] = {}  # user_id -> "active" | "away" | "inactive"

_VALID_STATUSES = {"active", "away", "inactive"}


async def _broadcast_presence():
    await sio.emit("online_users", {"users": list(online_users.keys())})
    await sio.emit("user_statuses", {"statuses": dict(user_statuses)})


@sio.event
async def connect(sid, environ, auth):
    print(f"[socket] connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[socket] disconnected: {sid}")
    user_id = sid_to_user.pop(sid, None)
    if user_id:
        online_users.pop(user_id, None)
        user_statuses.pop(user_id, None)
        await _broadcast_presence()


@sio.event
async def user_auth(sid, data):
    user_id = data.get("user_id")
    if user_id:
        online_users[user_id] = sid
        sid_to_user[sid] = user_id
        user_statuses.setdefault(user_id, "active")
    await _broadcast_presence()


@sio.event
async def set_user_status(sid, data):
    user_id = sid_to_user.get(sid)
    status = data.get("status")
    if user_id and status in _VALID_STATUSES:
        user_statuses[user_id] = status
        await _broadcast_presence()


@sio.event
async def join_channel(sid, data):
    room = f"channel:{data['channel_id']}"
    await sio.enter_room(sid, room)


@sio.event
async def leave_channel(sid, data):
    room = f"channel:{data['channel_id']}"
    await sio.leave_room(sid, room)


@sio.event
async def join_conversation(sid, data):
    room = f"conversation:{data['conversation_id']}"
    await sio.enter_room(sid, room)


@sio.event
async def leave_conversation(sid, data):
    room = f"conversation:{data['conversation_id']}"
    await sio.leave_room(sid, room)


@sio.event
async def typing_start(sid, data):
    room = f"channel:{data['channel_id']}"
    await sio.emit("user_typing", {"name": data.get("name", "Someone"), "channel_id": data["channel_id"]}, room=room, skip_sid=sid)


@sio.event
async def typing_stop(sid, data):
    room = f"channel:{data['channel_id']}"
    await sio.emit("user_stopped_typing", {"channel_id": data["channel_id"]}, room=room, skip_sid=sid)


@sio.event
async def dm_typing_start(sid, data):
    room = f"conversation:{data['conversation_id']}"
    await sio.emit("dm_user_typing", {"name": data.get("name", "Someone"), "conversation_id": data["conversation_id"]}, room=room, skip_sid=sid)


@sio.event
async def dm_typing_stop(sid, data):
    room = f"conversation:{data['conversation_id']}"
    await sio.emit("dm_user_stopped_typing", {"conversation_id": data["conversation_id"]}, room=room, skip_sid=sid)
