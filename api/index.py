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

from src.main import app
