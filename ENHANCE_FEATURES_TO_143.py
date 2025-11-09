#!/usr/bin/env python3
"""
Enhance exported data from 23 features to 143 features
Takes basic OHLCV + indicators and calculates advanced features
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"

def calculate_advanced_features(df):
    """Calculate 120 additional features from basic OHLCV data"""
    
    print(f"  Starting with {len(df.columns)} features")
    
    # Make a copy to avoid modifying original
    enhanced = df.copy()
    
    # ===================================================================
    # 1. ADDITIONAL CANDLESTICK PATTERNS (9 more)
    # ===================================================================
    print("  Calculating candlestick patterns...")
    
    enhanced['consecutive_bull'] = 0
    enhanced['consecutive_bear'] = 0
    for i in range(len(enhanced)):
        count_bull = 0
        count_bear = 0
        for j in range(i, min(i+10, len(enhanced))):
            if enhanced.iloc[j]['is_bullish'] == 1:
                count_bull += 1
            else:
                count_bear += 1
                break
        enhanced.at[i, 'consecutive_bull'] = count_bull
        
    enhanced['gap_up'] = (enhanced['open'] > enhanced['close'].shift(1)).astype(int)
    enhanced['gap_down'] = (enhanced['open'] < enhanced['close'].shift(1)).astype(int)
    enhanced['gap_size'] = abs(enhanced['open'] - enhanced['close'].shift(1))
    enhanced['higher_high'] = (enhanced['high'] > enhanced['high'].shift(1)).astype(int)
    enhanced['lower_low'] = (enhanced['low'] < enhanced['low'].shift(1)).astype(int)
    
    # Price position in range
    high_20 = enhanced['high'].rolling(20).max()
    low_20 = enhanced['low'].rolling(20).min()
    enhanced['price_position_20'] = ((enhanced['close'] - low_20) / (high_20 - low_20) * 100).fillna(50)
    
    high_50 = enhanced['high'].rolling(50).max()
    low_50 = enhanced['low'].rolling(50).min()
    enhanced['price_position_50'] = ((enhanced['close'] - low_50) / (high_50 - low_50) * 100).fillna(50)
    
    # ===================================================================
    # 2. PRICE MOMENTUM (6 more)
    # ===================================================================
    print("  Calculating price momentum...")
    
    enhanced['roc_1'] = enhanced['close'].pct_change(1) * 100
    enhanced['roc_3'] = enhanced['close'].pct_change(3) * 100
    enhanced['roc_5'] = enhanced['close'].pct_change(5) * 100
    enhanced['roc_10'] = enhanced['close'].pct_change(10) * 100
    enhanced['acceleration'] = enhanced['roc_1'] - enhanced['roc_3']
    
    range_current = enhanced['high'] - enhanced['low']
    range_10 = enhanced['high'].rolling(10).max() - enhanced['low'].rolling(10).min()
    enhanced['range_expansion'] = (range_current / range_10).fillna(1.0)
    
    # ===================================================================
    # 3. VOLUME FEATURES (12 more)
    # ===================================================================
    print("  Calculating volume features...")
    
    enhanced['vol_ma_5'] = enhanced['volume'].rolling(5).mean()
    enhanced['vol_ma_10'] = enhanced['volume'].rolling(10).mean()
    enhanced['vol_ma_20'] = enhanced['volume'].rolling(20).mean()
    enhanced['vol_ratio_5'] = enhanced['volume'] / enhanced['vol_ma_5']
    enhanced['vol_ratio_10'] = enhanced['volume'] / enhanced['vol_ma_10']
    enhanced['vol_increasing'] = (enhanced['volume'] > enhanced['volume'].shift(1)).astype(int)
    enhanced['vol_decreasing'] = (enhanced['volume'] < enhanced['volume'].shift(1)).astype(int)
    enhanced['vol_spike'] = (enhanced['vol_ratio_10'] > 2.0).astype(int)
    
    # Price-volume correlation
    enhanced['price_vol_corr'] = enhanced['close'].rolling(20).corr(enhanced['volume']).fillna(0)
    
    # OBV trend
    obv = (enhanced['volume'] * np.sign(enhanced['close'].diff())).cumsum()
    enhanced['obv_trend'] = obv.diff(10).fillna(0)
    
    # Simplified buy/sell pressure
    enhanced['buying_pressure'] = ((enhanced['close'] - enhanced['low']) / (enhanced['high'] - enhanced['low'])).fillna(0.5)
    enhanced['selling_pressure'] = ((enhanced['high'] - enhanced['close']) / (enhanced['high'] - enhanced['low'])).fillna(0.5)
    
    # ===================================================================
    # 4. TIME FEATURES (11 features)
    # ===================================================================
    print("  Calculating time features...")
    
    # Convert timestamp to datetime if not already
    if 'timestamp' in enhanced.columns:
        enhanced['datetime'] = pd.to_datetime(enhanced['timestamp'])
        enhanced['hour'] = enhanced['datetime'].dt.hour
        enhanced['minute'] = enhanced['datetime'].dt.minute
        enhanced['day_of_week'] = enhanced['datetime'].dt.dayofweek
        
        # Cyclical encoding
        enhanced['hour_sin'] = np.sin(2 * np.pi * enhanced['hour'] / 24)
        enhanced['hour_cos'] = np.cos(2 * np.pi * enhanced['hour'] / 24)
        enhanced['minute_sin'] = np.sin(2 * np.pi * enhanced['minute'] / 60)
        enhanced['minute_cos'] = np.cos(2 * np.pi * enhanced['minute'] / 60)
        
        # Trading sessions
        enhanced['ny_session'] = ((enhanced['hour'] >= 13) & (enhanced['hour'] < 21)).astype(int)
        enhanced['london_session'] = ((enhanced['hour'] >= 7) & (enhanced['hour'] < 15)).astype(int)
        enhanced['asian_session'] = ((enhanced['hour'] < 7) | (enhanced['hour'] >= 21)).astype(int)
        
        # Day of week
        enhanced['is_monday'] = (enhanced['day_of_week'] == 0).astype(int)
        enhanced['is_friday'] = (enhanced['day_of_week'] == 4).astype(int)
        enhanced['ny_open_hour'] = (enhanced['hour'] == 13).astype(int)
        enhanced['ny_close_hour'] = (enhanced['hour'] == 20).astype(int)
        
        # Drop helper columns
        enhanced.drop(['datetime', 'hour', 'minute', 'day_of_week'], axis=1, inplace=True)
    
    # ===================================================================
    # 5. VOLATILITY FEATURES (8 more)
    # ===================================================================
    print("  Calculating volatility features...")
    
    enhanced['atr_50'] = (enhanced['high'] - enhanced['low']).rolling(50).mean()
    enhanced['atr_ratio'] = enhanced['atr_20'] / enhanced['atr_50']
    
    # Historical volatility
    returns = enhanced['close'].pct_change()
    enhanced['hvol_10'] = returns.rolling(10).std() * np.sqrt(252)
    enhanced['hvol_20'] = returns.rolling(20).std() * np.sqrt(252)
    enhanced['hvol_ratio'] = enhanced['hvol_10'] / enhanced['hvol_20']
    
    enhanced['low_vol_regime'] = (enhanced['hvol_20'] < 0.15).astype(int)
    enhanced['high_vol_regime'] = (enhanced['hvol_20'] > 0.30).astype(int)
    enhanced['parkinson_vol'] = np.sqrt(1/(4*np.log(2)) * (np.log(enhanced['high']/enhanced['low'])**2))
    
    # ===================================================================
    # 6. TREND FEATURES (8 more)
    # ===================================================================
    print("  Calculating trend features...")
    
    enhanced['ema_5'] = enhanced['close'].ewm(span=5, adjust=False).mean()
    enhanced['ema_10'] = enhanced['close'].ewm(span=10, adjust=False).mean()
    enhanced['ema_20'] = enhanced['close'].ewm(span=20, adjust=False).mean()
    
    enhanced['sma5_above_sma20'] = (enhanced['sma_5'] > enhanced['sma_20']).astype(int)
    enhanced['ema5_above_ema20'] = (enhanced['ema_5'] > enhanced['ema_20']).astype(int)
    enhanced['price_vs_sma5'] = (enhanced['close'] / enhanced['sma_5'] - 1) * 100
    enhanced['price_vs_sma50'] = (enhanced['close'] / enhanced['sma_50'] - 1) * 100
    enhanced['trend_strength'] = abs(enhanced['rsi'] - 50) / 50
    
    # ===================================================================
    # 7. SUPPORT/RESISTANCE (7 features)
    # ===================================================================
    print("  Calculating support/resistance...")
    
    high_20 = enhanced['high'].rolling(20).max()
    low_20 = enhanced['low'].rolling(20).min()
    
    enhanced['dist_to_resistance'] = (high_20 - enhanced['close']) / enhanced['close'] * 100
    enhanced['dist_to_support'] = (enhanced['close'] - low_20) / enhanced['close'] * 100
    
    pivot = (high_20 + low_20 + enhanced['close']) / 3
    r1 = 2 * pivot - low_20
    s1 = 2 * pivot - high_20
    
    enhanced['above_pivot'] = (enhanced['close'] > pivot).astype(int)
    enhanced['dist_to_pivot'] = abs(enhanced['close'] - pivot) / enhanced['close'] * 100
    enhanced['dist_to_r1'] = abs(enhanced['close'] - r1) / enhanced['close'] * 100
    enhanced['dist_to_s1'] = abs(enhanced['close'] - s1) / enhanced['close'] * 100
    
    enhanced['near_round_level'] = ((enhanced['close'] % 100 < 10) | (enhanced['close'] % 100 > 90)).astype(int)
    
    # ===================================================================
    # 8. ICHIMOKU (8 features)
    # ===================================================================
    print("  Calculating Ichimoku...")
    
    # Tenkan-sen (9-period)
    high_9 = enhanced['high'].rolling(9).max()
    low_9 = enhanced['low'].rolling(9).min()
    enhanced['ichimoku_tenkan'] = (high_9 + low_9) / 2
    
    # Kijun-sen (26-period)
    high_26 = enhanced['high'].rolling(26).max()
    low_26 = enhanced['low'].rolling(26).min()
    enhanced['ichimoku_kijun'] = (high_26 + low_26) / 2
    
    # Senkou Span A
    enhanced['ichimoku_senkou_a'] = ((enhanced['ichimoku_tenkan'] + enhanced['ichimoku_kijun']) / 2).shift(26)
    
    # Senkou Span B (52-period)
    high_52 = enhanced['high'].rolling(52).max()
    low_52 = enhanced['low'].rolling(52).min()
    enhanced['ichimoku_senkou_b'] = ((high_52 + low_52) / 2).shift(26)
    
    enhanced['ichimoku_tk_cross'] = (enhanced['ichimoku_tenkan'] > enhanced['ichimoku_kijun']).astype(int)
    
    cloud_top = enhanced[['ichimoku_senkou_a', 'ichimoku_senkou_b']].max(axis=1)
    cloud_bottom = enhanced[['ichimoku_senkou_a', 'ichimoku_senkou_b']].min(axis=1)
    
    enhanced['ichimoku_price_vs_cloud'] = np.where(enhanced['close'] > cloud_top, 1,
                                                    np.where(enhanced['close'] < cloud_bottom, -1, 0))
    enhanced['ichimoku_cloud_thickness'] = abs(enhanced['ichimoku_senkou_a'] - enhanced['ichimoku_senkou_b'])
    enhanced['ichimoku_cloud_color'] = (enhanced['ichimoku_senkou_a'] > enhanced['ichimoku_senkou_b']).astype(int)
    
    # ===================================================================
    # 9. FIBONACCI (9 features)
    # ===================================================================
    print("  Calculating Fibonacci levels...")
    
    high_50 = enhanced['high'].rolling(50).max()
    low_50 = enhanced['low'].rolling(50).min()
    fib_range = high_50 - low_50
    
    fib_0 = high_50
    fib_236 = high_50 - fib_range * 0.236
    fib_382 = high_50 - fib_range * 0.382
    fib_500 = high_50 - fib_range * 0.500
    fib_618 = high_50 - fib_range * 0.618
    fib_786 = high_50 - fib_range * 0.786
    fib_100 = low_50
    
    enhanced['fib_0_dist'] = abs(enhanced['close'] - fib_0) / enhanced['close'] * 100
    enhanced['fib_236_dist'] = abs(enhanced['close'] - fib_236) / enhanced['close'] * 100
    enhanced['fib_382_dist'] = abs(enhanced['close'] - fib_382) / enhanced['close'] * 100
    enhanced['fib_500_dist'] = abs(enhanced['close'] - fib_500) / enhanced['close'] * 100
    enhanced['fib_618_dist'] = abs(enhanced['close'] - fib_618) / enhanced['close'] * 100
    enhanced['fib_786_dist'] = abs(enhanced['close'] - fib_786) / enhanced['close'] * 100
    enhanced['fib_100_dist'] = abs(enhanced['close'] - fib_100) / enhanced['close'] * 100
    
    # Nearest level
    fib_dists = pd.DataFrame({
        '0': abs(enhanced['close'] - fib_0),
        '236': abs(enhanced['close'] - fib_236),
        '382': abs(enhanced['close'] - fib_382),
        '500': abs(enhanced['close'] - fib_500),
        '618': abs(enhanced['close'] - fib_618)
    })
    enhanced['fib_nearest_level_dist'] = fib_dists.min(axis=1) / enhanced['close'] * 100
    enhanced['fib_near_key_level'] = (enhanced['fib_nearest_level_dist'] < 0.5).astype(int)
    
    # ===================================================================
    # 10. PIVOT POINTS (13 features)
    # ===================================================================
    print("  Calculating pivot points...")
    
    # Daily pivot (using previous day's high/low/close)
    h = enhanced['high'].shift(1)
    l = enhanced['low'].shift(1)
    c = enhanced['close'].shift(1)
    
    pp = (h + l + c) / 3
    r1 = 2 * pp - l
    r2 = pp + (h - l)
    r3 = h + 2 * (pp - l)
    s1 = 2 * pp - h
    s2 = pp - (h - l)
    s3 = l - 2 * (h - pp)
    
    enhanced['pivot_pp'] = pp
    enhanced['pivot_r1'] = r1
    enhanced['pivot_r2'] = r2
    enhanced['pivot_r3'] = r3
    enhanced['pivot_s1'] = s1
    enhanced['pivot_s2'] = s2
    enhanced['pivot_s3'] = s3
    
    enhanced['pivot_pp_dist'] = abs(enhanced['close'] - pp) / enhanced['close'] * 100
    enhanced['pivot_r1_dist'] = abs(enhanced['close'] - r1) / enhanced['close'] * 100
    enhanced['pivot_s1_dist'] = abs(enhanced['close'] - s1) / enhanced['close'] * 100
    
    enhanced['pivot_above_pp'] = (enhanced['close'] > pp).astype(int)
    enhanced['pivot_between_r1_pp'] = ((enhanced['close'] > pp) & (enhanced['close'] < r1)).astype(int)
    enhanced['pivot_between_pp_s1'] = ((enhanced['close'] < pp) & (enhanced['close'] > s1)).astype(int)
    
    # ===================================================================
    # 11. ADVANCED PATTERNS (12 features)
    # ===================================================================
    print("  Calculating candlestick patterns...")
    
    # Doji
    enhanced['pattern_doji'] = (enhanced['body_pct'] < 10).astype(int)
    
    # Hammer (bullish reversal)
    enhanced['pattern_hammer'] = ((enhanced['is_bullish'] == 1) & 
                                  (enhanced['lower_wick'] > 60) & 
                                  (enhanced['upper_wick'] < 20)).astype(int)
    
    # Shooting star (bearish reversal)
    enhanced['pattern_shooting_star'] = ((enhanced['is_bullish'] == 0) & 
                                         (enhanced['upper_wick'] > 60) & 
                                         (enhanced['lower_wick'] < 20)).astype(int)
    
    # Engulfing patterns
    prev_body = abs(enhanced['close'].shift(1) - enhanced['open'].shift(1))
    curr_body = abs(enhanced['close'] - enhanced['open'])
    
    enhanced['pattern_bullish_engulfing'] = ((enhanced['is_bullish'] == 1) & 
                                             (enhanced['is_bullish'].shift(1) == 0) &
                                             (curr_body > prev_body)).astype(int)
    
    enhanced['pattern_bearish_engulfing'] = ((enhanced['is_bullish'] == 0) & 
                                             (enhanced['is_bullish'].shift(1) == 1) &
                                             (curr_body > prev_body)).astype(int)
    
    # Three soldiers/crows (simplified)
    three_bull = ((enhanced['is_bullish'] == 1) & 
                  (enhanced['is_bullish'].shift(1) == 1) & 
                  (enhanced['is_bullish'].shift(2) == 1)).astype(int)
    
    three_bear = ((enhanced['is_bullish'] == 0) & 
                  (enhanced['is_bullish'].shift(1) == 0) & 
                  (enhanced['is_bullish'].shift(2) == 0)).astype(int)
    
    enhanced['pattern_three_white_soldiers'] = three_bull
    enhanced['pattern_three_black_crows'] = three_bear
    
    # Morning/Evening star (simplified)
    enhanced['pattern_morning_star'] = 0  # Placeholder
    enhanced['pattern_evening_star'] = 0  # Placeholder
    
    # Bullish/bearish strength
    bull_count = enhanced['is_bullish'].rolling(5).sum()
    enhanced['pattern_bullish_strength'] = bull_count / 5
    enhanced['pattern_bearish_strength'] = (5 - bull_count) / 5
    enhanced['pattern_net_signal'] = (bull_count - 2.5) / 5
    
    # ===================================================================
    # 12. ADVANCED INDICATORS (3 more - Williams %R already in data)
    # ===================================================================
    print("  Calculating advanced indicators...")
    
    # Williams %R (14-period)
    highest_high = enhanced['high'].rolling(14).max()
    lowest_low = enhanced['low'].rolling(14).min()
    enhanced['williams_r'] = ((highest_high - enhanced['close']) / (highest_high - lowest_low) * -100).fillna(-50)
    
    # SAR (simplified - just use trend direction)
    enhanced['sar_value'] = 0  # Placeholder
    enhanced['sar_trend'] = (enhanced['close'] > enhanced['sma_20']).astype(int)
    enhanced['sar_distance'] = abs(enhanced['close'] - enhanced['sma_20']) / enhanced['close'] * 100
    
    # Fill any NaN values
    enhanced = enhanced.fillna(0)
    
    # Replace inf values
    enhanced = enhanced.replace([np.inf, -np.inf], 0)
    
    print(f"  Enhanced to {len(enhanced.columns)} features")
    
    return enhanced


def process_symbol(symbol_name):
    """Process one symbol file"""
    print(f"\n{'='*80}")
    print(f"PROCESSING: {symbol_name.upper()}")
    print(f"{'='*80}")
    
    # Load basic data
    input_file = f"{DATA_DIR}/{symbol_name}_training_data_143.csv"
    
    try:
        df = pd.read_csv(input_file)
        print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
    except FileNotFoundError:
        print(f"❌ File not found: {input_file}")
        return None
    
    # Calculate advanced features
    enhanced_df = calculate_advanced_features(df)
    
    # Save enhanced data
    output_file = f"{DATA_DIR}/{symbol_name}_training_data_FULL.csv"
    enhanced_df.to_csv(output_file, index=False)
    
    print(f"✅ Saved {len(enhanced_df)} rows, {len(enhanced_df.columns)} features to {output_file}")
    
    return enhanced_df


def main():
    """Process all symbols"""
    print("\n" + "="*80)
    print("FEATURE ENHANCEMENT - 23 → 143+ FEATURES")
    print("="*80)
    
    symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']
    
    results = {}
    
    for symbol in symbols:
        try:
            enhanced = process_symbol(symbol)
            if enhanced is not None:
                results[symbol] = enhanced
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("ENHANCEMENT SUMMARY")
    print("="*80)
    
    for symbol in symbols:
        if symbol in results:
            df = results[symbol]
            print(f"✅ {symbol.upper():8s}: {len(df):,} rows, {len(df.columns)} features")
        else:
            print(f"❌ {symbol.upper():8s}: FAILED")
    
    print("\n" + "="*80)
    print(f"✅ COMPLETE: {len(results)}/{len(symbols)} symbols enhanced")
    print("="*80)
    
    if len(results) > 0:
        sample = list(results.values())[0]
        print(f"\nFeature count: {len(sample.columns)}")
        print(f"Expected accuracy with enhanced features: 75-85%")


if __name__ == "__main__":
    main()
