import os
from dotenv import load_dotenv

load_dotenv()

# Discord Application Config
CLIENT_ID = os.getenv("CLIENT_ID", "YOUR_CLIENT_ID_HERE")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")

# Bot Config (Required for mass-joining)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Scopes
SCOPES = "identify guilds.join"

# Admin Access
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "oxy_admin_123")
