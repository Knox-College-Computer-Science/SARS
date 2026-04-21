import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
SESSION_SECRET = os.getenv("SESSION_SECRET")

if not GOOGLE_CLIENT_ID:
    raise ValueError("Missing GOOGLE_CLIENT_ID in .env")
if not GOOGLE_CLIENT_SECRET:
    raise ValueError("Missing GOOGLE_CLIENT_SECRET in .env")
if not GOOGLE_REDIRECT_URI:
    raise ValueError("Missing GOOGLE_REDIRECT_URI in .env")
if not SESSION_SECRET:
    raise ValueError("Missing SESSION_SECRET in .env")