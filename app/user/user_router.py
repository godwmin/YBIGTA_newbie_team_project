from fastapi import APIRouter, HTTPException, Depends, status
from app.user.user_schema import User, UserLogin, UserUpdate, UserDeleteRequest
from app.user.user_service import UserService
from app.dependencies import get_user_service
from app.responses.base_response import BaseResponse

user = APIRouter(prefix="/api/user")


@user.post("/login", response_model=BaseResponse[User], status_code=status.HTTP_200_OK)
def login_user(user_login: UserLogin, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """사용자 로그인을 진행합니다.

    Args:
        user_login: 로그인 요청 정보 (email, password)
        service: 유저 서비스 인스턴스 (의존성 주입)

    Returns:
        성공 응답 객체 (BaseResponse[User])
    """
    try:
        logged_in_user = service.login(user_login)
        return BaseResponse(status="success", data=logged_in_user, message="Login Success.") 
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@user.post("/register", response_model=BaseResponse[User], status_code=status.HTTP_201_CREATED)
def register_user(new_user: User, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """신규 사용자를 등록(회원가입)합니다.

    Args:
        new_user: 등록할 사용자 정보 (email, password, username)
        service: 유저 서비스 인스턴스 (의존성 주입)

    Returns:
        성공 응답 객체 (BaseResponse[User])
    """
    try:
        registered_user = service.register_user(new_user)
        return BaseResponse(status="success", data=registered_user, message="User registration success.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@user.delete("/delete", response_model=BaseResponse[User], status_code=status.HTTP_200_OK)
def delete_user(user_delete_request: UserDeleteRequest, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """이메일 정보를 통해 사용자를 탈퇴(삭제) 처리합니다.

    Args:
        user_delete_request: 삭제할 사용자 정보 (email)
        service: 유저 서비스 인스턴스 (의존성 주입)

    Returns:
        성공 응답 객체 (BaseResponse[User])
    """
    try:
        deleted_user = service.delete_user(user_delete_request.email)
        return BaseResponse(status="success", data=deleted_user, message="User Deletion Success.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@user.put("/update-password", response_model=BaseResponse[User], status_code=status.HTTP_200_OK)
def update_user_password(user_update: UserUpdate, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """사용자의 비밀번호를 새 비밀번호로 업데이트합니다.

    Args:
        user_update: 변경 요청 정보 (email, new_password)
        service: 유저 서비스 인스턴스 (의존성 주입)

    Returns:
        성공 응답 객체 (BaseResponse[User])
    """
    try:
        updated_user = service.update_user_pwd(user_update)
        return BaseResponse(status="success", data=updated_user, message="User password update success.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))