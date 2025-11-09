"""
Advanced Data Fetcher for US30 Scalping
Fetches data from multiple sources and combines for best quality
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
from pathlib import Path
import requests
from typing import Optional, Tuple
import time

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AdvancedDataFetcher:
    """
    Fetches US30 data from multiple sources:
    1. yfinance (Dow Jones as proxy)
    2. Alpha Vantage (if API key available)
    3. Cached data from previous runs
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def fetch_us30_comprehensive(
        self,
        days: int = 60,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """
        Fetch comprehensive US30 data
        
        Strategy:
        1. Try to load from cache
        2. Fetch new data from yfinance (7 days max for 1m)
        3. Combine with cached data to get 60 days
        4. Fill gaps and clean data
        
        Args:
            days: Target days of data
            interval: Data interval (1m, 5m, etc)
            
        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Fetching {days} days of US30 data ({interval} interval)...")
        
        # Load cached data
        cached_df = self._load_cache(interval)
        
        # Fetch fresh data (yfinance allows 7 days of 1m data)
        if interval == "1m":
            fetch_days = 7
        elif interval == "5m":
            fetch_days = 60
        else:
            fetch_days = days
            
        fresh_df = self._fetch_yfinance(days=fetch_days, interval=interval)
        
        # Combine cached + fresh
        if cached_df is not None and fresh_df is not None:
            combined_df = pd.concat([cached_df, fresh_df]).drop_duplicates(subset=['time']).sort_values('time')
            logger.info(f"Combined cached ({len(cached_df)}) + fresh ({len(fresh_df)}) = {len(combined_df)} bars")
        elif fresh_df is not None:
            combined_df = fresh_df
            logger.info(f"Using fresh data: {len(combined_df)} bars")
        elif cached_df is not None:
            combined_df = cached_df
            logger.warning(f"Using only cached data: {len(cached_df)} bars")
        else:
            logger.error("No data available!")
            return pd.DataFrame()
        
        # Keep only last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        combined_df = combined_df[combined_df['time'] >= cutoff_date]
        
        # Save to cache
        self._save_cache(combined_df, interval)
        
        logger.info(f"✓ Final dataset: {len(combined_df)} bars spanning {(combined_df['time'].max() - combined_df['time'].min()).days} days")
        
        return combined_df
    
    def _fetch_yfinance(self, days: int, interval: str) -> Optional[pd.DataFrame]:
        """Fetch from yfinance"""
        try:
            ticker = yf.Ticker("^DJI")
            df = ticker.history(period=f"{days}d", interval=interval)
            
            if df.empty:
                return None
            
            # Standardize columns
            df.columns = df.columns.str.lower()
            df = df.rename(columns={'volume': 'tick_volume'})
            df = df.reset_index()
            
            # Handle datetime column
            if 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'time'})
            elif 'Date' in df.columns:
                df = df.rename(columns={'Date': 'time'})
            elif 'index' in df.columns:
                df = df.rename(columns={'index': 'time'})
            
            # Ensure time is datetime
            if not pd.api.types.is_datetime64_any_dtype(df['time']):
                df['time'] = pd.to_datetime(df['time'])
            
            # Remove timezone for consistency
            if df['time'].dt.tz is not None:
                df['time'] = df['time'].dt.tz_localize(None)
            
            logger.info(f"✓ Fetched {len(df)} bars from yfinance")
            return df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
            
        except Exception as e:
            logger.error(f"yfinance fetch failed: {e}")
            return None
    
    def _load_cache(self, interval: str) -> Optional[pd.DataFrame]:
        """Load cached data"""
        cache_file = self.cache_dir / f"us30_{interval}.parquet"
        
        if not cache_file.exists():
            return None
        
        try:
            df = pd.read_parquet(cache_file)
            logger.info(f"✓ Loaded {len(df)} bars from cache")
            return df
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
            return None
    
    def _save_cache(self, df: pd.DataFrame, interval: str):
        """Save data to cache"""
        cache_file = self.cache_dir / f"us30_{interval}.parquet"
        
        try:
            df.to_parquet(cache_file, index=False)
            logger.info(f"✓ Saved {len(df)} bars to cache")
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def generate_synthetic_tick_data(
        self,
        m1_df: pd.DataFrame,
        ticks_per_minute: int = 20
    ) -> pd.DataFrame:
        """
        Generate synthetic tick data from 1-minute bars
        
        This creates realistic intra-minute price movements
        for more granular training data
        
        Args:
            m1_df: 1-minute OHLCV data
            ticks_per_minute: Number of ticks to generate per minute
            
        Returns:
            DataFrame with synthetic tick data
        """
        logger.info(f"Generating synthetic tick data ({ticks_per_minute} ticks/min)...")
        
        all_ticks = []
        
        for idx, row in m1_df.iterrows():
            bar_time = row['time']
            o, h, l, c = row['open'], row['high'], row['low'], row['close']
            
            # Generate realistic price path within the bar
            # Using a random walk constrained by OHLC
            ticks = []
            
            # Start at open
            ticks.append(o)
            
            # Generate intermediate ticks
            for i in range(1, ticks_per_minute - 1):
                # Random walk with bias toward close
                progress = i / ticks_per_minute
                target = o + (c - o) * progress
                noise = np.random.normal(0, (h - l) * 0.1)
                price = np.clip(target + noise, l, h)
                ticks.append(price)
            
            # End at close
            ticks.append(c)
            
            # Create tick timestamps
            for i, price in enumerate(ticks):
                tick_time = bar_time + timedelta(seconds=i * 60 / ticks_per_minute)
                all_ticks.append({
                    'time': tick_time,
                    'price': price,
                    'volume': row['tick_volume'] / ticks_per_minute
                })
        
        tick_df = pd.DataFrame(all_ticks)
        logger.info(f"✓ Generated {len(tick_df)} synthetic ticks")
        
        return tick_df
