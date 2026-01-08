import os
import sys

# Ensure project root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.config.database import SessionLocal
from src.seeders import seed_all


def main() -> None:
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
