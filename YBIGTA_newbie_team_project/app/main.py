from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from app.user.user_router import user
from app.config import PORT
from database.mysql_connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 기동 시 MySQL(users) 테이블을 준비한다.

    DB에 붙지 못해도 서버 자체는 뜨도록 예외를 삼킨다.
    (DB가 필요한 요청에서 에러가 나므로 원인 파악은 그대로 가능)
    """
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        print(f"[startup] MySQL init skipped: {e}")
    yield


app = FastAPI(lifespan=lifespan)
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

app.include_router(user)

if __name__=="__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
