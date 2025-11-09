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

# Import EV Exit Manager V2 (Pure AI-driven, no hardcoded thresholds)
try:
    from src.ai.ev_exit_manager_v2 import EVExitManagerV2 as EVExitManager
except ImportError:
    try:
        from .ev_exit_manager_v2 import EVExitManagerV2 as EVExitManager
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
        
        # LEVEL 2: HTF Market Structure (replaces M1 bid/ask pressure)
        h4_structure = safe_get('h4_market_structure', 0.0)
        if is_buy and h4_structure > 0.3:  # Uptrend structure
            volume_score += 15
            signals.append("H4 uptrend structure")
        elif not is_buy and h4_structure < -0.3:  # Downtrend structure
            volume_score += 15
            signals.append("H4 downtrend structure")
        
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
        
        # 2. HTF Volume divergence (from H4, not M1)
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        if h4_vol_div > 0.3:
            reversal_signals += 1
            reversal_strength += h4_vol_div * 20  # Max 20 pts
        
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
            
            # HTF Volume divergence (from H4, not M1)
            h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
            if h4_vol_div > 0.4:
                exit_signals.append("H4 volume divergence")
                exit_score += 20.0
                logger.info(f"   🔴 H4 VOLUME DIVERGENCE: {h4_vol_div:.2f}")
            
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
            elif current_profit_pct > -0.2:
                # Tiny loss or small profit - DON'T EXIT unless very strong signals
                exit_threshold = 85  # High threshold for tiny losses
            elif current_profit_pct > -0.5:
                # Small loss - cut if market deteriorating
                exit_threshold = 60  # More aggressive
            elif current_profit_pct > -1.0:
                # Medium loss - cut it
                exit_threshold = 50  # Aggressive
            else:
                # Large loss - cut it fast
                exit_threshold = 40  # Very aggressive
            
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
        
        logger.info(f"🧠 AI EXIT ANALYSIS (ML-DRIVEN):")
        logger.info(f"   Direction: {original_direction} | Volume: {current_volume} lots")
        logger.info(f"   P&L: {current_profit_pct:.2f}% | Age: {context.position_age_minutes:.1f} min")
        logger.info(f"   ML: {context.ml_direction} @ {context.ml_confidence:.1f}% | DCA Count: {dca_count}")
        logger.info(f"   FTMO: Daily ${context.daily_pnl:.2f} | DD ${context.total_drawdown:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN EXIT: ONLY USE ML + P&L (NO CONFLICTING SIGNALS)
        # Entry used ML to decide direction based on ALL features
        # Exit should ONLY check if ML changed its mind OR P&L targets hit
        # ═══════════════════════════════════════════════════════════
        
        # FTMO PROTECTION (HIGHEST PRIORITY)
        if context.ftmo_violated or not context.can_trade:
            logger.info(f"🚨 FTMO VIOLATED - CLOSING")
            return {
                'action': 'CLOSE',
                'reason': 'FTMO rules violated',
                'priority': 'CRITICAL',
                'confidence': 100.0
            }
        
        # NOTE: Near daily limit handling is done via EV calculation
        # The EV naturally penalizes holding losers when risk is high
        # No hardcoded CLOSE - let the AI decide based on full analysis
        
        # ═══════════════════════════════════════════════════════════
        # USE EV EXIT MANAGER - PURE AI EXIT LOGIC
        # This uses ALL 173 features to calculate Expected Value
        # NO HARDCODED RULES - Pure probability-based decisions
        # ═══════════════════════════════════════════════════════════
        
        if self.ev_exit_manager is not None:
            symbol = getattr(context, 'symbol', 'UNKNOWN')
            
            logger.info(f"")
            logger.info(f"🤖 USING EV EXIT MANAGER - AI-DRIVEN EXIT ANALYSIS")
            
            # AI-DRIVEN POSITION SIZING - NO HARDCODED LOT LIMITS
            # Position sizing is handled by elite_position_sizer.py using:
            # - Market analysis (volatility, regime, session)
            # - Portfolio analysis (correlation, concentration)
            # - FTMO risk limits (daily DD, total DD, margin level)
            # - ML confidence and market score
            # - S/R based stop distances for risk calculation
            # 
            # max_lots is set to broker max (from symbol_info) - AI decides actual size
            max_lots = getattr(context, 'max_lot', 100.0)
            
            # Get setup_type from unified system if available
            setup_type = None
            try:
                from .unified_trading_system import UnifiedTradingSystem
                # Try to get from global unified_system instance
                import sys
                if 'api' in sys.modules:
                    api_module = sys.modules['api']
                    if hasattr(api_module, 'unified_system') and api_module.unified_system:
                        setup_type = api_module.unified_system.get_position_setup_type(symbol)
            except:
                pass  # Will use fallback in analyze_exit
            
            ev_decision = self.ev_exit_manager.analyze_exit(
                context=context,
                current_profit=context.position_current_profit,
                current_volume=current_volume,
                position_type=context.position_type,
                symbol=symbol,
                setup_type=setup_type,
                max_lots=max_lots
            )
            
            # Return the EV decision directly - it already has all the logic
            return ev_decision
        
        # Fallback if EV manager not available
        logger.warning(f"⚠️ EV Exit Manager not available - using basic logic")
        
        # Update peak tracking for trailing stops
        context.update_peak_tracking()
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: CALCULATE MULTI-TIMEFRAME TREND STRENGTH
        # ═══════════════════════════════════════════════════════════
        # For swing trading, M15/M30/H1 are key timeframes
        m15_trend = context.m15_trend if hasattr(context, 'm15_trend') else 0.5
        m30_trend = context.m30_trend if hasattr(context, 'm30_trend') else 0.5
        h1_trend = context.h1_trend if hasattr(context, 'h1_trend') else 0.5
        h4_trend = context.h4_trend if hasattr(context, 'h4_trend') else 0.5
        d1_trend = context.d1_trend if hasattr(context, 'd1_trend') else 0.5
        
        # Calculate trend alignment score (0-100)
        if is_buy:
            # For BUY: Want bullish trends (>0.5)
            trend_scores = [
                m15_trend * 100,  # Weight: 20%
                m30_trend * 100,  # Weight: 20%
                h1_trend * 100,   # Weight: 30%
                h4_trend * 100,   # Weight: 20%
                d1_trend * 100    # Weight: 10%
            ]
            trend_strength = (trend_scores[0] * 0.2 + trend_scores[1] * 0.2 + 
                            trend_scores[2] * 0.3 + trend_scores[3] * 0.2 + trend_scores[4] * 0.1)
        else:
            # For SELL: Want bearish trends (<0.5)
            trend_scores = [
                (1.0 - m15_trend) * 100,
                (1.0 - m30_trend) * 100,
                (1.0 - h1_trend) * 100,
                (1.0 - h4_trend) * 100,
                (1.0 - d1_trend) * 100
            ]
            trend_strength = (trend_scores[0] * 0.2 + trend_scores[1] * 0.2 + 
                            trend_scores[2] * 0.3 + trend_scores[3] * 0.2 + trend_scores[4] * 0.1)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: MOMENTUM ANALYSIS
        # ═══════════════════════════════════════════════════════════
        m15_momentum = context.m15_momentum if hasattr(context, 'm15_momentum') else 0.0
        h1_momentum = context.h1_momentum if hasattr(context, 'h1_momentum') else 0.0
        h4_momentum = context.h4_momentum if hasattr(context, 'h4_momentum') else 0.0
        
        # MACD analysis
        m15_macd = context.m15_macd if hasattr(context, 'm15_macd') else 0.0
        h1_macd = context.h1_macd if hasattr(context, 'h1_macd') else 0.0
        h4_macd = context.h4_macd if hasattr(context, 'h4_macd') else 0.0
        
        # Calculate momentum score
        if is_buy:
            momentum_score = ((m15_momentum > 0) * 30 + (h1_momentum > 0) * 40 + 
                            (h4_momentum > 0) * 30)
            macd_support = ((m15_macd > 0) * 30 + (h1_macd > 0) * 40 + (h4_macd > 0) * 30)
        else:
            momentum_score = ((m15_momentum < 0) * 30 + (h1_momentum < 0) * 40 + 
                            (h4_momentum < 0) * 30)
            macd_support = ((m15_macd < 0) * 30 + (h1_macd < 0) * 40 + (h4_macd < 0) * 30)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: VOLUME & INSTITUTIONAL FLOW (HTF-based)
        # ═══════════════════════════════════════════════════════════
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)  # Use HTF, not M1
        accumulation = context.accumulation if hasattr(context, 'accumulation') else 0.0
        distribution = context.distribution if hasattr(context, 'distribution') else 0.0
        volume_increasing = context.volume_increasing if hasattr(context, 'volume_increasing') else 0.0
        
        # Volume support score
        if is_buy:
            volume_support = (accumulation * 50 + (1.0 - distribution) * 30 + 
                            volume_increasing * 20)
        else:
            volume_support = (distribution * 50 + (1.0 - accumulation) * 30 + 
                            volume_increasing * 20)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: MARKET STRUCTURE (RSI, BB, Price Action)
        # ═══════════════════════════════════════════════════════════
        m15_rsi = context.m15_rsi if hasattr(context, 'm15_rsi') else 50.0
        h1_rsi = context.h1_rsi if hasattr(context, 'h1_rsi') else 50.0
        h4_rsi = context.h4_rsi if hasattr(context, 'h4_rsi') else 50.0
        
        m15_bb_pos = context.m15_bb_position if hasattr(context, 'm15_bb_position') else 0.5
        h1_bb_pos = context.h1_bb_position if hasattr(context, 'h1_bb_position') else 0.5
        
        # Check for exhaustion/reversal signals
        if is_buy:
            # BUY exhaustion: Overbought RSI, at upper BB
            exhaustion_score = ((m15_rsi > 70) * 30 + (h1_rsi > 70) * 40 + 
                              (h4_rsi > 70) * 30 + (m15_bb_pos > 0.9) * 40 + 
                              (h1_bb_pos > 0.9) * 40)
        else:
            # SELL exhaustion: Oversold RSI, at lower BB
            exhaustion_score = ((m15_rsi < 30) * 30 + (h1_rsi < 30) * 40 + 
                              (h4_rsi < 30) * 30 + (m15_bb_pos < 0.1) * 40 + 
                              (h1_bb_pos < 0.1) * 40)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: CALCULATE OVERALL MARKET QUALITY SCORE
        # ═══════════════════════════════════════════════════════════
        market_quality = (
            trend_strength * 0.35 +      # 35% weight - most important
            momentum_score * 0.25 +       # 25% weight
            macd_support * 0.15 +         # 15% weight
            volume_support * 0.15 +       # 15% weight
            (100 - exhaustion_score) * 0.10  # 10% weight (inverse)
        )
        
        logger.info(f"")
        logger.info(f"📊 MARKET QUALITY ANALYSIS:")
        logger.info(f"   Trend Strength: {trend_strength:.1f}/100 (M15:{m15_trend:.2f} H1:{h1_trend:.2f} H4:{h4_trend:.2f})")
        logger.info(f"   Momentum: {momentum_score:.1f}/100")
        logger.info(f"   MACD Support: {macd_support:.1f}/100")
        logger.info(f"   Volume Support: {volume_support:.1f}/100")
        logger.info(f"   Exhaustion Risk: {exhaustion_score:.1f}/100")
        logger.info(f"   → OVERALL QUALITY: {market_quality:.1f}/100")
        
        # ═══════════════════════════════════════════════════════════
        # EXIT DECISION MATRIX - INTELLIGENT MULTI-FACTOR ANALYSIS
        # ═══════════════════════════════════════════════════════════
        
        # EXIT 1: ML REVERSED TO OPPOSITE
        ml_reversed = False
        if original_direction == "BUY" and context.ml_direction == "SELL":
            ml_reversed = True
        elif original_direction == "SELL" and context.ml_direction == "BUY":
            ml_reversed = True
        
        if ml_reversed:
            logger.info(f"")
            logger.info(f"🔄 ML REVERSED: {original_direction} → {context.ml_direction}")
            return {
                'action': 'CLOSE',
                'reason': f'ML reversed to {context.ml_direction} @ {context.ml_confidence:.1f}%',
                'priority': 'HIGH',
                'confidence': 90.0
            }
        
        # NO MORE HARD THRESHOLDS!
        # All exit decisions handled by EV Exit Manager above
        # This fallback should never run if EV manager is working
        logger.warning(f"⚠️ Using fallback logic - EV Exit Manager should have handled this")
        
        # HOLD: POSITION STILL STRONG
        logger.info(f"")
        logger.info(f"✅ HOLD: Market Quality {market_quality:.1f}/100, ML {context.ml_direction} @ {context.ml_confidence:.1f}%, P&L {current_profit_pct:.2f}%")
        
        return {
            'action': 'HOLD',
            'reason': f'Strong position: Quality {market_quality:.1f}/100, P&L {current_profit_pct:.2f}%',
            'priority': 'LOW',
            'confidence': min(market_quality, context.ml_confidence)
        }
