# strategies/base_strategy.py
import pandas as pd
import talib

class BaseStrategy:
    def __init__(self, symbol="BTCUSDT", interval="1h", limit=100):
        self.symbol = symbol
        self.interval = interval
        self.limit = limit

    def fetch_data(self):
        """Fetch OHLCV data from Binance API."""
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": self.symbol,
            "interval": self.interval,
            "limit": self.limit
        }
        try:
            response = requests.get(url, params=params)
            data = response.json()
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return None

    def calculate_indicators(self, df):
        """Calculate indicators (override in child classes)."""
        raise NotImplementedError

    def generate_signal(self, df):
        """Generate trading signal (override in child classes)."""
        raise NotImplementedError
