from sqlalchemy.orm import Session

from src.config.database import SessionLocal
from src.models import WeightedMetric


def seed_weighted_metric(db: Session) -> None:
    metrics = [
        {
            "label": "service_price",
            "value": 0.40
        },
        {
            "label": "service_volume",
            "value": 0.40
        },
        {
            "label": "site_size",
            "value": 0.20
        }
    ]
    
    for metric in metrics:
        exists = db.query(WeightedMetric).filter_by(label=metric["label"]).first()
        if not exists:
            db.add(WeightedMetric(
                label=metric["label"],
                value=metric["value"]
            ))
    db.commit()


def main():
    db = SessionLocal()
    try:
        seed_weighted_metric(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
