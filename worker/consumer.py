import boto3
import json
import logging
import signal
import sys
import time
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

from worker.config import config
from worker.unified_processor import UnifiedJobProcessor
from worker.visibility_extender import VisibilityExtender

# Add imports for database updates
sys.path.append('/app')  # Ensure we can import from src
from src.config.database import SessionLocal
from src.repositories.sqs_message_history import SQSMessageHistoryRepository
from src.models.sqs_message_history import MessageStatus
from src.services.keyword import KeywordService
from src.utils.constants import StatusConst

logger = logging.getLogger(__name__)


class SQSConsumer:
    def __init__(self):
        self.running = True
        self.sqs_client = None
        self.processor = UnifiedJobProcessor()
        self._setup_signal_handlers()
        self._initialize_sqs()
        self._set_queue_config()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.running = False

    def _initialize_sqs(self):
        try:
            if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
                self.sqs_client = boto3.client(
                    'sqs',
                    region_name=config.AWS_REGION,
                    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
                )
            else:
                self.sqs_client = boto3.client('sqs', region_name=config.AWS_REGION)

            logger.info("SQS client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {str(e)}")
            raise

    def _set_queue_config(self):
        """Set queue URL for the unified job queue"""
        self.queue_url = config.SQS_JOB_QUEUE_URL
        self.queue_name = "Unified Job Queue"

        if not self.queue_url:
            raise ValueError("SQS_JOB_QUEUE_URL not configured")

    def start(self):
        logger.info(f"Starting SQS consumer for {self.queue_name} queue...")
        logger.info(f"Queue URL: {self.queue_url}")
        logger.info(f"Poll interval: {config.WORKER_POLL_INTERVAL}s")
        logger.info(f"Visibility timeout: {config.WORKER_VISIBILITY_TIMEOUT}s")

        consecutive_errors = 0
        max_consecutive_errors = 10

        logger.info("Entering polling loop...")
        while self.running:
            try:
                messages = self._receive_messages()

                if messages:
                    consecutive_errors = 0
                    for message in messages:
                        if not self.running:
                            # Worker is shutting down, return message to queue immediately
                            logger.info("Shutdown detected, returning message to queue...")
                            try:
                                self.sqs_client.change_message_visibility(
                                    QueueUrl=self.queue_url,
                                    ReceiptHandle=message['ReceiptHandle'],
                                    VisibilityTimeout=0
                                )
                                logger.info(f"Returned message {message.get('MessageId')} to queue (VisibilityTimeout=0)")
                            except Exception as e:
                                logger.error(f"Failed to return message to queue: {str(e)}")
                            continue

                        self._process_message(message)
                else:
                    logger.info("No messages received, waiting...")

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in consumer loop: {str(e)}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}). Shutting down.")
                    break

                wait_time = min(60, 2 ** consecutive_errors)
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        logger.info("Consumer stopped")

    def _receive_messages(self) -> list:
        try:
            logger.info(f"Polling SQS queue for messages...")
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=config.WORKER_MAX_MESSAGES,
                WaitTimeSeconds=config.WORKER_POLL_INTERVAL,
                VisibilityTimeout=config.WORKER_VISIBILITY_TIMEOUT,
                MessageAttributeNames=['All'],
                AttributeNames=['All']
            )

            messages = response.get('Messages', [])
            if messages:
                logger.info(f"Received {len(messages)} message(s)")
            return messages

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS SQS error: {error_code} - {error_message}")
            raise
        except Exception as e:
            logger.error(f"Failed to receive messages: {str(e)}")
            raise

    def _process_message(self, message: Dict[str, Any]):
        receipt_handle = message['ReceiptHandle']
        message_id = message.get('MessageId', 'unknown')
        start_time = time.time()

        try:
            body = json.loads(message['Body'])
            attributes = message.get('MessageAttributes', {})
            sqs_attributes = message.get('Attributes', {})

            job_id = body.get('job_id', 'unknown')
            message_type = body.get('message_type', 'unknown')
            keyword_ids = body.get('keyword_ids', [])
            user_id = body.get('user_id', 'unknown')
            retry_count = body.get('retry_count', 0)

            # Get SQS receive count (how many times this message was delivered)
            sqs_receive_count = int(sqs_attributes.get('ApproximateReceiveCount', 1))

            # Max retry limit
            MAX_RETRIES = 3

            # Check if message has exceeded max retries
            if sqs_receive_count > MAX_RETRIES:
                logger.error("=" * 60)
                logger.error(f"💀 MAX RETRIES EXCEEDED - DELETING MESSAGE")
                logger.error(f"  Message ID: {message_id}")
                logger.error(f"  Job ID: {job_id}")
                logger.error(f"  SQS Receive Count: {sqs_receive_count}")
                logger.error(f"  Max Retries: {MAX_RETRIES}")
                logger.error("=" * 60)

                # Update status to FAILED with max retries exceeded
                self._update_message_history(
                    message_id,
                    MessageStatus.FAILED,
                    error_details=f"Max retries exceeded ({sqs_receive_count}/{MAX_RETRIES})",
                    error_code="MAX_RETRIES_EXCEEDED"
                )

                # Update keyword status to FAILED in database
                self._fail_keywords(keyword_ids, message_type)

                # Delete the message to prevent further retries
                self._delete_message(receipt_handle)
                return

            # Log received job details
            logger.info("=" * 60)
            logger.info(f"📥 RECEIVED NEW JOB FROM SQS")
            logger.info(f"  Message ID: {message_id}")
            logger.info(f"  Job ID: {job_id}")
            logger.info(f"  Type: {message_type}")
            logger.info(f"  User ID: {user_id}")
            logger.info(f"  Keywords: {keyword_ids[:5]}{'...' if len(keyword_ids) > 5 else ''}")
            logger.info(f"  Total Keywords: {len(keyword_ids)}")
            logger.info(f"  SQS Receive Count: {sqs_receive_count}/{MAX_RETRIES}")
            logger.info("=" * 60)

            # Check if job was cancelled before processing
            db = SessionLocal()
            try:
                repo = SQSMessageHistoryRepository(db)
                existing_record = repo.get_by_job_id(job_id)

                if existing_record and existing_record.status == MessageStatus.CANCELLED:
                    logger.info("=" * 60)
                    logger.info(f"🚫 JOB CANCELLED - SKIPPING PROCESSING")
                    logger.info(f"  Message ID: {message_id}")
                    logger.info(f"  Job ID: {job_id}")
                    logger.info(f"  Cancelled at: {existing_record.updated_at}")
                    logger.info("=" * 60)

                    # Delete the message from SQS
                    self._delete_message(receipt_handle)

                    # Update status to DELETED
                    repo.update_status(message_id, MessageStatus.DELETED)
                    db.commit()

                    logger.info(f"✅ Cancelled job {job_id} deleted from SQS and marked as DELETED")
                    return
            finally:
                db.close()

            logger.info(f"⚙️  PROCESSING: Starting {message_type} job {job_id}")

            # Update status to PROCESSING
            self._update_message_history(
                message_id,
                MessageStatus.PROCESSING,
                sqs_receive_count=sqs_receive_count,
                job_id=job_id,
                message_type=message_type,
                keyword_ids=keyword_ids,
                user_id=user_id
            )

            # Start visibility extender for long-running jobs
            # Jobs with 25+ keywords are considered large and may need extended time
            # full_rank jobs process 100 items per keyword so they always need extended time
            visibility_extender = None
            if len(keyword_ids) >= 25 or message_type == 'full_rank':
                visibility_extender = VisibilityExtender(
                    self.sqs_client,
                    self.queue_url,
                    receipt_handle,
                    message_id
                )
                visibility_extender.start()
                logger.info(f"Started visibility extender for job {job_id} (keywords={len(keyword_ids)}, type={message_type})")

            try:
                # Process the job using unified processor
                result = self.processor.process_job(body)
            finally:
                # Always stop the extender when done
                if visibility_extender:
                    visibility_extender.stop()

            duration = round(time.time() - start_time, 2)

            # Handle result (dict with success, should_delete, reason)
            success = result.get('success', False)
            should_delete = result.get('should_delete', False)
            reason = result.get('reason', 'Unknown')

            if success:
                # Update status to COMPLETED
                self._update_message_history(message_id, MessageStatus.COMPLETED)

                # Delete the message from the queue
                self._delete_message(receipt_handle)
                logger.info("=" * 60)
                logger.info(f"✅ SUCCESS: Job {job_id} completed")
                logger.info(f"  Message ID: {message_id}")
                logger.info(f"  Duration: {duration} seconds")
                logger.info(f"  Keywords Processed: {len(keyword_ids)}")
                logger.info(f"  Reason: {reason}")
                logger.info("=" * 60)
            else:
                # Job failed - check if we should delete or retry
                if should_delete:
                    # Delete message without retry (e.g., invalid job, pending fetch status)
                    self._update_message_history(
                        message_id,
                        MessageStatus.FAILED,
                        error_details=reason,
                        error_code="JOB_REJECTED"
                    )
                    
                    # Update keyword status to FAILED in database
                    self._fail_keywords(keyword_ids, message_type)

                    self._delete_message(receipt_handle)
                    logger.error("=" * 60)
                    logger.error(f"❌ FAILED: Job {job_id} rejected (message deleted)")
                    logger.error(f"  Message ID: {message_id}")
                    logger.error(f"  Duration: {duration} seconds")
                    logger.error(f"  Reason: {reason}")
                    logger.error(f"  No retry will occur")
                    logger.error("=" * 60)
                else:
                    # Leave message for retry
                    self._update_message_history(
                        message_id,
                        MessageStatus.FAILED,
                        error_details=reason,
                        error_code="PROCESS_FAILED"
                    )
                    
                    # Update keyword status to FAILED in database
                    self._fail_keywords(keyword_ids, message_type)

                    logger.error("=" * 60)
                    logger.error(f"❌ FAILED: Job {job_id} failed to process")
                    logger.error(f"  Message ID: {message_id}")
                    logger.error(f"  Duration: {duration} seconds")
                    logger.error(f"  Reason: {reason}")
                    logger.error(f"  SQS Receive Count: {sqs_receive_count}/{MAX_RETRIES}")
                    logger.error(f"  Will be retried in 15 minutes (unless max retries exceeded)")
                    logger.error("=" * 60)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message body: {str(e)}")
            # Update status to FAILED for malformed messages
            self._update_message_history(
                message_id,
                MessageStatus.FAILED,
                error_details=f"JSON decode error: {str(e)}",
                error_code="MALFORMED_MESSAGE"
            )
            # Delete malformed messages to prevent infinite retries
            self._delete_message(receipt_handle)
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {str(e)}")
            # Update status to FAILED for unexpected errors
            self._update_message_history(
                message_id,
                MessageStatus.FAILED,
                error_details=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR"
            )
            # Try to fail keywords if we parsed them successfully
            if 'keyword_ids' in locals() and 'message_type' in locals():
                self._fail_keywords(keyword_ids, message_type)
            # Don't delete the message - let it become visible again for retry

    def _update_message_history(
        self,
        message_id: str,
        status: MessageStatus,
        error_details: Optional[str] = None,
        error_code: Optional[str] = None,
        sqs_receive_count: Optional[int] = None,
        job_id: Optional[str] = None,
        message_type: Optional[str] = None,
        keyword_ids: Optional[list] = None,
        user_id: Optional[int] = None
    ):
        """Update the message history in the database"""
        db = SessionLocal()
        try:
            repo = SQSMessageHistoryRepository(db)
            # If we have sqs_receive_count, use create_or_update to track it
            if sqs_receive_count is not None:
                # Convert message_type string to MessageType enum if provided
                from src.models.sqs_message_history import MessageType
                from src.models.user import User

                message_type_enum = None
                if message_type:
                    try:
                        message_type_enum = MessageType(message_type)
                    except ValueError:
                        logger.warning(f"Invalid message_type: {message_type}")

                # Fetch user_full_name from database
                user_full_name = None
                if user_id and user_id != 'unknown':
                    try:
                        user = db.query(User).filter(User.id == user_id).first()
                        if user:
                            user_full_name = user.full_name
                    except Exception as e:
                        logger.warning(f"Failed to fetch user full name: {str(e)}")

                repo.create_or_update(
                    sqs_message_id=message_id,
                    status=status,
                    sqs_receive_count=sqs_receive_count,
                    job_id=job_id,
                    message_type=message_type_enum,
                    keyword_ids=keyword_ids,
                    user_id=user_id if user_id != 'unknown' else None,
                    user_full_name=user_full_name
                )
            else:
                repo.update_status(
                    sqs_message_id=message_id,
                    status=status,
                    error_details=error_details,
                    error_code=error_code
                )
            db.commit()
            logger.info(f"Updated message history for {message_id} to {status.value}")
        except Exception as e:
            logger.error(f"Failed to update message history: {str(e)}")
            db.rollback()
        finally:
            db.close()

    def _delete_message(self, receipt_handle: str):
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
        except Exception as e:
            logger.error(f"Failed to delete message: {str(e)}")

    def _change_message_visibility(self, receipt_handle: str, timeout: int):
        try:
            self.sqs_client.change_message_visibility(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=timeout
            )
        except Exception as e:
            logger.error(f"Failed to change message visibility: {str(e)}")

    def _fail_keywords(self, keyword_ids: list[int], message_type: str):
        """
        Mark keywords as FAILED in the main database
        """
        if not keyword_ids:
            return
            
        status_field = None
        if message_type == 'fetch':
            status_field = 'fetch_status'
        elif message_type == 'partial_rank':
            status_field = 'partial_rank_status'
        elif message_type == 'full_rank':
            status_field = 'rank_status'
            
        if status_field:
            db = SessionLocal()
            try:
                service = KeywordService(db)
                service.set_keywords_status(keyword_ids, status_field, StatusConst.FAILED)
                
                # Also fail any stuck SERP results for these keywords
                # This ensures that if the job crashes, individual rows don't stay in PROCESSING
                count = service.fail_processing_serp_results(keyword_ids)
                if count > 0:
                    logger.info(f"Marked {count} stuck SERP results as FAILED for keywords {keyword_ids}")

                logger.info(f"Marked {len(keyword_ids)} keywords as FAILED in {status_field}")
            except Exception as e:
                logger.error(f"Failed to update keyword status to FAILED: {str(e)}")
            finally:
                db.close()