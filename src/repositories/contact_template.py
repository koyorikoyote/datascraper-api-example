from sqlalchemy.orm import Session
from typing import Optional, List

from src.models import ContactTemplate
from src.schemas.contact_template import ContactTemplateCreate, ContactTemplateUpdate


class ContactTemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, template_id: int) -> Optional[ContactTemplate]:
        return (
            self.db.query(ContactTemplate)
            .filter(ContactTemplate.id == template_id)
            .first()
        )

    def list(self, skip: int = 0, limit: int | None = None) -> List[ContactTemplate]:
        query = self.db.query(ContactTemplate).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, template_in: ContactTemplateCreate) -> ContactTemplate:
        db_obj = ContactTemplate(**template_in.model_dump(exclude_none=True))
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ContactTemplate, template_in: ContactTemplateUpdate) -> ContactTemplate:
        update_data = template_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ContactTemplate) -> None:
        self.db.delete(db_obj)
        self.db.commit()
