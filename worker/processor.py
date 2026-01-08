import logging
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.keyword import KeywordService
from src.schemas.user import TokenInfo
from src.repositories.keyword import KeywordRepository
from src.utils.constants import StatusConst
from worker.config import config

logger = logging.getLogger(__name__)


class RankProcessor:
    def __init__(self):
        self._setup_database_engine()

    def _setup_database_engine(self):
        config.validate()
        self.engine = create_engine(
            config.database_url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True,
            pool_timeout=30,
            connect_args={'connect_timeout': 10}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def process_job(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a rank job from SQS message

        Args:
            message: The parsed message body from SQS

        Returns:
            dict: {'success': bool, 'should_delete': bool, 'reason': str}
                - success: True if processing was successful
                - should_delete: True if message should be deleted from SQS
                - reason: Human-readable reason for the result
        """
        # Create a new session for this job
        db_session = self.SessionLocal()
        
        try:
            # Initialize services with the fresh session
            keyword_service = KeywordService(db_session)
            keyword_repo = KeywordRepository(db_session)
            
            job_id = message.get('job_id', 'unknown')
            message_type = message.get('message_type', 'unknown')
            keyword_ids = message.get('keyword_ids', [])
            token_info = message.get('token_info', {})
            retry_count = message.get('retry_count', 0)
            user_id = message.get('user_id', 'unknown')
            metadata = message.get('metadata', {})

            logger.info("~" * 60)
            if message_type == 'partial_rank':
                logger.info(f"🎯 PARTIAL RANK PROCESSOR: Starting quick rank check")
            else:
                logger.info(f"📊 FULL RANK PROCESSOR: Starting comprehensive ranking")

            logger.info(f"  Job ID: {job_id}")
            logger.info(f"  User ID: {user_id}")
            logger.info(f"  Total Keywords: {len(keyword_ids)}")
            logger.info(f"  Retry Count: {retry_count}")
            logger.info(f"  Source: {metadata.get('source', 'unknown')}")
            logger.info("~" * 60)

            # Reconstruct TokenInfo object
            token = TokenInfo(**token_info)
            logger.info(f"  ✓ Token reconstructed for user {user_id}")

            # Ensure we see the latest state for all keywords involved in this job.
            db_session.expire_all()

            # Validate that all keywords have fetch_status != PENDING
            keywords_with_pending_fetch = []
            for keyword_id in keyword_ids:
                keyword_obj = keyword_repo.get(keyword_id)
                if keyword_obj and keyword_obj.fetch_status == StatusConst.PENDING:
                    keywords_with_pending_fetch.append(keyword_id)

            if keywords_with_pending_fetch:
                logger.error("~" * 60)
                logger.error(f"❌ RANK JOB REJECTED: Keywords with PENDING fetch_status")
                logger.error(f"  Job ID: {job_id}")
                logger.error(f"  Keywords with pending fetch: {keywords_with_pending_fetch}")
                logger.error(f"  Total rejected: {len(keywords_with_pending_fetch)}/{len(keyword_ids)}")
                logger.error(f"  Action required: Run fetch operation first for these keywords")
                logger.error(f"  Message will be DELETED from SQS (no retry)")
                logger.error("~" * 60)
                return {
                    'success': False,
                    'should_delete': True,
                    'reason': f'PENDING_FETCH_STATUS: {len(keywords_with_pending_fetch)} keyword(s) require fetch operation first'
                }

            # Process based on message type
            if message_type == 'partial_rank':
                logger.info(f"  🔍 Checking target domain rankings...")
                logger.info(f"  → Processing {len(keyword_ids)} keywords for quick rank determination")

                for idx, keyword_id in enumerate(keyword_ids, 1):
                    logger.info(f"    → Checking rank for keyword {keyword_id} ({idx}/{len(keyword_ids)})")

                keyword_service.run_partial_rank(keyword_ids, token, job_id=job_id)

                logger.info("~" * 60)
                logger.info(f"✅ PARTIAL RANK COMPLETE: Job {job_id}")
                logger.info(f"  Successfully determined rankings for {len(keyword_ids)} keywords")
                logger.info("~" * 60)

            elif message_type == 'full_rank':
                logger.info(f"  📈 Calculating complete rankings...")
                logger.info(f"  → Processing {len(keyword_ids)} keywords for full rank calculation")

                for idx, keyword_id in enumerate(keyword_ids, 1):
                    logger.info(f"    → Calculating full rank for keyword {keyword_id} ({idx}/{len(keyword_ids)})")

                keyword_service.run_rank(keyword_ids, token, job_id=job_id)

                logger.info("~" * 60)
                logger.info(f"✅ FULL RANK COMPLETE: Job {job_id}")
                logger.info(f"  Successfully calculated all rankings for {len(keyword_ids)} keywords")
                logger.info("~" * 60)

            else:
                logger.error(f"❌ Unknown message type: {message_type}")
                return {
                    'success': False,
                    'should_delete': False,
                    'reason': f'Unknown message type: {message_type}'
                }

            return {
                'success': True,
                'should_delete': True,
                'reason': 'Job completed successfully'
            }

        except Exception as e:
            # Check if this is a cancellation exception
            from src.utils.cancellation import JobCancelledException
            if isinstance(e, JobCancelledException):
                logger.info("~" * 60)
                logger.info(f"🚫 RANK JOB CANCELLED: Job {job_id}")
                logger.info(f"  Job was cancelled by user, remaining keywords reset to pending")
                logger.info("~" * 60)
                return {
                    'success': False,
                    'should_delete': True,  # Delete the message since job was handled
                    'reason': 'Job cancelled by user'
                }
            
            logger.error("~" * 60)
            logger.error(f"❌ RANK PROCESSOR FAILED: Job {job_id}")
            logger.error(f"  Message Type: {message_type}")
            logger.error(f"  Error Type: {type(e).__name__}")
            logger.error(f"  Error Details: {str(e)}")
            logger.error("~" * 60)
            logger.exception(e)

            # Rollback the session if there's a pending transaction
            try:
                db_session.rollback()
                logger.info("  Database session rolled back successfully")
            except:
                pass

            return {
                'success': False,
                'should_delete': False,
                'reason': f'Exception: {str(e)}'
            }
        
        finally:
            # Always close the session
            db_session.close()

    def __del__(self):
        # We don't have a persistent session anymore, but we might want to dispose the engine
        # if the application is shutting down, though typically not strictly necessary for singletons
        pass
