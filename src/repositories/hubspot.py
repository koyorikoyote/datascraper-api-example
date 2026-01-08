from sqlalchemy.orm import Session
from typing import Optional, List

from src.models import HubspotIntegration
from src.schemas import HubspotCreate, HubspotUpdate


class HubspotRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, id: int) -> Optional[HubspotIntegration]:
        return self.db.query(HubspotIntegration).filter(HubspotIntegration.id == id).first()
    
    def get_by_hub_id(self, hub_id: int) -> Optional[HubspotIntegration]:
        return self.db.query(HubspotIntegration).filter(HubspotIntegration.hub_id == hub_id).first()
    
    def get_hub_domain_by_user_id(self, user_id: int) -> Optional[HubspotIntegration]:
        return (
            self.db.query(HubspotIntegration)
            .filter(HubspotIntegration.user_id == user_id)
            .order_by(HubspotIntegration.created_at.asc())
            .first()
        )
        
    def list(self, skip: int = 0, limit: int | None = None) -> List[HubspotIntegration]:
        query = self.db.query(HubspotIntegration).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, hubspot_in: HubspotCreate) -> HubspotIntegration:
        hubspot = HubspotIntegration(
            **hubspot_in.model_dump(exclude_none=True)
        )
        self.db.add(hubspot)
        self.db.commit()
        self.db.refresh(hubspot)
        return hubspot

    def update(self, db_hubspot: HubspotIntegration, hubspot_in: HubspotUpdate) -> HubspotIntegration:
        update_data = hubspot_in.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            setattr(db_hubspot, field, value)
        self.db.add(db_hubspot)
        self.db.commit()
        self.db.refresh(db_hubspot)
        return db_hubspot

    def delete(self, db_hubspot: HubspotIntegration) -> None:
        self.db.delete(db_hubspot)
        self.db.commit()
