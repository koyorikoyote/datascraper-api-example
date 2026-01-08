from enum import Enum, IntEnum
from typing import Any

class GoogleConst:
    GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"
    PAGE_SIZE = 1
    ITEMS = 101 # 101 eqivalent to 100 searches
    TTL_SECONDS = 15 * 60
    HTTP_TIMEOUT = 10.0
    CONCURRENCY = 10
    LANGUAGE = "lang_ja"
    GEOLOCATION = "jp"

class HubspotConst:
    AUTHORIZATION_URL = "https://app.hubspot.com/oauth/authorize"
    EXCHANGE_URL = "https://api.hubapi.com/oauth/v1/token"
    ACCESS_DETAILS_URL = "https://api.hubapi.com/oauth/v1/access-tokens"
    BASE_CRM_URL = "https://api.hubapi.com/crm/v3/objects"
    BASE_URL = "https://api.hubapi.com"
    COMPANY_PROPERTY_LIST: list = ["name", "domain", "next_form", "status", "batch_id"]
    
class StatusConst(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    SUCCESS = "success"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    WAITING = "waiting"
    
class RankConst:
    A_RANK = "A"
    B_RANK = "B"
    C_RANK = "C"
    D_RANK = "D"
    
    SERVICE_PRICE = "service_price"
    SERVICE_VOLUME = "service_volume"
    SITE_SIZE = "site_size"

class ExecutionTypeConst(Enum):
    URL_FETCH          = (1, "url_fetch",          "URL取得")
    RANK_FETCH         = (2, "rank_fetch",         "ランク取得")
    CSV_EXPORT         = (3, "csv_export",         "CSV出力")
    CONTACT_SENDING    = (4, "contact_sending",    "問い合わせ実行")
    PARTIAL_RANK_FETCH = (5, "partial_rank_fetch", "部分ランク取得")

    def __init__(self, code: int, code_str: str, jp_name: str):
        self._value_  = code          # numeric code (Enum value)
        self.code_str = code_str      # snake-case text
        self.jp_name  = jp_name       # Japanese label


    @classmethod
    def _missing_(cls, value):
        for m in cls:
            if value == m._value_:
                return m
        raise ValueError(f"{value!r} is not a valid {cls.__name__}")
    
    @classmethod
    def parse(cls, v: Any) -> "ExecutionTypeConst":
        if isinstance(v, cls):
            return v
        if isinstance(v, int):
            return cls(v)
        if isinstance(v, str):
            for m in cls:
                if v in {m.name, m.code_str, m.jp_name}:
                    return m
        if isinstance(v, dict):
            return cls.parse(v.get("code") or v.get("code_str") or v.get("jp_name"))
        raise ValueError(f"cannot convert {v!r} to ExecutionTypeConst")
    
    
class HubspotExcelColumnsConst:
    """
    Canonical column identifiers and their Japanese Excel headers.
    Example usage:
        jp_header = ExcelColumnsConst.JP_HEADER_MAP[ExcelColumnsConst.PHONE_NUMBER]
        internal_key = ExcelColumnsConst.JP_TO_KEY.get("会社名")
    """

    # snake_case keys
    COMPANY_NAME: str = "company_name"
    DOMAIN_NAME: str = "domain_name"
    CONTACT_PERSON: str = "contact_person"
    RANK: str = "rank"
    PHONE_NUMBER: str = "phone_number"
    URL_CORPORATE_SITE: str = "url_corporate_site"
    URL_SERVICE_SITE: str = "url_service_site"
    EMAIL_ADDRESS: str = "email_address"
    NOTES: str = "notes"
    ACTIVITY_DATE: str = "activity_date"

    # Mapping: snake_case -> Japanese header
    JP_HEADER_MAP: dict[str, str] = {
        COMPANY_NAME: "会社名",
        DOMAIN_NAME: "会社のドメイン名",
        CONTACT_PERSON: "会社の担当者",
        RANK: "リストランク",
        PHONE_NUMBER: "電話番号",
        URL_CORPORATE_SITE: "問い合わせURL（コーポレートサイト）",
        URL_SERVICE_SITE: "問い合わせURL（サービスサイト）",
        EMAIL_ADDRESS: "問い合わせメールアドレス",
        NOTES: "メモ",
        ACTIVITY_DATE: "アクティビティー日",
    }

    # Optional: reverse lookup (Japanese -> snake_case)
    JP_TO_KEY: dict[str, str] = {jp: key for key, jp in JP_HEADER_MAP.items()}
