from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from src.utils.dependencies import get_service
from src.services import AuthService

router = APIRouter(prefix="/auth", tags=["login"])
AuthServiceDep = Depends(get_service(AuthService))

@router.post("/login/")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = AuthServiceDep,
):
    tokens = service.login(form_data)
    if not tokens:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Store refresh token in a cookie, hide it from JS
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,      # 7 days
        path="/",
    )

    return {
        "access_token": tokens["access_token"],
        "token_type": "bearer",
        "user": tokens["user"]
    }
    
@router.post("/refresh/")
def refresh(
    request: Request, 
    response: Response,
    service: AuthService = AuthServiceDep
):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    tokens = service.refresh_access_token(refresh_token)

    # ★ Rotate the refresh token (optional but recommended)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

    return {
        "access_token": tokens["access_token"],
        "token_type": "bearer",
        "user": tokens["user"]
    }
    
@router.post("/logout/")
def logout(
    response: Response,
    service: AuthService = AuthServiceDep,
):
    service.logout()
    response.delete_cookie(
        key="refresh_token",
        path="/auth",
    )
    return {"detail": "Logged out"}