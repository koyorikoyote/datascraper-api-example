import logging
import os
import sys
from typing import Dict, Any
from datetime import datetime

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import SessionLocal
from src.services.keyword import KeywordService
from src.schemas.user import TokenInfo
from src.schemas.sqs_message import SQSMessageType
from worker.processor import RankProcessor
from worker.fetch_processor import FetchProcessor

logger = logging.getLogger(__name__)


class UnifiedJobProcessor:
    """
    Unified processor that routes jobs to appropriate handlers based on message type
    """
    def __init__(self):
        # Initialize all processors
        self.rank_processor = RankProcessor()
        self.fetch_processor = FetchProcessor()
        logger.info("UnifiedJobProcessor initialized with all job type handlers")

    def process_job(self, message_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a job by routing it to the appropriate processor based on message type

        Args:
            message_body: The parsed JSON message body from SQS

        Returns:
            dict: {'success': bool, 'should_delete': bool, 'reason': str}
        """
        job_id = message_body.get('job_id', 'unknown')
        message_type = message_body.get('message_type', 'unknown')
        keyword_ids = message_body.get('keyword_ids', [])
        user_id = message_body.get('user_id', 'unknown')

        logger.info("-" * 60)
        logger.info(f"🔄 ROUTING JOB TO PROCESSOR")
        logger.info(f"  Job ID: {job_id}")
        logger.info(f"  Message Type: {message_type}")
        logger.info(f"  Target Processor: {self._get_processor_name(message_type)}")
        logger.info("-" * 60)

        try:
            # Route to appropriate processor based on message type
            if message_type == SQSMessageType.FETCH.value:
                logger.info(f"📡 FETCH JOB: Starting SERP data retrieval")
                logger.info(f"  Task: Fetch search results for {len(keyword_ids)} keywords")
                result = self.fetch_processor.process_job(message_body)
                if result:
                    logger.info(f"✓ FETCH JOB: Successfully retrieved SERP data")
                    return {'success': True, 'should_delete': True, 'reason': 'Fetch completed'}
                else:
                    logger.error(f"✗ FETCH JOB: Failed to retrieve SERP data")
                    return {'success': False, 'should_delete': False, 'reason': 'Fetch failed'}

            elif message_type == SQSMessageType.PARTIAL_RANK.value:
                logger.info(f"🎯 PARTIAL RANK JOB: Starting quick rank check")
                logger.info(f"  Task: Determine target domain rankings for {len(keyword_ids)} keywords")
                result = self.rank_processor.process_job(message_body)
                if result.get('success'):
                    logger.info(f"✓ PARTIAL RANK JOB: Successfully determined rankings")
                else:
                    logger.error(f"✗ PARTIAL RANK JOB: Failed to determine rankings")
                return result

            elif message_type == SQSMessageType.FULL_RANK.value:
                logger.info(f"📊 FULL RANK JOB: Starting comprehensive ranking")
                logger.info(f"  Task: Calculate complete rankings for {len(keyword_ids)} keywords")
                result = self.rank_processor.process_job(message_body)
                if result.get('success'):
                    logger.info(f"✓ FULL RANK JOB: Successfully calculated all rankings")
                else:
                    logger.error(f"✗ FULL RANK JOB: Failed to calculate rankings")
                return result

            else:
                logger.error(f"❌ ROUTING ERROR: Unknown message type '{message_type}'")
                logger.error(f"  Job ID: {job_id}")
                logger.error(f"  Valid types: fetch, partial_rank, full_rank")
                return {'success': False, 'should_delete': False, 'reason': f'Unknown message type: {message_type}'}

        except Exception as e:
            logger.error("-" * 60)
            logger.error(f"💥 PROCESSOR ERROR: Unhandled exception in job {job_id}")
            logger.error(f"  Error Type: {type(e).__name__}")
            logger.error(f"  Error Message: {str(e)}")
            logger.error("-" * 60)
            logger.exception(e)
            return {'success': False, 'should_delete': False, 'reason': f'Exception: {str(e)}'}

    def _get_processor_name(self, message_type: str) -> str:
        """Get human-readable processor name"""
        if message_type == SQSMessageType.FETCH.value:
            return "FetchProcessor"
        elif message_type in [SQSMessageType.PARTIAL_RANK.value, SQSMessageType.FULL_RANK.value]:
            return "RankProcessor"
        else:
            return "Unknown"

    def get_processor_for_type(self, message_type: str):
        """
        Get the appropriate processor for a given message type

        Args:
            message_type: The type of message (fetch, partial_rank, full_rank)

        Returns:
            The appropriate processor instance
        """
        if message_type == SQSMessageType.FETCH.value:
            return self.fetch_processor
        elif message_type in [SQSMessageType.PARTIAL_RANK.value, SQSMessageType.FULL_RANK.value]:
            return self.rank_processor
        else:
            raise ValueError(f"Unknown message type: {message_type}")

    def cleanup(self):
        """
        Cleanup resources for all processors
        """
        try:
            # Close any open database connections
            if hasattr(self.fetch_processor, '_close_db_session'):
                self.fetch_processor._close_db_session()

            # RankProcessor manages its own db session
            if hasattr(self.rank_processor, 'db_session'):
                if self.rank_processor.db_session:
                    self.rank_processor.db_session.close()

            logger.info("UnifiedJobProcessor cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")