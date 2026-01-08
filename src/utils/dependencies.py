from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.config.config import get_env
from src.config.database import SessionLocal
from src.schemas.user import TokenInfo
from src.services.auth import AuthService


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def get_service(service_class):
    def _get_service(db: Session = Depends(get_db)):
        return service_class(db)
    return _get_service


auth_service_dep = Depends(get_service(AuthService))
oauth2_scheme = AuthService.oauth2_scheme
    
def get_current_user(
    auth_service: AuthService = auth_service_dep,
    token: str = Depends(oauth2_scheme),
)-> Optional[TokenInfo]:
    user_info = auth_service.verify_token(token)
    if user_info is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    if not isinstance(user_info, TokenInfo):
        user_info = TokenInfo(**user_info)

    return user_info