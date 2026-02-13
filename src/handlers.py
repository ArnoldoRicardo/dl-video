import asyncio
import logging
import os
import re
import time
import tempfile

from telegram import LabeledPrice, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from yt_dlp.utils import DownloadError, ExtractorError

from src.config import settings
from src.db import (
    async_session,
    count_downloads_today,
    create_subscription,
    delete_download,
    get_active_subscription,
    get_or_create_user,
    has_active_subscription,
    record_download,
    reserve_download,
)
from src.downloader import FileTooLargeError, download_video as dl_video

logger = logging.getLogger(__name__)

TWITTER_URL_PATTERN = re.compile(
    r"https?:\/\/(?:www\.)?(twitter|x|fxtwitter|vxtwitter)\.com\/\w+\/status\/(\d+)"
)

# Fix 7: Global semaphore — limits total concurrent downloads
_download_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)

# Fix 6: Per-user locks — one download at a time per user
# Use OrderedDict to auto-evict old entries and prevent memory leak
_user_locks: dict[int, asyncio.Lock] = {}
_MAX_USER_LOCKS = 1000


def _get_user_lock(user_id: int) -> asyncio.Lock:
    """Get or create a per-user lock. Evicts old entries if over limit."""
    if user_id not in _user_locks:
        # Evict oldest unlocked entries if we're over the limit
        if len(_user_locks) >= _MAX_USER_LOCKS:
            to_remove = [
                uid for uid, lock in _user_locks.items() if not lock.locked()
            ]
            for uid in to_remove[:len(to_remove) // 2]:
                del _user_locks[uid]
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and register the user."""
    tg_user = update.effective_user

    async with async_session() as session:
        await get_or_create_user(
            session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            is_bot=tg_user.is_bot,
            language_code=tg_user.language_code,
        )

    await update.message.reply_text(
        f"Hola {tg_user.first_name}!\n\n"
        f"Enviane un link de Twitter/X y te descargo el video.\n\n"
        f"Usa /status para ver tu cuenta o /subscribe para ser premium."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "/start - Iniciar el bot\n"
        "/help - Mostrar este mensaje de ayuda\n"
        "/status - Ver tu plan y descargas restantes\n"
        "/subscribe - Obtener plan premium\n\n"
        "Para descargar un video, pega el link del tweet."
    )
    await update.message.reply_text(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user their current plan status."""
    tg_user = update.effective_user

    async with async_session() as session:
        user = await get_or_create_user(
            session, telegram_id=tg_user.id, username=tg_user.username
        )
        downloads_today = await count_downloads_today(session, user.id)
        subscription = await get_active_subscription(session, user.id)

    if subscription:
        expires = subscription.expires_at.strftime("%d/%m/%Y")
        await update.message.reply_text(
            f"Plan: Premium\n"
            f"Descargas hoy: {downloads_today}\n"
            f"Limite diario: Ilimitado\n"
            f"Expira: {expires}"
        )
    else:
        remaining = max(0, settings.FREE_DAILY_LIMIT - downloads_today)
        await update.message.reply_text(
            f"Plan: Gratis\n"
            f"Descargas hoy: {downloads_today}/{settings.FREE_DAILY_LIMIT}\n"
            f"Restantes: {remaining}\n\n"
            f"Usa /subscribe para descargas ilimitadas."
        )


async def subscribe_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Send a Telegram Stars invoice for premium subscription."""
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Premium - Descargas Ilimitadas",
        description=(
            f"Plan premium por {settings.PREMIUM_DURATION_DAYS} dias.\n"
            f"Descarga videos de Twitter/X sin limite diario."
        ),
        payload=f"premium_{update.effective_user.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("Premium", settings.PREMIUM_PRICE_STARS)],
    )


async def pre_checkout_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Validate the payment before processing."""
    query = update.pre_checkout_query

    # Validate payload format and user match
    if not query.invoice_payload.startswith("premium_"):
        await query.answer(ok=False, error_message="Payload de pago invalido.")
        return

    try:
        payload_user_id = int(query.invoice_payload.split("_", 1)[1])
        if payload_user_id != query.from_user.id:
            await query.answer(ok=False, error_message="Pago no coincide con usuario.")
            return
    except (ValueError, IndexError):
        await query.answer(ok=False, error_message="Payload de pago invalido.")
        return

    await query.answer(ok=True)


async def successful_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle successful payment — activate premium subscription."""
    payment = update.message.successful_payment
    tg_user = update.effective_user

    async with async_session() as session:
        user = await get_or_create_user(
            session, telegram_id=tg_user.id, username=tg_user.username
        )
        subscription = await create_subscription(
            session,
            user_id=user.id,
            stars_paid=payment.total_amount,
            telegram_charge_id=payment.telegram_payment_charge_id,
            duration_days=settings.PREMIUM_DURATION_DAYS,
        )

    expires = subscription.expires_at.strftime("%d/%m/%Y")
    await update.message.reply_text(
        f"Pago recibido! Gracias por {payment.total_amount} Stars.\n\n"
        f"Tu plan Premium esta activo hasta el {expires}.\n"
        f"Disfruta de descargas ilimitadas!"
    )
    logger.info(
        f"Payment OK: user_id={tg_user.id} stars={payment.total_amount} "
        f"charge_id={payment.telegram_payment_charge_id}"
    )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download a video from Twitter/X."""
    message_text = update.message.text
    tg_user = update.effective_user

    match = TWITTER_URL_PATTERN.search(message_text)
    if not match:
        await update.message.reply_text("No es un link de Twitter/X valido.")
        return

    # Normalize URL to x.com (yt-dlp handles both)
    _, tweet_id = match.groups()
    tweet_url = f"https://x.com/i/status/{tweet_id}"

    # Fix 6: Per-user lock — only 1 download at a time per user
    user_lock = _get_user_lock(tg_user.id)
    if user_lock.locked():
        await update.message.reply_text(
            "Ya tienes una descarga en curso. Espera a que termine."
        )
        return

    async with user_lock:
        await _process_download(update, context, tg_user, tweet_url, tweet_id)


async def _process_download(update, context, tg_user, tweet_url, tweet_id):
    """Internal: handle the full download pipeline."""
    start_time = time.monotonic()

    # Get user and check limits
    async with async_session() as session:
        user = await get_or_create_user(
            session, telegram_id=tg_user.id, username=tg_user.username
        )
        is_premium = await has_active_subscription(session, user.id)

    # Fix 2: Reserve download slot BEFORE downloading (atomic check+insert)
    download_record = None
    if not is_premium:
        async with async_session() as session:
            download_record = await reserve_download(
                session, user.id, tweet_url, settings.FREE_DAILY_LIMIT
            )
            if download_record is None:
                await update.message.reply_text(
                    f"Alcanzaste tu limite de {settings.FREE_DAILY_LIMIT} "
                    f"descargas diarias.\n\n"
                    f"Usa /subscribe para obtener descargas ilimitadas "
                    f"por {settings.PREMIUM_PRICE_STARS} Stars/mes."
                )
                return

    # Fix 3: Unique filename using tempfile
    tmp_dir = tempfile.gettempdir()
    filename = os.path.join(tmp_dir, f"video_{tweet_id}_{tg_user.id}.mp4")

    # Fix 8: Feedback — show typing/uploading action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO
    )
    status_msg = await update.message.reply_text("Descargando video...")

    try:
        # Fix 1 + 7: Non-blocking download with global semaphore
        async with _download_semaphore:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, dl_video, tweet_url, filename)

    except FileTooLargeError as e:
        logger.warning(
            f"File too large: user_id={tg_user.id} tweet={tweet_id} "
            f"size={e.file_size / 1024 / 1024:.1f}MB"
        )
        await status_msg.edit_text(
            f"El video es demasiado grande "
            f"({e.file_size / 1024 / 1024:.0f}MB). "
            f"Telegram solo permite hasta 50MB."
        )
        # Rollback download reservation for free users
        if download_record:
            async with async_session() as session:
                await delete_download(session, download_record.id)
        return

    except (DownloadError, ExtractorError) as e:
        logger.error(f"Download error: user_id={tg_user.id} tweet={tweet_id} err={e}")
        await status_msg.edit_text(
            "Error descargando el video. Verifica que el tweet tiene un video."
        )
        if download_record:
            async with async_session() as session:
                await delete_download(session, download_record.id)
        return

    except Exception as e:
        logger.error(
            f"Unexpected error: user_id={tg_user.id} tweet={tweet_id} err={e}"
        )
        await status_msg.edit_text("Error inesperado descargando el video.")
        if download_record:
            async with async_session() as session:
                await delete_download(session, download_record.id)
        return

    # Send the video to the user
    try:
        file_size = os.path.getsize(filename)
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO
        )
        with open(filename, "rb") as video_file:
            await context.bot.send_video(
                chat_id=update.message.chat_id, video=video_file
            )
        await status_msg.delete()

        # Fix 9: Structured logging
        elapsed = time.monotonic() - start_time
        logger.info(
            f"Download OK: user_id={tg_user.id} tweet={tweet_id} "
            f"size={file_size / 1024 / 1024:.1f}MB time={elapsed:.1f}s "
            f"premium={is_premium}"
        )

    except Exception as e:
        logger.error(f"Send error: user_id={tg_user.id} tweet={tweet_id} err={e}")
        await status_msg.edit_text(
            "Error enviando el video. Puede ser demasiado grande para Telegram."
        )
        # Rollback for free users on send failure
        if download_record:
            async with async_session() as session:
                await delete_download(session, download_record.id)

    finally:
        # Always clean up the file
        if os.path.exists(filename):
            os.remove(filename)

    # Record download for premium users (free users already reserved above)
    if is_premium:
        try:
            async with async_session() as session:
                await record_download(session, user.id, tweet_url)
        except Exception as e:
            logger.error(f"Failed to record download: user_id={tg_user.id} err={e}")
