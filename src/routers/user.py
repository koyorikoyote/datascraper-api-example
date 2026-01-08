from fastapi import APIRouter, Depends, HTTPException, status
from src.schemas import UserOut, UserCreate, UserUpdate, TokenInfo
from src.services import UserService
from src.services import AuthService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/users", tags=["users"])

UserServiceDep = Depends(get_service(UserService))
AuthServiceDep = Depends(get_service(AuthService))

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate, 
    service: UserService = UserServiceDep,
    token: TokenInfo = Depends(get_current_user)
):
    return service.create_user(user_in)

@router.get("/{user_id}/", response_model=UserOut)
def read_user(
    user_id: int,
    service: UserService = UserServiceDep,
    token: TokenInfo = Depends(get_current_user)
):
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/", response_model=list[UserOut])
def list_users(
    skip: int = 0,
    limit: int | None = None,
    service: UserService = UserServiceDep,
    token: TokenInfo = Depends(get_current_user)
):
    return service.list_users(skip=skip, limit=limit)

@router.put("/{user_id}/", response_model=UserOut)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    service: UserService = UserServiceDep,
    token: TokenInfo = Depends(get_current_user)
):
    updated = service.update_user(user_id, user_in)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated

@router.delete("/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    service: UserService = UserServiceDep,
    token: TokenInfo = Depends(get_current_user)
):
    success = service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return None
