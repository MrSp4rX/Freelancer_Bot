import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = "sqlite:///database.db"
ADMIN_ID = os.getenv("ADMIN_ID")
