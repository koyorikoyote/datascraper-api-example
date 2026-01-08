from datetime import date, datetime, time, timezone
import textwrap
from typing import Any, Callable, Dict, Optional
from fastapi import HTTPException, status as http_status
from fastapi.responses import HTMLResponse
import time as time_module

from src.config.config import get_env
from src.repositories.batch_history_detail import BatchHistoryDetailRepository
from src.repositories.contact_template import ContactTemplateRepository
from src.repositories.hubspot import HubspotRepository
from src.repositories.batch_history import BatchHistoryRepository
from src.schemas import (
    HubspotAuthResponse,
    TokenInfo,
    HubspotUpdate,
    HubspotCreate,
    HubDomainResponse,
    ContactIn,
    CompanyIn,
    BatchHistoryCreate,
    BatchHistoryUpdate,
    ContactTemplateOut,
    BatchHistoryDetailCreate
)
from src.services.selenium import SeleniumService, COLUMN_ORDER
from src.utils.legacy_selenium_contact import LegacySeleniumContact
from src.utils.constants import ExecutionTypeConst, StatusConst
from src.utils.utils import decode_jwt, encode_jwt
from src.gateways.hubspot import HubspotGateway
from src.utils.company_properties import COMPANY_PROPERTIES
from src.utils.decorators import retry_on_429
import logging

