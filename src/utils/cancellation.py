"""Job cancellation utility for checking if a job has been cancelled"""
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class JobCancelledException(Exception):
    """Exception raised when a job has been cancelled"""
    def __init__(self, job_id: str, message: str = None):
        self.job_id = job_id
        self.message = message or f"Job {job_id} was cancelled"
        super().__init__(self.message)


def is_job_cancelled(job_id: str, db: Session) -> bool:
    """
    Check if a job has been cancelled by looking up the sqs_message_history table.
    
    Args:
        job_id: The job ID to check
        db: Database session
        
    Returns:
        True if the job is cancelled, False otherwise
    """
    from src.repositories.sqs_message_history import SQSMessageHistoryRepository
    from src.models.sqs_message_history import MessageStatus
    
    try:
        repo = SQSMessageHistoryRepository(db)
        record = repo.get_by_job_id(job_id)
        
        if record and record.status == MessageStatus.CANCELLED:
            logger.info(f"Job {job_id} has been cancelled")
            return True
        return False
    except Exception as e:
        logger.warning(f"Error checking job cancellation status: {e}")
        return False


def check_cancellation_and_raise(job_id: str, db: Session) -> None:
    """
    Check if a job is cancelled and raise JobCancelledException if so.
    
    Args:
        job_id: The job ID to check
        db: Database session
        
    Raises:
        JobCancelledException: If the job has been cancelled
    """
    if is_job_cancelled(job_id, db):
        raise JobCancelledException(job_id)
