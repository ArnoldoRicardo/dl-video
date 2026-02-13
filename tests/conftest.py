from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.models import Base


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_update_factory():
    def _make_update(
        user_id=123,
        chat_id=123,
        username="tester",
        first_name="Test",
        full_name="Test User",
        text="",
    ):
        user = SimpleNamespace(
            id=user_id,
            username=username,
            first_name=first_name,
            full_name=full_name,
            is_bot=False,
            language_code="es",
        )
        chat = SimpleNamespace(id=chat_id)
        message = MagicMock()
        message.text = text
        message.chat_id = chat_id
        message.reply_text = AsyncMock()

        return SimpleNamespace(
            effective_user=user,
            effective_chat=chat,
            message=message,
            pre_checkout_query=None,
        )

    return _make_update


@pytest.fixture
def mock_context_factory():
    def _make_context():
        bot = SimpleNamespace(
            send_invoice=AsyncMock(),
            send_chat_action=AsyncMock(),
            send_video=AsyncMock(),
        )
        return SimpleNamespace(bot=bot)

    return _make_context
