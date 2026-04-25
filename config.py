"""Central configuration for the app.

Loads environment variables (via .env) and exposes typed settings.
"""
from dotenv import load_dotenv
import os

load_dotenv()

JWT_SECRET = os.environ.get("JWT_SECRET_KEY") or os.environ.get("TELEGRAM_TOKEN") or "change-me"
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ACTIVE_JWT = os.environ.get("ACTIVE_JWT")
ESP32_TOKEN_ADMIN_KEY = os.environ.get("ESP32_TOKEN_ADMIN_KEY", "change-me-admin")

# Other config defaults you may want to expose
HTTP_HOST = os.environ.get("HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8000"))
