import os
import sys
from pathlib import Path

# Add project root to sys.path so modules in src can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure SQLite fallback is active in serverless context unless DATABASE_URL is explicitly provided
if not os.environ.get("DATABASE_URL") or "sqlite" in os.environ.get("DATABASE_URL", ""):
    os.environ["USE_SQLITE_FALLBACK"] = "1"

from src.main import app as _fastapi_app

async def app(scope, receive, send):
    if scope["type"] == "http":
        headers = dict(scope.get("headers", []))
        matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")
        if not matched_path:
            matched_path = headers.get(b"x-invoke-path", b"").decode("utf-8")
            
        if matched_path:
            scope["path"] = matched_path
        elif scope.get("path", "").startswith("/api/index.py"):
            rem = scope["path"][len("/api/index.py"):]
            scope["path"] = rem if rem else "/"
        elif scope.get("path", "").startswith("/api/index"):
            rem = scope["path"][len("/api/index"):]
            scope["path"] = rem if rem else "/"
    await _fastapi_app(scope, receive, send)
