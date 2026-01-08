from sqlalchemy.orm import Session

from src.config.database import SessionLocal
from src.models import ScoreThreshold


def seed_score_threshold(db: Session) -> None:
    thresholds = [
        {
            "label": "A",
            "value": 8.0
        },
        {
            "label": "B",
            "value": 6.0
        },
        {
            "label": "C",
            "value": 4.0
        },
    ]
    
    for threshold in thresholds:
        exists = db.query(ScoreThreshold).filter_by(label=threshold["label"]).first()
        if not exists:
            db.add(ScoreThreshold(
                label=threshold["label"],
                value=threshold["value"]
            ))
    db.commit()


def main():
    db = SessionLocal()
    try:
        seed_score_threshold(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
