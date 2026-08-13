from app.user.user_repository import UserRepository
from app.user.user_schema import User, UserLogin, UserUpdate

class UserService:
    def __init__(self, userRepoitory: UserRepository) -> None:
        self.repo = userRepoitory

    def login(self, user_login: UserLogin) -> User:
        """이메일과 비밀번호를 검증하여 로그인한다.

        Args:
            user_login: 로그인 요청 정보 (email, password)

        Returns:
            인증에 성공한 사용자

        Raises:
            ValueError: 해당 이메일의 사용자가 없거나, 비밀번호가 일치하지 않는 경우
        """
        user = self.repo.get_user_by_email(user_login.email)
        if user is None:
            raise ValueError("User not Found.")
        if user.password != user_login.password:
            raise ValueError("Invalid ID/PW")
        return user

    def register_user(self, new_user: User) -> User:
        """신규 사용자를 등록한다.

        Args:
            new_user: 등록할 사용자 (email, password, username)

        Returns:
            저장된 사용자

        Raises:
            ValueError: 같은 이메일의 사용자가 이미 존재하는 경우
        """
        if self.repo.get_user_by_email(new_user.email) is not None:
            raise ValueError("User already Exists.")
        return self.repo.save_user(new_user)

    def delete_user(self, email: str) -> User:
        """이메일로 사용자를 삭제한다.

        Args:
            email: 삭제할 사용자의 이메일

        Returns:
            삭제된 사용자

        Raises:
            ValueError: 해당 이메일의 사용자가 없는 경우
        """
        user = self.repo.get_user_by_email(email)
        if user is None:
            raise ValueError("User not Found.")
        return self.repo.delete_user(user)

    def update_user_pwd(self, user_update: UserUpdate) -> User:
        """사용자의 비밀번호를 새 비밀번호로 변경한다.

        Args:
            user_update: 변경 요청 정보 (email, new_password)

        Returns:
            비밀번호가 변경된 사용자

        Raises:
            ValueError: 해당 이메일의 사용자가 없는 경우
        """
        user = self.repo.get_user_by_email(user_update.email)
        if user is None:
            raise ValueError("User not Found.")
        user.password = user_update.new_password
        return self.repo.save_user(user)
