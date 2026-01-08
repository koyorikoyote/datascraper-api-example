from sqlalchemy.orm import Session

from src.schemas import UserRoleOut, UserRoleCreate, UserRoleUpdate
from src.repositories import UserRoleRepository


class UserRoleService:
    def __init__(self, db: Session):
        self.repo = UserRoleRepository(db)

    def create_role(self, role_in: UserRoleCreate) -> UserRoleOut:
        return self.repo.create(role_in)

    def get_role(self, role_id: int) -> UserRoleOut | None:
        return self.repo.get(role_id)

    def list_roles(self, skip: int = 0, limit: int | None = None) -> list[UserRoleOut]:
        return self.repo.list(skip, limit)

    def update_role(self, role_id: int, role_in: UserRoleUpdate) -> UserRoleOut | None:
        db_role = self.repo.get(role_id)
        if not db_role:
            return None
        return self.repo.update(db_role, role_in)

    def delete_role(self, role_id: int) -> bool:
        db_role = self.repo.get(role_id)
        if not db_role:
            return False
        self.repo.delete(db_role)
        return True
