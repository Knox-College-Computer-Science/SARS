const BASE = "http://localhost:8000";

async function req(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options;
  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function authHeader(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function normaliseMessage(m) {
  return {
    id:              m.id,
    channelId:       m.channel_id       ?? null,
    conversationId:  m.conversation_id  ?? null,
    senderId:        m.sender_id,
    senderName:      m.sender_name,
    senderInitials:  m.sender_initials,
    content:         m.content,
    sentAt:          m.sent_at,
    editedAt:        m.edited_at        ?? null,
    replyToId:       m.reply_to_id      ?? null,
    reactions:       m.reactions        ?? {},
  };
}

// ── Auth ──────────────────────────────────────────────────────────────
export function schoolLaunch(courseId = "CHEM101") {
  return req("/auth/school-launch", {
    method: "POST",
    body: JSON.stringify({ course_id: courseId, token: "test" }),
    credentials: "include",
  });
}

// ── Workspace ─────────────────────────────────────────────────────────
export async function fetchWorkspace(courseId, token) {
  return req(`/channels/courses/${courseId}/channels`, {
    headers: authHeader(token),
  });
}

export async function fetchMembers(courseId, token) {
  return req(`/channels/courses/${courseId}/members`, {
    headers: authHeader(token),
  });
}

// ── Conversations ──────────────────────────────────────────────────────
export async function fetchConversations(token) {
  return req("/conversations", {
    headers: authHeader(token),
  });
}

export function getOrCreateConversation(senderId, recipientId) {
  return req("/conversations", {
    method: "POST",
    body: JSON.stringify({ sender_id: senderId, recipient_id: recipientId }),
  });
}

// ── Channel messages ───────────────────────────────────────────────────
export async function fetchChannelMessages(channelId) {
  const data = await req(`/channels/${channelId}/messages?limit=50`);
  return { ...data, messages: data.messages.map(normaliseMessage) };
}

export function postChannelMessage(channelId, content, senderId, replyToId = null) {
  return req(`/channels/${channelId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, sender_id: senderId, reply_to_id: replyToId }),
  }).then(normaliseMessage);
}

export function editChannelMessage(channelId, messageId, content, senderId) {
  return req(`/channels/${channelId}/messages/${messageId}`, {
    method: "PATCH",
    body: JSON.stringify({ content, sender_id: senderId }),
  }).then(normaliseMessage);
}

export function deleteChannelMessage(channelId, messageId, senderId) {
  return req(`/channels/${channelId}/messages/${messageId}`, {
    method: "DELETE",
    body: JSON.stringify({ sender_id: senderId }),
  });
}

export function reactToMessage(channelId, messageId, userId, emoji) {
  return req(`/channels/${channelId}/messages/${messageId}/react`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, emoji }),
  }).then(normaliseMessage);
}

export function createChannel(courseId, name, token) {
  return req(`/channels/courses/${courseId}/channels`, {
    method: "POST",
    headers: authHeader(token),
    body: JSON.stringify({ name, channel_type: "custom" }),
  });
}

// ── DM messages ────────────────────────────────────────────────────────
export async function fetchDMMessages(conversationId) {
  const data = await req(`/conversations/${conversationId}/messages?limit=50`);
  return { ...data, messages: data.messages.map(normaliseMessage) };
}

export function postDM(conversationId, content, senderId) {
  return req(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, sender_id: senderId }),
  }).then(normaliseMessage);
}
