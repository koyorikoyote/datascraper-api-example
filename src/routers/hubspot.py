from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse

from src.schemas import HubspotAuthResponse, TokenInfo, HubDomainResponse, ContactIn, CompanyIn
from src.utils.dependencies import get_service, get_current_user
from src.services import HubspotService, SeleniumService
from src.config.config import get_env

router = APIRouter(prefix="/hubspot", tags=["hubspot"])

HubspotDep = Depends(get_service(HubspotService))


@router.get("/authorize/")
def authorize(
    service: HubspotService = HubspotDep, 
    token: TokenInfo = Depends(get_current_user)
):
    url = service.get_authorization_url(token)
    return {"authorization_url": url}


@router.get("/callback/")
def oauth_callback(code: str, state:str, service: HubspotService = HubspotDep):
    try:
        return service.exchange_code(code, state)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    
@router.get("/refresh/{hub_id}/", response_model=HubspotAuthResponse)
def oauth_refresh(
    hub_id: str, 
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user)
):
    try:
        return service.refresh_tokens(hub_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.get("/account/", response_model=HubDomainResponse)
def hubspot_account(
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user)
):
    try:
        return service.get_hub_account(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.get("/contact-send/{contact_template_id}/", response_model=None)
def contact_send(
    contact_template_id: str,
    background_tasks: BackgroundTasks,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user)
):
    try:
        # Start Selenium session now
        selenium_service = SeleniumService(headless=False)
        session_id = selenium_service.init_session()  # real driver.session_id

        # Kick off background processing with the same session
        background_tasks.add_task(
            service.process_contact_send,
            token,
            int(contact_template_id),
            selenium_service,
        )

        # Return session id immediately
        return {
            "status": "processing", 
            "session_id": session_id,
            "link": f"{get_env('SELENIUM_UI_URL', required=True)}#/session/{session_id}"
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

@router.get("/contact-send-list/{contact_template_id}/")
def get_contact_send_list(
    contact_template_id: str,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user)
):
    try:
        company_list, contact_template = service.get_contact_send_list(token, int(contact_template_id))
        
        # Create a batch history entry
        batch_history = service.create_batch_history(token, status=StatusConst.PROCESSING)
        
        return {
            "companies": company_list,
            "template": contact_template,
            "batch_id": batch_history.id
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

# CONTACTS
@router.post("/contacts/", response_model=dict)
def create_contact(
    body: ContactIn,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        return service.create_contact(token, body)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/contacts/{contact_id}/", response_model=dict)
def update_contact(
    contact_id: str,
    body: ContactIn,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        return service.update_contact(token, contact_id, body)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/contacts/{contact_id}/", status_code=204)
def delete_contact(
    contact_id: str,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        service.delete_contact(token, contact_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/contacts/", response_model=dict)
def list_contacts(
    limit: int = 20,
    after: Optional[str] = None,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        return service.list_contacts(token, limit, after)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

# COMPANIES
@router.post("/companies/", response_model=dict)
def create_company(
    body: CompanyIn,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        return service.create_company(token, body)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/companies/{company_id}/", response_model=dict)
def update_company(
    company_id: str,
    body: CompanyIn,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        return service.update_company(token, company_id, body)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/companies/{company_id}/", status_code=204)
def delete_company(
    company_id: str,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        service.delete_company(token, company_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/companies/", response_model= list[dict])
def list_companies(
    limit: Optional[int] = 200, # maximum
    after: Optional[str] = None,
    batch_id: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    service: HubspotService = HubspotDep,
    token: TokenInfo = Depends(get_current_user),
):
    try:
        return service.list_companies(
            token, limit, after, 
            batch_id=batch_id,
            start=start,
            end=end
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))