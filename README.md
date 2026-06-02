# SARS — Academic Hub

SARS is a full-stack academic platform that integrates Google Classroom, note storage, course discussion, direct messaging, to-do tracking, and an AI assistant that answers questions from uploaded course materials.

**Stack:** Next.js frontend, FastAPI backend, SQLite (local) or Supabase PostgreSQL (deployed), Socket.IO for real-time messaging.

---

## Setup

**Requirements:** Python 3.12, Node.js, a Google Cloud project with OAuth 2.0 and the Classroom API enabled, a free Groq API key (console.groq.com), and a free Google AI Studio API key (aistudio.google.com/apikey).

**Backend:**
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:
```
DATABASE_URL=sqlite:///./nexus.db
SESSION_SECRET=replace-with-a-secret

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...

EMBEDDING_PROVIDER=google
GOOGLE_API_KEY=AIza...
EMBEDDING_MODEL=gemini-embedding-001
```

Start the backend:
```bash
python -m uvicorn app.main:socket_app --reload --port 8000
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

---

## How to Use

1. Click **Connect Google Classroom** and sign in with Google.
2. SARS syncs your courses, assignments, and announcements automatically.
3. **Home** — view assignments due this week, recent announcements, Pomodoro timer, and personal to-dos.
4. **Upload** — upload notes (PDF, DOCX, PPTX, TXT, MD) for a course.
5. **Notes** — browse uploaded notes by course. Click a note to preview it.
6. **Discussion** — send messages in course channels or start direct messages with classmates.
7. **AI Assistant** — select a course, upload files for indexing, and ask questions. Answers stream in real time with source citations.

---

## Deployment (Vercel + Render + Supabase)

https://sars-git-ronak-ronak4170s-projects.vercel.app/connect

---

## Running the Tests

```bash
cd backend
python -m pytest tests/ -v
```

No external services are contacted. Tests use an in-memory SQLite database and mock all API calls (Google, Groq, Socket.IO).

See `TESTING.md` for full details on test architecture, what each file covers, input partitioning, and the manual regression checklist.
