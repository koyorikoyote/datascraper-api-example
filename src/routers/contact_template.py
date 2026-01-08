from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas import (
    ContactTemplateOut,
    ContactTemplateCreate,
    ContactTemplateUpdate,
    TokenInfo,
)
from src.services import ContactTemplateService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/contact-templates", tags=["contact-templates"])

ContactTemplateServiceDep = Depends(get_service(ContactTemplateService))


@router.post("/", response_model=ContactTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_in: ContactTemplateCreate,
    service: ContactTemplateService = ContactTemplateServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.create_template(template_in)


@router.get("/{template_id}/", response_model=ContactTemplateOut)
async def read_template(
    template_id: int,
    service: ContactTemplateService = ContactTemplateServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/", response_model=list[ContactTemplateOut])
async def list_templates(
    skip: int = 0,
    limit: int | None = None,
    service: ContactTemplateService = ContactTemplateServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_templates(skip=skip, limit=limit)


@router.put("/{template_id}/", response_model=ContactTemplateOut)
async def update_template(
    template_id: int,
    template_in: ContactTemplateUpdate,
    service: ContactTemplateService = ContactTemplateServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    updated = service.update_template(template_id, template_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Template not found")
    return updated


@router.delete("/{template_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    service: ContactTemplateService = ContactTemplateServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    success = service.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return None
