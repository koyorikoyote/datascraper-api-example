import os
from dotenv import load_dotenv
load_dotenv()

def get_database_url():
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
    
    if not MYSQL_USER or not MYSQL_PASSWORD or not MYSQL_HOST or not MYSQL_DATABASE:
        raise ValueError("Missing required database environment variables")

    return f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

def get_env(key: str, default: str = None, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

class Settings:
    def __init__(self):
        self._cache = {}

    def get(self, key: str, default: str = None) -> str:
        if key not in self._cache:
            self._cache[key] = os.getenv(key, default)
        return self._cache[key]

settings = Settings()