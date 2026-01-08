from sqlalchemy.orm import Session
from typing import List, Optional

from src.repositories.contact_template import ContactTemplateRepository
from src.schemas.contact_template import (
    ContactTemplateOut,
    ContactTemplateCreate,
    ContactTemplateUpdate,
)


class ContactTemplateService:
    def __init__(self, db: Session):
        self.repo = ContactTemplateRepository(db)

    def create_template(self, template_in: ContactTemplateCreate) -> ContactTemplateOut:
        return self.repo.create(template_in)

    def get_template(self, template_id: int) -> Optional[ContactTemplateOut]:
        return self.repo.get(template_id)

    def list_templates(self, skip: int = 0, limit: int | None = None) -> List[ContactTemplateOut]:
        return self.repo.list(skip, limit)

    def update_template(self, template_id: int, template_in: ContactTemplateUpdate) -> Optional[ContactTemplateOut]:
        db_obj = self.repo.get(template_id)
        if not db_obj:
            return None
        return self.repo.update(db_obj, template_in)

    def delete_template(self, template_id: int) -> bool:
        db_obj = self.repo.get(template_id)
        if not db_obj:
            return False
        self.repo.delete(db_obj)
        return True
