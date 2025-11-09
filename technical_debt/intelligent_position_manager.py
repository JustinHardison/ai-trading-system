"""
Intelligent Position Manager - AI-Driven Position Management
Handles DCA, scaling, exits using comprehensive market analysis
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Import EnhancedTradingContext - will be passed as parameter
try:
    from src.ai.enhanced_context import EnhancedTradingContext
except ImportError:
    # Fallback for different import paths
    try:
        from .enhanced_context import EnhancedTradingContext
    except ImportError:
        EnhancedTradingContext = None  # Will handle in code

# Import EV Exit Manager
try:
    from src.ai.ev_exit_manager import EVExitManager
except ImportError:
    try:
        from .ev_exit_manager import EVExitManager
    except ImportError:
        EVExitManager = None

# Import Smart Position Sizer
try:
    from src.ai.smart_position_sizer import get_smart_sizer
except ImportError:
    try:
        from .smart_position_sizer import get_smart_sizer
    except ImportError:
        get_smart_sizer = None


class IntelligentPositionManager:
    """
    AI-driven position management - makes ACTIVE decisions using ALL 100 features
    
    Prevents positions from sitting stuck for hours.
    Uses multi-timeframe data, volume, order book, and market regime
    to make intelligent decisions.
    """
    
    def __init__(self, max_dca_attempts: int = 2):
        self.max_dca_attempts = max_dca_attempts
        self.max_position_size = 10.0  # Max 10 lots per symbol
        
        # Initialize EV Exit Manager
        if EVExitManager is not None:
            self.ev_exit_manager = EVExitManager()
            logger.info(f"🤖 Intelligent Position Manager initialized with EV Exit Manager")
        else:
            self.ev_exit_manager = None
            logger.warning(f"⚠️ EV Exit Manager not available - using legacy logic")
        
        logger.info(f"🤖 Max DCA: {max_dca_attempts}, Max Size: {self.max_position_size} lots")
    
    def _comprehensive_market_score(self, context: 'EnhancedTradingContext', is_buy: bool) -> Dict:
        """
        COMPREHENSIVE MARKET ANALYSIS USING ALL 159+ FEATURES
        
        Used for ALL decisions: DCA, SCALE_IN, SCALE_OUT, RECOVERY
        Returns detailed scoring across all dimensions
        
        Returns: {
            'total_score': 0-100,
            'trend_score': 0-100,
            'momentum_score': 0-100,
            'volume_score': 0-100,
            'structure_score': 0-100,
            'ml_score': 0-100,
            'signals': []
        }
        """
        signals = []
        
        # Helper to safely get attribute
        def safe_get(attr, default=0.5):
            return getattr(context, attr, default)
        
        # Symbol-specific thresholds based on asset class
        symbol = context.symbol.lower()
        if 'eur' in symbol or 'gbp' in symbol or 'usd' in symbol or 'jpy' in symbol:
            # FOREX: Often ranges, needs looser thresholds
            trend_threshold_high = 0.52
            trend_threshold_low = 0.48
            align_threshold_high = 0.60
            align_threshold_low = 0.40
        elif 'us30' in symbol or 'us100' in symbol or 'us500' in symbol:
            # INDICES: Moderate trends
            trend_threshold_high = 0.54
            trend_threshold_low = 0.46
            align_threshold_high = 0.62
            align_threshold_low = 0.38
        else:
            # COMMODITIES (oil, gold): Strong trends
            trend_threshold_high = 0.56
            trend_threshold_low = 0.44
            align_threshold_high = 0.64
            align_threshold_low = 0.36
        
        # ═══════════════════════════════════════════════════════════
        # 1. MULTI-TIMEFRAME TREND ANALYSIS (7 timeframes)
        # GRADUATED SCORING: Give partial credit for weak trends
        # ═══════════════════════════════════════════════════════════
        trend_score = 0.0
        
        # D1 trend (highest weight) - context.d1_trend is 0.0-1.0 where 1.0=bullish
        # GRADUATED: Strong trend = full points, weak trend = partial points
        # RAISED weak threshold from 0.50 to 0.52 to avoid neutral trades
        d1_trend = safe_get('d1_trend', 0.5)
        logger.info(f"   📊 TREND VALUES: D1={d1_trend:.3f}, is_buy={is_buy}, threshold_high={trend_threshold_high:.3f}")
        if is_buy:
            if d1_trend > trend_threshold_high:
                trend_score += 25
                signals.append("D1 trend aligned")
            elif d1_trend > 0.52:  # Weak bullish (0.52-0.56) - RAISED from 0.50
                trend_score += 12  # Half credit
                signals.append("D1 weak bullish")
        else:
            if d1_trend < trend_threshold_low:
                trend_score += 25
                signals.append("D1 trend aligned")
            elif d1_trend < 0.48:  # Weak bearish (0.44-0.48) - RAISED from 0.50
                trend_score += 12  # Half credit
                signals.append("D1 weak bearish")
        
        # H4 trend
        h4_trend = safe_get('h4_trend', 0.5)
        if is_buy:
            if h4_trend > trend_threshold_high:
                trend_score += 20
                signals.append("H4 trend aligned")
            elif h4_trend > 0.52:  # RAISED from 0.50
                trend_score += 10
                signals.append("H4 weak bullish")
        else:
            if h4_trend < trend_threshold_low:
                trend_score += 20
                signals.append("H4 trend aligned")
            elif h4_trend < 0.48:  # RAISED from 0.50
                trend_score += 10
                signals.append("H4 weak bearish")
        
        # H1 trend
        h1_trend = safe_get('h1_trend', 0.5)
        if is_buy:
            if h1_trend > trend_threshold_high:
                trend_score += 15
                signals.append("H1 trend aligned")
            elif h1_trend > 0.52:  # RAISED from 0.50
                trend_score += 7
                signals.append("H1 weak bullish")
        else:
            if h1_trend < trend_threshold_low:
                trend_score += 15
                signals.append("H1 trend aligned")
            elif h1_trend < 0.48:  # RAISED from 0.50
                trend_score += 7
                signals.append("H1 weak bearish")
        
        # M15 trend
        m15_trend = safe_get('m15_trend', 0.5)
        if is_buy:
            if m15_trend > trend_threshold_high:
                trend_score += 10
                signals.append("M15 trend aligned")
            elif m15_trend > 0.52:  # RAISED from 0.50
                trend_score += 5
        else:
            if m15_trend < trend_threshold_low:
                trend_score += 10
                signals.append("M15 trend aligned")
            elif m15_trend < 0.48:  # RAISED from 0.50
                trend_score += 5
        
        # M5 trend
        m5_trend = safe_get('m5_trend', 0.5)
        if is_buy:
            if m5_trend > trend_threshold_high:
                trend_score += 5
            elif m5_trend > 0.52:  # RAISED from 0.50
                trend_score += 2
        else:
            if m5_trend < trend_threshold_low:
                trend_score += 5
            elif m5_trend < 0.48:  # RAISED from 0.50
                trend_score += 2
        
        # Trend alignment across all timeframes (context.trend_alignment)
        trend_align = safe_get('trend_alignment', 0.5)
        # GRADUATED: Perfect alignment = full, weak alignment = partial
        if is_buy:
            if trend_align > align_threshold_high:
                trend_score += 25
                signals.append("Perfect timeframe alignment")
            elif trend_align > 0.55:  # Weak alignment
                trend_score += 12
                signals.append("Moderate alignment")
        else:
            if trend_align < align_threshold_low:
                trend_score += 25
                signals.append("Perfect timeframe alignment")
            elif trend_align < 0.45:  # Weak alignment
                trend_score += 12
                signals.append("Moderate alignment")
        
        # ═══════════════════════════════════════════════════════════
        # 2. MOMENTUM INDICATORS (RSI, MACD across timeframes)
        # ═══════════════════════════════════════════════════════════
        momentum_score = 0.0
        
        # RSI confirmation - context has h4_rsi, h1_rsi, m15_rsi etc.
        h4_rsi = safe_get('h4_rsi', 50.0)
        h1_rsi = safe_get('h1_rsi', 50.0)
        m15_rsi = safe_get('m15_rsi', 50.0)
        
        if is_buy:
            if 30 < h4_rsi < 60:  # Not overbought
                momentum_score += 20
            if 30 < h1_rsi < 60:
                momentum_score += 15
            if 30 < m15_rsi < 60:
                momentum_score += 10
        else:
            if 40 < h4_rsi < 70:  # Not oversold
                momentum_score += 20
            if 40 < h1_rsi < 70:
                momentum_score += 15
            if 40 < m15_rsi < 70:
                momentum_score += 10
        
        # MACD alignment - context has h4_macd, h1_macd, d1_macd_signal etc.
        h4_macd = safe_get('h4_macd', 0.0)
        h1_macd = safe_get('h1_macd', 0.0)
        d1_macd_signal = safe_get('d1_macd_signal', 0.0)
        
        if is_buy:
            if h4_macd > 0:  # Bullish MACD
                momentum_score += 20
                signals.append("H4 MACD bullish")
            if h1_macd > 0:
                momentum_score += 15
        else:
            if h4_macd < 0:  # Bearish MACD
                momentum_score += 20
                signals.append("H4 MACD bearish")
            if h1_macd < 0:
                momentum_score += 15
        
        # MACD agreement across timeframes - context.macd_h1_h4_agree
        macd_agree = safe_get('macd_h1_h4_agree', 0.0)
        if macd_agree > 0.7:
            momentum_score += 30
            signals.append("MACD cross-timeframe agreement")
        
        # ═══════════════════════════════════════════════════════════
        # 3. VOLUME ANALYSIS (Multi-level scoring) - FIXED THRESHOLDS
        # ═══════════════════════════════════════════════════════════
        volume_score = 0.0
        
        # Get all volume features
        accumulation = safe_get('accumulation', 0.0)
        distribution = safe_get('distribution', 0.0)
        bid_pressure = safe_get('bid_pressure', 0.5)
        ask_pressure = safe_get('ask_pressure', 0.5)
        volume_ratio = safe_get('volume_ratio', 1.0)
        institutional = safe_get('institutional_bars', 0.0)
        volume_spike = safe_get('volume_spike_m1', 1.0)
        imbalance = safe_get('bid_ask_imbalance', 0.0)
        
        # BASELINE: Give credit for average or above volume
        # Require at least average volume for baseline credit
        if volume_ratio >= 1.2:  # Above average volume
            volume_score += 30  # Strong baseline
        elif volume_ratio >= 1.0:  # Average volume
            volume_score += 20  # Moderate baseline
        elif volume_ratio >= 0.8:  # Below average
            volume_score += 10  # Minimal credit
        
        # LEVEL 1: Institutional accumulation/distribution
        if is_buy and accumulation > 0.2:  # Lowered from 0.3
            volume_score += 20
            signals.append("Accumulation")
        elif not is_buy and distribution > 0.2:  # Lowered from 0.3
            volume_score += 20
            signals.append("Distribution")
        
        # LEVEL 2: Bid/ask pressure (LOWERED THRESHOLDS)
        if is_buy and bid_pressure > 0.52:  # Lowered from 0.6
            volume_score += 15
            signals.append("Bid pressure")
        elif not is_buy and ask_pressure > 0.52:  # Lowered from 0.6
            volume_score += 15
            signals.append("Ask pressure")
        
        # LEVEL 3: Above average volume
        if volume_ratio > 1.2:  # Raised from 1.0 for significance
            volume_score += 10
            signals.append("High volume")
        
        # LEVEL 4: Institutional activity
        if institutional > 0.3:  # Lowered from 0.5
            volume_score += 15
            signals.append("Institutional")
        
        # LEVEL 5: Volume spike
        if volume_spike > 1.5:  # Lowered from 2.0
            volume_score += 10
            signals.append("Volume spike")
        
        # LEVEL 6: Order book imbalance (LOWERED THRESHOLDS)
        if is_buy and imbalance > 0.1:  # Lowered from 0.2
            volume_score += 5
        elif not is_buy and imbalance < -0.1:  # Lowered from -0.2
            volume_score += 5
        
        # ═══════════════════════════════════════════════════════════
        # 4. MARKET STRUCTURE (Support/Resistance, Bollinger Bands)
        # ═══════════════════════════════════════════════════════════
        structure_score = 0.0
        
        # At key levels - context.h1_close_pos, context.h4_close_pos
        h1_close_pos = safe_get('h1_close_pos', 0.5)
        h4_close_pos = safe_get('h4_close_pos', 0.5)
        
        if is_buy:
            if h1_close_pos < 0.3:  # Near support
                structure_score += 25
                signals.append("At H1 support")
            if h4_close_pos < 0.3:
                structure_score += 20
                signals.append("At H4 support")
        else:
            if h1_close_pos > 0.7:  # Near resistance
                structure_score += 25
                signals.append("At H1 resistance")
            if h4_close_pos > 0.7:
                structure_score += 20
                signals.append("At H4 resistance")
        
        # Bollinger Bands position - context.h1_bb_position
        h1_bb_pos = safe_get('h1_bb_position', 0.5)
        if is_buy and h1_bb_pos < 0.3:
            structure_score += 15
        elif not is_buy and h1_bb_pos > 0.7:
            structure_score += 15
        
        # Confluence - context.has_strong_confluence()
        try:
            if context.has_strong_confluence():
                structure_score += 40
                signals.append("Strong confluence")
        except:
            pass  # Method might not exist
        
        # ═══════════════════════════════════════════════════════════
        # 5. ML CONFIDENCE
        # ═══════════════════════════════════════════════════════════
        ml_score = 0.0
        
        # Direction matches - context.ml_direction, context.ml_confidence
        ml_direction = safe_get('ml_direction', 'HOLD')
        ml_confidence = safe_get('ml_confidence', 50.0)
        
        if ml_direction == ("BUY" if is_buy else "SELL"):
            ml_score += 40
            
            # Confidence levels
            if ml_confidence > 75:
                ml_score += 40
                signals.append(f"ML very confident ({ml_confidence:.0f}%)")
            elif ml_confidence > 65:
                ml_score += 30
                signals.append(f"ML confident ({ml_confidence:.0f}%)")
            elif ml_confidence > 55:
                ml_score += 20
        
        # ═══════════════════════════════════════════════════════════
        # TOTAL SCORE (weighted average)
        # ═══════════════════════════════════════════════════════════
        total_score = (
            trend_score * 0.30 +      # Trend most important
            momentum_score * 0.25 +    # Momentum
            volume_score * 0.20 +      # Volume
            structure_score * 0.15 +   # Structure
            ml_score * 0.10            # ML
        )
        
        return {
            'total_score': total_score,
            'trend_score': trend_score,
            'momentum_score': momentum_score,
            'volume_score': volume_score,
            'structure_score': structure_score,
            'ml_score': ml_score,
            'signals': signals
        }
    
    def _calculate_recovery_probability(self, context: 'EnhancedTradingContext', current_loss_pct: float) -> float:
        """
        COMPREHENSIVE recovery probability using ALL 159+ features
        """
        is_buy = context.position_type == 0
        
        # Get comprehensive market score
        market_analysis = self._comprehensive_market_score(context, is_buy)
        
        # Base probability from market conditions
        base_prob = market_analysis['total_score'] / 100.0
        
        # Adjust for loss depth (deeper = harder to recover)
        loss_factor = 1.0
        if abs(current_loss_pct) > 2.0:
            loss_factor = 0.3
        elif abs(current_loss_pct) > 1.0:
            loss_factor = 0.6
        elif abs(current_loss_pct) > 0.5:
            loss_factor = 0.8
        
        recovery_prob = base_prob * loss_factor
        
        logger.info(f"   📊 COMPREHENSIVE RECOVERY ANALYSIS:")
        logger.info(f"      Market Score: {market_analysis['total_score']:.0f}/100")
        logger.info(f"      Trend: {market_analysis['trend_score']:.0f}, Momentum: {market_analysis['momentum_score']:.0f}")
        logger.info(f"      Volume: {market_analysis['volume_score']:.0f}, Structure: {market_analysis['structure_score']:.0f}")
        logger.info(f"      Signals: {', '.join(market_analysis['signals'][:3])}")
        logger.info(f"      Recovery Probability: {recovery_prob:.2f}")
        
        return recovery_prob
    
    def _calculate_breakeven_after_dca(self, current_volume: float, current_entry: float,
                                        dca_volume: float, dca_price: float) -> dict:
        """
        AI calculates new breakeven price after DCA.
        Shows how much profit needed to breakeven.
        """
        # Calculate weighted average entry
        total_volume = current_volume + dca_volume
        total_cost = (current_volume * current_entry) + (dca_volume * dca_price)
        new_breakeven = total_cost / total_volume
        
        # Calculate distance to breakeven
        distance_to_breakeven_pct = abs((new_breakeven - dca_price) / dca_price) * 100
        
        return {
            'new_breakeven': new_breakeven,
            'distance_pct': distance_to_breakeven_pct,
            'total_volume': total_volume
        }
    
    def _calculate_max_dca_attempts(self, context: 'EnhancedTradingContext',
                                     trend_strength: float, recovery_prob: float) -> int:
        """
        🤖 GENIUS AI: Max DCA attempts based on EVERYTHING.
        
        Now considers:
        - Trend strength
        - Recovery probability
        - ML confidence (85%+ = fight harder!)
        - Market regime (TRENDING = more attempts)
        - FTMO status
        """
        # Base limit
        base_limit = 2
        
        # Adjust for trend strength
        if trend_strength > 0.8:
            base_limit += 2  # Very strong = 4 attempts
        elif trend_strength > 0.65:
            base_limit += 1  # Strong = 3 attempts
        elif trend_strength < 0.5:
            base_limit -= 1  # Weak = 1 attempt
        
        # Adjust for recovery probability
        if recovery_prob > 0.7:
            base_limit += 1  # High probability
        elif recovery_prob < 0.4:
            base_limit -= 1  # Low probability
        
        # 🤖 GENIUS: ML Confidence Boost (fight harder when confident!)
        if context.ml_confidence > 85 and trend_strength > 0.7:
            base_limit += 1  # VERY confident + strong trend = 1 more attempt
            logger.info(f"   🧠 ML GENIUS ({context.ml_confidence:.0f}%) + Strong Trend: +1 DCA attempt")
        elif context.ml_confidence > 80 and recovery_prob > 0.6:
            base_limit += 1  # Confident + good recovery = 1 more attempt
            logger.info(f"   🧠 ML Confident ({context.ml_confidence:.0f}%): +1 DCA attempt")
        
        # 🤖 GENIUS: Regime-Specific Strategy
        regime = context.get_market_regime()
        if regime in ["TRENDING_UP", "TRENDING_DOWN"] and trend_strength > 0.65:
            base_limit += 1  # TRENDING market = fight harder
            logger.info(f"   📈 {regime} + Strong Trend: +1 DCA attempt")
        elif regime == "RANGING" and trend_strength < 0.5:
            base_limit = min(base_limit, 1)  # RANGING = cut fast
            logger.info(f"   ⚠️ RANGING + Weak Trend: Max 1 DCA")
        
        # Adjust for FTMO status
        if context.should_trade_conservatively():
            base_limit = min(base_limit, 2)  # Max 2 near limits
        
        # Ensure reasonable bounds (1-6 for genius AI)
        return max(1, min(6, base_limit))
    
    def _calculate_smart_dca_size_v2(self, context: 'EnhancedTradingContext',
                                      current_volume: float, current_entry: float,
                                      current_price: float, dca_count: int,
                                      recovery_prob: float) -> float:
        """
        AI calculates optimal DCA size to reach breakeven faster.
        
        Strategy:
        - High recovery prob = larger DCA (get to breakeven faster)
        - Low recovery prob = smaller DCA (limit risk)
        """
        # Calculate current loss
        is_buy = context.position_type == 0
        current_loss_pct = ((current_price - current_entry) / current_entry) * 100
        if not is_buy:
            current_loss_pct = -current_loss_pct
        
        # Target: Reach breakeven with X% move
        if recovery_prob > 0.7:
            target_move_pct = 0.3  # Need only 0.3% move to breakeven
        elif recovery_prob > 0.5:
            target_move_pct = 0.5  # Need 0.5% move
        else:
            target_move_pct = 0.8  # Need 0.8% move
        
        # Calculate DCA size needed
        required_dca = abs(current_loss_pct * current_volume) / target_move_pct
        
        # Apply limits - REDUCED for safety
        min_dca = current_volume * 0.15  # At least 15% of position
        max_dca = current_volume * 0.30  # At most 30% of position (REDUCED from 150%)
        
        optimal_dca = max(min_dca, min(max_dca, required_dca))
        
        # Reduce if near FTMO limit
        if context.should_trade_conservatively():
            optimal_dca *= 0.5
        
        return optimal_dca
    
    def _calculate_ai_trend_strength(self, context: 'EnhancedTradingContext') -> float:
        """
        AI calculates trend strength from multiple timeframes.
        Returns 0.0 (no trend) to 1.0 (very strong trend)
        
        Weights timeframes by importance for swing trading:
        - M15: 35% (most important for swings)
        - H1: 25% (confirms M15)
        - H4: 25% (big picture)
        - D1: 15% (macro context)
        """
        # Weight timeframes by importance
        m15_weight = 0.35
        h1_weight = 0.25
        h4_weight = 0.25
        d1_weight = 0.15
        
        # Get trend values (0.0 = bearish, 1.0 = bullish)
        m15_trend = context.m15_trend if hasattr(context, 'm15_trend') else 0.5
        h1_trend = context.h1_trend if hasattr(context, 'h1_trend') else 0.5
        h4_trend = context.h4_trend if hasattr(context, 'h4_trend') else 0.5
        d1_trend = context.d1_trend if hasattr(context, 'd1_trend') else 0.5
        
        # Calculate weighted trend strength
        trend_strength = (
            m15_trend * m15_weight +
            h1_trend * h1_weight +
            h4_trend * h4_weight +
            d1_trend * d1_weight
        )
        
        # Bonus for alignment (all timeframes agree)
        alignment_bonus = 0.0
        if abs(m15_trend - h1_trend) < 0.2 and abs(h1_trend - h4_trend) < 0.2:
            alignment_bonus = 0.15  # All aligned = stronger
        
        return min(1.0, trend_strength + alignment_bonus)
    
    def _calculate_ai_profit_target(self, context: 'EnhancedTradingContext', 
                                     trend_strength: float) -> float:
        """
        🤖 GENIUS AI: Determines profit target based on ALL market conditions.
        Returns multiplier of volatility (e.g., 2.0 = 2x volatility)
        
        Now considers:
        - Trend strength
        - ML confidence (80%+ = AGGRESSIVE)
        - Volume spikes (3x+ = INSTITUTIONAL)
        - Confluence strength (7/7 aligned = PERFECT)
        - Market regime
        """
        market_volatility = context.volatility if hasattr(context, 'volatility') else 0.5
        
        # SWING TRADING: Larger targets (2-5% for $200k account)
        if trend_strength > 0.8:
            base_multiplier = 8.0  # 4% target
            logger.info(f"🚀 VERY STRONG SWING TREND - Base: 8x volatility")
        elif trend_strength > 0.65:
            base_multiplier = 6.0  # 3% target
            logger.info(f"📈 STRONG SWING TREND - Base: 6x volatility")
        elif trend_strength > 0.5:
            base_multiplier = 4.0  # 2% target
            logger.info(f"📊 MODERATE SWING TREND - Base: 4x volatility")
        else:
            base_multiplier = 3.0  # 1.5% target
            logger.info(f"⚠️ WEAK SWING TREND - Base: 3x volatility")
        
        # 🤖 GENIUS: ML Confidence Boost (SQUEEZE when confident!)
        ml_boost = 0.0
        if context.ml_confidence > 85:
            ml_boost = 1.0  # VERY confident = +1.0x
            logger.info(f"   🧠 ML GENIUS (>{context.ml_confidence:.0f}%): +1.0x")
        elif context.ml_confidence > 75:
            ml_boost = 0.6  # Confident = +0.6x
            logger.info(f"   🧠 ML Confident ({context.ml_confidence:.0f}%): +0.6x")
        elif context.ml_confidence > 65:
            ml_boost = 0.3  # Good confidence = +0.3x
            logger.info(f"   🧠 ML Good ({context.ml_confidence:.0f}%): +0.3x")
        
        # 🤖 GENIUS: Volume Spike Detection (INSTITUTIONAL moves!)
        volume_boost = 0.0
        if context.volume_increasing > 0.7:
            if context.volume_spike_m1 > 3.0:  # 3x average volume
                volume_boost = 0.8  # HUGE spike = institutional
                logger.info(f"   💥 VOLUME SPIKE ({context.volume_spike_m1:.1f}x): +0.8x")
            elif context.volume_spike_m1 > 2.0:  # 2x average
                volume_boost = 0.5  # Big spike
                logger.info(f"   📈 Volume Surge ({context.volume_spike_m1:.1f}x): +0.5x")
            else:
                volume_boost = 0.3  # Normal increase
                logger.info(f"   📈 Volume Boost: +0.3x")
        
        # 🤖 GENIUS: Perfect Confluence (ALL timeframes aligned!)
        confluence_boost = 0.0
        m15_trend = context.m15_trend if hasattr(context, 'm15_trend') else 0.5
        h1_trend = context.h1_trend if hasattr(context, 'h1_trend') else 0.5
        h4_trend = context.h4_trend if hasattr(context, 'h4_trend') else 0.5
        d1_trend = context.d1_trend if hasattr(context, 'd1_trend') else 0.5
        
        # Count aligned timeframes
        is_buy = context.position_type == 0 if hasattr(context, 'position_type') else True
        aligned_count = 0
        if (is_buy and m15_trend > 0.6) or (not is_buy and m15_trend < 0.4): aligned_count += 1
        if (is_buy and h1_trend > 0.6) or (not is_buy and h1_trend < 0.4): aligned_count += 1
        if (is_buy and h4_trend > 0.6) or (not is_buy and h4_trend < 0.4): aligned_count += 1
        if (is_buy and d1_trend > 0.6) or (not is_buy and d1_trend < 0.4): aligned_count += 1
        
        if aligned_count == 4 and context.has_strong_confluence():
            confluence_boost = 0.7  # PERFECT setup
            logger.info(f"   ✨ PERFECT CONFLUENCE (4/4 TF): +0.7x")
        elif aligned_count >= 3:
            confluence_boost = 0.4  # Strong confluence
            logger.info(f"   ✨ Strong Confluence ({aligned_count}/4 TF): +0.4x")
        
        # Adjust for market regime
        regime = context.get_market_regime()
        regime_boost = 0.0
        if regime in ["TRENDING_UP", "TRENDING_DOWN"]:
            regime_boost = 0.2
            logger.info(f"   📈 Regime ({regime}): +0.2x")
        
        # 🤖 GENIUS: Combine all factors
        final_multiplier = base_multiplier + ml_boost + volume_boost + confluence_boost + regime_boost
        
        # Ensure reasonable bounds (0.5 to 5.0 for genius AI)
        final_multiplier = max(0.5, min(5.0, final_multiplier))
        
        logger.info(f"   🎯 GENIUS AI Target: {final_multiplier}x volatility ({final_multiplier * market_volatility:.2f}%)")
        
        return final_multiplier
    
    def _check_ai_exit_levels(self, context: 'EnhancedTradingContext', is_buy: bool) -> bool:
        """
        AI checks if price is near key resistance/support on SWING timeframes.
        Uses M15, H4, D1 - not just H1!
        """
        # Check M15 (most important for swings)
        m15_close_pos = context.m15_close_pos if hasattr(context, 'm15_close_pos') else 0.5
        m15_near_level = (
            (is_buy and m15_close_pos > 0.90) or
            (not is_buy and m15_close_pos < 0.10)
        )
        
        # Check H4 (big picture)
        h4_close_pos = context.h4_close_pos if hasattr(context, 'h4_close_pos') else 0.5
        h4_near_level = (
            (is_buy and h4_close_pos > 0.85) or
            (not is_buy and h4_close_pos < 0.15)
        )
        
        # Check D1 (major levels)
        d1_close_pos = context.d1_close_pos if hasattr(context, 'd1_close_pos') else 0.5
        d1_near_level = (
            (is_buy and d1_close_pos > 0.90) or
            (not is_buy and d1_close_pos < 0.10)
        )
        
        # AI decision: Exit if near key level on ANY swing timeframe
        if m15_near_level:
            logger.info(f"   ⚠️ Near M15 level (close_pos: {m15_close_pos:.2f})")
            return True
        if h4_near_level:
            logger.info(f"   ⚠️ Near H4 level (close_pos: {h4_close_pos:.2f})")
            return True
        if d1_near_level:
            logger.info(f"   ⚠️ Near D1 level (close_pos: {d1_close_pos:.2f})")
            return True
        
        return False
    
    def _check_partial_exit(self, context: 'EnhancedTradingContext', exit_score: float, exit_threshold: float) -> Dict:
        """
        AI-POWERED partial profit decision using market structure analysis
        
        Analyzes:
        - Multi-timeframe trend weakening (how many TFs reversed)
        - Volume divergence strength
        - Support/resistance proximity
        - Momentum exhaustion
        - Profit decline from peak (context)
        """
        current_profit = context.position_current_profit
        peak_profit = context.position_peak_profit
        decline_pct = context.position_decline_from_peak_pct
        is_buy = context.position_type == 0
        
        # Don't partial exit tiny profits (not worth spread)
        if current_profit < 10:
            return {'action': 'HOLD'}
        
        # ═══════════════════════════════════════════════════════════
        # AI ANALYSIS: Count reversal signals across market structure
        # ═══════════════════════════════════════════════════════════
        
        reversal_signals = 0
        reversal_strength = 0.0
        
        # 1. Multi-timeframe trend reversal count
        reversed_tfs = 0
        if is_buy:
            if context.m1_trend < 0.4: reversed_tfs += 1
            if context.m5_trend < 0.4: reversed_tfs += 1
            if context.m15_trend < 0.4: reversed_tfs += 1
            if context.m30_trend < 0.4: reversed_tfs += 1
            if context.h1_trend < 0.4: reversed_tfs += 1
            if context.h4_trend < 0.4: reversed_tfs += 1
        else:
            if context.m1_trend > 0.6: reversed_tfs += 1
            if context.m5_trend > 0.6: reversed_tfs += 1
            if context.m15_trend > 0.6: reversed_tfs += 1
            if context.m30_trend > 0.6: reversed_tfs += 1
            if context.h1_trend > 0.6: reversed_tfs += 1
            if context.h4_trend > 0.6: reversed_tfs += 1
        
        # 3+ timeframes reversed = moderate reversal
        if reversed_tfs >= 3:
            reversal_signals += 1
            reversal_strength += (reversed_tfs / 6.0) * 30  # Max 30 pts
        
        # 2. Volume divergence (price moving but volume declining)
        if context.volume_divergence > 0.5:
            reversal_signals += 1
            reversal_strength += context.volume_divergence * 20  # Max 20 pts
        
        # 3. RSI extreme on multiple timeframes
        rsi_extreme_count = 0
        if is_buy:
            if context.m15_rsi > 70: rsi_extreme_count += 1
            if context.h1_rsi > 70: rsi_extreme_count += 1
            if context.h4_rsi > 70: rsi_extreme_count += 1
        else:
            if context.m15_rsi < 30: rsi_extreme_count += 1
            if context.h1_rsi < 30: rsi_extreme_count += 1
            if context.h4_rsi < 30: rsi_extreme_count += 1
        
        if rsi_extreme_count >= 2:
            reversal_signals += 1
            reversal_strength += (rsi_extreme_count / 3.0) * 15  # Max 15 pts
        
        # 4. Near key support/resistance
        near_level = False
        if is_buy and context.m15_close_pos > 0.85:
            near_level = True
            reversal_signals += 1
            reversal_strength += 15
        elif not is_buy and context.m15_close_pos < 0.15:
            near_level = True
            reversal_signals += 1
            reversal_strength += 15
        
        # 5. Profit declining from peak (behavioral signal)
        if decline_pct > 10 and peak_profit > current_profit:
            reversal_signals += 1
            reversal_strength += min(decline_pct, 20)  # Max 20 pts
        
        # ═══════════════════════════════════════════════════════════
        # AI DECISION: Partial exit based on reversal strength
        # ═══════════════════════════════════════════════════════════
        
        logger.info(f"   🤖 PARTIAL EXIT ANALYSIS:")
        logger.info(f"      Reversal Signals: {reversal_signals}/5")
        logger.info(f"      Reversal Strength: {reversal_strength:.0f}/100")
        logger.info(f"      TFs Reversed: {reversed_tfs}/6")
        logger.info(f"      Profit Decline: {decline_pct:.1f}% from peak ${peak_profit:.2f}")
        
        # Strong reversal building (3+ signals, 60+ strength) → Close 50%
        if reversal_signals >= 3 and reversal_strength >= 60:
            logger.info(f"   💰 AI DECISION: PARTIAL EXIT 50% - Strong reversal building")
            return {
                'should_exit': False,
                'action': 'PARTIAL_CLOSE',
                'percent': 50,
                'reason': f'{reversal_signals} reversal signals (strength {reversal_strength:.0f}) - securing 50%',
                'exit_type': 'ai_partial_strong',
                'score': exit_score
            }
        
        # Moderate reversal (2 signals, 40+ strength) + profit declining → Close 25%
        if reversal_signals >= 2 and reversal_strength >= 40 and decline_pct > 10:
            logger.info(f"   💰 AI DECISION: PARTIAL EXIT 25% - Moderate reversal + declining")
            return {
                'should_exit': False,
                'action': 'PARTIAL_CLOSE',
                'percent': 25,
                'reason': f'{reversal_signals} reversal signals + profit declining {decline_pct:.0f}% - securing 25%',
                'exit_type': 'ai_partial_moderate',
                'score': exit_score
            }
        
        logger.info(f"   ✅ AI DECISION: HOLD - Reversal not strong enough ({reversal_signals}/5 signals)")
        return {'action': 'HOLD'}
    
    def _sophisticated_exit_analysis(self, context: EnhancedTradingContext, mtf_data: Dict = None) -> Dict:
        """
        COMPREHENSIVE EXIT ANALYSIS USING ALL 159+ FEATURES
        
        Analyzes EVERYTHING the entry does:
        - All 7 timeframes (M1, M5, M15, M30, H1, H4, D1)
        - RSI across all timeframes + divergences
        - MACD across all timeframes + crossovers
        - Bollinger Bands on all timeframes
        - Volume analysis (spikes, accumulation, distribution, institutional)
        - Order book pressure (bid/ask imbalance)
        - Market structure (support/resistance breaks)
        - Trend alignment across timeframes
        - Volatility regimes
        - Price action patterns
        
        Returns: {'should_exit': bool, 'reason': str, 'exit_type': str, 'score': float}
        """
        try:
            # Helper to safely get attributes
            def safe_get(attr, default=0.5):
                return getattr(context, attr, default)
            
            is_buy = (context.position_type == 0)
            current_profit = context.position_current_profit
            
            # Calculate P&L percentage for threshold logic
            account_balance = context.account_balance if hasattr(context, 'account_balance') else 100000
            current_profit_pct = (current_profit / account_balance) * 100 if account_balance > 0 else 0
            
            # Count exit signals across ALL features
            exit_signals = []
            exit_score = 0.0
            
            logger.info(f"🧠 COMPREHENSIVE EXIT ANALYSIS (159+ features):")
            
            # ═══════════════════════════════════════════════════════════
            # 1. MULTI-TIMEFRAME TREND REVERSAL (ALL 7 TIMEFRAMES!)
            # ═══════════════════════════════════════════════════════════
            
            # Check ALL timeframes for reversal - count how many reversed
            reversed_count = 0
            reversed_timeframes = []
            
            if is_buy:
                # For BUY, exit if trends turn bearish (<0.3)
                if safe_get('m1_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("M1")
                if safe_get('m5_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("M5")
                if safe_get('m15_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("M15")
                if safe_get('m30_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("M30")
                if safe_get('h1_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("H1")
                if safe_get('h4_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("H4")
                if safe_get('d1_trend', 0.5) < 0.3:
                    reversed_count += 1
                    reversed_timeframes.append("D1")
            else:
                # For SELL, exit if trends turn bullish (>0.7)
                if safe_get('m1_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("M1")
                if safe_get('m5_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("M5")
                if safe_get('m15_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("M15")
                if safe_get('m30_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("M30")
                if safe_get('h1_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("H1")
                if safe_get('h4_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("H4")
                if safe_get('d1_trend', 0.5) > 0.7:
                    reversed_count += 1
                    reversed_timeframes.append("D1")
            
            # Score based on HOW MANY timeframes reversed
            if reversed_count >= 5:  # Majority (5+ of 7)
                exit_signals.append(f"{reversed_count}/7 timeframes reversed")
                exit_score += 40.0
                logger.info(f"   🔴 MAJOR REVERSAL: {reversed_count}/7 timeframes: {', '.join(reversed_timeframes)}")
            elif reversed_count >= 3:  # Significant (3-4 of 7)
                exit_signals.append(f"{reversed_count}/7 timeframes reversed")
                exit_score += 25.0
                logger.info(f"   🟡 MODERATE REVERSAL: {reversed_count}/7 timeframes: {', '.join(reversed_timeframes)}")
            elif reversed_count >= 2:  # Minor (2 of 7)
                exit_signals.append(f"{reversed_count}/7 timeframes reversed")
                exit_score += 10.0
            
            # ═══════════════════════════════════════════════════════════
            # 2. RSI DIVERGENCE & EXTREMES (all timeframes)
            # ═══════════════════════════════════════════════════════════
            
            # RSI overbought/oversold on ALL 7 timeframes - count how many
            rsi_extreme_count = 0
            rsi_values = {
                'M1': safe_get('m1_rsi', 50.0),
                'M5': safe_get('m5_rsi', 50.0),
                'M15': safe_get('m15_rsi', 50.0),
                'M30': safe_get('m30_rsi', 50.0),
                'H1': safe_get('h1_rsi', 50.0),
                'H4': safe_get('h4_rsi', 50.0),
                'D1': safe_get('d1_rsi', 50.0)
            }
            
            for tf, rsi in rsi_values.items():
                if is_buy and rsi > 70:
                    rsi_extreme_count += 1
                elif not is_buy and rsi < 30:
                    rsi_extreme_count += 1
            
            # Score based on how many timeframes show RSI extreme
            if rsi_extreme_count >= 4 and current_profit > 0:
                exit_signals.append(f"RSI extreme on {rsi_extreme_count}/7 timeframes")
                exit_score += 25.0
                logger.info(f"   🔴 RSI EXTREME: {rsi_extreme_count}/7 timeframes overbought/oversold")
            elif rsi_extreme_count >= 2 and current_profit > 0:
                exit_signals.append(f"RSI extreme on {rsi_extreme_count}/7 timeframes")
                exit_score += 15.0
            
            # RSI divergence (price making new highs/lows but RSI not)
            if hasattr(context, 'rsi_divergence') and context.rsi_divergence > 0.5:
                exit_signals.append("RSI divergence")
                exit_score += 20.0
                logger.info(f"   🔴 RSI DIVERGENCE DETECTED")
            
            # ═══════════════════════════════════════════════════════════
            # 3. MACD CROSSOVERS (all timeframes)
            # ═══════════════════════════════════════════════════════════
            
            # MACD crossover - only exit if BOTH H1 AND H4 reversed
            # Context has h1_macd, h4_macd (not macd_h1)
            h1_macd = safe_get('h1_macd', 0.0)
            h4_macd = safe_get('h4_macd', 0.0)
            
            macd_h1_bearish = h1_macd < 0
            macd_h4_bearish = h4_macd < 0
            
            # Only exit if BOTH timeframes reversed (not just one)
            if is_buy and macd_h4_bearish and macd_h1_bearish:
                exit_signals.append("MACD bearish on H1+H4")
                exit_score += 20.0
                logger.info(f"   🔴 MACD BEARISH BOTH: H1={h1_macd:.3f}, H4={h4_macd:.3f}")
            elif not is_buy and (not macd_h4_bearish) and (not macd_h1_bearish):
                exit_signals.append("MACD bullish on H1+H4")
                exit_score += 20.0
                logger.info(f"   🔴 MACD BULLISH BOTH: H1={h1_macd:.3f}, H4={h4_macd:.3f}")
            
            # ═══════════════════════════════════════════════════════════
            # 4. VOLUME ANALYSIS (institutional activity)
            # ═══════════════════════════════════════════════════════════
            
            # Volume divergence (price moving but volume declining)
            if context.volume_divergence > 0.6:
                exit_signals.append("Volume divergence")
                exit_score += 20.0
                logger.info(f"   🔴 VOLUME DIVERGENCE: {context.volume_divergence:.2f}")
            
            # Institutional exit (distribution for BUY, accumulation for SELL)
            if is_buy and context.distribution > 0.6:
                exit_signals.append("Institutional distribution")
                exit_score += 25.0
                logger.info(f"   🔴 INSTITUTIONAL DISTRIBUTION: {context.distribution:.2f}")
            elif not is_buy and context.accumulation > 0.6:
                exit_signals.append("Institutional accumulation")
                exit_score += 25.0
                logger.info(f"   🔴 INSTITUTIONAL ACCUMULATION: {context.accumulation:.2f}")
            
            # Volume spike reversal
            if context.volume_spike_m1 > 3.0 and context.volume_increasing < 0.3:
                exit_signals.append("Volume spike exhaustion")
                exit_score += 15.0
            
            # ═══════════════════════════════════════════════════════════
            # 5. ORDER BOOK PRESSURE
            # ═══════════════════════════════════════════════════════════
            
            # Bid/ask imbalance shifted against position
            if is_buy and context.bid_ask_imbalance < -0.3:
                exit_signals.append("Order book pressure shifted (bearish)")
                exit_score += 20.0
                logger.info(f"   🔴 ORDER BOOK BEARISH: Imbalance={context.bid_ask_imbalance:.2f}")
            elif not is_buy and context.bid_ask_imbalance > 0.3:
                exit_signals.append("Order book pressure shifted (bullish)")
                exit_score += 20.0
            
            # ═══════════════════════════════════════════════════════════
            # 6. BOLLINGER BANDS (all timeframes)
            # ═══════════════════════════════════════════════════════════
            
            # Price at/beyond Bollinger Bands = potential reversal
            # Context has m15_bb_position, h1_bb_position (not bb_position_m15)
            m15_bb_pos = safe_get('m15_bb_position', 0.5)
            h1_bb_pos = safe_get('h1_bb_position', 0.5)
            
            if is_buy:
                bb_extreme = (m15_bb_pos > 0.9 or h1_bb_pos > 0.9)
            else:
                bb_extreme = (m15_bb_pos < 0.1 or h1_bb_pos < 0.1)
            
            if bb_extreme and current_profit > 0:
                exit_signals.append("Bollinger Band extreme")
                exit_score += 10.0
            
            # ═══════════════════════════════════════════════════════════
            # 7. MARKET REGIME CHANGE
            # ═══════════════════════════════════════════════════════════
            
            regime = context.get_market_regime()
            if regime == "RANGING" and current_profit > 0:
                exit_signals.append("Market regime: Trending → Ranging")
                exit_score += 15.0
                logger.info(f"   🟡 REGIME CHANGE: {regime}")
            elif regime == "VOLATILE":
                exit_signals.append("Market regime: Volatile")
                exit_score += 10.0
            
            # ═══════════════════════════════════════════════════════════
            # 8. TIMEFRAME CONFLUENCE BREAKDOWN
            # ═══════════════════════════════════════════════════════════
            
            # Timeframes no longer aligned
            if context.trend_alignment < 0.3 or context.trend_alignment > 0.7:
                # Timeframes disagree
                exit_signals.append("Timeframe confluence breakdown")
                exit_score += 15.0
                logger.info(f"   🟡 TIMEFRAMES MISALIGNED: {context.trend_alignment:.2f}")
            
            # ═══════════════════════════════════════════════════════════
            # 9. ML CONFIDENCE WEAKENING
            # ═══════════════════════════════════════════════════════════
            
            # ML no longer supports position
            if context.ml_direction != ("BUY" if is_buy else "SELL"):
                exit_signals.append("ML direction reversed")
                exit_score += 25.0
                logger.info(f"   🔴 ML REVERSED: Now {context.ml_direction} @ {context.ml_confidence:.1f}%")
            elif context.ml_confidence < 50:
                exit_signals.append("ML confidence weak")
                exit_score += 15.0
            
            # ═══════════════════════════════════════════════════════════
            # 10. SUPPORT/RESISTANCE BREAKS
            # ═══════════════════════════════════════════════════════════
            
            # Price broke key level against position
            if is_buy and hasattr(context, 'nearest_support'):
                if context.current_price < context.nearest_support:
                    exit_signals.append("Support broken")
                    exit_score += 25.0
                    logger.info(f"   🔴 SUPPORT BROKEN: Price below {context.nearest_support}")
            elif not is_buy and hasattr(context, 'nearest_resistance'):
                if context.current_price > context.nearest_resistance:
                    exit_signals.append("Resistance broken")
                    exit_score += 25.0
            
            # ═══════════════════════════════════════════════════════════
            # DECISION: Exit if score >= 50 (multiple strong signals)
            # ═══════════════════════════════════════════════════════════
            
            logger.info(f"   📊 EXIT SCORE: {exit_score:.0f}/100")
            logger.info(f"   📋 SIGNALS: {len(exit_signals)} - {', '.join(exit_signals[:3])}")
            
            # DYNAMIC EXIT THRESHOLD: Based on P&L PERCENTAGE
            # CRITICAL: Don't exit tiny losses - only exit real losses or take real profits
            if current_profit_pct > 0.5:
                # Good profit - take it
                exit_threshold = 65
            elif current_profit_pct > 0.2:
                # Decent profit - take it with more signals
                exit_threshold = 70
            elif current_profit_pct > -0.5:
                # Tiny loss or small profit - DON'T EXIT unless very strong signals
                exit_threshold = 95  # Almost never exit
            elif current_profit_pct > -1.0:
                # Medium loss - cut it
                exit_threshold = 70
            else:
                # Large loss - cut it fast
                exit_threshold = 60
            
            logger.info(f"   🎯 Exit threshold: {exit_threshold} (profit-adjusted)")
            
            if exit_score >= exit_threshold:
                reason = f"{len(exit_signals)} exit signals (score: {exit_score:.0f}): {', '.join(exit_signals[:2])}"
                logger.info(f"   🚨 EXIT TRIGGERED: {reason}")
                return {
                    'should_exit': True,
                    'reason': reason,
                    'exit_type': 'comprehensive_analysis',
                    'score': exit_score,
                    'signals': exit_signals
                }
            else:
                # Check for PARTIAL PROFIT TAKING before full hold
                partial_exit = self._check_partial_exit(context, exit_score, exit_threshold)
                if partial_exit['action'] != 'HOLD':
                    return partial_exit
                
                logger.info(f"   ✅ HOLDING: Score {exit_score:.0f} < {exit_threshold} threshold")
                return {
                    'should_exit': False,
                    'reason': f'Market structure intact (score: {exit_score:.0f})',
                    'exit_type': 'hold',
                    'score': exit_score
                }
            
        except Exception as e:
            logger.error(f"Comprehensive exit analysis error: {e}")
            import traceback
            traceback.print_exc()
            return {'should_exit': False, 'reason': f'Analysis error: {e}', 'exit_type': 'error', 'score': 0.0}
    
    def analyze_position(self, context: EnhancedTradingContext) -> Dict:
        """
        AI analyzes position using ALL 100 features and makes ACTIVE decision
        
        Now considers:
        - Multi-timeframe alignment (M1, H1, H4)
        - Volume regime (institutional flow)
        - Order book pressure
        - Market volatility regime
        - Timeframe confluence
        - Position age and DCA count
        
        Returns decision: DCA, CLOSE, SCALE_IN, or HOLD
        """
        
        if not context.has_position:
            return {'action': 'HOLD', 'reason': 'No position to manage', 'priority': 'LOW', 'confidence': 0.0}
        
        # Get position details
        is_buy = (context.position_type == 0)
        original_direction = "BUY" if is_buy else "SELL"
        current_volume = context.position_volume
        dca_count = context.position_dca_count if hasattr(context, 'position_dca_count') else 0
        position_age_minutes = context.position_age_minutes if hasattr(context, 'position_age_minutes') else 0
        
        # Calculate P&L percentage based on account balance (more meaningful than notional value)
        # For a $200k account, $1000 profit = 0.5%
        account_balance = context.account_balance if hasattr(context, 'account_balance') else 100000
        current_profit_pct = (context.position_current_profit / account_balance) * 100 if account_balance > 0 else 0
        
        # REMOVED: 60-minute time block - AI makes decisions based on market structure, not arbitrary time
        # AI analyzes 159+ features including trend, regime, confluence, ML signal, etc.
        # If AI says close, we close. If AI says hold, we hold. Time is just one factor among many.
        
        is_winning = current_profit_pct > 0
        is_losing = current_profit_pct < 0
        
        # Calculate trend strength and market volatility for profit targets
        trend_strength = self._calculate_ai_trend_strength(context)
        market_volatility = context.volatility if hasattr(context, 'volatility') else 0.5
        
        logger.info(f"🧠 ANALYZING POSITION (173 features with FTMO):")
        logger.info(f"   Direction: {original_direction} | Volume: {current_volume} lots")
        logger.info(f"   P&L: {current_profit_pct:.2f}% | Age: {context.position_age_minutes:.1f} min")
        logger.info(f"   ML: {context.ml_direction} @ {context.ml_confidence:.1f}% | DCA Count: {dca_count}")
        logger.info(f"   Regime: {context.get_market_regime()} | Volume: {context.get_volume_regime()}")
        logger.info(f"   Confluence: {context.has_strong_confluence()} | Trend Align: {context.trend_alignment:.2f}")
        logger.info(f"   FTMO: {context.get_ftmo_status()} | Daily: ${context.daily_pnl:.2f} | DD: ${context.total_drawdown:.2f}")
        logger.info(f"   Limits: Daily ${context.distance_to_daily_limit:.0f} left | DD ${context.distance_to_dd_limit:.0f} left")
        
        # ═══════════════════════════════════════════════════════════
        # PRIORITY 1: EV-BASED EXIT ANALYSIS (Pure AI, No Rules)
        # ═══════════════════════════════════════════════════════════
        if self.ev_exit_manager is not None:
            symbol = getattr(context, 'symbol', 'UNKNOWN')
            ev_decision = self.ev_exit_manager.analyze_exit(
                context=context,
                current_profit=context.position_current_profit,
                current_volume=current_volume,
                position_type=context.position_type,
                symbol=symbol
            )
            
            # If EV analysis says to exit or partial exit, do it
            if ev_decision['action'] in ['CLOSE', 'SCALE_OUT']:
                return ev_decision
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 0: FTMO PROTECTION (HIGHEST PRIORITY)
        # Check FTMO status BEFORE any other decision
        # ═══════════════════════════════════════════════════════════
        
        # FTMO VIOLATION - Close immediately
        if context.ftmo_violated or not context.can_trade:
            logger.info(f"🚨 FTMO VIOLATED - CLOSING ALL POSITIONS")
            return {
                'action': 'CLOSE',
                'reason': 'FTMO rules violated - protecting account',
                'priority': 'CRITICAL',
                'confidence': 100.0
            }
        
        # Near daily limit - Close losing positions, hold winners
        if context.distance_to_daily_limit < 1000:
            if current_profit_pct < 0:
                logger.info(f"⚠️ NEAR DAILY LIMIT (${context.distance_to_daily_limit:.0f} left) - Closing loser")
                return {
                    'action': 'CLOSE',
                    'reason': f'Near FTMO daily limit - cutting loss',
                    'priority': 'CRITICAL',
                    'confidence': 95.0
                }
            else:
                logger.info(f"⚠️ NEAR DAILY LIMIT - Holding winner, NO DCA/SCALE")
                # Continue to check other scenarios but NO DCA
        
        # Near drawdown limit - Very conservative
        if context.distance_to_dd_limit < 2000:
            if current_profit_pct < -0.2:  # Any meaningful loss
                logger.info(f"⚠️ NEAR DD LIMIT (${context.distance_to_dd_limit:.0f} left) - Closing")
                return {
                    'action': 'CLOSE',
                    'reason': f'Near FTMO drawdown limit - protecting account',
                    'priority': 'HIGH',
                    'confidence': 90.0
                }
        
        # REMOVED: Hard-coded profit target check
        # Let AI analyze ALL market data and decide when to exit (Scenario 5.5)
        # AI checks 5 exit signals: target, ML, trend, volume, key levels
        # Takes profit when 3/5 signals say exit - TRUE AI DECISION!
        
        # SWING HARD STOP LOSS: Cut losses at -2% ($4k max loss on $200k)
        if current_profit_pct < -2.0:
            logger.info(f"🛑 SWING HARD STOP: -2% reached")
            return {
                'action': 'CLOSE',
                'reason': f'Swing hard stop -2% triggered',
                'priority': 'CRITICAL',
                'confidence': 100.0
            }
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 1: MULTI-TIMEFRAME REVERSAL (MARKET CHANGED)
        # Enhanced: Check H4 trend reversal + ML + volume
        # ═══════════════════════════════════════════════════════════
        ml_changed = (context.ml_direction != original_direction)
        h4_reversed = (is_buy and context.h4_trend < 0.5) or (not is_buy and context.h4_trend > 0.5)
        institutional_exit = context.distribution > 0.5 if is_buy else context.accumulation > 0.5
        
        # SWING TRADING: Only close on VERY STRONG ML reversal (80%+)
        # Swing trades need conviction - don't exit on weak signals
        if ml_changed and context.ml_confidence > 80 and current_profit_pct < -0.5:
            logger.info(f"🔄 SWING ML REVERSAL: {original_direction} → {context.ml_direction} @ {context.ml_confidence:.1f}% + LOSING")
            return {
                'action': 'CLOSE',
                'reason': f'Strong swing reversal @ {context.ml_confidence:.1f}% while losing',
                'priority': 'HIGH',
                'confidence': context.ml_confidence
            }
        elif ml_changed and context.ml_confidence > 80 and current_profit_pct > 0:
            logger.info(f"💰 Swing ML reversed but WINNING - letting it run to target")
        
        # NEW: H4 trend reversal = immediate exit
        if h4_reversed and context.h4_rsi > 70 if is_buy else context.h4_rsi < 30:
            logger.info(f"🔄 H4 TREND REVERSED + RSI extreme")
            return {
                'action': 'CLOSE',
                'reason': f'H4 trend reversed - bigger timeframe against us',
                'priority': 'CRITICAL',
                'confidence': 90.0
            }
        
        # NEW: Institutional exit detected
        if institutional_exit and context.institutional_bars > 0.3:
            logger.info(f"🏦 INSTITUTIONAL EXIT DETECTED")
            return {
                'action': 'CLOSE',
                'reason': f'Institutional {"distribution" if is_buy else "accumulation"} detected',
                'priority': 'HIGH',
                'confidence': 85.0
            }
        
        # Check regime alignment - Factor into decision, don't hard block
        # AI considers regime as ONE factor among many
        market_regime = context.get_market_regime()
        regime_against_us = (
            (is_buy and market_regime == "TRENDING_DOWN") or
            (not is_buy and market_regime == "TRENDING_UP")
        )
        
        # Log regime status for AI analysis
        if regime_against_us:
            logger.info(f"⚠️ Position against regime: {original_direction} in {market_regime}")
            logger.info(f"   Trend Alignment: {context.trend_alignment:.2f}")
            logger.info(f"   P&L: {current_profit_pct:.2f}%")
            logger.info(f"   ML: {context.ml_direction} @ {context.ml_confidence:.1f}%")
            # AI will consider this in overall decision below
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 2: STRATEGIC DCA WITH CONFLUENCE
        # Enhanced: Check H1 + H4 levels + volume + order book
        # ═══════════════════════════════════════════════════════════
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN RECOVERY DECISION (NO HARDCODED THRESHOLDS!)
        # Let AI analyze ALL 159+ features and decide if recovery is possible
        # ═══════════════════════════════════════════════════════════
        
        # AI analyzes losing positions using 173 features
        # Let AI decide based on MARKET ANALYSIS, not arbitrary rules
        is_losing = current_profit_pct < 0
        
        if is_losing:
            logger.info(f"📉 LOSING POSITION: {current_profit_pct:.2f}%")
            logger.info(f"   DCA Count: {dca_count}")
            
            # 🤖 AI MARKET ANALYSIS - Use 173 features to determine if position should close
            trend_strength = self._calculate_ai_trend_strength(context)
            recovery_prob = self._calculate_recovery_probability(context, current_profit_pct)
            max_attempts = self._calculate_max_dca_attempts(context, trend_strength, recovery_prob)
            
            # CRITICAL: Analyze MARKET STRUCTURE to see if trade thesis is broken
            # Don't use time/loss thresholds - use market signals
            market_score = self._comprehensive_market_score(context, is_buy)
            
            logger.info(f"")
            logger.info(f"🤖 AI MARKET ANALYSIS (173 features):")
            logger.info(f"   Loss: {current_profit_pct:.2f}%")
            logger.info(f"   Market Score: {market_score['total_score']:.0f}/100")
            logger.info(f"   Trend: {market_score['trend_score']:.0f}, Momentum: {market_score['momentum_score']:.0f}")
            logger.info(f"   Volume: {market_score['volume_score']:.0f}, Structure: {market_score['structure_score']:.0f}")
            logger.info(f"   Recovery Probability: {recovery_prob:.2f}")
            logger.info(f"   DCA Count: {dca_count}/{max_attempts}")
            logger.info(f"   ML: {context.ml_direction} @ {context.ml_confidence:.1f}%")
            logger.info(f"   Regime: {context.get_market_regime()}")
            
            # AI DECISION LOGIC: Use market structure, not arbitrary thresholds
            
            # 1. MARKET THESIS BROKEN: Score dropped significantly from entry
            # If market score is now < 30 (was 60+ at entry), thesis is broken
            # CRITICAL: Only check this for meaningful losses (> 0.2%)
            # Don't exit tiny losses just because score is low
            if market_score['total_score'] < 30 and abs(current_profit_pct) > 0.2:
                logger.info(f"   ❌ AI DECISION: CUT LOSS")
                logger.info(f"   Reason: Market thesis broken (score {market_score['total_score']:.0f} < 30)")
                logger.info(f"   Signals: {', '.join(market_score['signals'][:3])}")
                return {
                    'action': 'CLOSE',
                    'reason': f'Market thesis broken (score {market_score["total_score"]:.0f})',
                    'priority': 'HIGH',
                    'confidence': 85.0
                }
            elif market_score['total_score'] < 30:
                logger.info(f"   ⏸️ Low market score ({market_score['total_score']:.0f}) but loss too small ({current_profit_pct:.3f}%) - monitoring")
            
            # 2. STRONG REVERSAL: Multiple timeframes reversed + volume confirms
            reversed_tfs = 0
            if is_buy:
                if context.m15_trend < 0.4: reversed_tfs += 1
                if context.h1_trend < 0.4: reversed_tfs += 1
                if context.h4_trend < 0.4: reversed_tfs += 1
                if context.d1_trend < 0.4: reversed_tfs += 1
            else:
                if context.m15_trend > 0.6: reversed_tfs += 1
                if context.h1_trend > 0.6: reversed_tfs += 1
                if context.h4_trend > 0.6: reversed_tfs += 1
                if context.d1_trend > 0.6: reversed_tfs += 1
            
            # Strong reversal = 3+ timeframes reversed + distribution/accumulation against us
            volume_against = (is_buy and context.distribution > 0.3) or (not is_buy and context.accumulation > 0.3)
            strong_reversal = reversed_tfs >= 3 and volume_against
            
            if strong_reversal:
                logger.info(f"   ❌ AI DECISION: CUT LOSS")
                logger.info(f"   Reason: Strong market reversal ({reversed_tfs}/4 TFs reversed + volume against)")
                return {
                    'action': 'CLOSE',
                    'reason': f'Strong reversal ({reversed_tfs} TFs + volume)',
                    'priority': 'HIGH',
                    'confidence': 90.0
                }
            
            # 3. ML CONFIDENCE COLLAPSED: ML now strongly disagrees with position
            ml_against = (is_buy and context.ml_direction == "SELL" and context.ml_confidence > 70) or \
                        (not is_buy and context.ml_direction == "BUY" and context.ml_confidence > 70)
            
            if ml_against:
                logger.info(f"   ❌ AI DECISION: CUT LOSS")
                logger.info(f"   Reason: ML strongly against position ({context.ml_direction} @ {context.ml_confidence:.0f}%)")
                return {
                    'action': 'CLOSE',
                    'reason': f'ML reversed ({context.ml_direction} @ {context.ml_confidence:.0f}%)',
                    'priority': 'HIGH',
                    'confidence': 80.0
                }
            
            # 4. MAX DCA REACHED + MARKET NOT IMPROVING
            if dca_count >= max_attempts:
                if market_score['total_score'] < 40:
                    logger.info(f"   ❌ AI DECISION: CUT LOSS")
                    logger.info(f"   Reason: Max DCAs ({dca_count}) + market not improving (score {market_score['total_score']:.0f})")
                    return {
                        'action': 'CLOSE',
                        'reason': f'Max DCA + weak market ({market_score["total_score"]:.0f})',
                        'priority': 'HIGH',
                        'confidence': 75.0
                    }
                else:
                    logger.info(f"   ⏸️ AI DECISION: HOLD")
                    logger.info(f"   Reason: Max DCAs but market still strong (score {market_score['total_score']:.0f})")
                    return {
                        'action': 'HOLD',
                        'reason': f'Max DCA but market score {market_score["total_score"]:.0f}',
                        'confidence': 50.0
                    }
            
            # 3. Check if trend STRONGLY reversed (not just weak)
            # Only close if trend is STRONGLY against us AND we're losing
            # Don't close on weak/neutral trends - give the trade time
            strong_reversal = (
                (is_buy and trend_strength < 0.2 and current_profit_pct < -0.3) or  # Strong down trend + losing
                (not is_buy and trend_strength > 0.8 and current_profit_pct < -0.3)  # Strong up trend + losing
            )
            if strong_reversal:
                logger.info(f"   ❌ AI DECISION: CUT LOSS")
                logger.info(f"   Reason: Strong trend reversal (strength: {trend_strength:.2f}) + losing")
                return {
                    'action': 'CLOSE',
                    'reason': f'Strong trend reversal',
                    'priority': 'HIGH',
                    'confidence': 85.0
                }
            
            # 4. FTMO CHECK
            if context.is_near_ftmo_limit():
                logger.info(f"   ⚠️ Near FTMO limit - NO DCA allowed")
                return {
                    'action': 'HOLD',
                    'reason': 'At key level but near FTMO limit',
                    'priority': 'MEDIUM',
                    'confidence': 50.0
                }
            
            # 5. AI DECISION: DCA based on comprehensive market analysis
            # Use recovery probability + ML confidence + market score from 173 features
            # AI determines if adding to position makes sense based on ALL available data
            dca_score = (recovery_prob * 100 * 0.4) + (context.ml_confidence * 0.3) + (market_score['total_score'] * 0.3)
            
            logger.info(f"   🤖 DCA DECISION SCORE: {dca_score:.0f}/100")
            logger.info(f"      Recovery: {recovery_prob:.2f} | ML: {context.ml_confidence:.1f}% | Market: {market_score['total_score']:.0f}")
            
            # AI says DCA if comprehensive score is strong (75+)
            # Raised threshold to be more selective about adding to losers
            if dca_score > 75:
                # Check if position size would exceed max
                if current_volume >= self.max_position_size:
                    logger.info(f"   ❌ Position at max size ({current_volume:.2f} >= {self.max_position_size} lots)")
                    logger.info(f"   AI DECISION: HOLD - Cannot DCA, position too large")
                    return {
                        'action': 'HOLD',
                        'reason': f'Position at max size ({current_volume:.2f} lots)',
                        'priority': 'MEDIUM',
                        'confidence': 60.0
                    }
                
                # Calculate optimal DCA size using Smart Position Sizer
                if get_smart_sizer is not None:
                    smart_sizer = get_smart_sizer()
                    symbol = getattr(context, 'symbol', 'UNKNOWN')
                    dca_size = smart_sizer.calculate_scale_in_size(
                        current_lots=current_volume,
                        current_profit_pct=current_profit_pct,
                        market_score=market_score['total_score'],
                        symbol=symbol
                    )
                else:
                    # Fallback to old method
                    dca_size = self._calculate_smart_dca_size_v2(
                        context,
                        current_volume,
                        context.position_entry_price,
                        context.current_price,
                        dca_count,
                        recovery_prob
                    )
                
                # Cap DCA to not exceed max position size
                max_allowed_dca = self.max_position_size - current_volume
                if dca_size > max_allowed_dca:
                    logger.info(f"   ⚠️ DCA capped: {dca_size:.2f} → {max_allowed_dca:.2f} lots (max position limit)")
                    dca_size = max_allowed_dca
                
                # Minimum DCA size
                if dca_size < 0.01:
                    logger.info(f"   ❌ DCA too small ({dca_size:.3f} lots) - HOLD instead")
                    return {
                        'action': 'HOLD',
                        'reason': 'DCA size too small after capping',
                        'priority': 'LOW',
                        'confidence': 50.0
                    }
                
                # Calculate breakeven
                breakeven_info = self._calculate_breakeven_after_dca(
                    current_volume,
                    context.position_entry_price,
                    dca_size,
                    context.current_price
                )
                
                logger.info(f"   ✅ AI DECISION: DCA")
                logger.info(f"   Reason: Good recovery prob ({recovery_prob:.2f}) at key level")
                logger.info(f"   DCA Size: {dca_size:.2f} lots (optimized for fast recovery)")
                logger.info(f"   New Breakeven: ${breakeven_info['new_breakeven']:.2f}")
                logger.info(f"   Distance to BE: {breakeven_info['distance_pct']:.2f}%")
                logger.info(f"   New Position: {breakeven_info['total_volume']:.2f} lots")
                
                return {
                    'action': 'DCA',
                    'reason': f'AI Recovery: {recovery_prob:.2f} prob @ key level',
                    'add_lots': dca_size,
                    'priority': 'HIGH',
                    'confidence': recovery_prob * 100,
                    'dca_attempt': dca_count + 1,
                    'breakeven': breakeven_info['new_breakeven'],
                    'distance_to_be': breakeven_info['distance_pct']
                }
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 3: CONVICTION DCA WITH MULTI-TIMEFRAME SUPPORT
        # Enhanced: Deep loss but ALL timeframes + volume support us
        # ═══════════════════════════════════════════════════════════
        deep_loss = current_profit_pct < -0.5
        very_confident = context.ml_confidence > 65
        
        # NEW: Check if ALL timeframes support our direction
        all_timeframes_support = (
            (is_buy and context.is_multi_timeframe_bullish()) or
            (not is_buy and context.is_multi_timeframe_bearish())
        )
        
        # NEW: Check if volume shows accumulation (not distribution)
        volume_accumulating = context.accumulation > 0.5 if is_buy else context.distribution > 0.5
        
        if deep_loss and very_confident and not ml_changed and dca_count < self.max_dca_attempts:
            # FTMO CHECK: NEVER conviction DCA if near limits
            if context.should_trade_conservatively():
                logger.info(f"⚠️ Deep loss + near FTMO limit - CLOSING instead of DCA")
                return {
                    'action': 'CLOSE',
                    'reason': f'Deep loss near FTMO limit - cutting loss',
                    'priority': 'HIGH',
                    'confidence': 85.0
                }
            
            # Only do conviction DCA if multi-timeframe supports us
            if all_timeframes_support or volume_accumulating:
                dca_size = self._calculate_smart_dca_size(current_volume, dca_count)
                
                logger.info(f"💪 CONVICTION DCA - MULTI-TIMEFRAME SUPPORT:")
                logger.info(f"   Loss: {current_profit_pct:.2f}%")
                logger.info(f"   ML: {context.ml_direction} @ {context.ml_confidence:.1f}%")
                logger.info(f"   All timeframes support: {all_timeframes_support}")
                logger.info(f"   Volume accumulating: {volume_accumulating}")
                logger.info(f"   DCA attempt {dca_count + 1}/{self.max_dca_attempts}")
                
                return {
                    'action': 'DCA',
                    'reason': f'Deep loss but multi-timeframe + volume support @ {context.ml_confidence:.1f}%',
                    'add_lots': dca_size,
                    'priority': 'HIGH',
                    'confidence': context.ml_confidence,
                    'dca_attempt': dca_count + 1
                }
            else:
                logger.info(f"⚠️ Deep loss but NO multi-timeframe support - NOT adding to loser")
                return {
                    'action': 'CLOSE',
                    'reason': f'Deep loss {current_profit_pct:.2f}% without multi-timeframe support',
                    'priority': 'HIGH',
                    'confidence': 80.0
                }
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 3.5: LARGE POSITION + PROFITABLE = SCALE OUT
        # AI decides based on position size and profit
        # ═══════════════════════════════════════════════════════════
        
        # AI-DRIVEN: Position is "large" based on lot size
        # Use lots as risk proxy (simpler and more accurate than notional value)
        is_large_by_size = current_volume > 5.0  # > 5 lots is "large"
        
        # 🤖 AI-DRIVEN: Scale out threshold adapts to profit target
        # Don't scale out until we're close to take profit target!
        market_volatility = context.volatility if hasattr(context, 'volatility') else 0.5
        trend_strength = self._calculate_ai_trend_strength(context)
        
        # Calculate profit target (same as take profit logic)
        profit_multiplier = self._calculate_ai_profit_target(context, trend_strength)
        profit_target = market_volatility * profit_multiplier
        
        # AI DECISION: Scale out at 70% of profit target
        # This locks in profits while still holding for the target
        if trend_strength > 0.7:
            # Strong trend - hold longer before scaling out
            scale_out_pct_of_target = 0.75  # 75% of target
        else:
            # Weak trend - scale out earlier
            scale_out_pct_of_target = 0.6  # 60% of target
        
        min_profit_to_scale_out = profit_target * scale_out_pct_of_target
        
        logger.info(f"💰 AI Scale Out Analysis:")
        logger.info(f"   Trend Strength: {trend_strength:.2f}")
        logger.info(f"   Profit Target: {profit_target:.2f}%")
        logger.info(f"   Scale Out Threshold: {min_profit_to_scale_out:.2f}% ({scale_out_pct_of_target*100:.0f}% of target)")
        
        if is_large_by_size and current_profit_pct > min_profit_to_scale_out:
            # Position is large and profitable - AI says take some profit
            logger.info(f"💰 AI SCALE OUT - LOCKING PROFITS:")
            logger.info(f"   Size: {current_volume:.2f} lots ({position_pct_of_account:.1f}% of account)")
            logger.info(f"   Profit: {current_profit_pct:.2f}% (target: {profit_target:.2f}%)")
            logger.info(f"   Trend Strength: {trend_strength:.2f}")
            logger.info(f"   AI Decision: SCALE OUT at {scale_out_pct_of_target*100:.0f}% of target")
            
            # AI-DRIVEN: Scale out % based on multiple factors
            profit_to_volatility_ratio = current_profit_pct / market_volatility if market_volatility > 0 else 1
            
            # Factor 1: Profit size
            if profit_to_volatility_ratio > 2.0:
                profit_factor = 0.6  # Huge profit = take more off
            elif profit_to_volatility_ratio > 1.0:
                profit_factor = 0.4  # Good profit = take some off
            else:
                profit_factor = 0.2  # Small profit = take little off
            
            # Factor 2: ML confidence weakening?
            ml_factor = 0.2 if context.ml_confidence < 55 else 0.0
            
            # Factor 3: Timeframes diverging?
            divergence_factor = 0.2 if not context.is_multi_timeframe_bullish() and is_buy else 0.0
            
            # AI DECISION: Combine factors
            scale_out_pct = min(0.8, profit_factor + ml_factor + divergence_factor)  # Max 80%
            
            reduce_lots = current_volume * scale_out_pct
            
            return {
                'action': 'SCALE_OUT',
                'reason': f'Large position ({current_volume:.2f} lots) + profit ({current_profit_pct:.2f}%) - locking {scale_out_pct*100:.0f}%',
                'reduce_lots': reduce_lots,
                'priority': 'MEDIUM',
                'confidence': 80.0
            }
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 4: SCALE IN - COMPREHENSIVE ANALYSIS
        # 🤖 Uses ALL 159+ features to decide if we should add to winner
        # ═══════════════════════════════════════════════════════════
        
        # Get comprehensive market score
        market_analysis = self._comprehensive_market_score(context, is_buy)
        
        logger.info(f"🧠 SCALE IN ANALYSIS (159+ features):")
        logger.info(f"   Market Score: {market_analysis['total_score']:.0f}/100")
        logger.info(f"   Trend: {market_analysis['trend_score']:.0f}, Momentum: {market_analysis['momentum_score']:.0f}")
        logger.info(f"   Volume: {market_analysis['volume_score']:.0f}, Structure: {market_analysis['structure_score']:.0f}")
        logger.info(f"   Top Signals: {', '.join(market_analysis['signals'][:3])}")
        
        # AI DECISION: SCALE IN based on comprehensive market analysis
        # Calculate scale-in score from 173 features: market quality + profit momentum + ML confidence
        scale_in_score = (market_analysis['total_score'] * 0.5) + (min(current_profit_pct * 20, 30)) + (context.ml_confidence * 0.2)
        
        logger.info(f"   🤖 SCALE-IN DECISION SCORE: {scale_in_score:.0f}/100")
        logger.info(f"      Market: {market_analysis['total_score']:.0f} | Profit: {current_profit_pct:.2f}% | ML: {context.ml_confidence:.1f}%")
        
        # AI says scale in if comprehensive score is strong (75+) and not maxed out
        # Raised threshold to be more selective about adding to winners
        should_scale_in = (scale_in_score > 75 and current_volume < 10.0)
        
        if should_scale_in:
            # Calculate scale size using Smart Position Sizer
            if get_smart_sizer is not None:
                smart_sizer = get_smart_sizer()
                symbol = getattr(context, 'symbol', 'UNKNOWN')
                scale_size = smart_sizer.calculate_scale_in_size(
                    current_lots=current_volume,
                    current_profit_pct=current_profit_pct,
                    market_score=market_analysis['total_score'],
                    symbol=symbol
                )
            else:
                # Fallback to old method
                score_multiplier = market_analysis['total_score'] / 100.0
                base_scale = current_volume * 0.3
                scale_size = base_scale * score_multiplier
                scale_size = max(0.01, min(scale_size, 2.0))
            
            logger.info(f"✅ SCALE IN APPROVED:")
            logger.info(f"   Market Score: {market_analysis['total_score']:.0f}/100 (threshold: 50)")
            logger.info(f"   Adding: {scale_size:.2f} lots")
            logger.info(f"   Signals: {', '.join(market_analysis['signals'][:5])}")
            
            return {
                'action': 'SCALE_IN',
                'reason': f'Strong market conditions (score: {market_analysis["total_score"]:.0f})',
                'add_lots': scale_size,
                'priority': 'MEDIUM',
                'confidence': market_analysis['total_score']
            }
        else:
            logger.info(f"⚠️ Market score {market_analysis['total_score']:.0f} < 50 threshold - not scaling in")
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 5: SOPHISTICATED MULTI-TIMEFRAME EXIT ANALYSIS
        # 🤖 TRUE AI: Analyzes H1/H4 structure, ATR targets, volume divergence
        # ═══════════════════════════════════════════════════════════
        
        logger.info(f"🤖 SOPHISTICATED EXIT ANALYSIS:")
        logger.info(f"   P&L: {current_profit_pct:.2f}%")
        
        # Call sophisticated exit analysis
        exit_decision = self._sophisticated_exit_analysis(context)
        
        if exit_decision['should_exit']:
            logger.info(f"✂️ SOPHISTICATED EXIT SIGNAL: {exit_decision['reason']}")
            return {
                'action': 'CLOSE',
                'reason': exit_decision['reason'],
                'exit_type': exit_decision['exit_type'],
                'priority': 'HIGH',
                'confidence': 85.0
            }
        else:
            logger.info(f"✅ MARKET STRUCTURE INTACT: {exit_decision['reason']}")
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 5.5: AI-DRIVEN TAKE PROFIT
        # 🤖 TRUE AI: Analyze if we should take profit based on ALL data
        # ═══════════════════════════════════════════════════════════
        
        # Only consider take profit if position is profitable
        if current_profit_pct > 0.1:  # At least 0.1% profit
            
            # ═══════════════════════════════════════════════════════════
            # 🤖 AI-ADAPTIVE TAKE PROFIT - Uses trend strength from M15/H4/D1
            # Strong trend = hold for 2-3x volatility
            # Weak trend = exit at 0.5-0.8x volatility
            # ═══════════════════════════════════════════════════════════
            
            market_volatility = context.volatility if hasattr(context, 'volatility') else 0.5
            
            # STEP 1: AI calculates trend strength from M15, H1, H4, D1
            trend_strength = self._calculate_ai_trend_strength(context)
            
            logger.info(f"")
            logger.info(f"🤖 AI TAKE PROFIT ANALYSIS:")
            logger.info(f"   Current Profit: {current_profit_pct:.2f}%")
            logger.info(f"   Market Volatility: {market_volatility:.2f}%")
            logger.info(f"   AI Trend Strength: {trend_strength:.2f} (0.0=weak, 1.0=very strong)")
            logger.info(f"   M15: {context.m15_trend:.2f} | H1: {context.h1_trend:.2f} | H4: {context.h4_trend:.2f} | D1: {context.d1_trend:.2f}")
            
            # STEP 2: AI calculates profit target based on trend strength
            profit_multiplier = self._calculate_ai_profit_target(context, trend_strength)
            profit_target = market_volatility * profit_multiplier
            
            profit_to_volatility = current_profit_pct / market_volatility if market_volatility > 0 else 0
            
            # STEP 3: AI analyzes exit signals
            
            # Signal 1: Reached profit target (AI-adaptive based on trend)
            reached_target = current_profit_pct >= profit_target
            
            # Signal 2: ML confidence weakening
            ml_weakening = context.ml_confidence < 55
            
            # Signal 3: Trend breaking on KEY timeframes (M15, H4)
            m15_trend = context.m15_trend if hasattr(context, 'm15_trend') else 0.5
            h4_trend = context.h4_trend if hasattr(context, 'h4_trend') else 0.5
            trend_breaking = (
                (is_buy and (m15_trend < 0.4 or h4_trend < 0.3)) or
                (not is_buy and (m15_trend > 0.6 or h4_trend > 0.7))
            )
            
            # Signal 4: Volume showing exit (distribution for BUY, accumulation for SELL)
            volume_exit = (
                (is_buy and context.distribution > 0.6) or
                (not is_buy and context.accumulation > 0.6)
            )
            
            # Signal 5: Near key level on SWING timeframes (M15, H4, D1)
            near_key_level = self._check_ai_exit_levels(context, is_buy)
            
            # Count exit signals
            exit_signals = [
                reached_target,
                ml_weakening,
                trend_breaking,
                volume_exit,
                near_key_level
            ]
            signal_count = sum(exit_signals)
            
            logger.info(f"")
            logger.info(f"   📊 EXIT SIGNALS:")
            logger.info(f"   1. Reached Target: {reached_target} (profit: {current_profit_pct:.2f}% vs target: {profit_target:.2f}%)")
            logger.info(f"   2. ML Weakening: {ml_weakening} (confidence: {context.ml_confidence:.1f}%)")
            logger.info(f"   3. Trend Breaking: {trend_breaking} (M15: {m15_trend:.2f}, H4: {h4_trend:.2f})")
            logger.info(f"   4. Volume Exit: {volume_exit}")
            logger.info(f"   5. Near Key Level: {near_key_level}")
            logger.info(f"")
            logger.info(f"   🎯 Exit Signals: {signal_count}/5")
            
            # DYNAMIC SIGNAL THRESHOLD: Adjust based on profit size
            # Large profit (>1.5%): Take it with 2 signals
            # Normal profit (0.5-1.5%): Standard 3 signals
            # Small profit (<0.5%): Be patient, 3 signals
            if current_profit_pct > 1.5:
                required_signals = 2  # Large profit - secure it
            else:
                required_signals = 3  # Normal/small profit - be patient
            
            logger.info(f"   🎯 Required signals: {required_signals}/5 (profit: {current_profit_pct:.2f}%)")
            
            # PARTIAL EXIT: Lock in some profit with 2 signals (if not already closing)
            if signal_count == 2 and current_profit_pct > 0.5 and required_signals > 2:
                scale_out_size = current_volume * 0.5
                
                logger.info(f"")
                logger.info(f"📉 AI DECISION: PARTIAL EXIT")
                logger.info(f"   Reason: 2/5 signals - locking in partial profit")
                logger.info(f"   Closing: {scale_out_size:.2f} lots (50%)")
                logger.info(f"   Keeping: {current_volume - scale_out_size:.2f} lots (50%)")
                
                return {
                    'action': 'SCALE_OUT',
                    'reduce_lots': scale_out_size,
                    'reason': f'Partial profit: 2/5 signals @ {current_profit_pct:.2f}%',
                    'priority': 'MEDIUM',
                    'confidence': 75.0
                }
            
            # FULL EXIT: Close entire position
            if signal_count >= required_signals:
                logger.info(f"")
                logger.info(f"✂️ AI DECISION: TAKE PROFIT")
                logger.info(f"   Reason: {signal_count}/{required_signals} exit signals triggered")
                logger.info(f"   Profit: {current_profit_pct:.2f}% ({profit_to_volatility:.2f}x volatility)")
                
                return {
                    'action': 'CLOSE',
                    'reason': f'AI Take Profit: {signal_count}/5 signals @ {current_profit_pct:.2f}%',
                    'priority': 'HIGH',
                    'confidence': 85.0
                }
            
            # HOLD - Let trend develop
            logger.info(f"")
            logger.info(f"✅ AI DECISION: HOLD")
            logger.info(f"   Reason: Only {signal_count}/5 exit signals")
            logger.info(f"   Trend Strength: {trend_strength:.2f} (holding for {profit_multiplier}x volatility)")
            logger.info(f"   Target: {profit_target:.2f}% (current: {current_profit_pct:.2f}%)")
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 5.7: STAGNANT POSITION DETECTION
        # 🤖 Close positions stuck at breakeven with weak conviction
        # ═══════════════════════════════════════════════════════════
        
        if position_age_minutes > 360:  # 6 hours
            if abs(current_profit_pct) < 0.15:  # Nearly breakeven
                if context.ml_confidence < 60:  # Weak conviction
                    logger.info(f"")
                    logger.info(f"⏰ STAGNANT POSITION DETECTED:")
                    logger.info(f"   Age: {position_age_minutes:.0f} minutes (>6 hours)")
                    logger.info(f"   P&L: {current_profit_pct:.2f}% (nearly breakeven)")
                    logger.info(f"   ML Confidence: {context.ml_confidence:.1f}% (weak)")
                    logger.info(f"   Decision: Close to free capital for better opportunities")
                    
                    return {
                        'action': 'CLOSE',
                        'reason': f'Stagnant position: {position_age_minutes:.0f}min @ {current_profit_pct:.2f}%',
                        'priority': 'MEDIUM',
                        'confidence': 70.0
                    }
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 6: AI RECOVERY CHECK - Should we give up?
        # 🤖 AI analyzes if position can still recover
        # ═══════════════════════════════════════════════════════════
        if dca_count >= 2 and current_profit_pct < -0.3:
            # Calculate recovery probability
            trend_strength = self._calculate_ai_trend_strength(context)
            recovery_prob = self._calculate_recovery_probability(context, current_profit_pct)
            max_attempts = self._calculate_max_dca_attempts(context, trend_strength, recovery_prob)
            
            logger.info(f"")
            logger.info(f"🤖 AI FINAL RECOVERY CHECK:")
            logger.info(f"   Loss: {current_profit_pct:.2f}%")
            logger.info(f"   DCA Count: {dca_count}/{max_attempts}")
            logger.info(f"   Trend Strength: {trend_strength:.2f}")
            logger.info(f"   Recovery Probability: {recovery_prob:.2f}")
            logger.info(f"   ML Confidence: {context.ml_confidence:.1f}%")
            
            # AI DECISION: Give up if recovery very unlikely
            if recovery_prob < 0.25 or (dca_count >= max_attempts and recovery_prob < 0.4):
                logger.info(f"   🏳️ AI DECISION: GIVE UP")
                logger.info(f"   Reason: Recovery probability too low ({recovery_prob:.2f})")
                logger.info(f"   Tried {dca_count} DCAs, not working - cut loss")
                
                return {
                    'action': 'CLOSE',
                    'reason': f'AI Recovery: Probability too low {recovery_prob:.2f} after {dca_count} DCAs',
                    'priority': 'HIGH',
                    'confidence': 80.0
                }
            else:
                logger.info(f"   ⏸️ AI DECISION: HOLD")
                logger.info(f"   Reason: Recovery still possible ({recovery_prob:.2f})")
                logger.info(f"   Waiting for better opportunity")
        
        # ═══════════════════════════════════════════════════════════
        # SCENARIO 7: HOLD AND MONITOR
        # AI-DRIVEN: Wait for market to move to key levels or ML to change
        # ═══════════════════════════════════════════════════════════
        return {
            'action': 'HOLD',
            'reason': f'Monitoring - P&L: {current_profit_pct:.2f}%, ML: {context.ml_direction} @ {context.ml_confidence:.1f}%',
            'priority': 'LOW',
            'confidence': context.ml_confidence
        }
    
    def _calculate_smart_dca_size(self, current_volume: float, dca_count: int) -> float:
        """
        AI-driven DCA sizing - gets more conservative with each attempt
        
        1st DCA: 40% of position (aggressive recovery)
        2nd DCA: 30% of position (moderate)
        3rd DCA: 20% of position (conservative)
        """
        
        if dca_count == 0:
            # First attempt - more aggressive
            return current_volume * 0.4
        elif dca_count == 1:
            # Second attempt - moderate
            return current_volume * 0.3
        else:
            # Third attempt - conservative
            return current_volume * 0.2
    
    def _check_at_key_level(
        self,
        is_buy: bool,
        current_price: float,
        h1_support: float = None,
        h1_resistance: float = None
    ) -> bool:
        """Check if price is at key H1 support/resistance level"""
        
        if is_buy and h1_support:
            # For BUY: check if at support (within 0.2%)
            return current_price <= h1_support * 1.002
        elif not is_buy and h1_resistance:
            # For SELL: check if at resistance (within 0.2%)
            return current_price >= h1_resistance * 0.998
        
        return False
    
    def get_dca_ml_threshold(self, dca_count: int) -> float:
        """
        AI-driven ML confidence threshold for DCA
        Gets stricter with each attempt
        """
        
        if dca_count == 0:
            return 52.0  # First DCA: lenient
        elif dca_count == 1:
            return 55.0  # Second DCA: moderate
        else:
            return 60.0  # Third DCA: strict
    
    def should_allow_dca(
        self,
        dca_count: int,
        ml_confidence: float,
        account_balance: float,
        total_exposure: float
    ) -> Tuple[bool, str]:
        """
        AI decides if DCA is allowed based on:
        - DCA count (max 3 attempts)
        - ML confidence (must meet threshold)
        - Account exposure (max 5% total risk)
        """
        
        # Check DCA count limit
        if dca_count >= self.max_dca_attempts:
            return False, f"Max DCA attempts reached ({dca_count}/{self.max_dca_attempts})"
        
        # Check ML confidence threshold
        required_confidence = self.get_dca_ml_threshold(dca_count)
        if ml_confidence < required_confidence:
            return False, f"ML confidence {ml_confidence:.1f}% below threshold {required_confidence:.1f}%"
        
        # Check account exposure
        exposure_pct = (total_exposure / account_balance) * 100
        if exposure_pct > 5.0:
            return False, f"Account exposure {exposure_pct:.1f}% too high (max 5%)"
        
        return True, f"DCA allowed - Attempt {dca_count + 1}/{self.max_dca_attempts}, ML {ml_confidence:.1f}%"
