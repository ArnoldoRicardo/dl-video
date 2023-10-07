import logging

from pymongo import MongoClient

from src.config import settings
from src.schemas import ChatModel, UserModel

connection_string = f"mongodb://{settings.MONGO_INITDB_ROOT_USERNAME}:{settings.MONGO_INITDB_ROOT_PASSWORD}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"  # noqa


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

db = client['dl-video-bot']
users_collection = db['users']
chats_collection = db['chats']


def create_or_update_user(user: UserModel):
    users_collection.update_one({"id": user.id}, {"$set": user.dict()}, upsert=True)


def delete_user_by_id(user_id: int):
    users_collection.delete_one({"id": user_id})


def find_user_by_id(user_id: int):
    return users_collection.find_one({"id": user_id})


def create_or_update_chat(chat: ChatModel):
    chats_collection.update_one({"id": chat.id}, {"$set": chat.dict()}, upsert=True)


def find_chat_by_id(chat_id: int):
    return chats_collection.find_one({"id": chat_id})


def delete_chat_by_id(chat_id: int):
    chats_collection.delete_one({"id": chat_id})
