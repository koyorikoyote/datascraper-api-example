import math
import re
from urllib.parse import urlparse
import jwt
from numbers import Number
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.config.config import get_env

def clamp(value: float, min_value: float = 0.0, max_value: float = 10.0) -> float:
    """
    Keep `value` within [min_value, max_value].

    Args:
        value (float): Number to limit.
        min_value (float): Lower bound.
        max_value (float): Upper bound.

    Returns:
        float: The clamped value.
    """
    return max(min_value, min(value, max_value))

def log_score(value: Number, min_log: float = 1.0, max_log: float = 6.0) -> float:
    """
    Convert a raw count to a 0–10 score using log-scaling.

    Args:
        value:    Positive count (e.g., search volume or indexed pages).
        min_log:  log10 threshold that maps to 0 pts  (default: log10(10)).
        max_log:  log10 threshold that maps to 10 pts (default: log10(1_000_000)).

    Returns:
        float in the range 0–10.
    """
    if value <= 0:
        return 0.0
    return clamp((math.log10(value) - min_log) / (max_log - min_log) * 10.0)

def encode_jwt(data: Dict[str, Any]) -> str:
    return jwt.encode(
        data,
        get_env("SECRET_KEY"),
        algorithm=get_env("ALGORITHM"),
    )

def decode_jwt(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        get_env("SECRET_KEY"),
        algorithms=[get_env("ALGORITHM")],
    )

def get_domain_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r'^https?://', raw):
        raw = 'https://' + raw  # default to HTTPS

    parsed = urlparse(raw)
    domain = parsed.netloc or parsed.path  # handle cases like 'example.com'
    return f'https://{domain}'

def get_bare_domain(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r'^https?://', raw, re.IGNORECASE):
        raw = 'https://' + raw  # ensure urlparse works

    parsed = urlparse(raw)
    domain = parsed.netloc or parsed.path

    # Strip port if present
    domain = domain.split(':')[0]

    # Strip "www." prefix if present
    if domain.startswith("www."):
        domain = domain[4:]

    return domain