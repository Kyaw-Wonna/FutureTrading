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

# bot.py (continued)
from strategies.bollinger_band import BollingerBandStrategy

# Strategy mapping
STRATEGIES = {
    "bollinger_band": BollingerBandStrategy
}

# /strategy command
async def select_strategy(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Bollinger Band", callback_data="bollinger_band")]
    ]
    await update.message.reply_text(
        "📊 Select a Strategy:",
        reply_markup=InlineKeyboardMarkup(keyboard)

        # bot.py (continued)
async def handle_strategy_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    strategy_name = query.data
    strategy_class = STRATEGIES.get(strategy_name)

    if not strategy_class:
        await query.edit_message_text("⚠️ Invalid strategy selected.")
        return

    # Fetch data and generate signal
    strategy = strategy_class()
    df = strategy.fetch_data()
    if df is None:
        await query.edit_message_text("⚠️ Failed to fetch data. Please try again.")
        return

    df = strategy.calculate_indicators(df)
    signal = strategy.generate_signal(df)

    # Format response
    latest = df.iloc[-1]
    response = f"""
    📊 *{strategy_name.upper()} Signal* ({signal})
    ---------------------------------
    🔹 Price: ${latest['close']:,.2f}
    🔸 Upper Band: ${latest['upper_band']:,.2f}
    🔹 Lower Band: ${latest['lower_band']:,.2f}
    🔸 RSI: {latest['rsi']:.2f}
    🔹 Volume Change: {latest['volume_pct_change']:.2f}%
    """
    await query.edit_message_text(response, parse_mode="Markdown")

# bot.py (continued)
application.add_handler(CommandHandler("strategy", select_strategy))
application.add_handler(CallbackQueryHandler(handle_strategy_selection))




