from sqlalchemy.orm import Session

from src.config.database import SessionLocal
from src.models import UserRole


def seed_roles(db: Session) -> None:
    roles = [
        "sales_manager",
        "sales_rep",
        "system",
    ]
    for name in roles:
        exists = db.query(UserRole).filter_by(role_name=name).first()
        if not exists:
            db.add(UserRole(role_name=name))
    db.commit()


def main():
    db = SessionLocal()
    try:
        seed_roles(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
