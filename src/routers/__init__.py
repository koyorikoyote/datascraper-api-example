from .user import router as user_router
from .auth import router as auth_router
from .user_role import router as user_role_router
from .keyword import router as keyword_router
from .google_oauth import router as google_oauth_router
from .hubspot import router as hubspot_router
from .serp_result import router as serp_result_router
from .batch_history import router as batch_history_router
from .contact_template import router as contact_template_router
from .score_setting import router as score_setting_router
from .dashboard import router as dashboard_router
from .temp_test import router as temp_test
from .sqs_monitor import router as sqs_monitor_router
from .client import router as client_router

__all__ = [
    "user_router",
    "auth_router",
    "user_role_router",
    "keyword_router",
    "google_oauth_router",
    "hubspot_router",
    "serp_result_router",
    "batch_history_router",
    "contact_template_router",
    "score_setting_router",
    "dashboard_router",
    "temp_test",
    "sqs_monitor_router",
    "client_router",
]
