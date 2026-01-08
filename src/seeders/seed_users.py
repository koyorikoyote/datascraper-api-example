from sqlalchemy.orm import Session
import bcrypt

from src.config.database import SessionLocal
from src.models import User, UserRole


def seed_user(db: Session) -> None:
    users_to_seed = [
        {"email": "keanujohn@yahoo.com", "full_name": "Keanu", "password": "admin", "role_name": "system"},
        {"email": "takeushi001@gmail.com", "full_name": "竹内望", "password": "admin", "role_name": "system"},
    ]

    for user_data in users_to_seed:
        existing_user = db.query(User).filter_by(email=user_data["email"]).first()
        if existing_user:
            continue

        # Check or create the role
        role = db.query(UserRole).filter_by(role_name=user_data["role_name"]).first()
        if not role:
            role = UserRole(role_name=user_data["role_name"])
            db.add(role)
            db.commit()
            db.refresh(role)

        password_hash = bcrypt.hashpw(user_data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db_user = User(email=user_data["email"], full_name=user_data["full_name"], password_hash=password_hash, role_id=role.id)
        db.add(db_user)

    db.commit()


def main():
    db = SessionLocal()
    try:
        seed_user(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
