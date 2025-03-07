# bot.py
import os
import logging
import pandas as pd
import numpy as np
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("7711959119:AAGn6kCivsjuHsU8TdHZROe-wTfv_1HCf2I")

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class BollingerStrategy:
    def __init__(self, symbol="BTCUSDT", interval="1h"):
        self.symbol = symbol
        self.interval = interval
        self.base_url = "https://api.binance.com/api/v3/klines"
        
    def fetch_data(self):
        """Fetch OHLCV data from Binance API"""
        try:
            params = {
                "symbol": self.symbol,
                "interval": self.interval,
                "limit": 100
            }
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            return df
        except Exception as e:
            logger.error(f"Data fetch error: {e}")
            return None

    def calculate_indicators(self, df):
        """Calculate technical indicators"""
        try:
            # Bollinger Bands
            df['upper_band'] = df['close'].rolling(20).mean() + 2*df['close'].rolling(20).std()
            df['lower_band'] = df['close'].rolling(20).mean() - 2*df['close'].rolling(20).std()
            df['middle_band'] = df['close'].rolling(20).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp12 = df['close'].ewm(span=12, adjust=False).mean()
            exp26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp12 - exp26
            df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            
            # Volume
            df['volume_pct_change'] = df['volume'].pct_change() * 100
            df['obv'] = (np.sign(df['close'].diff()) * df['volume']).cumsum()
            
            return df.dropna()
        except Exception as e:
            logger.error(f"Indicator error: {e}")
            return None

    def generate_signal(self, df):
        """Generate trading signal"""
        try:
            latest = df.iloc[-1]
            band_width = (latest['upper_band'] - latest['lower_band']) / latest['close']
            
            # Long conditions
            long_conditions = [
                latest['close'] <= latest['lower_band'] * 1.001,
                latest['rsi'] < 30,
                latest['macd'] > latest['signal'],
                latest['volume_pct_change'] > 20,
                band_width < 0.005
            ]
            
            # Short conditions
            short_conditions = [
                latest['close'] >= latest['upper_band'] * 0.999,
                latest['rsi'] > 70,
                latest['macd'] < latest['signal'],
                latest['volume_pct_change'] < -20,
                band_width < 0.005
            ]
            
            long_score = sum(long_conditions)
            short_score = sum(short_conditions)
            
            if long_score >= 3:
                return self._calculate_long_params(df)
            elif short_score >= 3:
                return self._calculate_short_params(df)
            return None
            
        except Exception as e:
            logger.error(f"Signal error: {e}")
            return None

    def _calculate_long_params(self, df):
        latest = df.iloc[-1]
        atr = df['high'].iloc[-3:].max() - df['low'].iloc[-3:].min()
        entry = latest['lower_band']
        sl = entry - (1.5 * atr)
        tp1 = latest['middle_band']
        tp2 = latest['upper_band']
        return ('LONG', entry, sl, tp1, tp2)

    def _calculate_short_params(self, df):
        latest = df.iloc[-1]
        atr = df['high'].iloc[-3:].max() - df['low'].iloc[-3:].min()
        entry = latest['upper_band']
        sl = entry + (1.5 * atr)
        tp1 = latest['middle_band']
        tp2 = latest['lower_band']
        return ('SHORT', entry, sl, tp1, tp2)

# Telegram Bot Setup
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("BTC/USDT", callback_data="BTCUSDT"),
        [InlineKeyboardButton("ETH/USDT", callback_data="ETHUSDT")]
    ]
    await update.message.reply_text(
        "Select Pair:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_pair(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.await()
    pair = query.data
    
    strategy = BollingerStrategy(symbol=pair)
    df = strategy.fetch_data()
    if df is None:
        await query.edit_message_text("Error fetching data")
        return
    
    df = strategy.calculate_indicators(df)
    if df is None:
        await query.edit_message_text("Error calculating indicators")
        return
    
    signal = strategy.generate_signal(df)
    if not signal:
        await query.edit_message_text("No trade signal")
        return
    
    direction, entry, sl, tp1, tp2 = signal
    response = (
        f"🚨 {direction} SIGNAL 🚨\n"
        f"Pair: {pair}\n"
        f"Entry: {entry:.2f}\n"
        f"Stop Loss: {sl:.2f}\n"
        f"Take Profit 1: {tp1:.2f}\n"
        f"Take Profit 2: {tp2:.2f}"
    )
    await query.edit_message_text(response)

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_pair))

if __name__ == "__main__":
    application.run_polling()
