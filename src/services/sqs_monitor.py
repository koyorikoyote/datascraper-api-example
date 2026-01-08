import boto3
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from botocore.exceptions import ClientError

from sqlalchemy.orm import Session
from src.config.config import settings
from src.models.user import User
from src.models.sqs_message_history import SQSMessageHistory, MessageStatus as DBMessageStatus, MessageType as DBMessageType
from src.repositories.sqs_message_history import SQSMessageHistoryRepository
from src.schemas.sqs_monitor import (
    SQSMessageDetail,
    SQSQueueMessages,
    SQSMonitorResponse,
    MessageStatus,
    SQSDeleteResponse
)


logger = logging.getLogger(__name__)


class SQSMonitorService:
    def __init__(self, db: Optional[Session] = None):
        self.sqs_client = None
        self.job_queue_url = None
        self.job_dlq_url = None
        self.db = db
        self._initialize_sqs()

    def _initialize_sqs(self):
        """Initialize SQS client and queue URLs"""
        try:
            aws_region = settings.get("AWS_REGION", "ap-northeast-1")
            aws_access_key = settings.get("AWS_ACCESS_KEY_ID")
            aws_secret_key = settings.get("AWS_SECRET_ACCESS_KEY")

            if aws_access_key and aws_secret_key:
                self.sqs_client = boto3.client(
                    'sqs',
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
            else:
                self.sqs_client = boto3.client('sqs', region_name=aws_region)

            self.job_queue_url = settings.get("SQS_JOB_QUEUE_URL")
            self.job_dlq_url = settings.get("SQS_JOB_DLQ_URL")

            logger.info(f"SQS Monitor initialized - Queue: {self.job_queue_url}")

        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {str(e)}")
            self.sqs_client = None

    def get_all_messages(
        self,
        max_messages: int = 100,
        db: Optional[Session] = None,
        include_in_flight: bool = False
    ) -> SQSMonitorResponse:
        """
        Fetch all messages from both main queue and DLQ
        Note: This does NOT remove messages from the queue, just reads them

        Args:
            max_messages: Maximum number of messages to fetch per queue

        Returns:
            SQSMonitorResponse with all message details
        """
        if not self.sqs_client:
            logger.error("SQS client not initialized")
            return SQSMonitorResponse(
                summary={"error": "SQS client not initialized"},
                timestamp=datetime.utcnow()
            )

        response = SQSMonitorResponse(
            summary={
                "total_available": 0,
                "total_in_flight": 0,
                "total_failed": 0,
                "total_all": 0
            }
        )

        # Fetch messages from main queue
        if self.job_queue_url:
            main_messages = self._fetch_queue_messages(
                self.job_queue_url,
                "main",
                max_messages,
                db=db or self.db,
                include_in_flight=include_in_flight
            )
            if main_messages:
                response.main_queue = main_messages
                # Count available and in-flight messages
                for msg in main_messages.messages:
                    if msg.status == MessageStatus.AVAILABLE:
                        response.summary["total_available"] += 1
                    elif msg.status == MessageStatus.IN_FLIGHT:
                        response.summary["total_in_flight"] += 1

        # Fetch messages from DLQ
        if self.job_dlq_url:
            dlq_messages = self._fetch_queue_messages(
                self.job_dlq_url,
                "dlq",
                max_messages,
                db=db or self.db,
                include_in_flight=False  # Never peek at DLQ in-flight messages
            )
            if dlq_messages:
                response.dead_letter_queue = dlq_messages
                response.summary["total_failed"] = dlq_messages.total_messages

        # Calculate total
        response.summary["total_all"] = (
            response.summary["total_available"] +
            response.summary["total_in_flight"] +
            response.summary["total_failed"]
        )

        return response

    def _fetch_queue_messages(
        self,
        queue_url: str,
        queue_type: str,
        max_messages: int = 100,
        db: Optional[Session] = None,
        include_in_flight: bool = False
    ) -> Optional[SQSQueueMessages]:
        """
        Fetch messages from a specific queue

        Args:
            queue_url: URL of the queue
            queue_type: Type of queue (main/dlq)
            max_messages: Maximum messages to fetch

        Returns:
            SQSQueueMessages or None if error
        """
        try:
            messages = []
            total_fetched = 0
            has_more = False

            # First, get queue attributes to know how many messages exist
            queue_attrs = self._get_queue_attributes(queue_url)
            total_available = int(queue_attrs.get('ApproximateNumberOfMessages', 0))
            total_in_flight = int(queue_attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
            total_in_queue = total_available + total_in_flight

            logger.info(f"Queue {queue_type}: {total_available} available, {total_in_flight} in flight")

            # If include_in_flight is True, try to peek at in-flight messages first
            if include_in_flight and total_in_flight > 0:
                logger.info(f"Attempting to peek at {total_in_flight} in-flight messages")

                # Fetch with a short visibility timeout to temporarily make them visible
                peek_messages = []
                peek_batches = (total_in_flight + 9) // 10  # Calculate number of batches needed

                for _ in range(min(peek_batches, 10)):  # Limit to 10 batches max
                    try:
                        peek_response = self.sqs_client.receive_message(
                            QueueUrl=queue_url,
                            MaxNumberOfMessages=10,
                            AttributeNames=['All'],
                            MessageAttributeNames=['All'],
                            VisibilityTimeout=1  # Very short timeout to peek
                        )

                        batch_msgs = peek_response.get('Messages', [])
                        if not batch_msgs:
                            break

                        for msg in batch_msgs:
                            # Parse and add as in-flight message
                            message_detail = self._parse_message(msg, MessageStatus.IN_FLIGHT, db=db)
                            messages.append(message_detail)
                            peek_messages.append((msg['MessageId'], msg['ReceiptHandle']))

                            # Log to database
                            if db:
                                self._log_message_to_db(message_detail, queue_type, db)

                    except Exception as e:
                        logger.warning(f"Failed to peek at in-flight messages: {str(e)}")
                        break

                # Immediately make peeked messages visible again
                if peek_messages:
                    for msg_id, receipt_handle in peek_messages:
                        try:
                            self.sqs_client.change_message_visibility(
                                QueueUrl=queue_url,
                                ReceiptHandle=receipt_handle,
                                VisibilityTimeout=0  # Make immediately visible again
                            )
                        except Exception as e:
                            logger.warning(f"Failed to reset visibility for message {msg_id}: {str(e)}")

                    logger.info(f"Peeked at {len(peek_messages)} in-flight messages and reset visibility")
                    total_fetched = len(messages)

            # Fetch available messages in batches (max 10 per request)
            while total_fetched < min(max_messages, total_available):
                batch_size = min(10, max_messages - total_fetched)

                # Receive messages without deleting them
                response = self.sqs_client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=batch_size,
                    AttributeNames=['All'],
                    MessageAttributeNames=['All'],
                    VisibilityTimeout=0  # Don't hide messages from queue
                )

                batch_messages = response.get('Messages', [])
                if not batch_messages:
                    break

                for msg in batch_messages:
                    message_detail = self._parse_message(msg, MessageStatus.AVAILABLE, db=db)
                    messages.append(message_detail)

                    # Log to database
                    if db:
                        self._log_message_to_db(message_detail, queue_type, db)

                total_fetched += len(batch_messages)

                # If we got fewer messages than requested, we've fetched all available
                if len(batch_messages) < batch_size:
                    break

            # Add placeholder entries for remaining in-flight messages we couldn't peek at
            if not include_in_flight and total_in_flight > 0:
                # Only add placeholders if we didn't peek at them
                remaining_in_flight = min(total_in_flight, max_messages - total_fetched)
                for i in range(remaining_in_flight):
                    messages.append(SQSMessageDetail(
                        message_id=f"in-flight-{i+1}",
                        status=MessageStatus.IN_FLIGHT,
                        body={"note": "Message currently being processed (use include_in_flight=true to see details)"}
                    ))

            # Check if there are more messages than we fetched
            has_more = total_in_queue > len(messages)

            return SQSQueueMessages(
                queue_url=queue_url,
                queue_type=queue_type,
                total_messages=total_in_queue,
                messages=messages,
                has_more=has_more,
                fetched_at=datetime.utcnow()
            )

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS SQS error for {queue_type}: {error_code} - {error_message}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch messages from {queue_type}: {str(e)}")
            return None

    def _parse_message(
        self,
        message: Dict[str, Any],
        status: MessageStatus,
        db: Optional[Session] = None
    ) -> SQSMessageDetail:
        """
        Parse an SQS message into our schema

        Args:
            message: Raw SQS message
            status: Status of the message

        Returns:
            SQSMessageDetail object
        """
        try:
            # Parse message body
            body = json.loads(message.get('Body', '{}'))

            # Get message attributes
            attributes = message.get('Attributes', {})
            message_attributes = message.get('MessageAttributes', {})

            # Extract sent timestamp
            sent_timestamp = None
            if 'SentTimestamp' in attributes:
                sent_timestamp = datetime.fromtimestamp(
                    int(attributes['SentTimestamp']) / 1000
                )

            # Extract first receive timestamp
            first_receive = None
            if 'ApproximateFirstReceiveTimestamp' in attributes:
                first_receive = datetime.fromtimestamp(
                    int(attributes['ApproximateFirstReceiveTimestamp']) / 1000
                )

            # Fetch user full name if user_id is present
            user_full_name = None
            user_id = body.get('user_id')
            if user_id and db:
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        user_full_name = user.full_name
                except Exception as e:
                    logger.warning(f"Failed to fetch user name for user_id {user_id}: {str(e)}")

            return SQSMessageDetail(
                message_id=message.get('MessageId', 'unknown'),
                receipt_handle=message.get('ReceiptHandle'),
                status=status,
                job_id=body.get('job_id'),
                message_type=body.get('message_type'),
                keyword_ids=body.get('keyword_ids', []),
                user_id=user_id,
                user_full_name=user_full_name,
                retry_count=body.get('retry_count', 0),
                sent_timestamp=sent_timestamp,
                first_receive_timestamp=first_receive,
                receive_count=int(attributes.get('ApproximateReceiveCount', 0)),
                visibility_timeout=None,  # Not available in this context
                body=body,
                attributes=attributes
            )

        except Exception as e:
            logger.error(f"Failed to parse message: {str(e)}")
            return SQSMessageDetail(
                message_id=message.get('MessageId', 'unknown'),
                status=status,
                body={"error": f"Failed to parse: {str(e)}"}
            )

    def _get_queue_attributes(self, queue_url: str) -> Dict[str, Any]:
        """
        Get attributes for a specific queue

        Args:
            queue_url: URL of the queue

        Returns:
            Dictionary of queue attributes
        """
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            return response.get('Attributes', {})
        except Exception as e:
            logger.error(f"Failed to get queue attributes: {str(e)}")
            return {}

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get basic queue statistics without fetching all messages

        Returns:
            Dictionary with queue statistics
        """
        if not self.sqs_client:
            return {"error": "SQS client not initialized"}

        stats = {
            "main_queue": {},
            "dead_letter_queue": {},
            "timestamp": datetime.utcnow().isoformat()
        }

        if self.job_queue_url:
            stats["main_queue"] = self._get_queue_attributes(self.job_queue_url)

        if self.job_dlq_url:
            stats["dead_letter_queue"] = self._get_queue_attributes(self.job_dlq_url)

        return stats

    def delete_message(self, message_id: str, receipt_handle: str) -> SQSDeleteResponse:
        """
        Delete a message from the SQS queue

        Args:
            message_id: The message ID (for logging/response)
            receipt_handle: The receipt handle required to delete the message

        Returns:
            SQSDeleteResponse indicating success or failure
        """
        if not self.sqs_client or not self.job_queue_url:
            logger.error("SQS client not initialized")
            return SQSDeleteResponse(
                success=False,
                message_id=message_id,
                message="SQS client not initialized"
            )

        try:
            # Delete the message from the queue
            self.sqs_client.delete_message(
                QueueUrl=self.job_queue_url,
                ReceiptHandle=receipt_handle
            )

            logger.info(f"Successfully deleted message {message_id} from queue")

            # Update database record if available
            if self.db:
                try:
                    repo = SQSMessageHistoryRepository(self.db)
                    repo.update_status(message_id, DBMessageStatus.DELETED)
                except Exception as e:
                    logger.warning(f"Failed to update database for deleted message: {str(e)}")

            return SQSDeleteResponse(
                success=True,
                message_id=message_id,
                message="Message successfully deleted from queue"
            )

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            if error_code == 'ReceiptHandleIsInvalid':
                msg = "Invalid receipt handle - message may have already been processed or deleted"
            elif error_code == 'MessageNotInflight':
                msg = "Message is not available for deletion"
            else:
                msg = f"AWS SQS error: {error_code} - {error_message}"

            logger.error(f"Failed to delete message {message_id}: {msg}")

            return SQSDeleteResponse(
                success=False,
                message_id=message_id,
                message=msg
            )

        except Exception as e:
            logger.error(f"Unexpected error deleting message {message_id}: {str(e)}")

            return SQSDeleteResponse(
                success=False,
                message_id=message_id,
                message=f"Failed to delete message: {str(e)}"
            )

    def _log_message_to_db(
        self,
        message_detail: SQSMessageDetail,
        queue_type: str,
        db: Session
    ):
        """
        Log SQS message details to the database
        """
        try:
            repo = SQSMessageHistoryRepository(db)

            # Map status
            db_status = DBMessageStatus.QUEUED
            if message_detail.status == MessageStatus.IN_FLIGHT:
                db_status = DBMessageStatus.PROCESSING
            elif message_detail.status == MessageStatus.FAILED:
                db_status = DBMessageStatus.DLQ if queue_type == "dlq" else DBMessageStatus.FAILED

            # Map message type to database enum
            db_message_type = None
            if message_detail.message_type:
                # Map string values to enum values (handle potential case differences)
                type_mapping = {
                    "fetch": DBMessageType.FETCH,
                    "partial_rank": DBMessageType.PARTIAL_RANK,
                    "full_rank": DBMessageType.FULL_RANK,
                    "fetch_and_rank": DBMessageType.FETCH_AND_RANK
                }
                db_message_type = type_mapping.get(message_detail.message_type.lower())

            # Create or update history record
            repo.create_or_update(
                sqs_message_id=message_detail.message_id,
                job_id=message_detail.job_id,
                message_type=db_message_type,
                keyword_ids=message_detail.keyword_ids,
                user_id=message_detail.user_id,
                user_full_name=message_detail.user_full_name,
                status=db_status,
                retry_count=message_detail.retry_count,
                queue_name=queue_type,
                receipt_handle=message_detail.receipt_handle,
                message_body=message_detail.body,
                message_attributes=message_detail.attributes,
                queued_at=message_detail.sent_timestamp,
                receive_count=message_detail.receive_count,
                visibility_timeout=message_detail.visibility_timeout
            )

        except Exception as e:
            logger.warning(f"Failed to log message to database: {str(e)}")