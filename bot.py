# bot.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
TOKEN = os.getenv("7711959119:AAGn6kCivsjuHsU8TdHZROe-wTfv_1HCf2I")

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
application = Application.builder().token(TOKEN).build()

# Error handler
async def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error: {context.error}")
    await update.message.reply_text("⚠️ An error occurred. Please try again.")

# Start command
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🎯 Welcome! Use /strategy to select a trading strategy."
    )

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_error_handler(error_handler)

# Run bot
if __name__ == "__main__":
    application.run_polling()
