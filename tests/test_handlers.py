import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from yt_dlp.utils import DownloadError

import src.handlers as handlers
from src.downloader import FileTooLargeError


@pytest.fixture(autouse=True)
def clear_user_locks():
    handlers._user_locks.clear()


@pytest.fixture
def patch_async_session(monkeypatch):
    fake_session = SimpleNamespace()

    @asynccontextmanager
    async def _session_cm():
        yield fake_session

    monkeypatch.setattr(handlers, "async_session", _session_cm)
    return fake_session


@pytest.mark.asyncio
async def test_start_registers_user_and_replies(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(text="/start")
    context = mock_context_factory()
    get_or_create = AsyncMock()
    monkeypatch.setattr(handlers, "get_or_create_user", get_or_create)

    await handlers.start(update, context)

    assert get_or_create.await_count == 1
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_command_replies_with_help_text(mock_update_factory, mock_context_factory):
    update = mock_update_factory(text="/help")
    context = mock_context_factory()

    await handlers.help_command(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "/start" in text
    assert "/subscribe" in text


@pytest.mark.asyncio
async def test_status_command_free_user(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(text="/status")
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=10)))
    monkeypatch.setattr(handlers, "count_downloads_today", AsyncMock(return_value=1))
    monkeypatch.setattr(handlers, "get_active_subscription", AsyncMock(return_value=None))

    await handlers.status_command(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "Plan: Gratis" in text
    assert "Restantes: 2" in text


@pytest.mark.asyncio
async def test_status_command_premium_user(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(text="/status")
    context = mock_context_factory()
    sub = SimpleNamespace(expires_at=datetime.now() + timedelta(days=3))
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=10)))
    monkeypatch.setattr(handlers, "count_downloads_today", AsyncMock(return_value=7))
    monkeypatch.setattr(handlers, "get_active_subscription", AsyncMock(return_value=sub))

    await handlers.status_command(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "Plan: Premium" in text
    assert "Ilimitado" in text


@pytest.mark.asyncio
async def test_subscribe_command_sends_invoice(mock_update_factory, mock_context_factory):
    update = mock_update_factory(text="/subscribe", user_id=555, chat_id=777)
    context = mock_context_factory()

    await handlers.subscribe_command(update, context)

    context.bot.send_invoice.assert_awaited_once()
    kwargs = context.bot.send_invoice.await_args.kwargs
    assert kwargs["chat_id"] == 777
    assert kwargs["payload"] == "premium_555"
    assert kwargs["currency"] == "XTR"
    assert kwargs["prices"][0].amount == handlers.settings.PREMIUM_PRICE_STARS


@pytest.mark.asyncio
async def test_pre_checkout_handler_accepts_valid_payload(mock_context_factory):
    query = SimpleNamespace(
        invoice_payload="premium_111",
        from_user=SimpleNamespace(id=111),
        answer=AsyncMock(),
    )
    update = SimpleNamespace(pre_checkout_query=query)
    context = mock_context_factory()

    await handlers.pre_checkout_handler(update, context)

    query.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
async def test_pre_checkout_handler_rejects_user_mismatch(mock_context_factory):
    query = SimpleNamespace(
        invoice_payload="premium_111",
        from_user=SimpleNamespace(id=222),
        answer=AsyncMock(),
    )
    update = SimpleNamespace(pre_checkout_query=query)
    context = mock_context_factory()

    await handlers.pre_checkout_handler(update, context)

    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs["ok"] is False


@pytest.mark.asyncio
async def test_pre_checkout_handler_rejects_bad_payload(mock_context_factory):
    query = SimpleNamespace(
        invoice_payload="bad_payload",
        from_user=SimpleNamespace(id=111),
        answer=AsyncMock(),
    )
    update = SimpleNamespace(pre_checkout_query=query)
    context = mock_context_factory()

    await handlers.pre_checkout_handler(update, context)

    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs["ok"] is False


@pytest.mark.asyncio
async def test_successful_payment_handler_creates_subscription_and_replies(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(text="paid", user_id=101)
    update.message.successful_payment = SimpleNamespace(
        total_amount=250,
        telegram_payment_charge_id="charge123",
    )
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=10)))
    monkeypatch.setattr(
        handlers,
        "create_subscription",
        AsyncMock(return_value=SimpleNamespace(expires_at=datetime.now() + timedelta(days=30))),
    )

    await handlers.successful_payment_handler(update, context)

    handlers.create_subscription.assert_awaited_once()
    text = update.message.reply_text.await_args.args[0]
    assert "Pago recibido" in text
    assert "Premium" in text


@pytest.mark.asyncio
async def test_download_video_rejects_invalid_url(mock_update_factory, mock_context_factory):
    update = mock_update_factory(text="hola")
    context = mock_context_factory()

    await handlers.download_video(update, context)

    update.message.reply_text.assert_awaited_once_with("No es un link de Twitter/X valido.")


