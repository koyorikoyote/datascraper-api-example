from sqlalchemy.orm import Session, selectinload
from typing import Optional, List

from src.models import User
from src.schemas import UserInDB, UserUpdate


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> Optional[User]:
        return (
            self.db.query(User)
            .options(selectinload(User.role))
            .filter(User.id == user_id)
            .first()
        )

    def get_by_email(self, email: str) -> Optional[User]:
        return (
            self.db.query(User)
            .options(selectinload(User.role))
            .filter(User.email == email)
            .first()
        )
        
    def list(self, skip: int = 0, limit: int | None = None) -> List[User]:
        query = (
            self.db.query(User)
            .options(selectinload(User.role))
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, user_in: UserInDB) -> User:
        db_user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            password_hash=user_in.password_hash,
            role_id=user_in.role_id,
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update(self, db_user: User, user_in: UserInDB) -> User:
        update_data = user_in.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user


    def delete(self, db_user: User) -> None:
        self.db.delete(db_user)
        self.db.commit()
