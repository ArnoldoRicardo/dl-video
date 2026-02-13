import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.models import Base, Download, Subscription, User

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


async def init_db():
    """Create all tables and configure SQLite pragmas."""
    # Ensure database directory exists
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    full_name: str | None = None,
    is_bot: bool = False,
    language_code: str | None = None,
) -> User:
    """Get an existing user or create a new one."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            is_bot=is_bot,
            language_code=language_code,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Created new user: {user}")
    else:
        user.username = username
        user.full_name = full_name
        user.language_code = language_code
        await session.commit()

    return user


async def count_downloads_today(session: AsyncSession, user_id: int) -> int:
    """Count how many downloads a user has made today."""
    today = date.today()
    stmt = select(func.count(Download.id)).where(
        Download.user_id == user_id,
        func.date(Download.created_at) == today,
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def reserve_download(
    session: AsyncSession, user_id: int, tweet_url: str, daily_limit: int
) -> Download | None:
    """Atomically check the daily limit and record a download.

    Returns the Download record if the user is within limits, or None
    if the daily limit has been reached.  This prevents race conditions
    where concurrent requests all pass the limit check.
    """
    today = date.today()
    stmt = select(func.count(Download.id)).where(
        Download.user_id == user_id,
        func.date(Download.created_at) == today,
    )
    result = await session.execute(stmt)
    count = result.scalar() or 0

    if count >= daily_limit:
        return None

    download = Download(user_id=user_id, tweet_url=tweet_url)
    session.add(download)
    await session.commit()
    await session.refresh(download)
    return download


async def delete_download(session: AsyncSession, download_id: int) -> None:
    """Delete a download record (used when download fails after reservation)."""
    stmt = select(Download).where(Download.id == download_id)
    result = await session.execute(stmt)
    download = result.scalar_one_or_none()
    if download:
        await session.delete(download)
        await session.commit()


async def has_active_subscription(session: AsyncSession, user_id: int) -> bool:
    """Check if a user has an active (non-expired) subscription."""
    now = datetime.now()
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.expires_at > now,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_active_subscription(
    session: AsyncSession, user_id: int
) -> Subscription | None:
    """Get the active subscription for a user, if any."""
    now = datetime.now()
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_subscription(
    session: AsyncSession,
    user_id: int,
    stars_paid: int,
    telegram_charge_id: str,
    duration_days: int = 30,
) -> Subscription:
    """Create a new subscription for a user."""
    now = datetime.now()
    subscription = Subscription(
        user_id=user_id,
        starts_at=now,
        expires_at=now + timedelta(days=duration_days),
        stars_paid=stars_paid,
        telegram_charge_id=telegram_charge_id,
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    logger.info(f"Created subscription for user {user_id}: {subscription}")
    return subscription


async def record_download(
    session: AsyncSession, user_id: int, tweet_url: str
) -> Download:
    """Record a video download (for premium users who skip reservation)."""
    download = Download(user_id=user_id, tweet_url=tweet_url)
    session.add(download)
    await session.commit()
    await session.refresh(download)
    return download
