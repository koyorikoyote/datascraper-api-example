import logging
import os
import sys
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import SessionLocal
from src.services.keyword import KeywordService
from src.schemas.user import TokenInfo
from src.utils.constants import StatusConst, ExecutionTypeConst

logger = logging.getLogger(__name__)


class FetchProcessor:
    def __init__(self):
        self.db = None

    def _get_db_session(self):
        """Create a new database session for this job"""
        if self.db:
            self.db.close()
        self.db = SessionLocal()
        return self.db

    def _close_db_session(self):
        """Close the database session"""
        if self.db:
            self.db.close()
            self.db = None

    def process_job(self, message_body: Dict[str, Any]) -> bool:
        """
        Process a fetch job from SQS

        Args:
            message_body: The parsed JSON message body from SQS

        Returns:
            True if processing was successful, False otherwise
        """
        job_id = message_body.get('job_id', 'unknown')
        keyword_ids = message_body.get('keyword_ids', [])
        token_info_dict = message_body.get('token_info', {})
        metadata = message_body.get('metadata', {})
        user_id = message_body.get('user_id', 'unknown')

        logger.info("~" * 60)
        logger.info(f"📡 FETCH PROCESSOR: Starting SERP data retrieval")
        logger.info(f"  Job ID: {job_id}")
        logger.info(f"  User ID: {user_id}")
        logger.info(f"  Total Keywords: {len(keyword_ids)}")
        logger.info(f"  Source: {metadata.get('source', 'unknown')}")
        logger.info("~" * 60)

        try:
            # Recreate TokenInfo from dictionary
            token = TokenInfo(**token_info_dict)

            # Get a fresh database session
            db = self._get_db_session()
            logger.info(f"  ✓ Database session established")

            # Create service instance with database session
            keyword_service = KeywordService(db)
            logger.info(f"  ✓ KeywordService initialized")

            # Process each keyword with progress logging
            logger.info(f"  📥 Starting SERP fetch for {len(keyword_ids)} keywords...")

            for idx, keyword_id in enumerate(keyword_ids, 1):
                logger.info(f"    → Processing keyword {keyword_id} ({idx}/{len(keyword_ids)})")

            # Run the actual fetch operation with job_id for cancellation checking
            keyword_service.run_fetch(keyword_ids, token, job_id=job_id)

            logger.info("~" * 60)
            logger.info(f"✅ FETCH COMPLETE: Job {job_id}")
            logger.info(f"  Successfully fetched SERP data for {len(keyword_ids)} keywords")
            logger.info("~" * 60)
            return True

        except Exception as e:
            # Check if this is a cancellation exception
            from src.utils.cancellation import JobCancelledException
            if isinstance(e, JobCancelledException):
                logger.info("~" * 60)
                logger.info(f"🚫 FETCH CANCELLED: Job {job_id}")
                logger.info(f"  Job was cancelled by user, remaining keywords reset to pending")
                logger.info("~" * 60)
                # Return False but this is not an error - it's a controlled cancellation
                return False
            
            logger.error("~" * 60)
            logger.error(f"❌ FETCH FAILED: Job {job_id}")
            logger.error(f"  Error Type: {type(e).__name__}")
            logger.error(f"  Error Details: {str(e)}")
            logger.error("~" * 60)
            logger.exception(e)
            return False

        finally:
            self._close_db_session()
            logger.info(f"  ✓ Database session closed")

    def process_batch(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process multiple fetch jobs

        Args:
            messages: List of parsed message bodies

        Returns:
            Summary of processing results
        """
        results = {
            "total": len(messages),
            "successful": 0,
            "failed": 0,
            "job_ids": []
        }

        for message in messages:
            job_id = message.get('job_id', 'unknown')
            results["job_ids"].append(job_id)

            if self.process_job(message):
                results["successful"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Batch processing complete: "
            f"{results['successful']}/{results['total']} successful, "
            f"{results['failed']} failed"
        )

        return results