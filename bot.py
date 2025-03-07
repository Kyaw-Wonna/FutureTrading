import os
import numpy as np
import pandas as pd
import requests

# ---------------------------
# Technical Indicator Functions
# ---------------------------

def bollinger_bands(df, window=20, num_std=2):
    """Calculate Bollinger Bands and band width (in % of price)."""
    df['SMA'] = df['close'].rolling(window).mean()
    df['STD'] = df['close'].rolling(window).std()
    df['UpperBand'] = df['SMA'] + num_std * df['STD']
    df['LowerBand'] = df['SMA'] - num_std * df['STD']
    # Band width in percentage: (upper - lower) / close * 100
    df['BandWidth'] = (df['UpperBand'] - df['LowerBand']) / df['close'] * 100
    return df

def rsi(df, period=14):
    """Calculate Relative Strength Index (RSI)."""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def macd(df, fast=12, slow=26, signal_period=9):
    """Calculate MACD line, signal line and histogram."""
    df['EMA_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = df['EMA_fast'] - df['EMA_slow']
    df['Signal'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    return df

def atr(df, period=14):
    """Calculate Average True Range (ATR)."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(period).mean()
    return df

def obv(df):
    """Calculate On-Balance Volume (OBV)."""
    obv_vals = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv_vals.append(obv_vals[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv_vals.append(obv_vals[-1] - df['volume'].iloc[i])
        else:
            obv_vals.append(obv_vals[-1])
    df['OBV'] = obv_vals
    return df

def volume_spike(df, period=24):
    """
    Flag a volume spike if current volume is 20% above the rolling average.
    Assume period=24 for hourly data (adjust if using 15m data).
    """
    df['VolAvg'] = df['volume'].rolling(period).mean()
    df['VolSpike'] = df['volume'] > 1.2 * df['VolAvg']
    return df

# ---------------------------
# Signal and Trade Logic
# ---------------------------

def calculate_confluence_score(df):
    """
    For the most recent bar, check indicator conditions and return:
      - signal: 'long', 'short', or 'no trade'
      - score: total percentage based on weights
    Weights: Bollinger (40), RSI (25), MACD (20), Volume (15)
    """
    # Grab last row (latest data)
    row = df.iloc[-1]
    score_long = 0
    score_short = 0

    # 1. Bollinger Band Position + Squeeze (40%)
    # For long: price touches lower band and low volatility (BandWidth < 0.5%)
    if row['close'] <= row['LowerBand'] and row['BandWidth'] < 0.5:
        score_long += 40
    # For short: price touches upper band and low volatility
    if row['close'] >= row['UpperBand'] and row['BandWidth'] < 0.5:
        score_short += 40

    # 2. RSI (25%)
    # For long: oversold (<30)
    if row['RSI'] < 30:
        score_long += 25
    # For short: overbought (>70)
    if row['RSI'] > 70:
        score_short += 25

    # 3. MACD (20%)
    # Check for bullish/bearish cross in the last two periods
    if len(df) >= 2:
        prev = df.iloc[-2]
        # Bullish cross: previous MACD below Signal and now above
        if prev['MACD'] < prev['Signal'] and row['MACD'] > row['Signal'] and row['MACD_Hist'] > 0:
            score_long += 20
        # Bearish cross: previous MACD above Signal and now below
        if prev['MACD'] > prev['Signal'] and row['MACD'] < row['Signal'] and row['MACD_Hist'] < 0:
            score_short += 20

    # 4. Volume Confirmation (15%)
    # For long: volume spike and OBV rising (compare last two OBV values)
    if row['VolSpike'] and (df['OBV'].iloc[-1] > df['OBV'].iloc[-2]):
        score_long += 15
    # For short: volume spike and OBV falling
    if row['VolSpike'] and (df['OBV'].iloc[-1] < df['OBV'].iloc[-2]):
        score_short += 15

    # Determine which side (if any) has sufficient confluence:
    # High confidence: >=85; Moderate: 60-84; else no trade
    trade_signal = 'no trade'
    confidence = 0
    if score_long >= 85:
        trade_signal = 'long'
        confidence = score_long
    elif score_short >= 85:
        trade_signal = 'short'
        confidence = score_short
    elif score_long >= 60:
        trade_signal = 'long'
        confidence = score_long
    elif score_short >= 60:
        trade_signal = 'short'
        confidence = score_short

    return trade_signal, confidence

def calculate_position_size(account_risk, portfolio_value, atr_val, band_width):
    """
    Calculate position size based on risk management.
    position_size = (account_risk * portfolio_value) / (ATR * leverage_multiplier)
    Leverage multiplier based on Band Width:
      - If band_width < 0.5%: 1x
      - If 0.5% <= band_width <= 1.5%: 3x
      - Else: 0.5x
    """
    if band_width < 0.5:
        leverage_multiplier = 1
    elif 0.5 <= band_width <= 1.5:
        leverage_multiplier = 3
    else:
        leverage_multiplier = 0.5

    # Avoid division by zero
    if atr_val == 0:
        return 0
    position_size = (account_risk * portfolio_value) / (atr_val * leverage_multiplier)
    return position_size

def calculate_trade_parameters(row, side):
    """
    Given the latest row and trade side ('long' or 'short'), calculate:
      - Entry price
      - Stop loss (using min/max of volatility-based and fixed % risk)
      - Take Profit levels (TP1 = middle band, TP2 = upper/lower band)
    """
    entry = row['close']
    atr_val = row['ATR']
    sma = row['SMA']
    if side == 'long':
        # For long, stop loss is the higher of:
        # lower band - (1.5 * ATR) and 2% below entry (choose the less risky: higher price)
        sl_vol = row['LowerBand'] - (1.5 * atr_val)
        sl_fixed = entry * 0.98
        stop_loss = max(sl_vol, sl_fixed)
        tp1 = sma  # middle band
        tp2 = row['UpperBand']
    elif side == 'short':
        # For short, stop loss is the lower of:
        # upper band + (1.5 * ATR) and 2% above entry (choose the less risky: lower price)
        sl_vol = row['UpperBand'] + (1.5 * atr_val)
        sl_fixed = entry * 1.02
        stop_loss = min(sl_vol, sl_fixed)
        tp1 = sma  # middle band
        tp2 = row['LowerBand']
    else:
        stop_loss = tp1 = tp2 = None

    return entry, stop_loss, tp1, tp2

# ---------------------------
# Telegram Bot Notification
# ---------------------------

def send_telegram_message(message):
    """
    Sends a message using Telegram's Bot API.
    Set environment variables TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials not set.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Telegram message sent.")
        else:
            print("Failed to send Telegram message.")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

# ---------------------------
# Main Bot Class
# ---------------------------

class CryptoFuturesBot:
    def __init__(self, account_risk=0.02, portfolio_value=100000):
        self.account_risk = account_risk
        self.portfolio_value = portfolio_value

    def prepare_data(self, df):
        """Calculate all indicators needed."""
        df = bollinger_bands(df)
        df = rsi(df)
        df = macd(df)
        df = atr(df)
        df = obv(df)
        df = volume_spike(df)
        # Drop any rows with NaN values due to rolling calculations
        df = df.dropna().reset_index(drop=True)
        return df

    def analyze(self, df):
        """Analyze latest data and generate a trade signal and parameters."""
        df = self.prepare_data(df)
        signal, confidence = calculate_confluence_score(df)
        latest = df.iloc[-1]
        band_width = latest['BandWidth']
        atr_val = latest['ATR']
        pos_size = calculate_position_size(self.account_risk, self.portfolio_value, atr_val, band_width)

        if signal in ['long', 'short']:
            entry, stop_loss, tp1, tp2 = calculate_trade_parameters(latest, signal)
            trade_details = {
                "signal": signal,
                "confidence": confidence,
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit1": tp1,
                "take_profit2": tp2,
                "position_size": pos_size,
                "band_width": band_width,
                "ATR": atr_val,
                "RSI": latest['RSI']
            }
        else:
            trade_details = {"signal": "no trade", "confidence": confidence}
        return trade_details

    def run(self, df):
        """Run analysis and send Telegram alert if trade signal found."""
        trade = self.analyze(df)
        if trade["signal"] != "no trade":
            message = (f"Trade Signal: {trade['signal'].upper()} | Confidence: {trade['confidence']}%\n"
                       f"Entry: {trade['entry']:.2f}\nStop Loss: {trade['stop_loss']:.2f}\n"
                       f"TP1 (Middle Band): {trade['take_profit1']:.2f}\nTP2 (Target Band): {trade['take_profit2']:.2f}\n"
                       f"Position Size: {trade['position_size']:.4f}\nRSI: {trade['RSI']:.2f}\nBand Width: {trade['band_width']:.2f}%")
            print(message)
            send_telegram_message(message)
        else:
            print("No trade signal generated.")

# ---------------------------
# Example Usage
# ---------------------------
if __name__ == "__main__":
    # Replace with your data source. For example, a CSV file with columns:
    # timestamp, open, high, low, close, volume
    # Here we simulate reading from 'data.csv'
    try:
        df = pd.read_csv("data.csv", parse_dates=["timestamp"])
    except Exception as e:
        print("Error reading data.csv. Please ensure the file exists with correct columns.")
        raise e

    bot = CryptoFuturesBot(account_risk=0.02, portfolio_value=100000)
    bot.run(df)
