from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.user.user_schema import User


class UserRepository:
    """MySQL의 users 테이블에 대한 CRUD를 담당한다.

    User가 pydantic 모델(ORM 모델이 아님)이므로 SQLAlchemy Core의 text() 쿼리로
    직접 SQL을 실행하고, 조회 결과를 User로 변환해 돌려준다.
    세션은 외부(dependencies.get_db / 테스트 fixture)에서 주입받는다.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자를 조회한다.

        Args:
            email: 조회할 사용자의 이메일

        Returns:
            사용자가 존재하면 User, 없으면 None
        """
        query = text("SELECT email, password, username FROM users WHERE email = :email")
        row = self.db.execute(query, {"email": email}).fetchone()
        if row is None:
            return None
        return User(email=row.email, password=row.password, username=row.username)

    def save_user(self, user: User) -> User:
        """사용자를 저장한다. 이미 존재하는 이메일이면 갱신(update)한다.

        MySQL의 ON DUPLICATE KEY UPDATE / SQLite의 UPSERT는 문법이 서로 다르므로,
        조회 후 INSERT 또는 UPDATE를 분기하여 두 DB에서 동일하게 동작하도록 한다.

        Args:
            user: 저장할 사용자 (email, password, username)

        Returns:
            저장된 사용자
        """
        params = {
            "email": str(user.email),
            "password": user.password,
            "username": user.username,
        }

        if self.get_user_by_email(str(user.email)) is None:
            query = text(
                "INSERT INTO users (email, password, username) "
                "VALUES (:email, :password, :username)"
            )
        else:
            query = text(
                "UPDATE users SET password = :password, username = :username "
                "WHERE email = :email"
            )

        self.db.execute(query, params)
        self.db.commit()
        return user

    def delete_user(self, user: User) -> User:
        """사용자를 삭제한다.

        Args:
            user: 삭제할 사용자

        Returns:
            삭제된 사용자
        """
        query = text("DELETE FROM users WHERE email = :email")
        self.db.execute(query, {"email": str(user.email)})
        self.db.commit()
        return user
