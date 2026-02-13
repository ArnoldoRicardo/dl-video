import logging
import os
import re

from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes
from yt_dlp.utils import DownloadError, ExtractorError

from src.config import settings
from src.db import (
    async_session,
    count_downloads_today,
    create_subscription,
    get_active_subscription,
    get_or_create_user,
    has_active_subscription,
    record_download,
)
from src.downloader import download_video as dl_video

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

TWITTER_URL_PATTERN = re.compile(
    r"https:\/\/(twitter|x)\.com\/\w+\/status\/(\d+)"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and register the user."""
    tg_user = update.effective_user

    async with async_session() as session:
        user = await get_or_create_user(
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
        f"Tu plan: {user.tier}\n"
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

    if not query.invoice_payload.startswith("premium_"):
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
        f"Payment received: user={tg_user.id}, stars={payment.total_amount}, "
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

    tweet_url = match.group(0)
    _, tweet_id = match.groups()
    filename = f"video_{tweet_id}.mp4"

    # Get or create user and check limits
    async with async_session() as session:
        user = await get_or_create_user(
            session, telegram_id=tg_user.id, username=tg_user.username
        )
        is_premium = await has_active_subscription(session, user.id)

        if not is_premium:
            downloads_today = await count_downloads_today(session, user.id)
            if downloads_today >= settings.FREE_DAILY_LIMIT:
                remaining_text = (
                    f"Alcanzaste tu limite de {settings.FREE_DAILY_LIMIT} "
                    f"descargas diarias.\n\n"
                    f"Usa /subscribe para obtener descargas ilimitadas "
                    f"por {settings.PREMIUM_PRICE_STARS} Stars/mes."
                )
                await update.message.reply_text(remaining_text)
                return

    # Download the video
    await update.message.reply_text("Descargando video...")

    try:
        dl_video(tweet_url, filename)
    except (DownloadError, ExtractorError) as e:
        logger.error(f"Error downloading video: {e}")
        await update.message.reply_text(
            "Error descargando el video. Verifica que el tweet tiene un video."
        )
        return
    except Exception as e:
        logger.error(f"Unexpected error downloading video: {e}")
        await update.message.reply_text("Error inesperado descargando el video.")
        return

    # Send the video to the user
    try:
        with open(filename, "rb") as video_file:
            await context.bot.send_video(
                chat_id=update.message.chat_id, video=video_file
            )
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        await update.message.reply_text(
            "Error enviando el video. Puede ser demasiado grande para Telegram."
        )
    finally:
        # Always clean up the file
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"Cleaned up file: {filename}")

    # Record the download
    async with async_session() as session:
        user = await get_or_create_user(
            session, telegram_id=tg_user.id, username=tg_user.username
        )
        await record_download(session, user.id, tweet_url)
