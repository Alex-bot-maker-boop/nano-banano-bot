import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 5823320202))
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")
