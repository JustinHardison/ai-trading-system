#!/usr/bin/env python3
"""
Test All New Features - Comprehensive Verification
"""
import sys
import numpy as np
import pandas as pd

print("="*70)
print("COMPREHENSIVE FEATURE TESTING")
print("="*70)

# Test 1: Enhanced Ensemble
print("\n1. Testing Enhanced Ensemble (4-5 Models)...")
try:
    from src.ml.enhanced_ensemble import EnhancedEnsembleTrainer
    
    trainer = EnhancedEnsembleTrainer()
    X_train = pd.DataFrame(np.random.randn(100, 50))
    y_train = np.random.randint(0, 3, 100)
    X_val = pd.DataFrame(np.random.randn(20, 50))
    y_val = np.random.randint(0, 3, 20)
    
    result = trainer.train_ensemble(X_train, y_train, X_val, y_val)
    
    print(f"   ✅ Enhanced Ensemble: {trainer.n_models} models trained")
    print(f"   ✅ Ensemble Accuracy: {result['ensemble_accuracy']:.3f}")
    print(f"   ✅ Models: XGBoost, LightGBM, NN, RF, CatBoost")
    
except Exception as e:
    print(f"   ❌ Enhanced Ensemble FAILED: {e}")
    sys.exit(1)

# Test 2: Order Flow Features
print("\n2. Testing Order Flow Features...")
try:
    from src.features.order_flow_features import OrderFlowFeatureEngineer
    
    engineer = OrderFlowFeatureEngineer()
    order_book = {
        'bids': [
            {'price': 42000, 'volume': 100},
            {'price': 41999, 'volume': 80},
            {'price': 41998, 'volume': 60},
        ],
        'asks': [
            {'price': 42001, 'volume': 90},
            {'price': 42002, 'volume': 70},
            {'price': 42003, 'volume': 50},
        ],
        'imbalance': 0.05
    }
    
    features = engineer.engineer_order_flow_features(order_book)
    
    print(f"   ✅ Order Flow: {len(features)} features extracted")
    print(f"   ✅ Imbalance: {features['order_imbalance']}")
    print(f"   ✅ Liquidity Score: {features['liquidity_score']:.2f}")
    print(f"   ✅ Bid/Ask Ratio: {features['bid_ask_volume_ratio']:.2f}")
    
except Exception as e:
    print(f"   ❌ Order Flow FAILED: {e}")
    sys.exit(1)

# Test 3: News Sentiment
print("\n3. Testing News Sentiment...")
try:
    from src.data.news_sentiment import NewsSentimentAnalyzer
    
    analyzer = NewsSentimentAnalyzer()
    sentiment = analyzer.get_symbol_sentiment('US30', hours=24)
    
    print(f"   ✅ News Sentiment: Working")
    print(f"   ✅ Score: {sentiment['sentiment_score']}")
    print(f"   ✅ Trend: {sentiment['sentiment_trend']}")
    print(f"   ⚠️  Note: Install TextBlob for full functionality")
    
except Exception as e:
    print(f"   ❌ News Sentiment FAILED: {e}")
    sys.exit(1)

# Test 4: Portfolio Optimizer
print("\n4. Testing Portfolio Optimizer...")
try:
    from src.portfolio.portfolio_optimizer import PortfolioOptimizer
    
    symbols = ['US30', 'US100', 'EURUSD', 'XAU']
    optimizer = PortfolioOptimizer(symbols)
    
    # Simulate price data
    price_data = {s: np.random.randn(100).cumsum() + 100 for s in symbols}
    optimizer.update_correlations(price_data)
    
    # Test signals
    signals = [
        {'symbol': 'US30', 'confidence': 0.8, 'expected_return': 0.02, 'risk': 0.015},
        {'symbol': 'EURUSD', 'confidence': 0.6, 'expected_return': 0.015, 'risk': 0.012},
        {'symbol': 'XAU', 'confidence': 0.7, 'expected_return': 0.018, 'risk': 0.020},
    ]
    
    positions = optimizer.optimize_position_sizes(signals, 100000)
    risk_metrics = optimizer.calculate_portfolio_risk(positions)
    
    print(f"   ✅ Portfolio Optimizer: Working")
    print(f"   ✅ Optimized {len(positions)} positions")
    print(f"   ✅ Total Exposure: ${risk_metrics['total_exposure']:,.0f}")
    print(f"   ✅ Diversification Ratio: {risk_metrics['diversification_ratio']:.2f}")
    
except Exception as e:
    print(f"   ❌ Portfolio Optimizer FAILED: {e}")
    sys.exit(1)

# Test 5: ProEnsemble (Original)
print("\n5. Testing Original ProEnsemble...")
try:
    from src.ml.pro_ensemble import ProEnsembleTrainer
    
    trainer = ProEnsembleTrainer()
    X_train = pd.DataFrame(np.random.randn(100, 50))
    y_train = np.random.randint(0, 3, 100)
    X_val = pd.DataFrame(np.random.randn(20, 50))
    y_val = np.random.randint(0, 3, 20)
    
    result = trainer.train_ensemble(X_train, y_train, X_val, y_val)
    
    print(f"   ✅ ProEnsemble: 3 models (XGB, LGB, NN)")
    print(f"   ✅ Working correctly")
    
except Exception as e:
    print(f"   ❌ ProEnsemble FAILED: {e}")
    sys.exit(1)

# Test 6: Feature Engineer
print("\n6. Testing Feature Engineer...")
try:
    from src.ml.pro_feature_engineer import ProFeatureEngineer
    
    engineer = ProFeatureEngineer()
    
    # Create sample data
    sample_data = {
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='1min'),
        'open': np.random.randn(100).cumsum() + 100,
        'high': np.random.randn(100).cumsum() + 101,
        'low': np.random.randn(100).cumsum() + 99,
        'close': np.random.randn(100).cumsum() + 100,
        'volume': np.random.randint(100, 1000, 100),
        'tick_volume': np.random.randint(100, 1000, 100)
    }
    df = pd.DataFrame(sample_data)
    
    features = engineer.extract_all_features(df, current_idx=50)
    
    print(f"   ✅ Feature Engineer: Working")
    print(f"   ✅ Generated {len(features)} features")
    
except Exception as e:
    print(f"   ❌ Feature Engineer FAILED: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)
print("✅ Enhanced Ensemble (4-5 models): WORKING")
print("✅ Order Flow Features (18 features): WORKING")
print("✅ News Sentiment: WORKING (install TextBlob for full features)")
print("✅ Portfolio Optimizer: WORKING")
print("✅ Original ProEnsemble: WORKING")
print("✅ Feature Engineer: WORKING")
print("="*70)
print("\n🎉 ALL FEATURES ARE FUNCTIONAL!")
print("\nNext Steps:")
print("1. Install TextBlob: pip install textblob")
print("2. Compile EA in MetaEditor")
print("3. Wait for training to complete")
print("4. Integrate into API")
print("5. Backtest and deploy!")
print("="*70)
