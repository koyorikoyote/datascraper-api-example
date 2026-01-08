from sqlalchemy.orm import Session
from typing import Optional, List

from src.models import UserRole
from src.schemas import UserRoleCreate, UserRoleUpdate


class UserRoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, role_id: int) -> Optional[UserRole]:
        return self.db.query(UserRole).filter(UserRole.id == role_id).first()

    def get_by_name(self, role_name: str) -> Optional[UserRole]:
        return self.db.query(UserRole).filter(UserRole.role_name == role_name).first()

    def list(self, skip: int = 0, limit: int | None = None) -> List[UserRole]:
        query = self.db.query(UserRole).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, role_in: UserRoleCreate) -> UserRole:
        db_role = UserRole(
            role_name=role_in.role_name,
            typical_title=role_in.typical_title,
            responsibilities=role_in.responsibilities,
        )
        self.db.add(db_role)
        self.db.commit()
        self.db.refresh(db_role)
        return db_role

    def update(self, db_role: UserRole, role_in: UserRoleUpdate) -> UserRole:
        if role_in.typical_title is not None:
            db_role.typical_title = role_in.typical_title
        if role_in.responsibilities is not None:
            db_role.responsibilities = role_in.responsibilities
        self.db.commit()
        self.db.refresh(db_role)
        return db_role

    def delete(self, db_role: UserRole) -> None:
        self.db.delete(db_role)
        self.db.commit()
