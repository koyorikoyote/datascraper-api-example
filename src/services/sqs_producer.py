import boto3
import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from botocore.exceptions import ClientError

from sqlalchemy.orm import Session
from src.config.config import settings
from src.models.sqs_message_history import SQSMessageHistory, MessageStatus as DBMessageStatus, MessageType as DBMessageType
from src.models.keyword import Keyword
from src.models.user import User
from src.repositories.sqs_message_history import SQSMessageHistoryRepository
from src.schemas.sqs_message import UnifiedJobMessage, SQSMessageType
from src.schemas.user import TokenInfo


logger = logging.getLogger(__name__)


class SQSProducerService:
    def __init__(self, db: Optional[Session] = None):
        self.sqs_client = None
        self.job_queue_url = None
        self.job_dlq_url = None
        self.db = db
        self._initialize_sqs()

    def _initialize_sqs(self):
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
            if self.job_queue_url:
                self.job_queue_url = self.job_queue_url.strip()
                
            self.job_dlq_url = settings.get("SQS_JOB_DLQ_URL")
            if self.job_dlq_url:
                self.job_dlq_url = self.job_dlq_url.strip()

            logger.info(f"SQS Producer initialized:")
            logger.info(f"  Job Queue (FIFO): {self.job_queue_url}")

            if not self.job_queue_url:
                logger.warning("SQS_JOB_QUEUE_URL not configured")

        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {str(e)}")
            raise

    def send_job(
        self,
        job_type: SQSMessageType,
        keyword_ids: List[int],
        token: TokenInfo,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Unified method to send any job type to the single queue"""
        if not self.sqs_client or not self.job_queue_url:
            raise ValueError("SQS client not properly initialized")

        try:
            job_id = str(uuid.uuid4())

            message = UnifiedJobMessage(
                job_id=job_id,
                message_type=job_type,
                keyword_ids=keyword_ids,
                user_id=token.id,  # Changed from token.user_id to token.id
                token_info=token.model_dump(),
                timestamp=datetime.utcnow(),
                metadata=metadata
            )

            message_payload = message.model_dump(mode="json")

            active_db = db or self.db
            if active_db:
                message_payload = self._enrich_message_body_with_keywords(
                    message_payload,
                    keyword_ids,
                    active_db
                )

            message_body = json.dumps(message_payload)

            message_attributes = {
                'job_id': {
                    'DataType': 'String',
                    'StringValue': job_id
                },
                'message_type': {
                    'DataType': 'String',
                    'StringValue': job_type.value
                },
                'user_id': {
                    'DataType': 'Number',
                    'StringValue': str(token.id)
                },
                'keyword_count': {
                    'DataType': 'Number',
                    'StringValue': str(len(keyword_ids))
                }
            }

            # Check if it's a FIFO queue and send accordingly
            send_params = {
                'QueueUrl': self.job_queue_url,
                'MessageBody': message_body,
                'MessageAttributes': message_attributes
            }

            # Only add FIFO parameters if queue name ends with .fifo
            if self._is_fifo_queue(self.job_queue_url):
                send_params['MessageGroupId'] = 'job-queue'
                # Include timestamp in deduplication ID to prevent FIFO duplicate rejection
                import time
                send_params['MessageDeduplicationId'] = f"{job_id}-{int(time.time() * 1000)}"

            response = self.sqs_client.send_message(**send_params)

            logger.info(
                f"Sent {job_type.value} job to SQS: job_id={job_id}, "
                f"message_id={response['MessageId']}, "
                f"keyword_ids={keyword_ids}"
            )

            # Log to database
            if active_db:
                self._log_sent_message_to_db(
                    sqs_message_id=response["MessageId"],
                    job_id=job_id,
                    job_type=job_type,
                    keyword_ids=keyword_ids,
                    user_id=token.id,
                    message_body=message_payload,
                    db=active_db
                )

            return {
                "job_id": job_id,
                "message_id": response['MessageId'],
                "status": "queued",
                "job_type": job_type.value,
                "keyword_ids": keyword_ids,
                "timestamp": message.timestamp.isoformat()
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS SQS error: {error_code} - {error_message}")
            raise
        except Exception as e:
            logger.error(f"Failed to send message to SQS: {str(e)}")
            raise

    # Compatibility methods that use the unified send_job
    def send_partial_rank_job(
        self,
        keyword_ids: List[int],
        token: TokenInfo,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        return self.send_job(SQSMessageType.PARTIAL_RANK, keyword_ids, token, metadata, db)

    def send_full_rank_job(
        self,
        keyword_ids: List[int],
        token: TokenInfo,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        return self.send_job(SQSMessageType.FULL_RANK, keyword_ids, token, metadata, db)

    def send_fetch_job(
        self,
        keyword_ids: List[int],
        token: TokenInfo,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        return self.send_job(SQSMessageType.FETCH, keyword_ids, token, metadata, db)

    def send_batch_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not self.sqs_client or not self.job_queue_url:
            raise ValueError("SQS client not properly initialized")

        try:
            entries = []
            for idx, msg in enumerate(messages[:10]):
                entry = {
                    'Id': str(idx),
                    'MessageBody': json.dumps(msg),
                    'MessageAttributes': {
                        'job_id': {
                            'DataType': 'String',
                            'StringValue': msg.get('job_id', str(uuid.uuid4()))
                        },
                        'message_type': {
                            'DataType': 'String',
                            'StringValue': msg.get('message_type', 'unknown')
                        }
                    }
                }

                if self._is_fifo_queue(self.job_queue_url):
                    entry['MessageGroupId'] = 'job-queue'
                    import time
                    job_id = msg.get('job_id', str(uuid.uuid4()))
                    entry['MessageDeduplicationId'] = f"{job_id}-{int(time.time() * 1000)}-{idx}"

                entries.append(entry)

            response = self.sqs_client.send_message_batch(
                QueueUrl=self.job_queue_url,
                Entries=entries
            )

            successful = len(response.get('Successful', []))
            failed = len(response.get('Failed', []))

            logger.info(f"Batch send result: {successful} successful, {failed} failed")

            return {
                "successful": successful,
                "failed": failed,
                "details": response
            }

        except Exception as e:
            logger.error(f"Failed to send batch messages to SQS: {str(e)}")
            raise

    def get_queue_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.sqs_client or not self.job_queue_url:
            return None

        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.job_queue_url,
                AttributeNames=['All']
            )
            return response['Attributes']
        except Exception as e:
            logger.error(f"Failed to get queue attributes: {str(e)}")
            return None

    def _is_fifo_queue(self, queue_url: str) -> bool:
        return queue_url and queue_url.strip().endswith('.fifo') if queue_url else False

    def _log_sent_message_to_db(
        self,
        sqs_message_id: str,
        job_id: str,
        job_type: SQSMessageType,
        keyword_ids: List[int],
        user_id: int,
        message_body: dict,
        db: Session
    ):
        """Log sent message to database"""
        try:
            repo = SQSMessageHistoryRepository(db)

            # Get user full name
            user_full_name = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user_full_name = user.full_name

            # Map message type
            db_message_type = None
            if job_type == SQSMessageType.FETCH:
                db_message_type = DBMessageType.FETCH
            elif job_type == SQSMessageType.PARTIAL_RANK:
                db_message_type = DBMessageType.PARTIAL_RANK
            elif job_type == SQSMessageType.FULL_RANK:
                db_message_type = DBMessageType.FULL_RANK
            elif job_type == SQSMessageType.FETCH_AND_RANK:
                db_message_type = DBMessageType.FETCH_AND_RANK

            # Create history record
            repo.create_or_update(
                sqs_message_id=sqs_message_id,
                job_id=job_id,
                message_type=db_message_type,
                keyword_ids=keyword_ids,
                user_id=user_id,
                user_full_name=user_full_name,
                status=DBMessageStatus.QUEUED,
                queue_name="main",
                message_body=message_body,
                queued_at=datetime.utcnow()
            )

            logger.info(f"Logged message {sqs_message_id} to database")

        except Exception as e:
            logger.warning(f"Failed to log message to database: {str(e)}")

    def _enrich_message_body_with_keywords(
        self,
        base_body: Dict[str, Any],
        keyword_ids: List[int],
        db: Session
    ) -> Dict[str, Any]:
        """Attach keyword terms to the message body for easier debugging."""
        if not keyword_ids:
            return base_body

        try:
            keyword_rows = (
                db.query(Keyword.id, Keyword.keyword)
                .filter(Keyword.id.in_(keyword_ids))
                .all()
            )
            keyword_map = {row.id: row.keyword for row in keyword_rows}

            # Preserve original order of keyword_ids when attaching terms
            base_body["keywords"] = [
                {
                    "id": keyword_id,
                    "keyword": keyword_map.get(keyword_id)
                }
                for keyword_id in keyword_ids
            ]
        except Exception as e:
            logger.warning("Failed to enrich message body with keyword terms: %s", str(e))

        return base_body

    def purge_queue(self) -> bool:
        if not self.sqs_client or not self.job_queue_url:
            return False

        try:
            self.sqs_client.purge_queue(QueueUrl=self.job_queue_url)
            logger.info(f"Purged queue: {self.job_queue_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to purge queue: {str(e)}")
            return False
