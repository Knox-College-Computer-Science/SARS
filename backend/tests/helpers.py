import os
import base64
import json
from itsdangerous import TimestampSigner


def make_session_cookie(data: dict) -> str:
    secret = os.environ.get("SESSION_SECRET", "test-secret-key")
    signer = TimestampSigner(secret)
    raw    = base64.b64encode(json.dumps(data).encode("utf-8"))
    return signer.sign(raw).decode("utf-8")
