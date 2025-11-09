#!/usr/bin/env python3
"""
Train ML/RL from LIVE MT5 Data
Fetches data directly from MT5 terminal via Python API
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import pickle
import sys

sys.path.insert(0, '/Users/justinhardison/ai-trading-system')

from src.ml.pro_feature_engineer import ProFeatureEngineer
from src.ml.pro_ensemble import ProEnsembleTrainer
from src.ml.reinforcement_learning import TradingRLAgent, StateEncoder
from src.utils.logger import get_logger
from sklearn.model_selection import train_test_split

logger = get_logger(__name__)


def simulate_llm_context(df: pd.DataFrame, idx: int) -> dict:
    """Simulate LLM context based on market conditions"""
    recent_bars = df.iloc[max(0, idx-50):idx+1]

    if len(recent_bars) < 20:
        return {'regime': 'unknown', 'bias': 'neutral', 'risk_level': 1.0}

    close = recent_bars['close'].values
    high = recent_bars['high'].values
    low = recent_bars['low'].values

    # Detect regime
    atr = (high[-20:] - low[-20:]).mean()
    price_range = close[-20:].max() - close[-20:].min()

    if atr > price_range * 0.8:
        regime = 'volatile'
    elif price_range < close[-1] * 0.01:
        regime = 'ranging'
    else:
        sma_20 = close[-20:].mean()
        if close[-1] > sma_20 * 1.005:
            regime = 'trending_up'
        elif close[-1] < sma_20 * 0.995:
            regime = 'trending_down'
        else:
            regime = 'ranging'

    # Detect bias
    momentum = (close[-1] - close[-10]) / close[-10]
    if momentum > 0.002:
        bias = 'bullish'
    elif momentum < -0.002:
        bias = 'bearish'
    else:
        bias = 'neutral'

    # Risk level
    volatility = close[-20:].std() / close[-20:].mean()
    if volatility > 0.015:
        risk_level = 0.5
    elif volatility < 0.005:
        risk_level = 1.5
    else:
        risk_level = 1.0

    return {
        'regime': regime,
        'bias': bias,
        'risk_level': risk_level
    }


def create_integrated_features(technical_features: dict, llm_context: dict) -> dict:
    """Combine technical features with LLM context"""
    integrated = technical_features.copy()

    # LLM regime features
    integrated['llm_regime_volatile'] = 1 if llm_context['regime'] == 'volatile' else 0
    integrated['llm_regime_ranging'] = 1 if llm_context['regime'] == 'ranging' else 0
    integrated['llm_regime_trending_up'] = 1 if llm_context['regime'] == 'trending_up' else 0
    integrated['llm_regime_trending_down'] = 1 if llm_context['regime'] == 'trending_down' else 0

    # LLM bias features
    integrated['llm_bias_bullish'] = 1 if llm_context['bias'] == 'bullish' else 0
    integrated['llm_bias_bearish'] = 1 if llm_context['bias'] == 'bearish' else 0
    integrated['llm_bias_neutral'] = 1 if llm_context['bias'] == 'neutral' else 0

    # LLM risk level
    integrated['llm_risk_level'] = llm_context['risk_level']

    # Interaction features
    if llm_context['regime'] == 'trending_up' and llm_context['bias'] == 'bullish':
        integrated['llm_trend_aligned'] = 1
    else:
        integrated['llm_trend_aligned'] = 0

    if llm_context['regime'] == 'ranging' and abs(technical_features.get('roc_5', 0)) < 0.001:
        integrated['llm_range_confirmed'] = 1
    else:
        integrated['llm_range_confirmed'] = 0

    return integrated


def create_labels(df: pd.DataFrame, profit_target: float = 40.0, forward_bars: int = 5) -> np.ndarray:
    """Create scalping labels based on forward price movement"""
    labels = []

    for i in range(len(df) - forward_bars):
        current_price = df['close'].iloc[i]
        future_high = df['high'].iloc[i+1:i+forward_bars+1].max()
        future_low = df['low'].iloc[i+1:i+forward_bars+1].min()

        up_move = future_high - current_price
        down_move = current_price - future_low

        # Label as BUY if up move > target and dominates
        if up_move >= profit_target and up_move > down_move * 1.2:
            labels.append(1)  # BUY
        # Label as SELL if down move > target and dominates
        elif down_move >= profit_target and down_move > up_move * 1.2:
            labels.append(2)  # SELL
        else:
            labels.append(0)  # HOLD

    # Pad end with HOLD
    labels.extend([0] * forward_bars)
    return np.array(labels)


def fetch_mt5_data(symbol: str = "US30Z25.sim", days: int = 90) -> pd.DataFrame:
    """Fetch historical data from MT5"""
    logger.info("="*70)
    logger.info("FETCHING DATA FROM MT5 TERMINAL")
    logger.info("="*70)

    # Initialize MT5
    if not mt5.initialize():
        logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
        return None

    logger.info(f"✓ MT5 connected: {mt5.terminal_info()}")
    logger.info(f"  Account: {mt5.account_info().login}")
    logger.info(f"  Server: {mt5.account_info().server}")

    # Calculate date range
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    logger.info(f"\n📊 Fetching {symbol} M1 data...")
    logger.info(f"  Period: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
    logger.info(f"  Days: {days}")

    # Fetch M1 bars
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, from_date, to_date)

    if rates is None or len(rates) == 0:
        logger.error(f"Failed to fetch data: {mt5.last_error()}")
        mt5.shutdown()
        return None

    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Rename columns
    df = df.rename(columns={
        'tick_volume': 'volume'
    })

    logger.info(f"✓ Fetched {len(df):,} M1 bars")
    logger.info(f"  Period: {df['time'].min()} to {df['time'].max()}")
    logger.info(f"  Price range: {df['close'].min():.2f} - {df['close'].max():.2f}")

    # Save to CSV for backup
    csv_file = 'us30_mt5_training_data.csv'
    df.to_csv(csv_file, index=False)
    logger.info(f"✓ Saved backup to {csv_file}")

    mt5.shutdown()
    return df


def main():
    """Main training pipeline"""
    logger.info("\n" + "="*70)
    logger.info("TRAINING ML/RL FROM LIVE MT5 DATA")
    logger.info("="*70)

    # 1. Fetch data from MT5
    df = fetch_mt5_data(symbol="US30Z25.sim", days=90)

    if df is None or len(df) < 10000:
        logger.error(f"Insufficient data: {len(df) if df is not None else 0} bars")
        logger.error("Need at least 10,000 bars for training")
        return

    # 2. Extract features with LLM integration
    logger.info("\n[2/5] Extracting integrated features...")
    feature_engineer = ProFeatureEngineer()

    features_list = []
    valid_indices = []

    for i in range(100, len(df) - 10):
        try:
            # Get technical features
            technical_features = feature_engineer.extract_all_features(df, i)
            if not technical_features:
                continue

            # Get LLM context
            llm_context = simulate_llm_context(df, i)

            # Integrate
            integrated_features = create_integrated_features(technical_features, llm_context)

            features_list.append(integrated_features)
            valid_indices.append(i)

        except Exception as e:
            continue

        if i % 5000 == 0:
            logger.info(f"  Processed {i:,}/{len(df):,} bars...")

    X = pd.DataFrame(features_list)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    logger.info(f"✓ Extracted {len(X):,} samples with {len(X.columns)} features")
    logger.info(f"  Technical: {len(X.columns) - 10}")
    logger.info(f"  LLM: 10")
    logger.info(f"  Total: {len(X.columns)}")

    # 3. Create labels
    logger.info("\n[3/5] Creating scalping labels...")
    all_labels = create_labels(df, profit_target=40.0, forward_bars=5)
    y = all_labels[valid_indices]

    logger.info(f"  Label distribution:")
    logger.info(f"    HOLD: {sum(y==0):,} ({sum(y==0)/len(y)*100:.1f}%)")
    logger.info(f"    BUY:  {sum(y==1):,} ({sum(y==1)/len(y)*100:.1f}%)")
    logger.info(f"    SELL: {sum(y==2):,} ({sum(y==2)/len(y)*100:.1f}%)")

    # 4. Train ensemble
    logger.info("\n[4/5] Training ensemble on integrated features...")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    ensemble_trainer = ProEnsembleTrainer()
    ensemble_result = ensemble_trainer.train_ensemble(X_train, y_train, X_val, y_val)

    logger.info(f"\n✓ Ensemble trained!")
    logger.info(f"  XGBoost accuracy: {ensemble_result.get('xgb_accuracy', 0):.2%}")
    logger.info(f"  LightGBM accuracy: {ensemble_result.get('lgb_accuracy', 0):.2%}")
    logger.info(f"  Ensemble accuracy: {ensemble_result.get('ensemble_accuracy', 0):.2%}")

    # 5. Train RL agent
    logger.info("\n[5/5] Training RL agent...")
    rl_agent = TradingRLAgent(state_size=20, action_size=3)

    trades_simulated = 0
    for i in range(len(X_val)):
        try:
            state = StateEncoder.encode_state(X_val.iloc[i].to_dict())
            pred, conf = ensemble_trainer.predict(X_val.iloc[i:i+1])

            if pred[0] > 0:  # If not HOLD
                actual = y_val.iloc[i] if hasattr(y_val, 'iloc') else y_val[i]

                # Simulate profit based on prediction accuracy
                if actual == pred[0]:
                    profit_pct = np.random.uniform(0.3, 0.8)
                else:
                    profit_pct = np.random.uniform(-0.4, -0.1)

                bars_held = np.random.randint(3, 15)
                volatility = X_val.iloc[i].get('atr_pct', 0.5)

                reward = rl_agent.calculate_reward(profit_pct, bars_held, volatility)
                rl_agent.update_stats(profit_pct)

                if i < len(X_val) - 1:
                    next_state = StateEncoder.encode_state(X_val.iloc[i+1].to_dict())
                    rl_agent.remember(state, pred[0], reward, next_state, False)
                    rl_agent.replay(batch_size=32)

                trades_simulated += 1
        except Exception as e:
            continue

    logger.info(f"✓ RL agent trained on {trades_simulated:,} simulated trades")

    # 6. Save models
    logger.info("\n[6/6] Saving models...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save ensemble
    ensemble_file = f"models/integrated_ensemble_{timestamp}.pkl"
    ensemble_data = {
        'xgb_model': ensemble_result['xgb_model'],
        'lgb_model': ensemble_result['lgb_model'],
        'nn_model': ensemble_result.get('nn_model'),
        'ensemble_weights': ensemble_result['ensemble_weights'],
        'feature_names': list(X.columns),
        'xgb_metrics': {'accuracy': ensemble_result.get('xgb_accuracy', 0)},
        'lgb_metrics': {'accuracy': ensemble_result.get('lgb_accuracy', 0)},
        'nn_metrics': {'accuracy': ensemble_result.get('nn_accuracy', 0)},
        'ensemble_accuracy': ensemble_result.get('ensemble_accuracy', 0),
        'timestamp': datetime.now().isoformat(),
        'integration_type': 'ml_llm_unified',
        'feature_count': len(X.columns),
        'llm_features': [
            'llm_regime_volatile', 'llm_regime_ranging', 'llm_regime_trending_up',
            'llm_regime_trending_down', 'llm_bias_bullish', 'llm_bias_bearish',
            'llm_bias_neutral', 'llm_risk_level', 'llm_trend_aligned', 'llm_range_confirmed'
        ],
        'training_samples': len(X_train),
        'validation_samples': len(X_val),
        'data_source': 'MT5_LIVE',
        'symbol': 'US30Z25.sim',
        'timeframe': 'M1',
        'training_days': 90
    }

    with open(ensemble_file, 'wb') as f:
        pickle.dump(ensemble_data, f)

    # Create symlink to latest
    latest_link = Path('models/integrated_ensemble_latest.pkl')
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(Path(ensemble_file).name)

    logger.info(f"✓ Ensemble saved: {ensemble_file}")
    logger.info(f"✓ Symlink updated: models/integrated_ensemble_latest.pkl")

    # Save RL agent
    rl_file = f"models/integrated_rl_{timestamp}.pkl"
    rl_agent.save(rl_file)

    rl_latest = Path('models/integrated_rl_latest.pkl')
    if rl_latest.exists():
        rl_latest.unlink()
    rl_latest.symlink_to(Path(rl_file).name)

    logger.info(f"✓ RL agent saved: {rl_file}")
    logger.info(f"✓ Symlink updated: models/integrated_rl_latest.pkl")

    # Print summary
    logger.info("\n" + "="*70)
    logger.info("TRAINING COMPLETE!")
    logger.info("="*70)
    logger.info(f"Data source: MT5 LIVE (US30Z25.sim M1)")
    logger.info(f"Training samples: {len(X_train):,}")
    logger.info(f"Validation samples: {len(X_val):,}")
    logger.info(f"Features: {len(X.columns)} (technical + LLM integrated)")
    logger.info(f"Ensemble accuracy: {ensemble_result.get('ensemble_accuracy', 0):.2%}")
    logger.info(f"RL trades simulated: {trades_simulated:,}")
    logger.info(f"\nModels saved:")
    logger.info(f"  {ensemble_file}")
    logger.info(f"  {rl_file}")
    logger.info("\n🚀 Ready to use with ml_api_integrated.py!")
    logger.info("="*70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Training interrupted by user")
    except Exception as e:
        logger.error(f"\n\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
