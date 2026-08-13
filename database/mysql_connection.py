from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

# .env 예시는 .env.example 참고 (로컬 MySQL / AWS RDS 모두 동일한 키 사용)
user = os.getenv("MYSQL_USER", "root")
passwd = os.getenv("MYSQL_PASSWORD", "")
host = os.getenv("MYSQL_HOST", "127.0.0.1")
port = os.getenv("MYSQL_PORT", "3306")
db = os.getenv("MYSQL_DATABASE", "ybigta")

# 비밀번호에 @ / : 같은 문자가 있으면 URL 파싱이 깨지므로 반드시 인코딩한다.
DB_URL = f'mysql+pymysql://{quote_plus(user)}:{quote_plus(passwd)}@{host}:{port}/{db}?charset=utf8'

# pool_pre_ping: RDS가 유휴 커넥션을 끊었을 때 발생하는 "MySQL server has gone away" 방지
engine = create_engine(DB_URL, echo=True, pool_pre_ping=True, pool_recycle=280)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    email VARCHAR(255) NOT NULL PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_db() -> None:
    """users 테이블이 없으면 생성한다. (앱 기동 시 1회 호출)"""
    with engine.begin() as conn:
        conn.execute(text(CREATE_USERS_TABLE))
