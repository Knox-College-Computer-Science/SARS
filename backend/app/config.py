import os
from pathlib import Path
from dotenv import load_dotenv

# Try loading from backend/.env first, then fall back to project-root env / .env
_backend_dir = Path(__file__).resolve().parent.parent   # /backend/
_project_dir = _backend_dir.parent                      # /SARS/

for candidate in [
    _backend_dir / ".env",
    _backend_dir / "env",
    _project_dir / ".env",
    _project_dir / "env",
]:
    if candidate.exists():
        load_dotenv(candidate)
        break

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")
SESSION_SECRET       = os.getenv("SESSION_SECRET", "dev-secret-change-in-production")
