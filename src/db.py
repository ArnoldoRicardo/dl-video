from pymongo import MongoClient
from src.config import settings
import os
import logging

connection_string = f"mongodb://{settings.MONGO_INITDB_ROOT_USERNAME}:{settings.MONGO_INITDB_ROOT_PASSWORD}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


try:
    client = MongoClient(connection_string)
except Exception as e:
    logger.error(e)
    raise e

def get_database(name: str) -> MongoClient:
    return client[name]