class HubspotService:
    def __init__(self, db):
        self.hubspot_repo = HubspotRepository(db)
        self.gateway = HubspotGateway()
        self.CLOCK_SKEW = 30
        self.client_id = self.gateway.client_id
        self.client_secret = self.gateway.client_secret
        self.redirect_uri = self.gateway.redirect_uri
        self.frontend_origin = get_env("FRONTEND_ORIGIN", required=True)
        self.batch_history_repo = BatchHistoryRepository(db)
        self.contact_template_repo = ContactTemplateRepository(db)
        self.batch_history_detail_repo = BatchHistoryDetailRepository(db)

    def get_authorization_url(self, token: TokenInfo) -> str:
        token_info = encode_jwt(token.model_dump())
        return self.gateway.build_authorization_url(token_info)

    def exchange_code(self, code: str, state_jwt: str) -> HubspotAuthResponse:
        user_info: Dict[str, Any] = decode_jwt(state_jwt)

        token_payload = self._request_tokens(code)
        hub_account = self._check_token(token_payload["access_token"])
        token_payload["hub_id"] = hub_account.hub_id
        token_payload["hub_domain"] = hub_account.hub_domain

        # 30 seconds buffer
        token_payload["expires_at"] = int(
            datetime.now(timezone.utc).timestamp()
            + token_payload["expires_in"]
            - self.CLOCK_SKEW
        )

        self._upsert_credentials(user_info["id"], token_payload)
        self.gateway.create_properties(token_payload["access_token"], COMPANY_PROPERTIES)
        
        html = textwrap.dedent(
            f"""\
            <!doctype html>
            <html>
            <body>
                <script>
                (function () {{
                    try {{
                    if (window.opener) {{
                        window.opener.postMessage(
                        {{ 
                            hubspot: 'connected'
                        }},
                        '{self.frontend_origin}'
                        );
                    }}
                    }} catch (e) {{
                    /* ignore */
                    }}
                    window.close();
                    setTimeout(() => window.close(), 150);
                }})();
                </script>
                Connecting to HubSpot…
            </body>
            </html>
            """
        )
        return HTMLResponse(content=html)

    def _request_tokens(self, code: str) -> Dict[str, Any]:
        return self.gateway.request_tokens(code)

    def _upsert_credentials(self, user_id: int, payload: Dict[str, Any]) -> None:
        hub_id = payload["hub_id"]
        record = self.hubspot_repo.get_by_hub_id(hub_id)

        dto_cls = HubspotUpdate if record else HubspotCreate
        dto = dto_cls(
            user_id=user_id,
            hub_id=hub_id,
            hub_domain=payload["hub_domain"],
            refresh_token=payload["refresh_token"],
            access_token=payload["access_token"],
            expires_at=payload["expires_at"],
            scopes=" ".join(payload.get("scopes", [])) or None,
        )
        if record:
            self.hubspot_repo.update(record, dto)
        else:
            self.hubspot_repo.create(dto)

    def _check_token(self, access_token: str) -> HubDomainResponse | bool:
        result = self.gateway.check_token(access_token)
        if not result:
            return False
        return HubDomainResponse(
            hub_id=result.get("hub_id"),
            hub_domain=result.get("hub_domain"),
        )

    def get_hub_account(self, token: TokenInfo) -> HubDomainResponse:
        record = self.hubspot_repo.get_hub_domain_by_user_id(token.id)
        return HubDomainResponse(
            hub_domain=record.hub_domain if record else None,
            hub_id=record.hub_id if record else None,
        )

    def _refresh_access_token_if_expired(self, hub_id) -> str:
        record = self.hubspot_repo.get_by_hub_id(hub_id)
        access_token = record.access_token

        if not record:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Portal not connected")

        if not self._check_token(record.access_token):
            payload = self._request_refresh(record.refresh_token)
            access_token = payload["access_token"]
            payload["hub_id"] = hub_id
            payload["expires_at"] = int(
                datetime.now(timezone.utc).timestamp()
                + payload["expires_in"]
                - self.CLOCK_SKEW
            )

            dto = HubspotUpdate(
                user_id=record.user_id,
                hub_id=hub_id,
                refresh_token=payload["refresh_token"],
                access_token=payload["access_token"],
                expires_at=payload["expires_at"],
            )
            self.hubspot_repo.update(record, dto)

        return access_token

    def refresh_tokens(self, hub_id: int) -> HubspotAuthResponse:
        record = self.hubspot_repo.get_by_hub_id(hub_id)
        if not record:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Portal not connected")

        payload = self._request_refresh(record.refresh_token)
        payload["hub_id"] = hub_id
        payload["expires_at"] = int(
            datetime.now(timezone.utc).timestamp()
            + payload["expires_in"]
            - self.CLOCK_SKEW
        )

        dto = HubspotUpdate(
            user_id=record.user_id,
            hub_id=hub_id,
            refresh_token=payload["refresh_token"],
            access_token=payload["access_token"],
            expires_at=payload["expires_at"],
        )
        self.hubspot_repo.update(record, dto)

        return HubspotAuthResponse(**payload)

    def _request_refresh(self, refresh_token: str) -> Dict[str, Any]:
        return self.gateway.request_refresh(refresh_token)

    # Hubspot CRUD
    def get_access_token(self, token: TokenInfo) -> str:
        record = self.hubspot_repo.get_hub_domain_by_user_id(token.id)
        if not record:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Hubspotアカウントが接続されていません",
            )
        return self._refresh_access_token_if_expired(record.hub_id)

    def _get_hubspot_range(self, start_date: str, end_date: str) -> tuple[int, int]:
        """
        Convert start and end dates (YYYY-MM-DD) into HubSpot-compatible
        Unix timestamps in milliseconds covering the full date range.

        Returns:
            (start_ms, end_ms): Tuple of start-of-day and end-of-day timestamps in ms
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        start_of_day = datetime.combine(start_dt.date(), time.min)
        end_of_day = datetime.combine(end_dt.date(), time.max)

        start_ms = int(start_of_day.timestamp() * 1000)
        end_ms = int(end_of_day.timestamp() * 1000)

        return start_ms, end_ms

    def list_companies(
        self,
        token: TokenInfo,
        limit: int = 200,
        after: Optional[str] = None,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        batch_id: Optional[int] = None,
        status: Optional[list[StatusConst]] = None,
        domain: Optional[str] = None,
    ) -> list[dict]:
        """
        Return **all** companies matching filters.
        Handles filter logic here.
        """        
        filter_groups = self._build_company_filter_groups(
            status=[], # no filter
            start=start,
            end=end,
            batch_id=batch_id,
            domain=domain
        )
        
        return self._handle_paginated(
            self.gateway.list_companies,
            token=token,
            limit=limit,
            after=after,
            filter_groups=filter_groups
        )
    
    def _build_company_filter_groups(
        self,
        *,
        status: Optional[list[StatusConst]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        batch_id: Optional[int] = None,
        domain: Optional[str] = None,
    ) -> list[dict]:
        """
        Construct HubSpot-compatible filterGroups for the company search API.

        Parameters:
            status (list[StatusConst] | None): List of statuses to filter (OR logic). If None, filters NOT_HAS_PROPERTY.
            start (str | None): ISO date string for next_form range start.
            end (str | None): ISO date string for next_form range end.
            batch_id (int | None): Optional batch ID to filter.
            domain (str | None): Optional domain to filter.

        Returns:
            list[dict]: Filter groups for the search request.
        """
        # Convert date to UNIX ms
        start_ms = end_ms = None
        if start and end:
            start_ms, end_ms = self._get_hubspot_range(start, end)

        # If multiple statuses are provided, build OR groups
        if status:
            filter_groups = []
            for s in status:
                filters = [{"propertyName": "status", "operator": "EQ", "value": s.value}]
                if start_ms is not None and end_ms is not None:
                    filters.append({
                        "propertyName": "next_form",
                        "operator": "BETWEEN",
                        "value": start_ms,
                        "highValue": end_ms,
                    })
                if batch_id is not None:
                    filters.append({
                        "propertyName": "batch_id",
                        "operator": "EQ",
                        "value": batch_id
                    })
                filter_groups.append({"filters": filters})
            return filter_groups

        # Else: only one group with AND logic
        filters = []

        # status is None → NOT_HAS_PROPERTY
        if status is None:
            filters.append({
                "propertyName": "status",
                "operator": "NOT_HAS_PROPERTY"
            })

        if start_ms is not None and end_ms is not None:
            filters.append({
                "propertyName": "next_form",
                "operator": "BETWEEN",
                "value": start_ms,
                "highValue": end_ms,
            })

        if batch_id is not None:
            filters.append({
                "propertyName": "batch_id",
                "operator": "EQ",
                "value": batch_id
            })

        if domain is not None:
            filters.append({
                "propertyName": "domain",
                "operator": "CONTAINS_TOKEN",
                "value": domain
            })
            
        return [{"filters": filters}] if filters else []


    def _handle_paginated(
        self,
        fetch_fn: Callable[..., dict],
        *,
        token: TokenInfo,
        limit: int = 100,
        after: Optional[str] = None,
        **kwargs
    ) -> list[dict]:
        """
        Generic pagination handler for HubSpot API calls.

        Parameters:
            fetch_fn (Callable): The gateway method to fetch one page of results.
            token (TokenInfo): User info details, Used to get hubspot access token.
            limit (int): Max records per request.
            after (str): Pagination cursor.
            kwargs: Additional arguments passed to fetch_fn.

        Returns:
            List[dict]: Flattened list of all results.
        """
        results = []

        @retry_on_429(max_retries=3, initial_wait=1)
        def _fetch_with_retry(**kwargs):
            return fetch_fn(**kwargs)

        while True:
            access_token = self.get_access_token(token)
            payload = _fetch_with_retry(
                access_token=access_token,
                limit=limit,
                after=after,
                **kwargs
            )
            results.extend(payload.get("results", []))
            after = payload.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

        return results
    
    def _batch_update_companies(
        self,
        token: TokenInfo,
        updates: list[dict],
        *,
        status: Optional[str] = None,
        batch_id: Optional[int] = None,
    ) -> list[dict]:
        """
        Updates companies in batches of 100. Cleans read-only properties and handles logic like chunking and property injection.
        """
        max_batch_size = 100
        results = []

        READ_ONLY_FIELDS = {"hs_object_id", "createdate", "lastmodifieddate", "archived"}

        def chunked(items, size):
            for i in range(0, len(items), size):
                yield items[i:i + size]

        for chunk in chunked(updates, max_batch_size):
            cleaned_chunk = []
            for item in chunk:
                props = {
                    k: v for k, v in item.get("properties", {}).items()
                    if k not in READ_ONLY_FIELDS
                }

                if status:
                    props["status"] = status
                if batch_id is not None:
                    props["batch_id"] = batch_id

                cleaned_chunk.append({
                    "id": item["id"],
                    "properties": props
                })

            access_token = self.get_access_token(token)
            response = self.gateway.batch_update_companies(
                access_token=access_token,
                inputs=cleaned_chunk
            )
            results.append(response)

        return results

    
    def get_contact_send_list(self, token: TokenInfo, contact_template_id: int) -> tuple[list[dict], dict]:
        """
        Get the list of companies and the template for contact sending.
        Used by the local client.
        """
        contact_template = self.contact_template_repo.get(contact_template_id)
        contact_template_dict = ContactTemplateOut.model_validate(contact_template).model_dump()
        
        date_today = date.today().isoformat()
        filter_groups = self._build_company_filter_groups(
            status=None,
            start=date_today,
            end=date_today,
            batch_id=None
        )
        
        company_list = self._handle_paginated(
            self.gateway.list_companies,
            token=token,
            filter_groups=filter_groups
        )
        
        if not company_list:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "No Company List")
            
        return company_list, contact_template_dict

    def create_batch_history(self, token: TokenInfo, status: str = StatusConst.PROCESSING) -> Any:
        execution_type_id = ExecutionTypeConst.CONTACT_SENDING.value
        return self.batch_history_repo.create(
            BatchHistoryCreate(
                execution_type_id=execution_type_id,
                user_id=token.id,
                status=status
            )
        )

    def process_contact_send(self, token: TokenInfo, contact_template_id: int, selenium_service: SeleniumService) -> None: 
        company_list, contact_template_dict = self.get_contact_send_list(token, contact_template_id)
        
        try:
            batch_history = self.create_batch_history(token)
            
            try:
                self._batch_update_companies(
                    token,
                    company_list,
                    status=StatusConst.PENDING,
                )
            except Exception as e:
                logging.exception("Error in hubspot batch update")
                  
            # Use this if testing without selenium process
            # import random
            # status = random.choice(["failed", "success"])
            
            # Loop companies and Do the contact sending (selenium)
            company_list = selenium_service.send_contact(company_list, contact_template_dict)
                
            for company in company_list:
                self.batch_history_detail_repo.create(
                    BatchHistoryDetailCreate(
                        batch_id      = batch_history.id,
                        target        = company["properties"]["domain"],
                        status        = company["properties"]["status"],
                        error_message = company.get("error_message"),
                    )
                )
                company.pop("error_message", None) 
                
            try:
                self._batch_update_companies(
                    token,
                    company_list,
                    batch_id=batch_history.id
                )
            except Exception as e:
                logging.exception("Error in hubspot batch update")
            
            batch_history = self.batch_history_repo.update(
                batch_history,
                BatchHistoryUpdate(
                    status=StatusConst.SUCCESS
                )
            )
            sleep_time = len(company_list) * 5 * 60  # seconds
            time_module.sleep(sleep_time)
            logging.info(f"Sleeping for {sleep_time/60:.0f} minutes...")
            return None
        except Exception:
            batch_history = self.batch_history_repo.update(
                batch_history,
                BatchHistoryUpdate(
                    status=StatusConst.FAILED
                )
            )

    # VOID
    def process_contact_wait(self, token: TokenInfo, contact_template_id: int, selenium_service: SeleniumService) -> None:
        """Open and prefill company contact forms in Selenium and wait.

        Each contact page is opened in its own tab within a headed Selenium
        browser and prefilled using :class:`LegacySeleniumContact`. Submission
        is intentionally skipped so that a human can review and send later.
        The browser session remains active for one hour.
        """
        contact_template = self.contact_template_repo.get(contact_template_id)
        contact_template_dict = ContactTemplateOut.model_validate(
            contact_template
        ).model_dump()

        date_today = date.today().isoformat()
        filter_groups = self._build_company_filter_groups(
            status= StatusConst.FAILED,
            start=date_today,
            end=date_today,
            batch_id=None,
        )

        company_list = self._handle_paginated(
            self.gateway.list_companies,
            token=token,
            filter_groups=filter_groups,
        )
        
        if not company_list:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "No Company List")

        targets: list[tuple[str, str]] = []
        for company in company_list:
            url = (
                company["properties"].get("corporate_contact_url")
                or company["properties"].get("domain")
            )
            if url:
                title = company["properties"].get("name", "")
                targets.append((url, title))
        
            driver = selenium_service.driver
            company_list = selenium_service.open_company_urls(company_list, contact_template_dict)

            sleep_time = len(company_list) * 5 * 60  # seconds
            logging.info(f"Sleeping for {sleep_time/60:.0f} minutes...")



    """ VOID BELOW NOT USED"""
    # Contacts
    def create_contact(self, token: TokenInfo, data: ContactIn) -> Dict[str, Any]:
        payload = {
            "properties": data.model_dump(exclude_none=True, exclude={"properties"})
            | data.properties
        }
        access_token = self.get_access_token(token)
        return self.gateway.create_contact(access_token, payload)

    def update_contact(
        self, token: TokenInfo, contact_id: str, data: ContactIn
    ) -> Dict[str, Any]:
        payload = {
            "properties": data.model_dump(exclude_none=True, exclude={"properties"})
            | data.properties
        }
        access_token = self.get_access_token(token)
        return self.gateway.update_contact(access_token, contact_id, payload)

    def delete_contact(self, token: TokenInfo, contact_id: str) -> None:
        access_token = self.get_access_token(token)
        self.gateway.delete_contact(access_token, contact_id)

    def list_contacts(
        self, token: TokenInfo, limit: int = 20, after: Optional[str] = None
    ) -> Dict[str, Any]:
        access_token = self.get_access_token(token)
        return self.gateway.list_contacts(access_token, limit, after)

    # Companies
    def create_company(self, token: TokenInfo, data: CompanyIn) -> Dict[str, Any]:
        payload = {
            "properties": data.model_dump(exclude_none=True, exclude={"properties"})
            | data.properties
        }
        access_token = self.get_access_token(token)
        return self.gateway.create_company(access_token, payload)

    def update_company(
        self, token: TokenInfo, company_id: str, data: CompanyIn
    ) -> Dict[str, Any]:
        payload = {
            "properties": data.model_dump(exclude_none=True, exclude={"properties"})
            | data.properties
        }
        access_token = self.get_access_token(token)
        return self.gateway.update_company(access_token, company_id, payload)

    def delete_company(self, token: TokenInfo, company_id: str) -> None:
        access_token = self.get_access_token(token)
        self.gateway.delete_company(access_token, company_id)

    def get_serp_domains(self, limit: int = 10) -> list[dict]:
        from src.models.serp_result import SerpResult
        
        results = (
            self.hubspot_repo.db.query(SerpResult)
            .filter(SerpResult.domain_name.isnot(None))
            .order_by(SerpResult.created_at.desc())
            .limit(limit)
            .all()
        )
        
        # Format as company objects compatible with our client
        companies = []
        for r in results:
            companies.append({
                "id": str(r.id), # Use SerpResult ID as company ID
                "properties": {
                    "name": r.title or r.domain_name,
                    "domain": r.domain_name,
                    "corporate_contact_url": r.url_corporate_site or r.link
                }
            })
            
        return companies
        