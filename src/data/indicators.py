"""
Technical indicators calculator
Calculates all technical indicators needed for trading decisions
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

from ..utils.logger import get_logger


logger = get_logger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators from price data"""

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> Dict:
        """
        Calculate all technical indicators from OHLCV data

        Args:
            df: DataFrame with columns: open, high, low, close, volume

        Returns:
            Dictionary with all calculated indicators
        """
        if df.empty or len(df) < 50:
            logger.warning("Insufficient data for indicator calculation")
            return TechnicalIndicators._empty_indicators()

        try:
            indicators = {}

            # Current price action
            indicators["price_action"] = TechnicalIndicators._price_action(df)

            # Trend indicators
            indicators["trend"] = TechnicalIndicators._trend_indicators(df)

            # Momentum indicators
            indicators["momentum"] = TechnicalIndicators._momentum_indicators(df)

            # Volatility indicators
            indicators["volatility"] = TechnicalIndicators._volatility_indicators(df)

            # Volume indicators
            indicators["volume"] = TechnicalIndicators._volume_indicators(df)

            logger.debug(f"Calculated indicators for {len(df)} bars")
            return indicators

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return TechnicalIndicators._empty_indicators()

    @staticmethod
    def _price_action(df: pd.DataFrame) -> Dict:
        """Get current price action"""
        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) > 1 else latest

        return {
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": float(latest["close"]),
            "volume": float(latest["volume"]) if "volume" in latest else 0,
            "change": float(latest["close"] - previous["close"]),
            "change_pct": float(((latest["close"] / previous["close"]) - 1) * 100) if previous["close"] > 0 else 0,
        }

    @staticmethod
    def _trend_indicators(df: pd.DataFrame) -> Dict:
        """Calculate trend indicators"""
        close = df["close"]

        # Simple Moving Averages
        sma_20 = SMAIndicator(close, window=20).sma_indicator()
        sma_50 = SMAIndicator(close, window=50).sma_indicator()
        sma_200 = SMAIndicator(close, window=200).sma_indicator() if len(df) >= 200 else None

        # Exponential Moving Averages
        ema_12 = EMAIndicator(close, window=12).ema_indicator()
        ema_26 = EMAIndicator(close, window=26).ema_indicator()

        # MACD
        macd_indicator = MACD(close)
        macd = macd_indicator.macd()
        macd_signal = macd_indicator.macd_signal()
        macd_hist = macd_indicator.macd_diff()

        return {
            "sma_20": float(sma_20.iloc[-1]) if not sma_20.empty else 0,
            "sma_50": float(sma_50.iloc[-1]) if not sma_50.empty else 0,
            "sma_200": float(sma_200.iloc[-1]) if sma_200 is not None and not sma_200.empty else 0,
            "ema_12": float(ema_12.iloc[-1]) if not ema_12.empty else 0,
            "ema_26": float(ema_26.iloc[-1]) if not ema_26.empty else 0,
            "macd": float(macd.iloc[-1]) if not macd.empty else 0,
            "macd_signal": float(macd_signal.iloc[-1]) if not macd_signal.empty else 0,
            "macd_hist": float(macd_hist.iloc[-1]) if not macd_hist.empty else 0,
        }

    @staticmethod
    def _momentum_indicators(df: pd.DataFrame) -> Dict:
        """Calculate momentum indicators"""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # RSI
        rsi = RSIIndicator(close, window=14).rsi()

        # Stochastic Oscillator
        stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
        stoch_k = stoch.stoch()
        stoch_d = stoch.stoch_signal()

        return {
            "rsi": float(rsi.iloc[-1]) if not rsi.empty else 50,
            "stoch_k": float(stoch_k.iloc[-1]) if not stoch_k.empty else 50,
            "stoch_d": float(stoch_d.iloc[-1]) if not stoch_d.empty else 50,
        }

    @staticmethod
    def _volatility_indicators(df: pd.DataFrame) -> Dict:
        """Calculate volatility indicators"""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Bollinger Bands
        bb = BollingerBands(close, window=20, window_dev=2)
        bb_upper = bb.bollinger_hband()
        bb_middle = bb.bollinger_mavg()
        bb_lower = bb.bollinger_lband()
        bb_width = bb.bollinger_wband()

        # Average True Range
        atr = AverageTrueRange(high, low, close, window=14).average_true_range()

        return {
            "bb_upper": float(bb_upper.iloc[-1]) if not bb_upper.empty else 0,
            "bb_middle": float(bb_middle.iloc[-1]) if not bb_middle.empty else 0,
            "bb_lower": float(bb_lower.iloc[-1]) if not bb_lower.empty else 0,
            "bb_width": float(bb_width.iloc[-1]) if not bb_width.empty else 0,
            "atr": float(atr.iloc[-1]) if not atr.empty else 0,
        }

    @staticmethod
    def _volume_indicators(df: pd.DataFrame) -> Dict:
        """Calculate volume indicators"""
        if "volume" not in df.columns:
            return {
                "current": 0,
                "average": 0,
                "ratio": 1.0,
            }

        volume = df["volume"]
        current_volume = float(volume.iloc[-1])
        avg_volume = float(volume.rolling(window=20).mean().iloc[-1])

        return {
            "current": current_volume,
            "average": avg_volume,
            "ratio": current_volume / avg_volume if avg_volume > 0 else 1.0,
        }

    @staticmethod
    def _empty_indicators() -> Dict:
        """Return empty indicators structure"""
        return {
            "price_action": {
                "open": 0, "high": 0, "low": 0, "close": 0,
                "volume": 0, "change": 0, "change_pct": 0,
            },
            "trend": {
                "sma_20": 0, "sma_50": 0, "sma_200": 0,
                "ema_12": 0, "ema_26": 0,
                "macd": 0, "macd_signal": 0, "macd_hist": 0,
            },
            "momentum": {
                "rsi": 50, "stoch_k": 50, "stoch_d": 50,
            },
            "volatility": {
                "bb_upper": 0, "bb_middle": 0, "bb_lower": 0,
                "bb_width": 0, "atr": 0,
            },
            "volume": {
                "current": 0, "average": 0, "ratio": 1.0,
            },
        }
