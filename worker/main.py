#!/usr/bin/env python3
"""
Main entry point for the unified SQS worker that handles all job types
"""
import logging
import sys
import os

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker.consumer import SQSConsumer
from worker.config import config


def setup_logging():
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce boto3 logging noise
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting Unified SQS Worker Service")
        logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.info(f"Queue URL: {config.SQS_JOB_QUEUE_URL}")
        logger.info("This worker handles all job types: fetch, partial_rank, and full_rank")

        # Validate configuration
        config.validate()

        # Start the consumer for the unified queue
        consumer = SQSConsumer()
        consumer.start()

    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()