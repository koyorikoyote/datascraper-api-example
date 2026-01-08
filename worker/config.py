import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory (where main app's .env is)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class WorkerConfig:
    # Database Configuration
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

    # AWS SQS Configuration
    AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    # Single unified queue for all job types
    SQS_JOB_QUEUE_URL = os.getenv("SQS_JOB_QUEUE_URL")
    SQS_JOB_DLQ_URL = os.getenv("SQS_JOB_DLQ_URL")

    # Worker Configuration
    WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "20"))  # Long polling wait time
    WORKER_VISIBILITY_TIMEOUT = int(os.getenv("WORKER_VISIBILITY_TIMEOUT", "900"))  # 15 minutes
    WORKER_MAX_MESSAGES = int(os.getenv("WORKER_MAX_MESSAGES", "1"))
    WORKER_SHUTDOWN_GRACE_PERIOD = int(os.getenv("WORKER_SHUTDOWN_GRACE_PERIOD", "30"))

    # Selenium Configuration
    SELENIUM_GRID_URL = os.getenv("SELENIUM_GRID_URL", "http://localhost:4444/wd/hub")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self):
        return (
            f"mysql+mysqlconnector://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@"
            f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    def validate(self):
        required_vars = [
            ("MYSQL_USER", self.MYSQL_USER),
            ("MYSQL_PASSWORD", self.MYSQL_PASSWORD),
            ("MYSQL_DATABASE", self.MYSQL_DATABASE),
            ("SQS_JOB_QUEUE_URL", self.SQS_JOB_QUEUE_URL),
        ]

        missing = [var[0] for var in required_vars if not var[1]]

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


config = WorkerConfig()