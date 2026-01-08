from sqlalchemy.orm import Session

from .seed_user_roles import seed_roles
from .seed_users import seed_user
from .seed_weighted_metric import seed_weighted_metric
from .seed_score_threshold import seed_score_threshold


SEED_FUNCTIONS = [
    seed_roles,
    seed_user,
    seed_weighted_metric,
    seed_score_threshold
]


def seed_all(db: Session) -> None:
    """Run all seeders with the provided database session."""
    for func in SEED_FUNCTIONS:
        func(db)
