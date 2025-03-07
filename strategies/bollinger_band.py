# strategies/bollinger_band.py
from .base_strategy import BaseStrategy

class BollingerBandStrategy(BaseStrategy):
    def calculate_indicators(self, df):
        df['upper_band'], df['middle_band'], df['lower_band'] = talib.BBANDS(
            df['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
        )
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        df['volume_pct_change'] = df['volume'].pct_change() * 100
        return df

    def generate_signal(self, df):
        latest = df.iloc[-1]
        conditions = {
            "bb_squeeze": (latest['upper_band'] - latest['lower_band']) / latest['close'] < 0.005,
            "at_lower_band": latest['close'] <= latest['lower_band'] * 1.001,
            "rsi_oversold": latest['rsi'] < 30,
            "volume_spike": latest['volume_pct_change'] > 20
        }
        score = sum(conditions.values())
        return "STRONG LONG" if score >= 3 else "NO TRADE"
