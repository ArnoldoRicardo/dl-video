from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from src.config import settings
from src.db import init_db
from src.handlers import (
    download_video,
    help_command,
    pre_checkout_handler,
    start,
    status_command,
    subscribe_command,
    successful_payment_handler,
)


async def post_init(application: Application) -> None:
    """Initialize the database when the bot starts."""
    await init_db()


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(settings.TOKEN).post_init(post_init).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))

    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )

    # Video download (any text message that's not a command)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, download_video)
    )

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
