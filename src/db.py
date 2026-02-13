import logging
from datetime import date, datetime, timedelta

from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.models import Base, Download, Subscription, User

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode for better concurrent read performance."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
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
        # Update fields if they changed
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

    # Update user tier
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one()
    user.tier = "premium"

    await session.commit()
    await session.refresh(subscription)
    logger.info(f"Created subscription for user {user_id}: {subscription}")
    return subscription


async def record_download(
    session: AsyncSession, user_id: int, tweet_url: str
) -> Download:
    """Record a video download."""
    download = Download(user_id=user_id, tweet_url=tweet_url)
    session.add(download)
    await session.commit()
    await session.refresh(download)
    return download
