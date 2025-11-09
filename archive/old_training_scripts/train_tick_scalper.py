#!/usr/bin/env python3
"""
Train Tick-by-Tick Scalping Models for US30
Uses MT5 historical data to train ultra-fast ML models

Entry Model: Predicts BUY/SELL/HOLD on every tick
Exit Model: Predicts HOLD/TAKE_PROFIT/STOP_LOSS for open positions
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime, timedelta
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import yfinance as yf

from src.ml.tick_feature_engineer import TickFeatureEngineer
from src.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_us30_data(symbol: str = "^DJI", days: int = 30):
    """
    Fetch US30 (Dow Jones) M1 and M5 data from yfinance
    
    Args:
        symbol: Trading symbol (^DJI for Dow Jones)
        days: Number of days of history
        
    Returns:
        Tuple of (m1_df, m5_df)
    """
    logger.info(f"Fetching {days} days of Dow Jones data from yfinance...")
    
    # Fetch 1-minute data (M1)
    ticker = yf.Ticker(symbol)
    m1_df = ticker.history(period=f"{days}d", interval="1m")
    
    if m1_df.empty:
        logger.error("Failed to fetch M1 data")
        return None, None
    
    # Rename columns to match MT5 format
    m1_df.columns = m1_df.columns.str.lower()
    m1_df = m1_df.rename(columns={'volume': 'tick_volume'})
    m1_df = m1_df.reset_index()
    if 'Datetime' in m1_df.columns:
        m1_df = m1_df.rename(columns={'Datetime': 'time'})
    elif 'index' in m1_df.columns:
        m1_df = m1_df.rename(columns={'index': 'time'})
    
    logger.info(f"✓ Fetched {len(m1_df)} M1 bars")
    
    # Fetch 5-minute data (M5)
    m5_df = ticker.history(period=f"{days}d", interval="5m")
    
    if m5_df.empty:
        logger.warning("Failed to fetch M5 data, using M1 only")
        return m1_df, None
    
    m5_df.columns = m5_df.columns.str.lower()
    m5_df = m5_df.rename(columns={'volume': 'tick_volume'})
    m5_df = m5_df.reset_index()
    if 'Datetime' in m5_df.columns:
        m5_df = m5_df.rename(columns={'Datetime': 'time'})
    elif 'index' in m5_df.columns:
        m5_df = m5_df.rename(columns={'index': 'time'})
    
    logger.info(f"✓ Fetched {len(m5_df)} M5 bars")
    
    return m1_df, m5_df


def create_entry_labels(m1_df: pd.DataFrame, forward_bars: int = 5, profit_threshold: float = 50.0):
    """
    Create labels for entry model
    
    Label logic for scalping:
    - BUY (1): If price goes up by profit_threshold points in next forward_bars
    - SELL (2): If price goes down by profit_threshold points in next forward_bars
    - HOLD (0): Otherwise
    
    Args:
        m1_df: M1 DataFrame
        forward_bars: Look ahead this many bars
        profit_threshold: Minimum points move to label as trade
        
    Returns:
        Labels array
    """
    labels = []
    
    for i in range(len(m1_df) - forward_bars):
        current_price = m1_df['close'].iloc[i]
        future_high = m1_df['high'].iloc[i+1:i+forward_bars+1].max()
        future_low = m1_df['low'].iloc[i+1:i+forward_bars+1].min()
        
        up_move = future_high - current_price
        down_move = current_price - future_low
        
        # Label based on which direction has bigger move
        if up_move >= profit_threshold and up_move > down_move:
            labels.append(1)  # BUY
        elif down_move >= profit_threshold and down_move > up_move:
            labels.append(2)  # SELL
        else:
            labels.append(0)  # HOLD
    
    # Pad remaining with HOLD
    labels.extend([0] * forward_bars)
    
    return np.array(labels)


def create_exit_labels(m1_df: pd.DataFrame, entry_price: float, direction: str, 
                       take_profit: float = 60.0, stop_loss: float = 30.0):
    """
    Create labels for exit model
    
    Label logic:
    - TAKE_PROFIT (1): Hit profit target
    - STOP_LOSS (2): Hit stop loss
    - HOLD (0): Neither hit yet
    
    Args:
        m1_df: M1 DataFrame
        entry_price: Entry price
        direction: 'BUY' or 'SELL'
        take_profit: Take profit in points
        stop_loss: Stop loss in points
        
    Returns:
        Labels array
    """
    labels = []
    
    for i in range(len(m1_df)):
        current_price = m1_df['close'].iloc[i]
        
        if direction == 'BUY':
            profit = current_price - entry_price
            if profit >= take_profit:
                labels.append(1)  # TAKE_PROFIT
            elif profit <= -stop_loss:
                labels.append(2)  # STOP_LOSS
            else:
                labels.append(0)  # HOLD
        else:  # SELL
            profit = entry_price - current_price
            if profit >= take_profit:
                labels.append(1)  # TAKE_PROFIT
            elif profit <= -stop_loss:
                labels.append(2)  # STOP_LOSS
            else:
                labels.append(0)  # HOLD
    
    return np.array(labels)


def train_entry_model(m1_df: pd.DataFrame, m5_df: pd.DataFrame):
    """
    Train entry model using tick features
    
    Returns:
        Trained model dict
    """
    logger.info("\n" + "="*70)
    logger.info("TRAINING ENTRY MODEL (Tick-by-Tick Scalping)")
    logger.info("="*70)
    
    feature_engineer = TickFeatureEngineer()
    
    # Create labels (look 5 bars ahead, 50 point threshold)
    labels = create_entry_labels(m1_df, forward_bars=5, profit_threshold=50.0)
    
    # Extract features for each bar
    features_list = []
    valid_indices = []
    
    logger.info("Extracting features from M1 bars...")
    for i in range(50, len(m1_df)):  # Need 50 bars history
        try:
            # Get recent bars
            m1_recent = m1_df.iloc[i-50:i]
            m5_recent = m5_df[m5_df['time'] <= m1_df['time'].iloc[i]].tail(20) if m5_df is not None else None
            
            # Extract features
            features = feature_engineer.extract_tick_features(
                current_price=m1_df['close'].iloc[i],
                bid=m1_df['close'].iloc[i] - 5,  # Approximate bid
                ask=m1_df['close'].iloc[i] + 5,  # Approximate ask
                volume=m1_df['tick_volume'].iloc[i],
                m1_bars=m1_recent,
                m5_bars=m5_recent
            )
            
            features_list.append(features)
            valid_indices.append(i)
            
        except Exception as e:
            continue
    
    # Convert to DataFrame
    X = pd.DataFrame(features_list)
    y = labels[valid_indices]
    
    logger.info(f"✓ Extracted {len(X)} samples with {len(X.columns)} features")
    logger.info(f"  Label distribution: HOLD={sum(y==0)}, BUY={sum(y==1)}, SELL={sum(y==2)}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Train model (Gradient Boosting for speed and accuracy)
    logger.info("\nTraining Gradient Boosting Classifier...")
    model = GradientBoostingClassifier(
        n_estimators=100,  # Fast training
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
        verbose=1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    logger.info(f"\n✓ Entry Model Accuracy: {accuracy*100:.2f}%")
    logger.info("\nClassification Report:")
    logger.info(classification_report(y_test, y_pred, target_names=['HOLD', 'BUY', 'SELL']))
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    logger.info("\nTop 10 Most Important Features:")
    logger.info(feature_importance.head(10).to_string(index=False))
    
    return {
        'model': model,
        'features': list(X.columns),
        'accuracy': accuracy,
        'trained_on': 'US30_M1_tick_scalping',
        'timestamp': datetime.now().isoformat(),
        'label_distribution': {
            'HOLD': int(sum(y==0)),
            'BUY': int(sum(y==1)),
            'SELL': int(sum(y==2))
        }
    }


def train_exit_model(m1_df: pd.DataFrame):
    """
    Train exit model for position management
    
    Returns:
        Trained model dict
    """
    logger.info("\n" + "="*70)
    logger.info("TRAINING EXIT MODEL (Position Management)")
    logger.info("="*70)
    
    feature_engineer = TickFeatureEngineer()
    
    # Simulate trades and create exit labels
    features_list = []
    labels_list = []
    
    logger.info("Simulating trades and extracting exit features...")
    
    # Simulate BUY trades
    for i in range(100, len(m1_df) - 20, 50):  # Every 50 bars, simulate a trade
        entry_price = m1_df['close'].iloc[i]
        
        # Simulate holding for up to 20 bars
        for hold_bars in range(1, min(20, len(m1_df) - i)):
            current_idx = i + hold_bars
            current_price = m1_df['close'].iloc[current_idx]
            
            # Extract exit features
            m1_recent = m1_df.iloc[current_idx-50:current_idx]
            features = feature_engineer.extract_exit_features(
                entry_price=entry_price,
                current_price=current_price,
                direction='BUY',
                bars_held=hold_bars,
                m1_bars=m1_recent
            )
            
            # Create label
            profit = current_price - entry_price
            if profit >= 60:  # Take profit
                label = 1
            elif profit <= -30:  # Stop loss
                label = 2
            else:
                label = 0  # Hold
            
            features_list.append(features)
            labels_list.append(label)
    
    # Simulate SELL trades
    for i in range(100, len(m1_df) - 20, 50):
        entry_price = m1_df['close'].iloc[i]
        
        for hold_bars in range(1, min(20, len(m1_df) - i)):
            current_idx = i + hold_bars
            current_price = m1_df['close'].iloc[current_idx]
            
            m1_recent = m1_df.iloc[current_idx-50:current_idx]
            features = feature_engineer.extract_exit_features(
                entry_price=entry_price,
                current_price=current_price,
                direction='SELL',
                bars_held=hold_bars,
                m1_bars=m1_recent
            )
            
            profit = entry_price - current_price
            if profit >= 60:
                label = 1
            elif profit <= -30:
                label = 2
            else:
                label = 0
            
            features_list.append(features)
            labels_list.append(label)
    
    # Convert to DataFrame
    X = pd.DataFrame(features_list)
    y = np.array(labels_list)
    
    logger.info(f"✓ Extracted {len(X)} samples with {len(X.columns)} features")
    logger.info(f"  Label distribution: HOLD={sum(y==0)}, TAKE_PROFIT={sum(y==1)}, STOP_LOSS={sum(y==2)}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    logger.info("\nTraining Exit Model...")
    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        verbose=1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    logger.info(f"\n✓ Exit Model Accuracy: {accuracy*100:.2f}%")
    logger.info("\nClassification Report:")
    logger.info(classification_report(y_test, y_pred, target_names=['HOLD', 'TAKE_PROFIT', 'STOP_LOSS']))
    
    return {
        'model': model,
        'features': list(X.columns),
        'accuracy': accuracy,
        'trained_on': 'US30_M1_exit_scalping',
        'timestamp': datetime.now().isoformat()
    }


def main():
    """Main training pipeline"""
    logger.info("="*70)
    logger.info("US30 TICK-BY-TICK SCALPING MODEL TRAINING")
    logger.info("="*70)
    
    try:
        # Fetch data from yfinance (Dow Jones = US30)
        # Note: yfinance only allows 7 days of 1-minute data
        m1_df, m5_df = fetch_us30_data(symbol="^DJI", days=7)
        
        if m1_df is None:
            logger.error("Failed to fetch data")
            return
        
        # Train entry model
        entry_model = train_entry_model(m1_df, m5_df)
        
        # Save entry model
        models_dir = Path('models')
        models_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        entry_path = models_dir / f'us30_tick_entry_{timestamp}.pkl'
        
        with open(entry_path, 'wb') as f:
            pickle.dump(entry_model, f)
        
        logger.info(f"\n✓ Entry model saved: {entry_path}")
        
        # Create symlink to latest
        latest_entry = models_dir / 'us30_tick_entry_latest.pkl'
        if latest_entry.exists():
            latest_entry.unlink()
        latest_entry.symlink_to(entry_path.name)
        
        logger.info(f"✓ Symlink created: {latest_entry}")
        
        # Train exit model
        exit_model = train_exit_model(m1_df)
        
        # Save exit model
        exit_path = models_dir / f'us30_tick_exit_{timestamp}.pkl'
        
        with open(exit_path, 'wb') as f:
            pickle.dump(exit_model, f)
        
        logger.info(f"\n✓ Exit model saved: {exit_path}")
        
        # Create symlink to latest
        latest_exit = models_dir / 'us30_tick_exit_latest.pkl'
        if latest_exit.exists():
            latest_exit.unlink()
        latest_exit.symlink_to(exit_path.name)
        
        logger.info(f"✓ Symlink created: {latest_exit}")
        
        logger.info("\n" + "="*70)
        logger.info("TRAINING COMPLETE!")
        logger.info("="*70)
        logger.info(f"Entry Model Accuracy: {entry_model['accuracy']*100:.2f}%")
        logger.info(f"Exit Model Accuracy: {exit_model['accuracy']*100:.2f}%")
        logger.info("\nRestart ml_api_ultimate.py to use new models")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
