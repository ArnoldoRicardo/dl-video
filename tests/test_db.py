from datetime import datetime, timedelta

import pytest

from src.db import (
    count_downloads_today,
    create_subscription,
    delete_download,
    get_active_subscription,
    get_or_create_user,
    has_active_subscription,
    record_download,
    reserve_download,
)
from src.models import Download, Subscription


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new_user(db_session):
    user = await get_or_create_user(
        db_session,
        telegram_id=1001,
        username="new_user",
        full_name="New User",
    )

    assert user.id is not None
    assert user.telegram_id == 1001
    assert user.username == "new_user"
    assert user.full_name == "New User"


@pytest.mark.asyncio
async def test_get_or_create_user_updates_existing_user(db_session):
    first = await get_or_create_user(db_session, telegram_id=1002, username="old_name")
    second = await get_or_create_user(
        db_session,
        telegram_id=1002,
        username="new_name",
        full_name="Updated Name",
        language_code="en",
    )

    assert first.id == second.id
    assert second.username == "new_name"
    assert second.full_name == "Updated Name"
    assert second.language_code == "en"


@pytest.mark.asyncio
async def test_count_downloads_today_returns_zero_without_downloads(db_session):
    user = await get_or_create_user(db_session, telegram_id=1003, username="u3")

    count = await count_downloads_today(db_session, user.id)

    assert count == 0


@pytest.mark.asyncio
async def test_count_downloads_today_counts_only_today(db_session):
    user = await get_or_create_user(db_session, telegram_id=1004, username="u4")
    today_download = Download(user_id=user.id, tweet_url="https://x.com/i/status/1")
    yesterday_download = Download(
        user_id=user.id,
        tweet_url="https://x.com/i/status/2",
        created_at=datetime.now() - timedelta(days=1),
    )
    db_session.add(today_download)
    db_session.add(yesterday_download)
    await db_session.commit()

    count = await count_downloads_today(db_session, user.id)

    assert count == 1


@pytest.mark.asyncio
async def test_reserve_download_creates_record_when_under_limit(db_session):
    user = await get_or_create_user(db_session, telegram_id=1005, username="u5")

    download = await reserve_download(db_session, user.id, "https://x.com/i/status/10", 3)

    assert download is not None
    assert download.user_id == user.id


@pytest.mark.asyncio
async def test_reserve_download_returns_none_when_limit_reached(db_session):
    user = await get_or_create_user(db_session, telegram_id=1006, username="u6")
    for i in range(3):
        db_session.add(Download(user_id=user.id, tweet_url=f"https://x.com/i/status/{i}"))
    await db_session.commit()

    download = await reserve_download(db_session, user.id, "https://x.com/i/status/99", 3)

    assert download is None


@pytest.mark.asyncio
async def test_reserve_download_respects_limit_across_multiple_calls(db_session):
    user = await get_or_create_user(db_session, telegram_id=1007, username="u7")

    first = await reserve_download(db_session, user.id, "https://x.com/i/status/11", 2)
    second = await reserve_download(db_session, user.id, "https://x.com/i/status/12", 2)
    third = await reserve_download(db_session, user.id, "https://x.com/i/status/13", 2)

    assert first is not None
    assert second is not None
    assert third is None


@pytest.mark.asyncio
async def test_delete_download_removes_existing_record(db_session):
    user = await get_or_create_user(db_session, telegram_id=1008, username="u8")
    download = await record_download(db_session, user.id, "https://x.com/i/status/20")

    await delete_download(db_session, download.id)

    count = await count_downloads_today(db_session, user.id)
    assert count == 0


@pytest.mark.asyncio
async def test_delete_download_ignores_missing_id(db_session):
    await delete_download(db_session, 999999)


@pytest.mark.asyncio
async def test_has_active_subscription_false_without_subscription(db_session):
    user = await get_or_create_user(db_session, telegram_id=1009, username="u9")

    assert await has_active_subscription(db_session, user.id) is False


@pytest.mark.asyncio
async def test_has_active_subscription_true_with_active_subscription(db_session):
    user = await get_or_create_user(db_session, telegram_id=1010, username="u10")
    await create_subscription(
        db_session,
        user_id=user.id,
        stars_paid=250,
        telegram_charge_id="charge-1",
        duration_days=30,
    )

    assert await has_active_subscription(db_session, user.id) is True


@pytest.mark.asyncio
async def test_has_active_subscription_false_with_expired_subscription(db_session):
    user = await get_or_create_user(db_session, telegram_id=1011, username="u11")
    expired = Subscription(
        user_id=user.id,
        starts_at=datetime.now() - timedelta(days=10),
        expires_at=datetime.now() - timedelta(days=1),
        stars_paid=250,
        telegram_charge_id="expired-charge",
    )
    db_session.add(expired)
    await db_session.commit()

    assert await has_active_subscription(db_session, user.id) is False


@pytest.mark.asyncio
async def test_get_active_subscription_returns_latest_active(db_session):
    user = await get_or_create_user(db_session, telegram_id=1012, username="u12")
    older = Subscription(
        user_id=user.id,
        starts_at=datetime.now() - timedelta(days=5),
        expires_at=datetime.now() + timedelta(days=2),
        stars_paid=250,
        telegram_charge_id="older",
    )
    newer = Subscription(
        user_id=user.id,
        starts_at=datetime.now() - timedelta(days=1),
        expires_at=datetime.now() + timedelta(days=5),
        stars_paid=250,
        telegram_charge_id="newer",
    )
    db_session.add(older)
    db_session.add(newer)
    await db_session.commit()

    active = await get_active_subscription(db_session, user.id)

    assert active is not None
    assert active.telegram_charge_id == "newer"


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_when_all_expired(db_session):
    user = await get_or_create_user(db_session, telegram_id=1013, username="u13")
    expired = Subscription(
        user_id=user.id,
        starts_at=datetime.now() - timedelta(days=10),
        expires_at=datetime.now() - timedelta(days=2),
        stars_paid=250,
        telegram_charge_id="old",
    )
    db_session.add(expired)
    await db_session.commit()

    active = await get_active_subscription(db_session, user.id)

    assert active is None


@pytest.mark.asyncio
async def test_create_subscription_sets_expected_fields(db_session):
    user = await get_or_create_user(db_session, telegram_id=1014, username="u14")

    subscription = await create_subscription(
        db_session,
        user_id=user.id,
        stars_paid=300,
        telegram_charge_id="charge-xyz",
        duration_days=15,
    )

    assert subscription.user_id == user.id
    assert subscription.stars_paid == 300
    assert subscription.telegram_charge_id == "charge-xyz"
    assert subscription.expires_at > subscription.starts_at


@pytest.mark.asyncio
async def test_record_download_creates_download(db_session):
    user = await get_or_create_user(db_session, telegram_id=1015, username="u15")

    download = await record_download(db_session, user.id, "https://x.com/i/status/999")

    assert download.id is not None
    assert download.user_id == user.id
    assert download.tweet_url == "https://x.com/i/status/999"
