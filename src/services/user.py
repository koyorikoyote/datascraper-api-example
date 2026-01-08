from datetime import datetime
from sqlalchemy.orm import Session
from src.schemas import UserOut, UserCreate, UserUpdate, UserInDB
from src.repositories import UserRepository
from src.config.logger import get_logger
import bcrypt

logger = get_logger(__name__)


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def create_user(self, user_in: UserCreate) -> UserOut:
        logger.info("Creating user %s", user_in.email)
        hashed_password = bcrypt.hashpw(
            user_in.password.encode("utf-8"), bcrypt.gensalt()
        )
        
        user_in_db = UserInDB(
            email=user_in.email,
            full_name=user_in.full_name,
            role_id=user_in.role_id,
            password_hash=hashed_password,
        )

        return self.repo.create(user_in_db)

    def get_user(self, user_id: int) -> UserOut | None:
        return self.repo.get(user_id)

    def list_users(self, skip: int = 0, limit: int | None = None) -> list[UserOut]:
        return self.repo.list(skip, limit)

    def update_user(self, user_id: int, user_in: UserUpdate) -> UserOut:
        logger.info("Updating user %s", user_id)

        db_user = self.repo.get(user_id)
        if not db_user:
            return None

        user_update_db = UserUpdate(
            full_name=user_in.full_name,
            role_id=user_in.role_id,
            password_hash=(
                bcrypt.hashpw(user_in.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                if user_in.password else None
            )
        )

        return self.repo.update(db_user, user_update_db)

    def delete_user(self, user_id: int) -> bool:
        logger.info("Deleting user %s", user_id)
        db_user = self.repo.get(user_id)
        if not db_user:
            logger.warning("User %s not found", user_id)
            return False
        self.repo.delete(db_user)
        return True