# SARS
AI-powered web application for optimizing study sessions!

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/Knox-College-Computer-Science/SARS.git
cd SARS-App
```

### 2. Run the Backend

```bash
cd backend
pip install fastapi uvicorn python-multipart aiofiles
python -m uvicorn app:app --reload
```

Backend runs at: `http://127.0.0.1:8000`

### 3. Run the Frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:3000`

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| POST | `/upload` | Upload a PDF + subject |
| GET | `/notes` | Get all notes |
| GET | `/files/{filename}` | Download/view a PDF |

---

## How to Upload Notes

1. Go to `http://localhost:3000/upload`
2. Select a PDF file
3. Choose a subject from the dropdown
4. Click **Upload**
5. Visit `http://localhost:3000/notes` to see it listed


