from pydantic import BaseModel


class UserModel(BaseModel):
    id: int
    full_name: str
    username: str
    is_bot: bool
    language_code: str


class ChatModel(BaseModel):
    id: int
    type: str
    title: str
    user_id: int
