from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from src.config.config import get_env
from src.repositories import UserRepository
import logging

from src.utils.utils import encode_jwt, decode_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class AuthService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def create_access_token(self, data: dict) -> str:
        minutes = int(get_env("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        return self._sign_jwt(data, timedelta(minutes=minutes))

    def create_refresh_token(self, data: dict) -> str:
        days = int(get_env("REFRESH_TOKEN_EXPIRE_DAYS", 7))
        return self._sign_jwt(data, timedelta(days=days))
    
    def _serialize_user(self, user) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role_id": user.role_id,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "role": {
                "id": user.role.id,
                "role_name": user.role.role_name,
                "responsibilities": user.role.responsibilities,
                "typical_title": user.role.typical_title,
            }
        }

    def login(self, form_data: OAuth2PasswordRequestForm) -> dict | None:
        logging.info("Login attempt for %s", form_data.username)
        user = self.repo.get_by_email(form_data.username)
        if not user:
            logging.warning("User %s not found", form_data.username)
            return None

        if not bcrypt.checkpw(
            form_data.password.encode("utf-8"),
            user.password_hash.encode("utf-8"),
        ):
            logging.warning("Invalid password for %s", form_data.username)
            return None

        token_data = {"sub": user.email, "id": user.id, "role_id": user.role_id}

        access = self.create_access_token(token_data)
        refresh = self.create_refresh_token(token_data)

        logging.info("User %s logged in successfully", form_data.username)

        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "user": self._serialize_user(user)
        }
        
    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Validate the given refresh token and issue a new access + refresh pair.
        Raises 401 on any failure.
        """
        try:
            payload = decode_jwt(refresh_token)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user_id = payload.get("id")
        email = payload.get("sub")

        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed refresh token",
            )

        user = self.repo.get_by_email(email)
        if not user or user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or token mismatch",
            )

        new_access = self.create_access_token({"sub": user.email, "id": user.id, "role_id": user.role_id})
        new_refresh = self.create_refresh_token({"sub": user.email, "id": user.id, "role_id": user.role_id})

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "user": self._serialize_user(user)
        }

        
    def verify_token(self, token: str = Depends(oauth2_scheme)) -> dict | None:
        try:
            payload = decode_jwt(token)
            sub = payload.get("sub")
            user_id = payload.get("id")
            if not sub or not user_id:
                return None
            return {"email": sub, "id": user_id}
        except jwt.PyJWTError:
            return None
        
    def logout(self) -> None:
        """
        Stateless logout: the client should delete its refresh cookie/token.
        """
        return None
    
    def _sign_jwt(
        self,
        data: dict,
        expires_delta: timedelta,
    ) -> str:
        to_encode = data.copy()
        to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
        return encode_jwt(to_encode)
        
AuthService.oauth2_scheme = oauth2_scheme
