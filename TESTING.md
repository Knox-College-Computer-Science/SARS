# Testing Guide

This guide explains how to run the SARS test suite, what the existing tests verify, and what assumptions the tests make. It is intended for developers, graders, or contributors who have downloaded the project and want to confirm that the backend still behaves correctly after changes.

## Overview

SARS uses automated backend API tests written with `pytest`. The tests exercise FastAPI routes directly through FastAPI's `TestClient`, so a developer does not need to manually start the backend server before running the test suite.

The current test suite focuses on deterministic backend behavior:

- Authentication/session handling
- Course channel behavior
- Public channel messages
- Direct conversations
- Notes upload/listing
- RAG file metadata routes
- Todo/task CRUD behavior

The tests intentionally avoid real external services such as Google OAuth, Google Drive, Google Classroom, Gemini, or Groq. This keeps the suite repeatable for anyone running it locally.

## Running The Backend Tests

From the repository root:

```powershell
cd backend
python -m pytest
```

If using a virtual environment from the repository root, activate it first:

```powershell
.\.venv\Scripts\activate
cd backend
python -m pytest
```

On macOS/Linux, the equivalent activation command is usually:

```bash
source .venv/bin/activate
cd backend
python -m pytest
```

The `backend/pytest.ini` file configures pytest to discover tests from:

```text
backend/tests/
```

## Test Architecture

The shared test setup lives in:

```text
backend/tests/conftest.py
```

It provides:

- An in-memory SQLite database: `sqlite:///:memory:`
- A FastAPI `TestClient`
- Fake users, courses, enrollments, and channels
- Authentication headers and session cookies
- Mocked Socket.IO emit calls
- Per-test database rollback for isolation

Because each test runs inside a transaction that is rolled back afterward, tests should not depend on the order in which they run.

## Environment Assumptions

During tests, `conftest.py` sets safe placeholder environment variables before importing the app:

```text
DATABASE_URL=sqlite:///:memory:
SESSION_SECRET=test-secret-key
GOOGLE_API_KEY=test-key
GROQ_API_KEY=test-key
LLM_PROVIDER=groq
EMBEDDING_PROVIDER=google
```

These values are only for test execution. They are not production credentials and are not used to call real external APIs.

## What The Tests Cover

### Authentication Tests

File:

```text
backend/tests/test_auth.py
```

These tests verify that:

- School launch creates a demo user.
- School launch returns a token.
- School launch creates a course if needed.
- Repeating school launch with the same course is safe.
- Authenticated session lookup returns the expected user and course.
- Unknown course lookup returns `course: null`.
- Session lookup requires authentication.
- Google disconnect returns a success message.
- `/auth/google/me` returns `401` when no Google account is connected.

### Channel Tests

File:

```text
backend/tests/test_channels.py
```

These tests verify that:

- A course returns its discussion channels.
- The response includes course information.
- Listing channels requires authentication.
- Unknown courses return `404`.
- Users who are not enrolled in a course receive `403`.
- Creating a channel succeeds for valid input.
- Channel names are normalized, such as `Study Group` becoming `study-group`.
- Duplicate channel names are rejected with `409`.
- The members endpoint excludes the requesting user and includes classmates.

### Public Message Tests

File:

```text
backend/tests/test_messages.py
```

These tests verify that:

- Empty channels return an empty message list.
- Sent messages appear in channel message lists.
- Unknown channels return `404`.
- Valid messages return `201`.
- Empty messages are rejected.
- Overly long messages are rejected.
- A message author can edit their own message.
- A different user cannot edit someone else's message.
- Deleting a message removes it from the visible message list.
- A different user cannot delete someone else's message.
- Reactions can be added.
- Sending the same reaction twice toggles it off.

### Direct Conversation Tests

File:

```text
backend/tests/test_conversations.py
```

These tests verify that:

