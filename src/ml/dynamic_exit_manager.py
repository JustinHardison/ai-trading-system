"""
Dynamic Exit Manager - ML-Driven Position Management
NO FIXED STOP LOSS OR TAKE PROFIT

The ML model decides on EVERY TICK whether to:
- HOLD: Keep position open
- TAKE_PROFIT: Close with profit
- STOP_LOSS: Cut losses
- TRAIL_STOP: Move stop to breakeven or trailing

Based on:
- Current profit/loss
- Market momentum
- Volatility changes
- Time in trade
- LLM market context
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from datetime import datetime


class DynamicExitManager:
    """
    Manages position exits dynamically using ML predictions
    
    NO FIXED LEVELS - Every decision is based on current market conditions
    """
    
    def __init__(self):
        self.positions = {}  # Track open positions
        
    def should_exit(
        self,
        position_id: int,
        entry_price: float,
        current_price: float,
        direction: str,
        bars_held: int,
        m1_bars: pd.DataFrame,
        ml_exit_model,
        llm_regime: str = "unknown",
        llm_bias: str = "neutral"
    ) -> Tuple[str, float, str]:
        """
        Decide if position should exit based on ML + market conditions
        
        Args:
            position_id: Position ticket
            entry_price: Entry price
            current_price: Current price
            direction: 'BUY' or 'SELL'
            bars_held: Bars held
            m1_bars: Recent M1 bars
            ml_exit_model: Trained exit model
            llm_regime: Cached LLM regime
            llm_bias: Cached LLM bias
            
        Returns:
            (action, confidence, reason)
            action: 'HOLD', 'TAKE_PROFIT', 'STOP_LOSS', 'TRAIL_STOP'
        """
        # Calculate current P/L
        if direction == 'BUY':
            profit_points = current_price - entry_price
        else:  # SELL
            profit_points = entry_price - current_price
        
        profit_pct = (profit_points / entry_price) * 100 if entry_price > 0 else 0
        
        # ================================================================
        # RULE 1: EMERGENCY EXITS (Hard Rules - Override ML)
        # ================================================================
        
        # Emergency stop: -2% loss (catastrophic)
        if profit_pct < -2.0:
            return 'STOP_LOSS', 100.0, 'Emergency stop: -2% loss'
        
        # Time-based exit: Held too long (>30 bars = 30 minutes on M1)
        if bars_held > 30:
            if profit_points > 0:
                return 'TAKE_PROFIT', 90.0, 'Time exit: 30+ bars held with profit'
            else:
                return 'STOP_LOSS', 90.0, 'Time exit: 30+ bars held with loss'
        
        # ================================================================
        # RULE 2: DYNAMIC PROFIT PROTECTION
        # ================================================================
        
        # If profit > 1%, protect it
        if profit_pct > 1.0:
            # Check if momentum is reversing
            if len(m1_bars) >= 5:
                recent_close = m1_bars['close'].tail(5).values
                momentum = (recent_close[-1] - recent_close[0]) / recent_close[0]
                
                # If we're in profit but momentum is reversing, take profit
                if direction == 'BUY' and momentum < -0.001:  # Downward momentum
                    return 'TAKE_PROFIT', 85.0, f'Profit protection: {profit_pct:.2f}% + reversal detected'
                elif direction == 'SELL' and momentum > 0.001:  # Upward momentum
                    return 'TAKE_PROFIT', 85.0, f'Profit protection: {profit_pct:.2f}% + reversal detected'
        
        # ================================================================
        # RULE 3: VOLATILITY-BASED EXITS
        # ================================================================
        
        if len(m1_bars) >= 20:
            # Calculate current volatility
            recent_high = m1_bars['high'].tail(20).max()
            recent_low = m1_bars['low'].tail(20).min()
            current_atr = recent_high - recent_low
            
            # If volatility spike and we're in profit, take it
            if profit_pct > 0.3:  # Any profit
                # Check if we're near the edge of recent range
                price_position = (current_price - recent_low) / (recent_high - recent_low) if (recent_high - recent_low) > 0 else 0.5
                
                if direction == 'BUY' and price_position > 0.9:  # Near top of range
                    return 'TAKE_PROFIT', 80.0, f'Volatility exit: Near range top with {profit_pct:.2f}% profit'
                elif direction == 'SELL' and price_position < 0.1:  # Near bottom of range
                    return 'TAKE_PROFIT', 80.0, f'Volatility exit: Near range bottom with {profit_pct:.2f}% profit'
        
        # ================================================================
        # RULE 4: LLM CONTEXT-BASED EXITS
        # ================================================================
        
        # If LLM regime changed against us, exit
        if direction == 'BUY' and llm_bias == 'bearish' and profit_pct > 0:
            return 'TAKE_PROFIT', 75.0, f'LLM regime shift: Bearish bias, taking {profit_pct:.2f}% profit'
        elif direction == 'SELL' and llm_bias == 'bullish' and profit_pct > 0:
            return 'TAKE_PROFIT', 75.0, f'LLM regime shift: Bullish bias, taking {profit_pct:.2f}% profit'
        
        # ================================================================
        # RULE 5: ML MODEL DECISION (Primary)
        # ================================================================
        
        # Extract exit features
        from src.ml.tick_feature_engineer import TickFeatureEngineer
        feature_engineer = TickFeatureEngineer()
        
        features = feature_engineer.extract_exit_features(
            entry_price=entry_price,
            current_price=current_price,
            direction=direction,
            bars_held=bars_held,
            m1_bars=m1_bars
        )
        
        # ML prediction
        features_df = pd.DataFrame([features])
        
        if ml_exit_model:
            try:
                prediction = ml_exit_model['model'].predict(features_df)[0]
                probabilities = ml_exit_model['model'].predict_proba(features_df)[0]
                confidence = float(max(probabilities)) * 100
                
                # Map prediction: 0=HOLD, 1=TAKE_PROFIT, 2=STOP_LOSS
                action_map = {0: 'HOLD', 1: 'TAKE_PROFIT', 2: 'STOP_LOSS'}
                ml_action = action_map.get(int(prediction), 'HOLD')
                
                # Require high confidence for exits
                if ml_action == 'TAKE_PROFIT' and confidence >= 60.0:
                    return 'TAKE_PROFIT', confidence, f'ML exit: {confidence:.1f}% confident to take {profit_pct:.2f}% profit'
                elif ml_action == 'STOP_LOSS' and confidence >= 65.0:
                    return 'STOP_LOSS', confidence, f'ML exit: {confidence:.1f}% confident to cut {profit_pct:.2f}% loss'
                
            except Exception as e:
                # ML failed, use rules
                pass
        
        # ================================================================
        # DEFAULT: HOLD
        # ================================================================
        
        return 'HOLD', 50.0, f'Holding: {profit_pct:.2f}% P/L, {bars_held} bars'
    
    def get_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        direction: str,
        max_profit_seen: float
    ) -> float:
        """
        Calculate dynamic trailing stop based on max profit seen
        
        Args:
            entry_price: Entry price
            current_price: Current price
            direction: 'BUY' or 'SELL'
            max_profit_seen: Maximum profit in points seen so far
            
        Returns:
            Trailing stop price
        """
        # Trail stop at 50% of max profit
        trail_distance = max_profit_seen * 0.5
        
        if direction == 'BUY':
            # Trail stop below current price
            return current_price - trail_distance
        else:  # SELL
            # Trail stop above current price
            return current_price + trail_distance
    
    def should_move_to_breakeven(
        self,
        entry_price: float,
        current_price: float,
        direction: str,
        profit_pct: float
    ) -> bool:
        """
        Decide if stop should be moved to breakeven
        
        Args:
            entry_price: Entry price
            current_price: Current price
            direction: 'BUY' or 'SELL'
            profit_pct: Current profit percentage
            
        Returns:
            True if should move to breakeven
        """
        # Move to breakeven at 0.5% profit
        return profit_pct >= 0.5
