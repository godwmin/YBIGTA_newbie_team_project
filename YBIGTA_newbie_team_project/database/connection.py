import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/ybigta_db")
client = MongoClient(MONGO_URL)

# URL 마지막 경로에서 DB 이름 파싱 (없으면 기본값 ybigta_db)
db_name = MONGO_URL.split("/")[-1].split("?")[0] or "ybigta_db"
mongo_db = client[db_name]
