from urllib.parse import urlencode
import httpx

from src.config.config import get_env


class GoogleOAuthService:
    def __init__(self, db):
        # No DB interactions needed for OAuth flows
        pass

    def get_authorization_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": get_env("GOOGLE_OAUTH_CLIENT_ID", required=True),
            "redirect_uri": get_env("GOOGLE_OAUTH_REDIRECT_URI", required=True),
            "scope": "https://www.googleapis.com/auth/adwords",
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    def exchange_code(self, code: str) -> str:
        data = {
            "code": code,
            "client_id": get_env("GOOGLE_OAUTH_CLIENT_ID", required=True),
            "client_secret": get_env("GOOGLE_OAUTH_CLIENT_SECRET", required=True),
            "redirect_uri": get_env("GOOGLE_OAUTH_REDIRECT_URI", required=True),
            "grant_type": "authorization_code",
        }
        response = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=10.0)
        response.raise_for_status()
        refresh_token = response.json().get("refresh_token")
        if not refresh_token:
            raise ValueError("Refresh token not found in response")
        return refresh_token
