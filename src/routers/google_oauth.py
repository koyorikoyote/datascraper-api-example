from fastapi import APIRouter, Depends, HTTPException, status

from src.utils.dependencies import get_service
from src.services import GoogleOAuthService

router = APIRouter(prefix="/google-oauth", tags=["google-oauth"])

GoogleOAuthDep = Depends(get_service(GoogleOAuthService))


@router.get("/authorize/")
def authorize(service: GoogleOAuthService = GoogleOAuthDep):
    url = service.get_authorization_url()
    return {"authorization_url": url}


@router.get("/callback/")
def oauth_callback(code: str, service: GoogleOAuthService = GoogleOAuthDep):
    try:
        refresh_token = service.exchange_code(code)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"refresh_token": refresh_token}
