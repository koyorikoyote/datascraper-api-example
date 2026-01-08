"""
Visibility timeout extender for long-running jobs
This module helps prevent message timeout for jobs that take longer than 15 minutes
"""

import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class VisibilityExtender:
    """
    Automatically extends message visibility timeout while job is processing.
    Prevents messages from becoming visible again during long-running jobs.
    """

    def __init__(self, sqs_client, queue_url: str, receipt_handle: str, message_id: str):
        self.sqs_client = sqs_client
        self.queue_url = queue_url
        self.receipt_handle = receipt_handle
        self.message_id = message_id
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.extension_interval = 600  # Extend every 10 minutes
        self.extension_timeout = 900   # Extend by 15 minutes each time

    def start(self):
        """Start the visibility extender thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._extend_loop, daemon=True)
        self.thread.start()
        logger.info(f"Started visibility extender for message {self.message_id}")

    def stop(self):
        """Stop the visibility extender thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"Stopped visibility extender for message {self.message_id}")

    def _extend_loop(self):
        """Main loop that extends visibility periodically"""
        while self.running:
            try:
                # Wait for the interval (10 minutes)
                for _ in range(self.extension_interval):
                    if not self.running:
                        break
                    time.sleep(1)

                if not self.running:
                    break

                # Extend the visibility
                self.sqs_client.change_message_visibility(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=self.receipt_handle,
                    VisibilityTimeout=self.extension_timeout
                )

                logger.info(
                    f"Extended visibility timeout for message {self.message_id} "
                    f"by {self.extension_timeout} seconds"
                )

            except Exception as e:
                logger.error(
                    f"Failed to extend visibility for message {self.message_id}: {str(e)}"
                )
                # Continue trying even if one extension fails