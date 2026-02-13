from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserInfo(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    tier: str = "free"
    downloads_today: int = 0
    daily_limit: int = 3
    subscription_expires: Optional[datetime] = None
