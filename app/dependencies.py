from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.user.user_repository import UserRepository
from app.user.user_service import UserService
from database.mysql_connection import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """요청 1건당 MySQL 세션을 하나 열고, 응답이 끝나면 반드시 닫는다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_user_service(repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repo)
