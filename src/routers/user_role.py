from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas import UserRoleOut, UserRoleCreate, UserRoleUpdate, TokenInfo
from src.services import UserRoleService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/roles", tags=["roles"])

UserRoleServiceDep = Depends(get_service(UserRoleService))


@router.post("/", response_model=UserRoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    role_in: UserRoleCreate,
    service: UserRoleService = UserRoleServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.create_role(role_in)


@router.get("/{role_id}/", response_model=UserRoleOut)
def read_role(
    role_id: int,
    service: UserRoleService = UserRoleServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.get("/", response_model=list[UserRoleOut])
def list_roles(
    skip: int = 0,
    limit: int | None = None,
    service: UserRoleService = UserRoleServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_roles(skip=skip, limit=limit)


@router.put("/{role_id}/", response_model=UserRoleOut)
def update_role(
    role_id: int,
    role_in: UserRoleUpdate,
    service: UserRoleService = UserRoleServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    updated = service.update_role(role_id, role_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Role not found")
    return updated


@router.delete("/{role_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    service: UserRoleService = UserRoleServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    success = service.delete_role(role_id)
    if not success:
        raise HTTPException(status_code=404, detail="Role not found")
    return None
