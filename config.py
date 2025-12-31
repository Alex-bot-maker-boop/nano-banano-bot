import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN","")
DB_NAME = "users.db"
FREE_GENERATIONS = 3
