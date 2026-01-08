import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import httpx
from sqlalchemy.orm import Session

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from src.config.config import get_env
from src.schemas import SerpRequest, SerpResponse, SearchResult
from src.repositories import KeywordRepository, SerpResultRepository
from src.schemas.keyword import KeywordBulk, KeywordUpdate
from src.utils.constants import GoogleConst, StatusConst
from src.utils.decorators import try_except_decorator_no_raise, retry_on_429

class SerpService:
    def __init__(self, db: Session):
        self.keyword_repo = KeywordRepository(db)
        self.serp_repo = SerpResultRepository(db)
        self.api_key = get_env("GOOGLE_API_KEY", required=True)
        self.cse_id = get_env("GOOGLE_CSE_ID", required=True)

        # Google Ads credentials
        self.geo_id = get_env("GOOGLE_ADS_GEO_ID", default="2392")
        self.lang_id = get_env("GOOGLE_ADS_LANGUAGE_ID", default="1000")
        self.ads_developer_token = get_env("GOOGLE_ADS_DEVELOPER_TOKEN", required=True)
        self.ads_refresh_token = get_env("GOOGLE_ADS_REFRESH_TOKEN", required=True)
        self.ads_customer_id = get_env("GOOGLE_ADS_CUSTOMER_ID", required=True)
        
        ads_config = {
            "developer_token": self.ads_developer_token,
            "client_id": get_env("GOOGLE_OAUTH_CLIENT_ID", required=True),
            "client_secret": get_env("GOOGLE_OAUTH_CLIENT_SECRET", required=True),
            "refresh_token": self.ads_refresh_token,
            "use_proto_plus": True,
        }
        
        self.ads_client = GoogleAdsClient.load_from_dict(ads_config)

    # Google Call
    @try_except_decorator_no_raise(fallback_value=[])
    def _search_page(self, query: str, start: int) -> List[Dict]:
        @retry_on_429(max_retries=5, initial_wait=1)
        def _make_request():
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q":  query,
                "num": GoogleConst.PAGE_SIZE,
                "start": start,
                "lr": GoogleConst.LANGUAGE,
                "gl": GoogleConst.GEOLOCATION
            }
            return httpx.get(GoogleConst.GOOGLE_API_URL, params=params, timeout=GoogleConst.HTTP_TIMEOUT)
        
        res = _make_request()
        if res:
            res.raise_for_status()  # Will raise HTTPStatusError if not 2xx
            return res.json().get("items", [])
        return []

    @try_except_decorator_no_raise(fallback_value=0)
    def site_size(self, link: str) -> int:
        @retry_on_429(max_retries=5, initial_wait=1)
        def _make_request():
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q":  f"site:{link}",
            }
            return httpx.get(GoogleConst.GOOGLE_API_URL, params=params, timeout=GoogleConst.HTTP_TIMEOUT)
        
        res = _make_request()
        if res:
            res.raise_for_status()  # Will raise HTTPStatusError if not 2xx
            info = res.json().get("searchInformation", {})
            return int(info.get("totalResults", 0))
        return 0
    
    @try_except_decorator_no_raise(fallback_value=[])
    def fetch_top_100(self, keyword: str) -> List[Dict]:
        """10 paginated requests → ≤ 100 items."""
        all_items: List[Dict] = []
        
        # 1,11,21…91
        for start in range(1, GoogleConst.PAGE_SIZE * GoogleConst.ITEMS, GoogleConst.PAGE_SIZE):
            items = self._search_page(keyword, start)
            if not items:
                break
            all_items.extend(items)
        return all_items

    @try_except_decorator_no_raise(fallback_value=0)
    def fetch_search_volume(self, keyword: str) -> int:
        """
        Return the average monthly search volume for `keyword`
        using Google Ads KeywordPlanIdeaService.

        Args:
            keyword (str): The keyword to query.

        Returns:
            int: Integer average of monthly search volumes.
                Returns 0 if no volume data is found or an error occurs.
        """
        @retry_on_429(max_retries=5, initial_wait=1)
        def _make_ads_request():
            svc = self.ads_client.get_service("CustomerService")
            logging.info(svc.list_accessible_customers().resource_names)
            
            idea_service = self.ads_client.get_service("KeywordPlanIdeaService")
            request = self.ads_client.get_type("GenerateKeywordHistoricalMetricsRequest")
            request.customer_id = self.ads_customer_id
            request.keyword_plan_network = (
                self.ads_client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
            )
            request.keywords.append(keyword)

            request.geo_target_constants.append(f"geoTargetConstants/{self.geo_id}")
            request.language = f"languageConstants/{self.lang_id}"

            try:
                response = idea_service.generate_keyword_historical_metrics(request=request)
                return response
            except GoogleAdsException as e:
                # Check if it's a rate limit error from Google Ads
                for error in e.failure.errors:
                    if "RESOURCE_EXHAUSTED" in str(error.error_code) or "quota" in str(error.message).lower():
                        # Create a mock response with status_code 429 to trigger retry
                        class MockResponse:
                            status_code = 429
                        return MockResponse()
                raise

        response = _make_ads_request()
        
        # If we got a MockResponse (429), it means we exhausted retries
        if hasattr(response, 'status_code') and response.status_code == 429:
            return 0

        total_searches = 0
        months_count = 0
        
        if response and response.results:
            result = response.results[0]
            for msv in result.keyword_metrics.monthly_search_volumes:
                total_searches += msv.monthly_searches
                months_count += 1

        if months_count == 0:
            return 0

        return total_searches // months_count
