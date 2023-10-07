import logging
import os
import re

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

import twitter_video_dl.twitter_video_dl as tvdl
from src.config import settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat = update.effective_chat
    user_id = user.id
    user_name = user.full_name
    username = user.username
    is_bot = user.is_bot

    chat_type = chat.type
    chat_id = chat.id
    chat_title = chat.title if chat.type != "private" else "Private Chat"

    print(f"User ID: {user_id}")
    print(f"Full Name: {user_name}")
    print(f"Username: @{username}")
    print(f"Is Bot: {is_bot}")
    print(f"Chat Type: {chat_type}")
    print(f"Chat ID: {chat_id}")
    print(f"Chat Title: {chat_title}")

    await update.message.reply_text(f"Hola {user_name}! Tu ID es {user_id}.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help = """
    /start - Iniciar el bot
    /help - Mostrar este mensaje de ayuda

    para descargar un video de twiiter pega el link del tweet
    """
    await update.message.reply_text(help)


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download a video from twitter."""
    message_text = update.message.text

    pattern = r'https:\/\/(twitter|x)\.com\/\w+\/status\/(\d+)'
    match = re.match(pattern, message_text)
    if match:
        plataform, tweet_id = match.groups()
        filename = f"video_{tweet_id}.mp4"

        if not os.path.exists(filename):
            url = match.string.replace(plataform, 'twitter')
            try:
                tvdl.download_video(url, filename)
            except Exception as e:
                logger.error(f"Error downloading video: {e}")
                await update.message.reply_text("Error descargando el video.")
                return

        bot = context.bot
        try:
            await bot.send_video(chat_id=update.message.chat_id, video=open(filename, 'rb'))
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            await update.message.reply_text("Error enviando el video.")
    else:
        await update.message.reply_text("No es un link de twitter")


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(settings.TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                           download_video))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