- Creating a direct conversation returns a conversation ID.
- Creating the same conversation twice returns the same conversation instead of duplicating it.
- Listing conversations requires authentication.
- Started conversations appear in the conversation list.
- Sending a direct message succeeds.
- Empty direct messages are rejected.
- Direct messages are returned in sent order.
- Reactions can be added to direct messages.
- Repeating a direct-message reaction toggles it off.

### Notes Tests

File:

```text
backend/tests/test_notes.py
```

These tests verify that:

- Uploading a note requires authentication.
- Uploading with a valid session succeeds.
- Successful upload creates a database row.
- A course with no notes returns an empty list.
- Uploaded notes are returned by `/notes?course_id=...`.
- Notes are filtered by course, so one course does not show another course's files.

### RAG Metadata Tests

File:

```text
backend/tests/test_rag.py
```

These tests verify RAG file metadata routes. They do not run full PDF parsing, chunking, embedding, or AI answering.

They verify that:

- `/rag/health` returns `ok`.
- Listing RAG files requires authentication.
- Seeded RAG files appear in `/rag/files`.
- Deleted RAG files are hidden from file lists.
- File status returns statuses such as `processing`.
- Unknown file status returns `404`.
- Deleting a RAG file marks it deleted.
- Deleted RAG files disappear from the visible list.
- Labels can be saved to a RAG file.
- New labels replace old labels.
- Updating labels for an unknown file returns `404`.

### Todo Tests

File:

```text
backend/tests/test_todos.py
```

These tests verify that:

- A new user starts with an empty todo list.
- Todo listing requires authentication.
- Creating a todo returns the created item.
- Missing category defaults to `Personal`.
- Creating a todo requires authentication.
- Updating a todo can mark it done.
- Updating a todo can change its text.
- Updating a missing todo returns `404`.
- Deleting a todo removes it from the list.
- Todos are scoped per user.

## Input Partitioning

The tests were chosen to cover both successful behavior and important failure cases.

| Feature | Input Partitions Covered |
| --- | --- |
| Authentication | valid session, missing auth, unknown course, repeated launch |
| Channels | enrolled user, unauthenticated user, non-enrolled user, unknown course, duplicate channel |
| Public messages | valid content, empty content, too-long content, owner edit/delete, non-owner edit/delete |
| Conversations | new conversation, repeated conversation, valid message, empty message, reactions |
| Notes | authenticated upload, unauthenticated upload, no notes, course-filtered notes |
| RAG metadata | indexed file, processing file, deleted file, unknown file, label updates |
| Todos | create, list, update, delete, missing auth, wrong user, missing todo |

## What The Tests Prove

The automated tests give confidence that the backend correctly handles core API behavior, including:

- Authentication checks
- User ownership checks
- Course enrollment checks
- Course-based filtering
- Message validation
- Soft deletion behavior
- RAG file metadata state changes
- Per-user todo isolation

They are regression tests. If a future change breaks one of these behaviors, pytest should fail and point to the affected route or expected behavior.

## Known Gaps

The current suite does not fully automate:

- Google OAuth login
- Google Classroom sync
- Google Drive upload/download behavior
- Full RAG PDF parsing
- Embedding generation
- AI answer quality
- Browser-based frontend workflows

Those areas should be manually checked before a demo or expanded with integration/end-to-end tests in the future.

## Recommended Manual Checklist

1. Start the backend.
2. Start the frontend.
3. Sign in with Google.
4. Confirm current and past courses appear correctly.
5. Upload a note to a course.
6. Confirm the note appears on the Notes page for that course.
7. Index a file from the computer in the AI Assistant.
8. Index a file from existing Notes in the AI Assistant.
9. Confirm indexed files move from `indexing` to `ready`.
10. Ask the AI a question answered by the indexed material.
11. Confirm the answer cites the expected file.
12. Delete a RAG file and confirm it disappears from the visible list.
13. Add someone connected to that course to private chat and be able to message


