from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.config import settings
from src.handlers import download_video, help_command, start


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
