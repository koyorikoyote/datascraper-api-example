import json
import logging
import math
import re
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import csv
import io
from datetime import datetime, time, timedelta
import urllib.parse
import asyncio
import time as time_module
import pandas as pd


from src.models.keyword import Keyword
from src.models.batch_history import BatchHistory
from src.models.batch_history_detail import BatchHistoryDetail
from src.models.user import User
from src.repositories.serp_result import SerpResultRepository
from src.repositories.batch_history import BatchHistoryRepository
from src.repositories.batch_history_detail import BatchHistoryDetailRepository
from src.repositories.user import UserRepository
from src.schemas import (
    KeywordOut,
    KeywordCreate,
    KeywordUpdate,
    KeywordInDB,
    RankGPTResponse,
    ScoreSetting,
    SerpResultInDBBase,
    ScoreThresholdOut,
    WeightedMetricOut,
    LinkGPTResponse,
    RankComputation,
    CandidateKeyword,
    KeywordComputedOut,
    SearchResult,
    SearchResultUpdate,
    SerpResponse,
    TokenInfo,
    BatchHistoryCreate,
    BatchHistoryUpdate,
    BatchHistoryDetailCreate,
    BatchHistoryDetailUpdate,
)
from src.repositories import KeywordRepository
from src.services.chatgpt import ChatGPTService
from src.services.score_setting import ScoreSettingService
from src.services.selenium import SeleniumService
from src.services.serp import SerpService
from src.services.hubspot import HubspotService
from src.utils.constants import RankConst, StatusConst, ExecutionTypeConst
from src.utils.utils import get_domain_url, log_score, get_bare_domain
from src.utils.decorators import (
    track_batch_history,
    track_batch_detail,
    try_except_decorator,
    try_except_decorator_no_raise,
)


