# bot.py
from strategies.bollinger_band import BollingerBandStrategy

# Strategy mapping
STRATEGIES = {
    "bollinger_band": BollingerBandStrategy
}

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