@pytest.mark.asyncio
async def test_download_video_normalizes_url_and_calls_process(
    monkeypatch, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(text="https://twitter.com/someone/status/123456")
    context = mock_context_factory()
    process = AsyncMock()
    monkeypatch.setattr(handlers, "_process_download", process)

    await handlers.download_video(update, context)

    process.assert_awaited_once()
    args = process.await_args.args
    assert args[3] == "https://x.com/i/status/123456"
    assert args[4] == "123456"


@pytest.mark.asyncio
async def test_download_video_blocks_if_user_already_downloading(
    monkeypatch, mock_update_factory, mock_context_factory
):
    update1 = mock_update_factory(user_id=808, text="https://x.com/a/status/1")
    update2 = mock_update_factory(user_id=808, text="https://x.com/a/status/2")
    context = mock_context_factory()
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_process(*_args, **_kwargs):
        started.set()
        await release.wait()

    monkeypatch.setattr(handlers, "_process_download", fake_process)

    first = asyncio.create_task(handlers.download_video(update1, context))
    await started.wait()
    await handlers.download_video(update2, context)
    release.set()
    await first

    update2.message.reply_text.assert_awaited_once_with(
        "Ya tienes una descarga en curso. Espera a que termine."
    )


@pytest.mark.asyncio
async def test_process_download_free_user_limit_reached(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(user_id=901)
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=42)))
    monkeypatch.setattr(handlers, "has_active_subscription", AsyncMock(return_value=False))
    monkeypatch.setattr(handlers, "reserve_download", AsyncMock(return_value=None))

    await handlers._process_download(update, context, update.effective_user, "https://x.com/i/status/1", "1")

    text = update.message.reply_text.await_args.args[0]
    assert "Alcanzaste tu limite" in text


@pytest.mark.asyncio
async def test_process_download_free_user_success(
    monkeypatch, tmp_path, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(user_id=902)
    status_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    update.message.reply_text = AsyncMock(return_value=status_msg)
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=43)))
    monkeypatch.setattr(handlers, "has_active_subscription", AsyncMock(return_value=False))
    monkeypatch.setattr(
        handlers, "reserve_download", AsyncMock(return_value=SimpleNamespace(id=777))
    )
    monkeypatch.setattr(handlers, "delete_download", AsyncMock())
    monkeypatch.setattr(handlers, "record_download", AsyncMock())
    monkeypatch.setattr(handlers.tempfile, "gettempdir", lambda: str(tmp_path))

    def fake_dl(_url, filename):
        with open(filename, "wb") as fp:
            fp.write(b"video")

    monkeypatch.setattr(handlers, "dl_video", fake_dl)

    await handlers._process_download(update, context, update.effective_user, "https://x.com/i/status/2", "2")

    context.bot.send_video.assert_awaited_once()
    status_msg.delete.assert_awaited_once()
    handlers.delete_download.assert_not_awaited()
    handlers.record_download.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_download_rolls_back_on_download_error(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(user_id=903)
    status_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    update.message.reply_text = AsyncMock(return_value=status_msg)
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=44)))
    monkeypatch.setattr(handlers, "has_active_subscription", AsyncMock(return_value=False))
    monkeypatch.setattr(
        handlers, "reserve_download", AsyncMock(return_value=SimpleNamespace(id=778))
    )
    monkeypatch.setattr(handlers, "delete_download", AsyncMock())

    def fake_dl(_url, _filename):
        raise DownloadError("boom")

    monkeypatch.setattr(handlers, "dl_video", fake_dl)

    await handlers._process_download(update, context, update.effective_user, "https://x.com/i/status/3", "3")

    handlers.delete_download.assert_awaited_once()
    status_msg.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_download_rolls_back_on_file_too_large(
    monkeypatch, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(user_id=904)
    status_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    update.message.reply_text = AsyncMock(return_value=status_msg)
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=45)))
    monkeypatch.setattr(handlers, "has_active_subscription", AsyncMock(return_value=False))
    monkeypatch.setattr(
        handlers, "reserve_download", AsyncMock(return_value=SimpleNamespace(id=779))
    )
    monkeypatch.setattr(handlers, "delete_download", AsyncMock())

    def fake_dl(_url, _filename):
        raise FileTooLargeError(60 * 1024 * 1024)

    monkeypatch.setattr(handlers, "dl_video", fake_dl)

    await handlers._process_download(update, context, update.effective_user, "https://x.com/i/status/4", "4")

    handlers.delete_download.assert_awaited_once()
    status_msg.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_download_premium_records_download(
    monkeypatch, tmp_path, patch_async_session, mock_update_factory, mock_context_factory
):
    update = mock_update_factory(user_id=905)
    status_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    update.message.reply_text = AsyncMock(return_value=status_msg)
    context = mock_context_factory()
    monkeypatch.setattr(handlers, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=46)))
    monkeypatch.setattr(handlers, "has_active_subscription", AsyncMock(return_value=True))
    monkeypatch.setattr(handlers, "reserve_download", AsyncMock())
    monkeypatch.setattr(handlers, "record_download", AsyncMock())
    monkeypatch.setattr(handlers.tempfile, "gettempdir", lambda: str(tmp_path))

    def fake_dl(_url, filename):
        with open(filename, "wb") as fp:
            fp.write(b"video")

    monkeypatch.setattr(handlers, "dl_video", fake_dl)

    await handlers._process_download(update, context, update.effective_user, "https://x.com/i/status/5", "5")

    handlers.reserve_download.assert_not_awaited()
    handlers.record_download.assert_awaited_once()