class KeywordService:
    def __init__(self, db: Session):
        self.keyword_repo = KeywordRepository(db)
        self.serp_repo = SerpResultRepository(db)
        self.serp_service = SerpService(db)
        self.chatgpt_service = ChatGPTService(db)
        self.score_setting = ScoreSettingService(db)
        self.batch_history_repo = BatchHistoryRepository(db)
        self.batch_history_detail_repo = BatchHistoryDetailRepository(db)
        self.user_repo = UserRepository(db)
        self.hubspot_service = HubspotService(db)

    def create_keyword(self, keyword_in: KeywordCreate, token: TokenInfo) -> KeywordOut:
        # Check for existing keyword
        existing_keyword = self.keyword_repo.get_by_keyword(keyword_in.keyword)

        if existing_keyword:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"キーワード「{keyword_in.keyword}」はすでに存在します。",
            )

        # Create new keyword
        keyword_db = KeywordInDB(**keyword_in.model_dump())
        return self.keyword_repo.create(keyword_db, token)

    def get_keyword(self, keyword_id: int) -> KeywordOut | None:
        return self.keyword_repo.get(keyword_id)

    def list_keywords(
        self, skip: int = 0, limit: int | None = None
    ) -> list[KeywordComputedOut]:
        return self.keyword_repo.list(skip, limit)

    def update_keyword(
        self, keyword_id: int, keyword_in: KeywordUpdate
    ) -> KeywordOut | None:
        db_keyword = self.keyword_repo.get(keyword_id)
        if not db_keyword:
            return None
        return self.keyword_repo.update(db_keyword, keyword_in)

    def delete_keyword(self, keyword_id: int) -> bool:
        db_keyword = self.keyword_repo.get(keyword_id)
        if not db_keyword:
            return False
        self.keyword_repo.delete(db_keyword)
        return True

    def delete_keywords_bulk(self, ids: list[int]) -> int:
        return self.keyword_repo.delete_bulk(ids)

    def set_keywords_status(self, ids: list[int], status_field: str, status_value: str) -> None:
        """
        Bulk update status for keywords.
        
        Args:
            ids: List of keyword IDs to update
            status_field: The field to update ('fetch_status', 'rank_status', or 'partial_rank_status')
            status_value: The new status value
        """
        if not ids:
            return

        # Using direct update for efficiency
        stmt = (
            text(f"UPDATE keyword SET {status_field} = :status, updated_at = NOW() WHERE id IN :ids")
            .bindparams(status=status_value)
            .bindparams(ids=tuple(ids))  # tuple is required for IN clause with bindparams in sqlalchemy
        )
        
        # Handle the tuple conversion manually         
        self.keyword_repo.db.query(Keyword).filter(Keyword.id.in_(ids)).update(
            {status_field: status_value, "updated_at": datetime.now()}, 
            synchronize_session=False
        )
        self.keyword_repo.db.commit()

    def set_fetch_status(self, ids: list[int], status: str) -> None:
        self.set_keywords_status(ids, "fetch_status", status)

    def set_rank_status(self, ids: list[int], status: str) -> None:
        self.set_keywords_status(ids, "rank_status", status)

    def set_partial_rank_status(self, ids: list[int], status: str) -> None:
        self.set_keywords_status(ids, "partial_rank_status", status)

    def fail_processing_serp_results(self, keyword_ids: list[int]) -> int:
        """
        Mark all processing SERP results for the given keywords as FAILED.
        """
        return self.serp_repo.update_processing_to_failed(keyword_ids)


    def _create_batch_history(
        self, execution_type_id: int, user_id: int, keyword_id: int = None
    ) -> BatchHistory:
        """Create a new batch history record with PROCESSING status"""
        return self.batch_history_repo.create(
            BatchHistoryCreate(
                execution_type_id=execution_type_id,
                user_id=user_id,
                keyword_id=keyword_id,
                status=StatusConst.PROCESSING,
            )
        )

    @track_batch_history(ExecutionTypeConst.CSV_EXPORT)
    def export_to_csv(self, ids: list[int], token: TokenInfo) -> tuple[str, str]:
        """Export SERP results to CSV format"""
        serp_results = []

        for keyword_id in ids:
            results = self._process_keyword_for_csv(keyword_id)
            if results:
                serp_results.extend(results)

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        headers_jp = [
            "会社名",
            "会社のドメイン名",
            "Hubspot重複",
            "会社の担当者",
            "リストランク",
            "電話番号",
            "問い合わせURL（コーポレートサイト）",
            "問い合わせURL（サービスサイト）",
            "問い合わせメールアドレス",
            "メモ",
            "アクティビティー日",
            "タイトル",
            "サービス単価",
            "KW検索ボリューム",
            "サイト規模",
            "コラム有無",
            "自社サービス有無",
            "業種"
        ]

        headers_en = [
            "Company Name",
            "Company Domain Name",
            "Hubspot Duplicate",
            "Company Contact Person",
            "List Rank",
            "Phone Number",
            "Inquiry URL (Corporate Site)",
            "Inquiry URL (Service Site)",
            "Inquiry Email Address",
            "Memo",
            "Activity Date",
            "Title",
            "Service Unit Price",
            "KW Search Volume",
            "Site Scale",
            "Has Column",
            "Has Own Product or Service",
            "Industry"
        ]

        writer.writerow(headers_jp)

        # Write data rows
        for result in serp_results:

            # Export completed (SUCCESS), partial (PARTIAL), and fetched (PENDING) results; skip failures and in-progress
            if result.status in [StatusConst.FAILED, StatusConst.PROCESSING]:
                continue
            
            result: SerpResultInDBBase = result  # Ensure type is correct
            row = [
                result.company_name or "",
                result.domain_name or "",
                "重複" if result.is_hubspot_duplicate else "重複なし",
                result.contact_person or "",
                result.rank or "",
                result.phone_number or "",
                result.url_corporate_site or "",
                result.url_service_site or "",
                result.email_address or "",
                result.notes or "",
                (
                    result.activity_date.strftime("%m/%d/%Y")
                    if result.activity_date
                    else ""
                ),
                result.title or "",
                result.service_price or "",
                result.service_volume or "",
                result.site_size or "",
                ('あり' if result.has_column_section is True else 'なし' if result.has_column_section is False else ""),
                ('あり' if result.has_own_product_service_offer is True else 'なし' if result.has_own_product_service_offer is False else ""),
                (result.industry or ""),
            ]
            writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        # 【HubSpotインポート用】_{user_name}_{current_date}.csv
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"【HubSpotインポート用】_{token.email}_{current_date}.csv"
        encoded_filename = urllib.parse.quote(filename)

        return csv_content, encoded_filename

    @track_batch_detail()
    def _process_keyword_for_csv(self, keyword_id: int):
        keyword_obj = self.keyword_repo.get(keyword_id)
        return keyword_obj.serp_results

    def _verify_hubspot_token(self, token) -> str:
        self.hubspot_service.get_access_token(token)
        
    @track_batch_history(ExecutionTypeConst.URL_FETCH)
    def run_fetch(self, ids: list[int], token: TokenInfo, job_id: str = None) -> list[SerpResponse]:
        """
        Run URL fetch for the given keyword IDs.
        
        Args:
            ids: List of keyword IDs to fetch
            token: User token info
            job_id: Optional SQS job ID for cancellation checking
        """
        responses: list[SerpResponse] = []
        keywords_to_process = []
        
        # First phase: Filter valid keywords
        for keyword_id in ids:
            keyword_obj = self.keyword_repo.get(keyword_id)
            if not keyword_obj:
                continue          
            
            keywords_to_process.append(keyword_id)

        # Second phase: Process each keyword with cancellation checking
        for keyword_id in keywords_to_process:
            # Update status to PROCESSING just before starting work
            keyword_to_update = self.keyword_repo.get(keyword_id)
            if keyword_to_update:
                self.keyword_repo.update(
                    keyword_to_update, KeywordUpdate(fetch_status=StatusConst.PROCESSING)
                )

            # Check for cancellation before processing each keyword
            if job_id:
                from src.utils.cancellation import is_job_cancelled, JobCancelledException
                if is_job_cancelled(job_id, self.keyword_repo.db):
                    logging.info(f"Job {job_id} cancelled - resetting remaining keywords to pending")
                    # Reset remaining keywords to pending
                    for remaining_id in keywords_to_process[keywords_to_process.index(keyword_id):]:
                        remaining_keyword = self.keyword_repo.get(remaining_id)
                        if remaining_keyword:
                            self.keyword_repo.update(
                                remaining_keyword, KeywordUpdate(fetch_status=StatusConst.PENDING)
                            )
                    raise JobCancelledException(job_id, "Fetch job cancelled by user")
            
            try:
                result = self._process_keyword_for_fetch(keyword_id, token)
                if result:
                    responses.append(result)
            except Exception as e:
                from src.utils.cancellation import JobCancelledException
                if isinstance(e, JobCancelledException):
                    logging.info(f"Job {job_id} cancelled during fetch - resetting current and remaining keywords")
                    # Reset current keyword
                    if keyword_to_update:
                        self.keyword_repo.update(keyword_to_update, KeywordUpdate(fetch_status=StatusConst.PENDING))
                    
                    # Reset remaining keywords
                    current_idx = keywords_to_process.index(keyword_id)
                    for remaining_id in keywords_to_process[current_idx + 1:]:
                        remaining_keyword = self.keyword_repo.get(remaining_id)
                        if remaining_keyword:
                            self.keyword_repo.update(remaining_keyword, KeywordUpdate(fetch_status=StatusConst.PENDING))
                    raise  # Re-raise cancellation exceptions
                
                logging.error(
                    "Unexpected Error at run_fetch for keyword_id %s: %s",
                    keyword_id,
                    str(e),
                )
                # Update keyword status to FAILED
                keyword_obj = self.keyword_repo.get(keyword_id)
                if keyword_obj:
                    self.keyword_repo.update(
                        keyword_obj, KeywordUpdate(fetch_status=StatusConst.FAILED)
                    )
                continue

        return responses

    @track_batch_detail()
    def _process_keyword_for_fetch(self, keyword_id: int, token: TokenInfo) -> SerpResponse | None:
        keyword_obj = self.keyword_repo.get(keyword_id)

        if not keyword_obj or not keyword_obj.keyword:
            raise ValueError("Keyword not found")

        items = self.serp_service.fetch_top_100(keyword_obj.keyword)
        if not items:
            self.keyword_repo.update(
                keyword_obj, KeywordUpdate(fetch_status=StatusConst.FAILED)
            )
            raise ValueError(f"Failed to fetch SERP for keyword={keyword_obj.keyword}")
                
        seen_links = set()
        seen_domains = set()
        filtered_items = []
        for idx, item in enumerate(items, start=1):
            link = item.get("link", "")
            if link and link not in seen_links:
                serp_domain = (get_bare_domain(link) or "").lower().lstrip(".")
                
                # Filter out duplicate domains
                if serp_domain in seen_domains:
                    continue
                seen_domains.add(serp_domain)
                
                seen_links.add(link)
                match_list = self.hubspot_service.list_companies(token, limit=1, domain=serp_domain)
                is_hubspot_duplicate = True if match_list else False

                filtered_items.append(
                    SearchResult(
                        title=item.get("title", ""),
                        link=link,
                        snippet=item.get("snippet", ""),
                        position=idx,
                        is_hubspot_duplicate=is_hubspot_duplicate,
                    )
                )

        self.serp_repo.upsert_bulk_hubspot_duplicate(keyword_obj.id, filtered_items)

        self.keyword_repo.update(
            keyword_obj, KeywordUpdate(fetch_status=StatusConst.SUCCESS)
        )

        return SerpResponse(
            keyword_id=keyword_obj.id,
            keyword=keyword_obj.keyword,
            results=filtered_items,  # return all non-internal-duplicate results
        )

    @track_batch_history(ExecutionTypeConst.RANK_FETCH)
    def run_rank(self, ids: list[int], token: TokenInfo, job_id: str = None) -> None:
        """
        Run full ranking for the given keyword IDs.
        
        Args:
            ids: List of keyword IDs to rank
            token: User token info
            job_id: Optional SQS job ID for cancellation checking
        """
        score_setting = self.score_setting.list_settings()
        keywords_to_process = []

        # First phase: Filter valid keywords
        for keyword_id in ids:
            keyword_obj = self.keyword_repo.get(keyword_id)
            if not keyword_obj:
                continue

            # Skip keywords with pending fetch_status
            if keyword_obj.fetch_status == StatusConst.PENDING:
                logging.warning(
                    "Skipping keyword %s - fetch_status is PENDING (must run fetch first)",
                    keyword_id
                )
                continue

            # Skip keywords that have already been successfully ranked
            if keyword_obj.rank_status == StatusConst.SUCCESS:
                logging.info(
                    "Skipping keyword %s as it's already successfully ranked",
                    keyword_id,
                )
                continue

            # Allow all other statuses (PENDING, FAILED, WAITING, PROCESSING, CANCELLED, etc.) to be re-processed
            keywords_to_process.append(keyword_id)

        # Second phase: Process each keyword with cancellation checking
        for keyword_id in keywords_to_process:
            # Update status to PROCESSING just before starting work
            keyword_to_update = self.keyword_repo.get(keyword_id)
            if keyword_to_update:
                self.keyword_repo.update(
                    keyword_to_update, KeywordUpdate(rank_status=StatusConst.PROCESSING)
                )

            # Check for cancellation before processing each keyword
            if job_id:
                from src.utils.cancellation import is_job_cancelled, JobCancelledException
                if is_job_cancelled(job_id, self.keyword_repo.db):
                    logging.info(f"Job {job_id} cancelled - resetting remaining keywords to pending")
                    for remaining_id in keywords_to_process[keywords_to_process.index(keyword_id):]:
                        remaining_keyword = self.keyword_repo.get(remaining_id)
                        if remaining_keyword:
                            self.keyword_repo.update(
                                remaining_keyword, KeywordUpdate(rank_status=StatusConst.PENDING)
                            )
                    raise JobCancelledException(job_id, "Rank job cancelled by user")
            
            try:
                # Reset FAILED items to PENDING so they are included in this run (manual retry)
                # This works in tandem with _process_keyword_for_rank skipping FAILED items
                self.serp_repo.update_failed_to_pending(keyword_id)

                self._process_keyword_for_rank(
                    keyword_id, score_setting, job_id=job_id
                )
            except Exception as e:
                from src.utils.cancellation import JobCancelledException
                if isinstance(e, JobCancelledException):
                    logging.info(f"Job {job_id} cancelled during rank - resetting current and remaining keywords")
                    # Reset current keyword
                    if keyword_to_update:
                        self.keyword_repo.update(keyword_to_update, KeywordUpdate(rank_status=StatusConst.PENDING))
                    
                    # Reset remaining keywords
                    current_idx = keywords_to_process.index(keyword_id)
                    for remaining_id in keywords_to_process[current_idx + 1:]:
                        remaining_keyword = self.keyword_repo.get(remaining_id)
                        if remaining_keyword:
                            self.keyword_repo.update(remaining_keyword, KeywordUpdate(rank_status=StatusConst.PENDING))
                    raise  # Re-raise cancellation exceptions
                logging.error(
                    "Unexpected Error at run_rank for keyword_id %s: %s",
                    keyword_id,
                    str(e),
                )
                # Update keyword status to FAILED to prevent it from being stuck at PROCESSING
                keyword_obj = self.keyword_repo.get(keyword_id)
                if keyword_obj:
                    self.keyword_repo.update(
                        keyword_obj, KeywordUpdate(rank_status=StatusConst.FAILED)
                    )
                continue

    @track_batch_history(ExecutionTypeConst.PARTIAL_RANK_FETCH)
    def run_partial_rank(self, ids: list[int], token: TokenInfo, job_id: str = None) -> None:
        """
        Run partial ranking - only updates specific fields.
        
        Args:
            ids: List of keyword IDs to rank
            token: User token info
            job_id: Optional SQS job ID for cancellation checking
        """
        score_setting = self.score_setting.list_settings()
        keywords_to_process = []

        # First phase: Filter valid keywords
        for keyword_id in ids:
            keyword_obj = self.keyword_repo.get(keyword_id)
            if not keyword_obj:
                continue

            # Skip keywords with pending fetch_status
            if keyword_obj.fetch_status == StatusConst.PENDING:
                logging.warning(
                    "Skipping keyword %s - fetch_status is PENDING (must run fetch first)",
                    keyword_id
                )
                continue

            # Skip keywords that have already been successfully ranked
            if keyword_obj.partial_rank_status == StatusConst.SUCCESS:
                logging.info(
                    "Skipping keyword %s as it's already successfully ranked",
                    keyword_id,
                )
                continue

            # Allow all other statuses (PENDING, FAILED, WAITING, PROCESSING, CANCELLED, etc.) to be re-processed
            keywords_to_process.append(keyword_id)

        # Second phase: Process each keyword with partial updates and cancellation checking
        for keyword_id in keywords_to_process:
            # Update status to PROCESSING just before starting work
            keyword_to_update = self.keyword_repo.get(keyword_id)
            if keyword_to_update:
                self.keyword_repo.update(
                    keyword_to_update, KeywordUpdate(partial_rank_status=StatusConst.PROCESSING)
                )

            # Check for cancellation before processing each keyword
            if job_id:
                from src.utils.cancellation import is_job_cancelled, JobCancelledException
                if is_job_cancelled(job_id, self.keyword_repo.db):
                    logging.info(f"Job {job_id} cancelled - resetting remaining keywords to pending")
                    for remaining_id in keywords_to_process[keywords_to_process.index(keyword_id):]:
                        remaining_keyword = self.keyword_repo.get(remaining_id)
                        if remaining_keyword:
                            self.keyword_repo.update(
                                remaining_keyword, KeywordUpdate(partial_rank_status=StatusConst.PENDING)
                            )
                    raise JobCancelledException(job_id, "Partial rank job cancelled by user")
            
            try:
                # Reset FAILED items to PENDING so they are included in this run (manual retry)
                # This works in tandem with _process_keyword_for_partial_rank skipping FAILED items
                self.serp_repo.update_failed_to_pending(keyword_id)

                self._process_keyword_for_partial_rank(
                    keyword_id, score_setting, job_id=job_id
                )
            except Exception as e:
                from src.utils.cancellation import JobCancelledException
                if isinstance(e, JobCancelledException):
                    logging.info(f"Job {job_id} cancelled during partial rank - resetting current and remaining keywords")
                    # Reset current keyword
                    if keyword_to_update:
                        self.keyword_repo.update(keyword_to_update, KeywordUpdate(partial_rank_status=StatusConst.PENDING))
                    
                    # Reset remaining keywords
                    current_idx = keywords_to_process.index(keyword_id)
                    for remaining_id in keywords_to_process[current_idx + 1:]:
                        remaining_keyword = self.keyword_repo.get(remaining_id)
                        if remaining_keyword:
                            self.keyword_repo.update(remaining_keyword, KeywordUpdate(partial_rank_status=StatusConst.PENDING))
                    raise  # Re-raise cancellation exceptions
                logging.error(
                    "Unexpected Error at run_partial_rank for keyword_id %s: %s",
                    keyword_id,
                    str(e),
                )
                # Update keyword status to FAILED to prevent it from being stuck at PROCESSING
                keyword_obj = self.keyword_repo.get(keyword_id)
                if keyword_obj:
                    self.keyword_repo.update(
                        keyword_obj, KeywordUpdate(partial_rank_status=StatusConst.FAILED)
                    )
                continue

    def validate_batch_for_rerun(self, batch_id: int) -> None:
        """
        Validate that a batch exists and is a RANK_FETCH type.

        Args:
            batch_id: The ID of the batch history to validate

        Raises:
            ValueError: If the batch doesn't exist or is not a RANK_FETCH operation
        """
        batch_history = self.batch_history_repo.get(batch_id)

        if not batch_history:
            raise ValueError("Batch history with ID %s not found" % batch_id)

        # Check if it's a RANK_FETCH type
        if batch_history.execution_type_id != ExecutionTypeConst.RANK_FETCH.value:
            raise ValueError(
                "Batch history with ID %s is not a RANK_FETCH operation" % batch_id
            )

        # Check if there are any details with keyword_id
        details = [
            detail for detail in batch_history.details if detail.keyword_id is not None
        ]

        if not details:
            raise ValueError("No keyword details found in this batch")

        # Extract keyword IDs from details
        keyword_ids = [detail.keyword_id for detail in details if detail.keyword_id]

        if not keyword_ids:
            raise ValueError("No keyword IDs found in batch details")

    def run_rank_from_failed_batch_bg(self, batch_id: int, token: TokenInfo) -> None:
        """
        Background task version of run_rank_from_failed_batch.
        This function is designed to be run as a background task to prevent timeout issues.

        Args:
            batch_id: The ID of the batch history to re-run
            token: The TokenInfo object containing user information
        """
        try:
            # Get the batch history record to update its status
            batch_history = self.batch_history_repo.get(batch_id)
            if not batch_history:
                logging.error(
                    "Background task: Batch history with ID %s not found", batch_id
                )
                return

            # Update batch history to indicate processing has started
            self.batch_history_repo.update(
                batch_history, BatchHistoryUpdate(status=StatusConst.PROCESSING)
            )

            # Run the actual processing
            result = self.run_rank_from_failed_batch(batch_id, token)

            # Update batch history to indicate processing is complete
            duration_seconds = (
                datetime.now() - batch_history.created_at
            ).total_seconds()
            h, rem = divmod(duration_seconds, 3600)
            m, s = divmod(rem, 60)
            duration_time = time(int(h), int(m), int(s))

            self.batch_history_repo.update(
                batch_history,
                BatchHistoryUpdate(status=StatusConst.SUCCESS, duration=duration_time),
            )

            logging.info(
                "Background task completed successfully for batch %s: %s",
                batch_id,
                result,
            )

        except Exception as e:
            logging.error("Error in background task for batch %s: %s", batch_id, str(e))

            # Try to update batch history to indicate failure
            try:
                batch_history = self.batch_history_repo.get(batch_id)
                if batch_history:
                    duration_seconds = (
                        datetime.now() - batch_history.created_at
                    ).total_seconds()
                    h, rem = divmod(duration_seconds, 3600)
                    m, s = divmod(rem, 60)
                    duration_time = time(int(h), int(m), int(s))

                    self.batch_history_repo.update(
                        batch_history,
                        BatchHistoryUpdate(
                            status=StatusConst.FAILED, duration=duration_time
                        ),
                    )
            except Exception as update_error:
                logging.error(
                    "Failed to update batch status after error: %s", update_error
                )

    @try_except_decorator_no_raise(
        fallback_value={"message": "An error occurred during rank operation"}
    )
    def run_rank_from_failed_batch(self, batch_id: int, token: TokenInfo) -> dict:
        """
        Re-run rank operations from a specific batch history.
        This function processes all details in the batch history, regardless of their status.

        Args:
            batch_id: The ID of the batch history to re-run
            token: The TokenInfo object containing user information

        Returns:
            A dictionary with information about the re-run operation
        """
        # Get the batch history record
        batch_history = self.batch_history_repo.get(batch_id)

        if not batch_history:
            raise ValueError(f"Batch history with ID {batch_id} not found")

        # Check if it's a RANK_FETCH type
        if batch_history.execution_type_id != ExecutionTypeConst.RANK_FETCH.value:
            raise ValueError(
                f"Batch history with ID {batch_id} is not a RANK_FETCH operation"
            )

        # Get all details from this batch that have keyword_id
        details = [
            detail for detail in batch_history.details if detail.keyword_id is not None
        ]

        if not details:
            return {"message": "No keyword details found in this batch"}

        # Extract keyword IDs from details
        keyword_ids = [detail.keyword_id for detail in details if detail.keyword_id]

        if not keyword_ids:
            return {"message": "No keyword IDs found in batch details"}

        # Store the current batch history for detail tracking
        self._current_batch_history = batch_history

        # Get score settings
        score_setting = self.score_setting.list_settings()
        processed_count = 0
        success_count = 0

        # Process each keyword
        for keyword_id in keyword_ids:
            keyword_obj = self.keyword_repo.get(keyword_id)
            if not keyword_obj:
                continue

            # Find the corresponding detail record
            detail = next((d for d in details if d.keyword_id == keyword_id), None)
            if not detail:
                continue

            processed_count += 1

            # Mark keyword as PROCESSING
            self.keyword_repo.update(
                keyword_obj, KeywordUpdate(rank_status=StatusConst.PROCESSING)
            )

            try:
                # Process the keyword
                self._process_keyword_for_rank(
                    keyword_id, score_setting
                )
                success_count += 1

                # Update the detail status to SUCCESS
                self.batch_history_detail_repo.update(
                    detail,
                    BatchHistoryDetailUpdate(
                        status=StatusConst.SUCCESS, error_message=None
                    ),
                )
            except Exception as e:
                logging.error("Error processing keyword %s: %s", keyword_id, str(e))
                # Update the detail with the new error message
                self.batch_history_detail_repo.update(
                    detail,
                    BatchHistoryDetailUpdate(
                        status=StatusConst.FAILED, error_message=str(e)
                    ),
                )

        return {
            "message": f"Re-ran rank operation for {processed_count} keywords",
            "batch_id": batch_id,
            "processed": processed_count,
            "successful": success_count,
            "failed": processed_count - success_count,
        }

    def run_fetch_and_rank_scheduled(self, token: TokenInfo) -> dict:
        """
        Run fetch and rank operations for all scheduled keywords.
        First fetches SERP results for the scheduled keywords, then ranks them.
        """
        # Get all scheduled keywords
        scheduled_keywords = self.keyword_repo.list_scheduled()

        if not scheduled_keywords:
            return {"message": "No scheduled keywords found"}

        # Extract the IDs
        keyword_ids = [keyword.id for keyword in scheduled_keywords]

        # Run fetch operation
        fetch_results = self.run_fetch(keyword_ids, token)

        # Run rank operation
        self.run_rank(keyword_ids, token)

        return {
            "message": f"Fetch and rank operations completed for {len(keyword_ids)} scheduled keywords",
            "keywords": [
                {"id": kw.id, "keyword": kw.keyword} for kw in scheduled_keywords
            ],
            "fetch_results_count": len(fetch_results),
        }
        
    def unstick_processing_records(self, keyword_id: int = None) -> dict:
        """
        Find and update records with 'processing' status to 'pending' in both
        keyword and serp_result tables.
        
        Args:
            keyword_id: Optional keyword ID to update only records for a specific keyword.
                       If None, updates all records with processing status.
        
        Returns:
            A dictionary with statistics about the operation
        """
        # Update keywords
        keyword_results = self.keyword_repo.update_processing_to_pending(keyword_id)
        
        # Update SERP results
        serp_results = self.serp_repo.update_processing_to_pending(keyword_id)
        
        # Combine results
        total_updated = (
            keyword_results["fetch_status_updated"] + 
            keyword_results["rank_status_updated"] + 
            keyword_results["partial_rank_status_updated"] + 
            serp_results["status_updated"]
        )
        
        # Prepare message
        if keyword_id:
            message = f"Successfully unstuck processing records for keyword ID {keyword_id}"
        else:
            message = "Successfully unstuck all processing records"
        
        return {
            "message": message,
            "keyword_fetch_status_updated": keyword_results["fetch_status_updated"],
            "keyword_rank_status_updated": keyword_results["rank_status_updated"],
            "keyword_partial_rank_status_updated": keyword_results["partial_rank_status_updated"],
            "serp_result_status_updated": serp_results["status_updated"],
            "total_updated": total_updated
        }

    def import_keywords_bytes(self, file_bytes: bytes, filename: str, token: TokenInfo) -> dict:
        """
        Parse uploaded CSV/XLS/XLSX, read first column from 2nd row onward,
        and insert keywords with is_scheduled = False.
        """
        if not file_bytes:
            return {"inserted": 0, "skipped": 0, "keywords": []}
        ext = ""
        if filename and "." in filename:
            ext = filename.lower().rsplit(".", 1)[-1]

        # Read only the first column with robust settings and encoding fallbacks
        buf = io.BytesIO(file_bytes)
        df = None
        last_exc: Exception | None = None

        if ext in ("xlsx", "xls"):
            try:
                df = pd.read_excel(
                    buf,
                    header=None,
                    usecols=[0],
                    dtype=str,
                    engine="openpyxl" if ext == "xlsx" else "xlrd",
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse Excel file: {str(e)}",
                )
        else:
            # CSV: try multiple encodings, disable low_memory, and force string dtype
            for enc in ("utf-8-sig", "utf-8", "cp932"):
                try:
                    buf.seek(0)
                    df = pd.read_csv(
                        buf,
                        header=None,
                        usecols=[0],
                        dtype=str,
                        encoding=enc,
                        low_memory=False,
                    )
                    if df.shape[0] > 0 and df.iloc[:, 0].notna().any():
                        break
                except Exception as e:
                    last_exc = e
                    df = None
                    continue
            if df is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse CSV file: {last_exc}",
                )

        # Ensure at least one column exists
        if df is None or df.shape[1] < 1:
            return {"inserted": 0, "skipped": 0, "keywords": []}

        # First column only, skip the first row per requirement, clean, drop empties
        col = df.iloc[:, 0].astype(str).iloc[1:]
        cleaned: list[str] = []
        for raw in col.tolist():
            if raw is None:
                continue
            s = str(raw).strip()
            # Remove BOM, zero-width, non-breaking spaces, then trim again
            s = s.replace("\ufeff", "").replace("\u200b", "").replace("\u00A0", " ").strip()
            if s == "" or s.lower() == "nan":
                continue
            cleaned.append(s)
        cleaned_count = len(cleaned)

        # Preserve order, enforce DB length limit (100), and de-duplicate on normalized stored value
        def _norm(s: str) -> str:
            return re.sub(r"\s+", "", s or "").replace("\u3000", "").replace("\u200b", "").replace("\ufeff", "").replace("\u00A0", "").lower()
        seen_norm: set[str] = set()
        keywords: list[str] = []
        for v in cleaned:
            sv = (v or "")[:100]  # DB column is String(100)
            nv = _norm(sv)
            if sv and nv not in seen_norm:
                seen_norm.add(nv)
                keywords.append(sv)

        # Determine duplicates using repository exists_normalized (uses per-request cache)
        to_insert = [sv for sv in keywords if not self.keyword_repo.exists_normalized(sv)]
        duplicates_by_exists = len(keywords) - len(to_insert)
        in_file_duplicates = cleaned_count - len(keywords)

        # Bulk insert with DB-level deduplication for performance on large files
        inserted = self.keyword_repo.bulk_insert_ignore(to_insert, user_id=token.id, is_scheduled=False)
        skipped = len(keywords) - inserted
        db_ignored_after_filter = len(to_insert) - inserted  # rows considered new by exists_normalized but ignored by DB unique index
        # Log totals including duplicates detected by exists_normalized specifically
        logging.info(
            "ImportKeywords completed: processed_unique=%d, inserted=%d, skipped_total=%d, skipped_by_exists_normalized=%d, in_file_duplicates=%d, db_ignored_after_filter=%d",
            len(keywords), inserted, skipped, duplicates_by_exists, in_file_duplicates, db_ignored_after_filter
        )
        # Avoid returning the entire keyword list to keep response small and prevent client/proxy timeouts
        return {"inserted": inserted, "skipped": skipped, "processed": len(keywords)}

    @track_batch_detail()
    def _process_keyword_for_rank(
        self,
        keyword_id: int,
        score_setting: ScoreSetting,
        job_id: str = None,
    ):
        keyword_obj = self.keyword_repo.get(keyword_id)
        user_obj = self.user_repo.get(keyword_obj.created_by_user_id)

        if not keyword_obj:
            raise ValueError("Keyword not found")

        try:
            # Process only PENDING or FAILED SERP results for this keyword to reduce memory usage
            serp_results = self.serp_repo.list_pending_failed_or_partial(keyword_id)
            logging.info(
                "Processing %d pending/failed SERP results for keyword %d",
                len(serp_results),
                keyword_id,
            )

            # Initialize SeleniumService once for all items
            selenium_service = SeleniumService()

            try:
                for idx, serp in enumerate(serp_results):
                    # Skip previously failed items to avoid re-processing loop after crash
                    if serp.status == StatusConst.FAILED:
                        logging.warning(
                            "Skipping previously FAILED item for serp_id %s to avoid re-processing loop.",
                            serp.id,
                        )
                        continue

                    # Check for cancellation
                    if job_id:
                        from src.utils.cancellation import check_cancellation_and_raise
                        check_cancellation_and_raise(job_id, self.keyword_repo.db)

                    try:
                        # Process SERP with timeout handling
                        self._process_serp_with_timeout(
                            serp, score_setting, selenium_service, user_obj, timeout=240
                        )
                        
                        # Add delay between items to allow memory cleanup - keeping this from original logic
                        if idx < len(serp_results) - 1:
                            time_module.sleep(1.0)
                            
                    except TimeoutError:
                        logging.error("Timeout processing serp %s", serp.id)
                        # Reset driver to kill any stuck threads/requests
                        selenium_service.reset_driver()
                        # Mark SERP as failed due to timeout
                        self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
                        
                    except Exception as e:
                        logging.error(
                            "Error on _process_serp for serp_id %s: %s", serp.id, str(e)
                        )
                        # Ensure we mark as failed if not already handled
                        self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
                        continue
            finally:
                # Clean up the selenium service after all items are processed
                try:
                    selenium_service._cleanup(force=True)
                except Exception as cleanup_error:
                    logging.error("Error cleaning up selenium service: %s", cleanup_error)

            # Check for failed SERP results
            failed_count = self.serp_repo.count_failed_by_keyword(keyword_id)
            total_count = self.serp_repo.count_by_keyword(keyword_id)
            final_status = StatusConst.SUCCESS
            
            # Fail if 1/3 or more of items failed
            threshold = math.ceil(total_count / 3) if total_count > 0 else 3
            
            if failed_count >= threshold:
                logging.warning(
                    "Keyword %d has %d failed SERP results (>= %d) -> setting rank_status to FAILED",
                    keyword_id, failed_count, threshold
                )
                final_status = StatusConst.FAILED

            return self.keyword_repo.update(
                keyword_obj, KeywordUpdate(rank_status=final_status)
            )

        except Exception as e:
            self.keyword_repo.update(
                keyword_obj, KeywordUpdate(rank_status=StatusConst.FAILED)
            )
            raise

    def _process_keyword_for_partial_rank(
        self,
        keyword_id: int,
        score_setting: ScoreSetting,
        job_id: str = None,
    ):
        """Process keyword for partial ranking - only specific fields"""
        keyword_obj = self.keyword_repo.get(keyword_id)
        user_obj = self.user_repo.get(keyword_obj.created_by_user_id)

        if not keyword_obj:
            raise ValueError("Keyword not found")

        try:
            # Process only PENDING or FAILED SERP results for this keyword
            serp_results = self.serp_repo.list_pending_failed_or_partial(keyword_id)
            logging.info(
                "Processing %d pending/failed SERP results for partial rank - keyword %d",
                len(serp_results),
                keyword_id,
            )

            # Get service volume using the main keyword directly (no GPT)
            service_volume = self.serp_service.fetch_search_volume(keyword_obj.keyword)
            logging.info(
                "Fetched search volume for keyword '%s': %d", 
                keyword_obj.keyword, 
                service_volume
            )

            for serp in serp_results:
                # Skip previously failed items to avoid re-processing loop after crash
                if serp.status == StatusConst.FAILED:
                    logging.warning(
                        "Skipping previously FAILED item for serp_id %s to avoid re-processing loop.",
                        serp.id,
                    )
                    continue

                # Check for cancellation
                if job_id:
                    from src.utils.cancellation import check_cancellation_and_raise
                    check_cancellation_and_raise(job_id, self.keyword_repo.db)
                    
                try:
                    self._process_serp_partial(serp, score_setting, user_obj, keyword_obj, service_volume)
                except Exception as e:
                    logging.error(
                        "Error on _process_serp_partial for serp_id %s: %s", serp.id, str(e)
                    )
                    continue
            # Check for failed SERP results
            failed_count = self.serp_repo.count_failed_by_keyword(keyword_id)
            total_count = self.serp_repo.count_by_keyword(keyword_id)
            final_status = StatusConst.SUCCESS
            
            # Fail if 1/3 or more of items failed
            threshold = math.ceil(total_count / 3) if total_count > 0 else 3
            
            if failed_count >= threshold:
                logging.warning(
                    "Keyword %d has %d failed SERP results (>= %d) -> setting partial_rank_status to FAILED",
                    keyword_id, failed_count, threshold
                )
                final_status = StatusConst.FAILED

            return self.keyword_repo.update(
                keyword_obj, KeywordUpdate(partial_rank_status=final_status)
            )

        except Exception as e:
            self.keyword_repo.update(
                keyword_obj, KeywordUpdate(partial_rank_status=StatusConst.FAILED)
            )
            raise

    def _process_serp_with_timeout(
        self,
        serp: SerpResultInDBBase,
        score_setting: ScoreSetting,
        selenium_service: SeleniumService,
        user_obj: User,
        timeout: int = 240,
    ) -> None:
        """
        Wrapper for _process_serp with timeout handling.
        Uses a simple time-based check instead of signal/multiprocessing for cross-platform compatibility.
        """
        import threading
        
        result = {"success": False, "error": None}
        
        def worker():
            try:
                self._process_serp(serp, score_setting, selenium_service, user_obj)
                result["success"] = True
            except Exception as e:
                result["error"] = e
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            # Thread is still running after timeout
            logging.error(f"SERP processing timed out after {timeout}s for serp_id {serp.id}")
            # Mark as failed and raise TimeoutError
            # The selenium_service cleanup in the batch handler will kill the Chrome process
            raise TimeoutError(f"Processing timed out after {timeout} seconds")
        
        if result["error"]:
            raise result["error"]

    @track_batch_detail()
    def _process_serp(
        self,
        serp: SerpResultInDBBase,
        score_setting: ScoreSetting,
        selenium_service: SeleniumService,
        user_obj: User,
    ) -> None:
        try:
            # Mark SERP as processing
            self.serp_repo.update(
                serp, SearchResultUpdate(status=StatusConst.PROCESSING)
            )

            domain_url = get_domain_url(serp.link)
            
            # Tiered fetching strategy:
            # 1. Domain URL
            # 2. Original SERP Link
            # 3. Parent Directory of SERP Link
            
            # Helper to get parent directory
            def _get_parent_url(u: str) -> str | None:
                try:
                    parsed = urllib.parse.urlparse(u)
                    path = parsed.path
                    if path == "" or path == "/":
                        return None
                    # If it ends with slash, strip it to go up
                    if path.endswith("/"):
                        path = path[:-1]
                    
                    # Split and remove last component
                    parts = path.split("/")
                    if len(parts) <= 1:
                        return None
                        
                    new_path = "/".join(parts[:-1])
                    if not new_path.endswith("/"):
                         new_path += "/"
                    
                    return parsed._replace(path=new_path, query="", fragment="").geturl()
                except Exception:
                    return None

            candidate_urls = []
            if domain_url:
                candidate_urls.append(domain_url)
            
            if serp.link and serp.link not in candidate_urls:
                candidate_urls.append(serp.link)
                
            parent_url = _get_parent_url(serp.link)
            if parent_url and parent_url not in candidate_urls:
                candidate_urls.append(parent_url)
            
            all_possible_links_list = []
            initial_text = None
            successful_url = None

            for url in candidate_urls:
                logging.info(f"Attempting to fetch main page data from: {url}")
                current_links, current_text, effective_url = selenium_service.fetch_main_page_data(
                    url, max_retries=2
                )

                # Check protocol correction (HTTPS -> HTTP)
                if effective_url != url and "http://" in effective_url and "https://" in url:
                    logging.warning(f"Protocol correction detected. Updating SERP link from {url} to {effective_url}")
                    # Update the SERP result in DB with the working HTTP link
                    try:
                        self.serp_repo.update(serp, SearchResultUpdate(link=effective_url))
                        # Also update local serp reference just in case
                        serp.link = effective_url 
                    except Exception as db_err:
                        logging.error(f"Failed to update SERP link in DB: {db_err}")
                
                # If we got substantial content, stop
                if current_text and len(current_text) >= 50:
                    all_possible_links_list = current_links
                    initial_text = current_text
                    successful_url = url
                    logging.info(f"Successfully fetched data from {url}")
                    break
                else:
                    logging.warning(f"Fetch failed or content too short for {url}")
            
            # If all failed, use domain_url as fallback for cache key to avoid errors downstream, 
            # though content is empty
            if not successful_url:
                 successful_url = domain_url
            
            # Soft check for content length
            if not initial_text or len(initial_text) < 50:
                logging.warning("Main page content too short or empty for serp_id %s (length: %d). Attempting fallback strategy.", serp.id, len(initial_text) if initial_text else 0)
                
                # If we have very little content, we might have missed links too.
                # Inject common fallback paths to try and "rescue" the ranking
                fallback_paths = [
                    "about", "company", "company/", "corporate", "profile", "gaiyo", # About/Company
                    "contact", "inquiry", "form", "ask" # Contact
                ]
                
                # Ensure we have a list
                if not all_possible_links_list:
                    all_possible_links_list = []
                    
                # Add these as absolute URLs
                from urllib.parse import urljoin
                for path in fallback_paths:
                    candidate = urljoin(domain_url, path)
                    # Add strictly if not already present (naive check)
                    if candidate not in all_possible_links_list:
                        all_possible_links_list.append(candidate)
                        
                # We do NOT return here. We let it proceed to GPT to pick from these candidate links.
                # If GPT picks them, we will try to fetch them. If they fail (404), _gather_link_texts handles it.
            
            # Additional safety: if list is still empty, add at least successful_url
            if not all_possible_links_list:
                all_possible_links_list = [successful_url]

            link_gpt = self._get_links_gpt(all_possible_links_list, serp.id)
            
            link_list = [successful_url]
            if link_gpt:
                if link_gpt.about:
                    link_list.append(link_gpt.about)
                    # Also add /company as additional fallback for About pages
                    from urllib.parse import urljoin
                    company_url = urljoin(successful_url, "company")
                    if company_url not in link_list and company_url != link_gpt.about:
                        link_list.append(company_url)
                if link_gpt.contact:
                    link_list.append(link_gpt.contact)
            else:
                logging.warning("Failed to get links from GPT for serp_id %s - falling back to successful_url only", serp.id)

            logging.info("Gathering text content from links: %s", link_list)
            # Pass initial_text mapped to successful_url so we don't re-fetch it
            text_content = self._gather_link_texts(selenium_service, link_list, initial_cache={successful_url: initial_text})
            logging.info("Fetched text content: %d chars", len(text_content))

            if not text_content:
                logging.warning("Failed to text_content %s", serp.id)
                self.serp_repo.update(
                    serp, SearchResultUpdate(status=StatusConst.FAILED)
                )
                return

            if not text_content or len(text_content) < 50:
                logging.warning("Text content too short or empty for serp_id %s (length: %d)", serp.id, len(text_content) if text_content else 0)
                self.serp_repo.update(
                    serp, SearchResultUpdate(status=StatusConst.FAILED)
                )
                return

            rank_gpt = self._get_rank_gpt(text_content, serp.id, serp.title)

            if rank_gpt is None:
                logging.warning("Failed to get rank from GPT for serp_id %s", serp.id)
                self.serp_repo.update(
                    serp, SearchResultUpdate(status=StatusConst.FAILED)
                )
                return

            computation = self._compute_weight(rank_gpt, domain_url, score_setting)
            rank = self._determine_rank(computation.total_weight, score_setting)

            # Update SERP with all results and mark as SUCCESS
            return self.serp_repo.update(
                serp,
                SearchResultUpdate(
                    rank=rank,
                    status=StatusConst.SUCCESS,
                    **computation.model_dump(),
                    company_name=rank_gpt.company_name,
                    domain_name=domain_url,
                    contact_person=user_obj.full_name,
                    phone_number=rank_gpt.phone_number,
                    url_corporate_site=rank_gpt.url_corporate_site,
                    url_service_site=rank_gpt.url_service_site,
                    email_address=rank_gpt.email_address,
                    has_column_section=rank_gpt.has_column_section,
                    column_determination_reason=rank_gpt.column_determination_reason,
                    industry=rank_gpt.industry,
                    has_own_product_service_offer=rank_gpt.has_own_product_service_offer,
                    own_product_service_determination_reason=rank_gpt.own_product_service_determination_reason,
                ),
            )
        except Exception as e:
            logging.warning("Exception %s: %s", serp.id, e)
            self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
            raise

    @track_batch_detail()
    def _process_serp_partial(
        self,
        serp: SerpResultInDBBase,
        score_setting: ScoreSetting,
        user_obj: User,
        keyword_obj: Keyword,
        service_volume: int,
    ) -> None:
        """
        Process SERP for partial ranking WITHOUT GPT - only updates:
        - domain_name
        - contact_person
        - service_volume (using main keyword only)
        - site_size
        - activity_date
        """
        try:
            # Mark SERP as processing
            self.serp_repo.update(
                serp, SearchResultUpdate(status=StatusConst.PROCESSING)
            )

            domain_url = get_domain_url(serp.link)            
            
            # Get site size
            raw_site_size = self.serp_service.site_size(domain_url)
            
            # Update SERP with ONLY the specific fields requested
            return self.serp_repo.update(
                serp,
                SearchResultUpdate(
                    status=StatusConst.PARTIAL,
                    domain_name=domain_url,
                    contact_person=user_obj.full_name,
                    service_volume=service_volume,
                    site_size=raw_site_size,
                    # Use database time instead of application server time to avoid clock skew
                    # Manual adjustment to UTC+9 (JST)
                    activity_date=datetime.now() + timedelta(hours=9),
                ),
            )
        except Exception as e:
            logging.warning("Exception %s: %s", serp.id, e)
            self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
            raise

    def _gather_link_texts(
        self, 
        selenium_service: SeleniumService, 
        link_list: list[str],
        initial_cache: dict[str, str] = None
    ) -> str:
        """
        Download visible text from every URL in ``link_list`` and return one
        newline-separated string.  If a page cannot be fetched, it is skipped.
        
        Args:
            initial_cache: Dict of {url: text} for content already fetched.
        """
        text_content: list[str] = []  # initialise once, as a list
        cache = initial_cache or {}

        for link in link_list:
            try:
                # Use cached content if available and valid
                if link in cache and cache[link]:
                    logging.info("Using cached content for %s", link)
                    text_content.append(cache[link].strip())
                    continue
                    
                page_text = selenium_service.get_text_content(link, max_retries=2)
                if page_text:
                    text_content.append(page_text.strip())
            except Exception as e:
                logging.warning("Could not fetch text from %s: %s", link, e)

        return "\n".join(text_content)

    def _get_links_gpt(
        self, all_possible_links_list: list[str], serp_id: int
    ) -> LinkGPTResponse | None:
        prompt = self._link_prompt(all_possible_links_list)
        gpt_response = self.chatgpt_service.generate_response(prompt)
        if not gpt_response:
            logging.warning("OpenAI call failed for serp_id %s; skipping", serp_id)
            return None
        try:
            parsed = self.chatgpt_service.parse_gpt_json(gpt_response)
            return LinkGPTResponse(**parsed)
        except ValueError as e:
            logging.warning("Bad GPT JSON for serp_id %s: %s", serp_id, e)
            return None

    def _get_rank_gpt(self, html: str, serp_id: int, title: str = None) -> RankGPTResponse | None:
        prompt = self._rank_prompt(html, title)
        gpt_response = self.chatgpt_service.generate_response(prompt)
        if not gpt_response:
            logging.warning("OpenAI call failed for serp_id %s; skipping", serp_id)
            return None
        try:
            parsed = self.chatgpt_service.parse_gpt_json(gpt_response)
            return RankGPTResponse(**parsed)
        except ValueError as e:
            logging.warning("Bad GPT JSON for serp_id %s: %s", serp_id, e)
            return None

    @try_except_decorator
    def _compute_weight(
        self, gpt_res: RankGPTResponse, url: str, score_setting: ScoreSetting
    ) -> RankComputation:
        raw_price = gpt_res.price
        service_price = self._service_price(raw_price)

        raw_volume = 0
        candidate_keyword: list[CandidateKeyword] = []

        # Collect all candidate keywords
        candidate_keys = [key for key in gpt_res.keyword if key]
        
        # Batch fetch their volumes
        if candidate_keys:
            volume_map = self.serp_service.fetch_search_volumes_batch(candidate_keys)
        else:
            volume_map = {}

        for candidate_key in candidate_keys:
            candidate_volume = volume_map.get(candidate_key, 0)
            raw_volume += candidate_volume
            candidate_keyword.append(
                CandidateKeyword(keyword=candidate_key, volume=candidate_volume)
            )

        search_volume = log_score(raw_volume)

        raw_site_size = self.serp_service.site_size(url)
        site_size = log_score(raw_site_size)

        metric_price = self._get_metric_value(
            score_setting.weighted_metrics, RankConst.SERVICE_PRICE
        )
        metric_volume = self._get_metric_value(
            score_setting.weighted_metrics, RankConst.SERVICE_VOLUME
        )
        metric_site_size = self._get_metric_value(
            score_setting.weighted_metrics, RankConst.SITE_SIZE
        )

        total_weight = (
            metric_price * service_price
            + metric_volume * search_volume
            + metric_site_size * site_size
        )

        return RankComputation(
            total_weight=float(total_weight),
            service_price=int(raw_price),
            service_volume=int(raw_volume),
            site_size=int(raw_site_size),
            metric_price=float(metric_price),
            metric_volume=float(metric_volume),
            metric_site_size=float(metric_site_size),
            candidate_keyword=candidate_keyword,
        )

    @try_except_decorator
    def _determine_rank(self, weight: float, score_setting: ScoreSetting) -> str:
        """
        Dynamic rank determination using only _get_metric_value.

        - Collect labels from score_setting.score_thresholds (e.g., A/B/C/D/...)
        - For each label, get its numeric threshold via _get_metric_value
        - Sort by threshold DESC (tie-break by label for determinism)
        - Return the first label whose threshold <= weight
        - If none match, return the label with the smallest threshold
        - If no thresholds exist, default to RankConst.D_RANK
        """
        metrics = getattr(score_setting, "score_thresholds", None)
        default_rank = RankConst.D_RANK

        if not metrics:
            return default_rank

        # Build (label, threshold) pairs using only _get_metric_value
        labels: list[tuple[str, float]] = []
        seen: set[str] = set()
        for m in metrics:
            label = getattr(m, "label", None)
            if not label:
                continue

            # Always obtain the threshold via the helper
            thr_raw = self._get_metric_value(metrics, label)
            try:
                thr = float(thr_raw)
                if math.isnan(thr):
                    continue
            except (TypeError, ValueError):
                # Don't mark as seen on invalid value; allow later valid duplicates
                continue

            if label in seen:
                # We already recorded a valid numeric threshold for this label
                continue

            seen.add(label)
            labels.append((label, thr))

        if not labels:
            return default_rank


        # Sort by threshold DESC, then label ASC for deterministic results on ties
        labels.sort(key=lambda kv: (-kv[1], str(kv[0])))

        # Pick the first label whose threshold is met
        for label, thr in labels:
            if weight >= thr:
                return label

        # If weight is below all thresholds
        return default_rank

    def _get_metric_value(
        self, metrics: list[ScoreThresholdOut] | list[WeightedMetricOut], label: str
    ) -> float:
        return next(
            (m.value for m in metrics if m.label == label), 0  # default if not found
        )

    def _service_price(self, yen: int | float) -> float:
        """
        Discrete five-level score based on expected revenue per deal (JPY).
        """
        match yen:
            case p if p >= 100_000:
                return 10.0
            case p if 60_000 <= p <= 99_999:
                return 7.5
            case p if 30_000 <= p <= 59_999:
                return 5.0
            case p if 10_000 <= p <= 29_999:
                return 2.5
            case _:
                return 0.0

    def _truncate_for_token_limit(self, text: str, max_tokens: int = 125000) -> str:
        """
        Truncate text to fit within ChatGPT token limits.
        Based on observed data: Japanese content averages 1.3-1.36 chars/token.
        Using 1.3 to account for variation.
        
        Calculation for 128k limit:
        - Prompt template: ~1,000 tokens (2,907 chars at ~3 chars/token for English)
        - Response buffer: ~2,000 tokens
        - Available for content: 128,000 - 3,000 = 125,000 tokens
        - At 1.3 chars/token: 125,000 * 1.3 = 162,500 chars max
        """
        if not text:
            return text
        max_chars = int(max_tokens * 1.3)
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        logging.warning("Text truncated from %d to %d chars for token limit", len(text), len(truncated))
        return truncated

    def _rank_prompt(self, text_content: str, title: str = None) -> str:
        """
        Build the instruction prompt for GPT so that its JSON output matches
        RankGPTResponse exactly.
        """
        text_content = self._truncate_for_token_limit(text_content)
        
        title_context = ""
        if title:
            title_context = f"The expected page title is: '{title}'. Use this to verify if the content matches the company."

        return f"""
You are an experienced market analyst familiar with Japanese B2B / B2C
pricing, web-site structures, and lead-generation best practices.

TASKS
1. Read the raw HTML/text below (it may include text extracted from About / Contact pages and other candidate pages).
   {title_context}
2. **CRITICAL VERIFICATION**: Check if the content is a legitimate company website or a generic error/parking page (e.g., "403 Forbidden", "Access Denied", "Cloudflare", "GoDaddy", "Domain Parked", "pardon our interruption").
   - IF valid site: Identify the page's **main product or service**.
   - IF generic/error page: Return empty strings for all company details. Do NOT hallucinate a company name from the infrastructure provider (like "Cloudflare" or "nginx").
3. Suggest **exactly three** highly relevant Japanese keywords (closely related to the identified product/service).
   - If unsure, make your best guess—**always return 3 keywords**.
4. Estimate the typical one-time deal value in Japanese yen (integer only).
5. Extract the following company/contact information **if present**; if a field cannot be found, output an empty string (`""`):

• company_name - official company name in Japanese (or the title tag).
• phone_number - first domestic phone number you see.
• url_corporate_site - contact / inquiry URL on the corporate (main) site.
• url_service_site  - contact / inquiry URL on product/service sub-site (if different).
• email_address - first contact email you see.

6. Additional site-level analyses (new fields):
• has_column_section - true or false
    - true if the site contains a dedicated collection of column/blog/article/resource content (multiple entries, typically with titles/dates/excerpts/categories), OR if sitewide UI clearly indicates such a section via labels found in any components listed in Step 1. Navigation heuristic (strong rule): If ANY navigation link text — including in the footer — contains words that imply a blog/columns/resources section, then set has_column_section = true (unless it clearly refers only to corporate news/press). Indicative Japanese/English terms include but are not limited to: 「ブログ」/ Blog, 「コラム」/ Column(s), 「記事」/ Articles, COLUMN, BLOG, MAGAZINE, 「マガジン」, KNOWLEDGE, 「ナレッジ」, INSIGHTS, 「お役立ち情報」, 「読み物」, 「資料」/ Resources (when used for article/knowledge content), 「導入事例」/ Case Studies, 「ケーススタディ」. Also consider URL path hints in link targets like /blog, /column(s), /knowledge, /insights, /resources as supporting evidence.
    - false if not already determined to be true and none found or ambiguous, OR if the only content areas discovered are strictly corporate news-only such as 「News/ニュース」「Press Releases/プレスリリース」「Announcements/お知らせ」「IR/投資家情報」 without any non-news column/blog/article/resource area.
• column_determination_reason - concise natural language (Japanese) explaining the final true/false decision on "has_column_section", explicitly stating whether columns were excluded because they were news/press/announcements only, or included because non-news columns were found, and where the evidence was found on the site (e.g., header navigation "コラム", footer link text, blog index page path, sidebar list).
• has_own_product_service_offer - true or false (Always set this to false for websites belonging to government agencies or other public institutions, regardless of the presence of contact pages, service descriptions, or informational resources)
    - true if the HTML indicates that the website offers or promotes its own products or services (e.g., "自社製品", "サービス紹介", "お問い合わせ", "製品一覧", "導入事例", "購入", or pages clearly describing what they provide).
    - false if the website mainly provides information, news, listings, or external resources but does not promote its own offering.
• own_product_service_determination_reason - explain the reason for your final decision on "has_own_product_service_offer" in a concise, natural language (Japanese). Include where on the site you found the reason (e.g., path or location in the header/footer/service introduction page/product list/case studies, etc.) and how many relevant locations you checked.
• industry - choose the single most appropriate industry from the following list and output only in Japanese; if none match, output "その他":

建設・工事
小売関連
コンサルティング
不動産
商社関連
IT・テクノロジー
食品
製造
医療・福祉・バイオ
エンタメ・レジャー
機械製造
教育・スクール関連
運輸・物流
人材サービス
生活用品
自動車・乗り物
ファッション・美容
広告
金融関連
外食
機械関連サービス
化学
電気製品
エネルギー
メディア・出版関連
通信及び通信機器
専門サービス
ゲーム
石炭・鉱石採掘業界
公共サービス業界

OUTPUT
Return exactly one valid JSON object only—no prose before or after, no code fences. Keys and order must match the example. price must be an integer (digits only, no commas, no "¥").

{{
  "keyword": ["kw1", "kw2", "kw3"],
  "price": 123456,
  "company_name": "",
  "phone_number": "",
  "url_corporate_site": "",
  "url_service_site": "",
  "email_address": "",
  "has_column_section": false,
  "column_determination_reason": "",
  "has_own_product_service_offer": false,
  "own_product_service_determination_reason": "",
  "industry": ""
}}

HTML START
{text_content}
HTML END
"""

    def _link_prompt(self, url_list: list[str]) -> str:
        urls_block = "\n".join(url_list)
        return f"""
You are an expert web analyst familiar with both Japanese and English site structures.

TASK  
From the list of URLs below, select:
- One URL that most likely leads to the site's **About / Company Information / 会社概要** page
- One URL that most likely leads to the site's **Contact / お問い合わせ** page

If no matching URL is found for either, return an empty string for that field.

OUTPUT  
Return **exactly one** valid JSON object and nothing else:

{{
  "about": "<chosen URL or empty string>",
  "contact": "<chosen URL or empty string>"
}}

URL LIST START
{urls_block}
URL LIST END
"""
