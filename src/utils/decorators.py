import datetime
from functools import wraps
import logging
from datetime import datetime, time as datetime_time
from typing import Callable, Optional
import time

import httpx
from fastapi import HTTPException, status
from src.schemas import (
    BatchHistoryCreate,
    BatchHistoryUpdate,
    BatchHistoryDetailCreate,
    BatchHistoryDetailUpdate,
)
from src.utils.constants import StatusConst, ExecutionTypeConst


def retry_on_429(max_retries: int = 5, initial_wait: int = 1):
    """
    Decorator to handle 429 errors with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_wait: Initial wait time in minutes
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait_time = initial_wait
            for attempt in range(max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    # Check if it's an httpx response and has status_code
                    if hasattr(response, 'status_code'):
                        if response.status_code == 429:
                            if attempt < max_retries:
                                logging.warning(f"Rate limit hit (429) for {func.__name__}. Attempt {attempt + 1}/{max_retries}. Waiting {wait_time} minutes...")
                                time.sleep(wait_time * 60)  # Convert minutes to seconds
                                wait_time *= 2  # Exponential backoff
                                continue
                            else:
                                logging.error(f"Max retries reached for {func.__name__} after 429 errors")
                                raise HTTPException(
                                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                    detail=f"Resource exhausted after {max_retries} retries"
                                )
                    return response
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        if attempt < max_retries:
                            logging.warning(f"Rate limit hit (429) for {func.__name__}. Attempt {attempt + 1}/{max_retries}. Waiting {wait_time} minutes...")
                            time.sleep(wait_time * 60)
                            wait_time *= 2
                            continue
                        else:
                            logging.error(f"Max retries reached for {func.__name__} after 429 errors")
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Resource exhausted after {max_retries} retries"
                            )
                    raise
                except Exception as e:
                    # For non-429 errors, just raise them
                    raise
            return None  # Should not reach here
        return wrapper
    return decorator


def try_except_decorator(func):
    """Wraps in try-except. Logs function calls, arguments, and results."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            logging.info("Function %s returned: %s", func.__name__, result)
            return result
        except httpx.HTTPStatusError as e:
            logging.error("HTTP status error in %s: %s", func.__name__, e.response.text)
            raise RuntimeError(
                f"HubSpot returned error response: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logging.error("HTTP request error in %s: %s", func.__name__, str(e))
            raise RuntimeError(f"HubSpot request failed: {e}")
        except Exception as e:
            logging.error("Exception in %s: %s", func.__name__, str(e))
            raise e  # Re-raise the exception

    return wrapper


def try_except_decorator_no_raise(fallback_value=None):
    """
    Decorator similar to try_except_decorator, but on exception:
    - Logs the error (with special handling for httpx exceptions)
    - Returns 'fallback_value' (default: None)
    - Does NOT re-raise, so execution continues.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                logging.info("Function %s returned: %s", func.__name__, result)
                return result
            except httpx.HTTPStatusError as e:
                logging.error(
                    "HTTP status error in %s: %s | response: %s",
                    func.__name__,
                    str(e),
                    e.response.text,
                )
            except httpx.RequestError as e:
                logging.error("HTTP request error in %s: %s", func.__name__, str(e))
            except Exception as e:
                logging.error("Exception in %s: %s", func.__name__, str(e))

            logging.warning(
                "Returning fallback_value=%s instead of raising.", fallback_value
            )
            return fallback_value

        return wrapper

    return decorator


def track_batch_history(execution_type: ExecutionTypeConst):
    """
    Decorator to track batch history for a function.
    Creates a batch history record before executing the function,
    and updates it with the status and duration after the function completes.

    Args:
        execution_type: The ExecutionTypeConst value for the batch history record

    The decorated function must have the following parameters:
    - self: The instance of the class containing the batch_history_repo
    - token: The TokenInfo object containing the user ID
    - ids: A list of keyword IDs (optional, first ID will be used as keyword_id if provided)
    """


def track_batch_history(execution_type: ExecutionTypeConst):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            token = kwargs.get("token") or (args[1] if len(args) > 1 else None)

            ids = kwargs.get("ids") or (args[0] if len(args) > 0 else [])
            first_keyword_id = ids[0] if ids else None

            # Check if token is None or doesn't have an id attribute
            user_id = token.id if token and hasattr(token, "id") else None

            batch_history = self.batch_history_repo.create(
                BatchHistoryCreate(
                    execution_type_id=execution_type.value,
                    user_id=user_id,
                    keyword_id=first_keyword_id,
                    status=StatusConst.PROCESSING,
                )
            )

            # 💡 Attach to self so decorated method can use it
            self._current_batch_history = batch_history
            self._execution_type_id = execution_type.value

            start_time = datetime.now()

            try:
                result = func(self, *args, **kwargs)

                duration_seconds = (datetime.now() - start_time).total_seconds()
                h, rem = divmod(duration_seconds, 3600)
                m, s = divmod(rem, 60)
                duration_time = datetime_time(int(h), int(m), int(s))

                self.batch_history_repo.update(
                    batch_history,
                    BatchHistoryUpdate(
                        status=StatusConst.SUCCESS, duration=duration_time
                    ),
                )

                return result
            except Exception as e:
                duration_seconds = (datetime.now() - start_time).total_seconds()
                h, rem = divmod(duration_seconds, 3600)
                m, s = divmod(rem, 60)
                duration_time = datetime_time(int(h), int(m), int(s))

                logging.error(f"Error in {func.__name__}: {e}")
                self.batch_history_repo.update(
                    batch_history,
                    BatchHistoryUpdate(
                        status=StatusConst.FAILED, duration=duration_time
                    ),
                )
                return None

        return wrapper

    return decorator


def track_batch_detail():
    """
    Decorator to create a batch history detail record for each keyword operation.

    Assumes:
    - The decorated method is a class method with `self`
    - Accepts `keyword_id` as an argument or kwarg
    - Uses `batch_id`
    - Uses `BatchHistoryDetailCreate`
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):

            # Determine the target identifier for batch tracking
            try:
                keyword_id = None
                if self._execution_type_id == ExecutionTypeConst.CONTACT_SENDING.value:
                    company = kwargs.get("company") or (args[0] if args else None)
                    domain = (
                        company.get("properties", {}).get("domain")
                        if isinstance(company, dict)
                        else None
                    )
                    target = domain if domain else "-"

                elif "serp" in kwargs and hasattr(kwargs["serp"], "link"):
                    target = kwargs["serp"].link

                elif args and hasattr(args[0], "link"):
                    target = args[0].link

                else:
                    keyword_id = kwargs.get("keyword_id") or (args[0] if args else None)
                    keyword_obj = self.keyword_repo.get(keyword_id)
                    keyword = (
                        getattr(keyword_obj, "keyword", None) if keyword_obj else None
                    )
                    target = keyword if keyword else "-"

            except Exception as e:
                logging.warning("Failed to extract target: %s", e)
                target = "-"

            # Truncate target to fit database column limit (2000 chars)
            if target and len(target) > 2000:
                target = target[:1997] + "..."

            try:
                result = func(self, *args, **kwargs)

                # Determine result status
                if result is None:
                    # Consider "no results" a failure (customizable)
                    self.batch_history_detail_repo.create(
                        BatchHistoryDetailCreate(
                            batch_id=self._current_batch_history.id,
                            target=target,
                            keyword_id=keyword_id if keyword_id else None,
                            status=StatusConst.FAILED,
                            error_message="No result returned",
                        )
                    )
                else:
                    # Successful processing
                    self.batch_history_detail_repo.create(
                        BatchHistoryDetailCreate(
                            batch_id=self._current_batch_history.id,
                            keyword_id=keyword_id if keyword_id else None,
                            target=target,
                            status=StatusConst.SUCCESS,
                        )
                    )
                return result

            except Exception as e:
                logging.error("Error processing %s: %s", target, e)
                error_msg = str(e)
                # Truncate error message to fit database column limit (1000 chars)
                if len(error_msg) > 1000:
                    error_msg = error_msg[:997] + "..."

                self.batch_history_detail_repo.create(
                    BatchHistoryDetailCreate(
                        batch_id=self._current_batch_history.id,
                        target=target,
                        status=StatusConst.FAILED,
                        error_message=error_msg,
                    )
                )
                return None  # or raise if you want to halt on error

        return wrapper

    return decorator
