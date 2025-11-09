"""
Data Collection for ML Model Training
Collects historical data from MT5 and labels trades for supervised learning
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pickle

from ..brokers.mt5_file_client import MT5FileClient
from ..data.indicators import TechnicalIndicators
from .feature_engineering import FeatureEngineer
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DataCollector:
    """
    Collects and labels historical trading data for ML training
    """

    def __init__(self, mt5_client: Optional[MT5FileClient] = None):
        self.mt5 = mt5_client or MT5FileClient()
        self.feature_engineer = FeatureEngineer()
        self.data_dir = Path("data/ml_training")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def collect_training_data(
        self,
        symbols: List[str],
        timeframes: List[str] = None,
        lookforward_bars: int = 10,
        min_profit_pct: float = 0.5
    ) -> pd.DataFrame:
        """
        Collect historical data and label profitable trade setups

        Args:
            symbols: List of trading symbols
            timeframes: List of timeframes to analyze (default: M15, M30, H1, H4, D1)
            lookforward_bars: How many bars ahead to check for profit
            min_profit_pct: Minimum profit % to label as successful trade

        Returns:
            DataFrame with features and labels
        """
        if timeframes is None:
            timeframes = ['M15', 'M30', 'H1', 'H4', 'D1']

        logger.info(f"Collecting training data for {len(symbols)} symbols...")

        all_samples = []

        for symbol in symbols:
            logger.info(f"Processing {symbol}...")

            try:
                # Get multi-timeframe data
                mtf_data = {}
                for tf in timeframes:
                    df = self.mt5.get_rates(symbol, tf, count=500)
                    if df is not None and len(df) >= 100:
                        mtf_data[tf] = df

                if len(mtf_data) < 3:
                    logger.warning(f"Insufficient data for {symbol}, skipping")
                    continue

                # Use H1 as primary timeframe for sampling
                primary_df = mtf_data.get('H1')
                if primary_df is None or len(primary_df) < 100:
                    continue

                # Sample every 10 bars to avoid correlation
                sample_indices = range(100, len(primary_df) - lookforward_bars, 10)

                for idx in sample_indices:
                    # Extract features at this point in time
                    features = self._extract_features_at_bar(
                        symbol=symbol,
                        mtf_data=mtf_data,
                        bar_index=idx,
                        timeframes=timeframes
                    )

                    if not features:
                        continue

                    # Label the trade
                    label = self._label_trade(
                        df=primary_df,
                        bar_index=idx,
                        lookforward_bars=lookforward_bars,
                        min_profit_pct=min_profit_pct
                    )

                    # Combine features and label
                    sample = {**features, **label}
                    all_samples.append(sample)

                logger.info(f"  Collected {len([s for s in all_samples if s.get('symbol') == hash(symbol) % 1000])} samples from {symbol}")

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

        # Convert to DataFrame
        if not all_samples:
            logger.error("No training data collected!")
            return pd.DataFrame()

        df = pd.DataFrame(all_samples)
        logger.info(f"Total samples collected: {len(df)}")
        logger.info(f"Buy signals: {df['label_buy'].sum()}")
        logger.info(f"Sell signals: {df['label_sell'].sum()}")
        logger.info(f"Hold signals: {df['label_hold'].sum()}")

        # Save to disk
        filename = self.data_dir / f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        df.to_pickle(filename)
        logger.info(f"Saved training data to {filename}")

        return df

    def _extract_features_at_bar(
        self,
        symbol: str,
        mtf_data: Dict[str, pd.DataFrame],
        bar_index: int,
        timeframes: List[str]
    ) -> Optional[Dict]:
        """Extract features at a specific bar in history"""
        try:
            # Slice data up to this bar (simulate what we'd know at that time)
            sliced_data = {}
            sliced_indicators = {}

            for tf in timeframes:
                if tf not in mtf_data:
                    continue

                df = mtf_data[tf]

                # Find corresponding bar index in this timeframe
                # (Different timeframes have different bar counts)
                # For simplicity, use proportional index
                ratio = len(df) / len(mtf_data['H1'])
                tf_index = int(bar_index * ratio)

                if tf_index >= len(df) - 10:
                    continue

                # Slice data up to this point
                sliced_df = df.iloc[:tf_index + 1].copy()

                # Calculate indicators on historical data only
                indicators = TechnicalIndicators.calculate_all(sliced_df)

                sliced_data[tf] = sliced_df
                sliced_indicators[tf] = indicators

            if len(sliced_data) < 3:
                return None

            # Extract features
            features = self.feature_engineer.extract_features(
                symbol=symbol,
                mtf_data=sliced_data,
                mtf_indicators=sliced_indicators
            )

            return features

        except Exception as e:
            logger.debug(f"Error extracting features: {e}")
            return None

    def _label_trade(
        self,
        df: pd.DataFrame,
        bar_index: int,
        lookforward_bars: int = 10,
        min_profit_pct: float = 0.5
    ) -> Dict[str, int]:
        """
        Label a trade as buy/sell/hold based on future price movement

        Args:
            df: Price data
            bar_index: Current bar index
            lookforward_bars: How many bars to look ahead
            min_profit_pct: Minimum profit to consider trade successful

        Returns:
            Dict with label_buy, label_sell, label_hold
        """
        try:
            current_price = df['close'].iloc[bar_index]
            current_atr = df['high'].iloc[bar_index-14:bar_index].mean() - df['low'].iloc[bar_index-14:bar_index].mean()

            if current_atr == 0:
                current_atr = current_price * 0.001  # 0.1% default

            # Look ahead
            future_prices = df['close'].iloc[bar_index+1:bar_index+1+lookforward_bars]

            if len(future_prices) < lookforward_bars:
                return {'label_buy': 0, 'label_sell': 0, 'label_hold': 1}

            max_future_price = future_prices.max()
            min_future_price = future_prices.min()

            # Calculate potential profit
            buy_profit_pct = (max_future_price - current_price) / current_price * 100
            sell_profit_pct = (current_price - min_future_price) / current_price * 100

            # Check for stop loss hit (2 ATR)
            stop_loss_distance = 2 * current_atr
            buy_stop_hit = (current_price - min_future_price) > stop_loss_distance
            sell_stop_hit = (max_future_price - current_price) > stop_loss_distance

            # Label logic
            label_buy = 0
            label_sell = 0
            label_hold = 0

            # Buy signal: Price went up enough without hitting stop
            if buy_profit_pct >= min_profit_pct and not buy_stop_hit:
                label_buy = 1

            # Sell signal: Price went down enough without hitting stop
            elif sell_profit_pct >= min_profit_pct and not sell_stop_hit:
                label_sell = 1

            # Hold: Neither condition met
            else:
                label_hold = 1

            return {
                'label_buy': label_buy,
                'label_sell': label_sell,
                'label_hold': label_hold
            }

        except Exception as e:
            logger.debug(f"Error labeling trade: {e}")
            return {'label_buy': 0, 'label_sell': 0, 'label_hold': 1}

    def load_training_data(self, filename: Optional[str] = None) -> pd.DataFrame:
        """Load previously collected training data"""
        if filename:
            filepath = self.data_dir / filename
        else:
            # Load most recent file
            files = sorted(self.data_dir.glob("training_data_*.pkl"))
            if not files:
                logger.error("No training data files found")
                return pd.DataFrame()
            filepath = files[-1]

        logger.info(f"Loading training data from {filepath}")
        df = pd.read_pickle(filepath)
        logger.info(f"Loaded {len(df)} samples")
        return df
