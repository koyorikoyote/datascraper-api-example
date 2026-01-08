from datetime import timezone, datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

from src.config.config import get_env
from src.utils.constants import HubspotConst, StatusConst
from src.utils.decorators import try_except_decorator_no_raise, try_except_decorator
import logging

class HubspotGateway:
    def __init__(self) -> None:
        self.client_id = get_env("HUBSPOT_CLIENT_ID", required=True)
        self.client_secret = get_env("HUBSPOT_CLIENT_SECRET", required=True)
        self.redirect_uri = get_env("HUBSPOT_REDIRECT_URI", required=True)

    # OAuth
    def build_authorization_url(self, state: str) -> str:
        scopes = (
            "oauth "
            "crm.objects.contacts.read "
            "crm.objects.contacts.write "
            "crm.objects.companies.read "
            "crm.objects.companies.write "
            "crm.schemas.companies.read "
            "crm.schemas.companies.write"

        )
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scopes,
            "state": state,
        }
        return f"{HubspotConst.AUTHORIZATION_URL}?{urlencode(params)}"
    
    @try_except_decorator
    def request_tokens(self, code: str) -> Dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        response = httpx.post(HubspotConst.EXCHANGE_URL, data=data, timeout=10.0)
        response.raise_for_status()
        return response.json()

    @try_except_decorator
    def request_refresh(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        r = httpx.post(HubspotConst.EXCHANGE_URL, data=data, timeout=10.0)
        r.raise_for_status()
        return r.json()

    @try_except_decorator_no_raise(fallback_value=False)
    def check_token(self, access_token: str) -> Dict[str, Any] | bool:
        response = httpx.get(
            f"{HubspotConst.ACCESS_DETAILS_URL}/{access_token}",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    # CRM endpoints
    def _headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
    @try_except_decorator
    def create_contact(
        self, access_token: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = httpx.post(
            f"{HubspotConst.BASE_CRM_URL}/contacts",
            headers=self._headers(access_token),
            json=payload,
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    @try_except_decorator
    def update_contact(
        self, access_token: str, contact_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = httpx.patch(
            f"{HubspotConst.BASE_CRM_URL}/contacts/{contact_id}",
            headers=self._headers(access_token),
            json=payload,
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    @try_except_decorator
    def delete_contact(self, access_token: str, contact_id: str) -> None:
        r = httpx.delete(
            f"{HubspotConst.BASE_CRM_URL}/contacts/{contact_id}",
            headers=self._headers(access_token),
            timeout=10.0,
        )
        if r.status_code not in (200, 204):
            r.raise_for_status()

    @try_except_decorator
    def list_contacts(
        self, access_token: str, limit: int = 20, after: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {"limit": limit}
        if after:
            params["after"] = after
        r = httpx.get(
            f"{HubspotConst.BASE_CRM_URL}/contacts",
            headers=self._headers(access_token),
            params=params,
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    @try_except_decorator
    def create_company(
        self, access_token: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = httpx.post(
            f"{HubspotConst.BASE_CRM_URL}/companies",
            headers=self._headers(access_token),
            json=payload,
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    @try_except_decorator
    def update_company(
        self, access_token: str, company_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = httpx.patch(
            f"{HubspotConst.BASE_CRM_URL}/companies/{company_id}",
            headers=self._headers(access_token),
            json=payload,
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()
    
    @try_except_decorator
    def delete_company(self, access_token: str, company_id: str) -> None:
        r = httpx.delete(
            f"{HubspotConst.BASE_CRM_URL}/companies/{company_id}",
            headers=self._headers(access_token),
            timeout=10.0,
        )
        if r.status_code not in (200, 204):
            r.raise_for_status()
    
    @try_except_decorator
    def list_companies(
        self,
        access_token: str,
        filter_groups: list[dict],
        limit: int = 200,
        after: Optional[str] = None,
    ) -> list[dict]:
        body = {
            "filterGroups": filter_groups,
            "properties": HubspotConst.COMPANY_PROPERTY_LIST,
            "limit": limit,
        }
        if after:
            body["after"] = after
        logging.info(filter_groups)
        r = httpx.post(
            f"{HubspotConst.BASE_CRM_URL}/companies/search",
            headers=self._headers(access_token),
            json=body,
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    @try_except_decorator
    def batch_update_companies(
        self,
        access_token: str,
        inputs: list[dict]
    ) -> dict:
        url = f"{HubspotConst.BASE_CRM_URL}/companies/batch/update"
        body = {"inputs": inputs}

        response = httpx.post(
            url,
            headers=self._headers(access_token),
            json=body,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
    
    @try_except_decorator
    def create_properties(self, access_token: str, properties: list[dict]) -> list[dict]:
        """
        Create multiple HubSpot custom properties under the 'companies' object if they do not exist.

        :param access_token: OAuth access token.
        :param properties: A list of property definitions (dicts).
        :return: List of response dicts from HubSpot.
        """
        base_url = f"{HubspotConst.BASE_URL}/crm/v3/properties/companies"
        results = []

        for prop in properties:
            property_name = prop.get("name")
            if not property_name:
                results.append({"error": "Missing property name", "property": prop})
                continue

            # Check if property already exists
            check_url = f"{base_url}/{property_name}"
            check_response = httpx.get(
                check_url,
                headers=self._headers(access_token),
                timeout=10.0,
            )

            if check_response.status_code == 200:
                # Property exists
                results.append({"status": "exists", "property": property_name})
                continue
            elif check_response.status_code != 404:
                # Unexpected error
                results.append({
                    "error": f"Failed to check property '{property_name}'",
                    "detail": check_response.text,
                    "status_code": check_response.status_code
                })
                continue

            # Property does not exist, create it
            create_response = httpx.post(
                base_url,
                headers=self._headers(access_token),
                json=prop,
                timeout=10.0,
            )
            try:
                create_response.raise_for_status()
                results.append(create_response.json())
            except httpx.HTTPStatusError as e:
                results.append({
                    "error": str(e),
                    "detail": create_response.text,
                    "property": property_name
                })

        return results
