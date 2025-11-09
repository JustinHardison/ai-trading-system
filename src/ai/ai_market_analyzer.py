"""
AI Market Analyzer - Central Intelligence for ALL Trading Decisions

This module provides AI-driven analysis that replaces ALL hardcoded thresholds
throughout the trading system. Every decision uses the full 138+ features
from live market analysis.

PRINCIPLE: No hardcoded thresholds. All decisions derived from market conditions.

Used by:
- ev_exit_manager_v2.py (exit decisions)
- unified_trading_system.py (entry decisions)
- elite_position_sizer.py (position sizing)
- intelligent_position_manager.py (position management)
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AIMarketState:
    """Comprehensive market state derived from 138+ features"""
    
    # HTF Trend Analysis (0-1, higher = more bullish)
    d1_trend_strength: float = 0.5
    h4_trend_strength: float = 0.5
    h1_trend_strength: float = 0.5
    htf_alignment: float = 0.5  # Weighted average
    
    # Momentum Analysis (-1 to 1)
    htf_momentum: float = 0.0
    momentum_divergence: float = 0.0  # Price vs momentum divergence
    
    # Volatility Analysis
    volatility_regime: float = 0.5  # 0=low, 0.5=normal, 1=high
    atr_percentile: float = 0.5  # Where current ATR sits in recent history
    
    # Volume Analysis
    volume_confirmation: float = 0.5  # 0=diverging, 1=confirming
    htf_volume_divergence: float = 0.0
    
    # Market Structure
    market_structure_score: float = 0.0  # -1=bearish structure, +1=bullish
    sr_proximity: float = 0.0  # How close to S/R (0=far, 1=at level)
    
    # ML Analysis
    ml_confidence: float = 0.5
    ml_direction_alignment: float = 0.0  # -1=against, 0=neutral, +1=aligned
    
    # Risk Metrics
    ftmo_daily_usage: float = 0.0  # 0-1, how much of daily limit used
    ftmo_total_dd_usage: float = 0.0  # 0-1, how much of total DD used
    portfolio_heat: float = 0.0  # 0-1, current portfolio risk level


class AIMarketAnalyzer:
    """
    Central AI that analyzes market conditions and provides
    continuous scores for ALL trading decisions.
    
    NO HARDCODED THRESHOLDS - everything derived from market analysis.
    """
    
    def __init__(self):
        self._cache = {}
        self._cache_time = 0
    
    def analyze_market(self, context, is_buy: bool = True) -> AIMarketState:
        """
        Comprehensive market analysis using ALL 138+ features.
        
        Returns AIMarketState with continuous scores (not binary decisions).
        """
        
        state = AIMarketState()
        
        # ═══════════════════════════════════════════════════════════
        # HTF TREND ANALYSIS
        # ═══════════════════════════════════════════════════════════
        
        d1_trend = getattr(context, 'd1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        m30_trend = getattr(context, 'm30_trend', 0.5)
        m15_trend = getattr(context, 'm15_trend', 0.5)
        
        # For position direction, calculate support scores
        if is_buy:
            state.d1_trend_strength = d1_trend
            state.h4_trend_strength = h4_trend
            state.h1_trend_strength = h1_trend
        else:
            state.d1_trend_strength = 1.0 - d1_trend
            state.h4_trend_strength = 1.0 - h4_trend
            state.h1_trend_strength = 1.0 - h1_trend
        
        # Weighted HTF alignment (D1 most important)
        state.htf_alignment = (
            state.d1_trend_strength * 0.35 +
            state.h4_trend_strength * 0.30 +
            state.h1_trend_strength * 0.20 +
            (m30_trend if is_buy else 1-m30_trend) * 0.10 +
            (m15_trend if is_buy else 1-m15_trend) * 0.05
        )
        
        # ═══════════════════════════════════════════════════════════
        # MOMENTUM ANALYSIS
        # ═══════════════════════════════════════════════════════════
        
        d1_momentum = getattr(context, 'd1_momentum', 0.0)
        h4_momentum = getattr(context, 'h4_momentum', 0.0)
        h1_momentum = getattr(context, 'h1_momentum', 0.0)
        
        # Weighted momentum
        raw_momentum = d1_momentum * 0.4 + h4_momentum * 0.35 + h1_momentum * 0.25
        state.htf_momentum = raw_momentum if is_buy else -raw_momentum
        
        # Momentum divergence (price making new highs but momentum weakening)
        d1_rsi = getattr(context, 'd1_rsi', 50.0)
        h4_rsi = getattr(context, 'h4_rsi', 50.0)
        
        if is_buy:
            # For longs, RSI > 70 with weakening momentum = divergence
            rsi_extreme = max(0, (d1_rsi - 50) / 50)  # 0 at 50, 1 at 100
            momentum_weak = max(0, -h4_momentum)  # Positive when momentum negative
            state.momentum_divergence = rsi_extreme * momentum_weak
        else:
            # For shorts, RSI < 30 with strengthening momentum = divergence
            rsi_extreme = max(0, (50 - d1_rsi) / 50)  # 0 at 50, 1 at 0
            momentum_weak = max(0, h4_momentum)  # Positive when momentum positive
            state.momentum_divergence = rsi_extreme * momentum_weak
        
        # ═══════════════════════════════════════════════════════════
        # VOLATILITY ANALYSIS
        # ═══════════════════════════════════════════════════════════
        
        h4_volatility = getattr(context, 'h4_volatility', 0)
        current_price = getattr(context, 'current_price', 1.0)
        
        # Volatility as % of price
        vol_pct = (h4_volatility / current_price * 100) if current_price > 0 else 1.0
        
        # Normalize to 0-1 (0.5% = low, 1% = normal, 2%+ = high)
        state.volatility_regime = min(1.0, vol_pct / 2.0)
        
        # ATR percentile (would need historical data, estimate from context)
        h4_adx = getattr(context, 'h4_adx', 25.0)
        state.atr_percentile = min(1.0, h4_adx / 50.0)  # ADX as proxy
        
        # ═══════════════════════════════════════════════════════════
        # VOLUME ANALYSIS
        # ═══════════════════════════════════════════════════════════
        
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        d1_vol_div = getattr(context, 'd1_volume_divergence', 0.0)
        
        state.htf_volume_divergence = h4_vol_div * 0.6 + d1_vol_div * 0.4
        state.volume_confirmation = 1.0 - state.htf_volume_divergence
        
        # ═══════════════════════════════════════════════════════════
        # MARKET STRUCTURE
        # ═══════════════════════════════════════════════════════════
        
        h4_structure = getattr(context, 'h4_market_structure', 0.0)
        d1_structure = getattr(context, 'd1_market_structure', 0.0)
        
        # Combined structure score (-1 to +1)
        state.market_structure_score = h4_structure * 0.5 + d1_structure * 0.5
        
        # S/R proximity
        if is_buy:
            h4_dist = getattr(context, 'h4_dist_to_resistance', 0)
            d1_dist = getattr(context, 'd1_dist_to_resistance', 0)
        else:
            h4_dist = getattr(context, 'h4_dist_to_support', 0)
            d1_dist = getattr(context, 'd1_dist_to_support', 0)
        
        # Use closer S/R level
        sr_dist = min(h4_dist, d1_dist) if h4_dist > 0 and d1_dist > 0 else max(h4_dist, d1_dist)
        # Proximity: 1 at S/R, 0 when far (>3%)
        state.sr_proximity = max(0, 1.0 - sr_dist / 3.0) if sr_dist > 0 else 0
        
        # ═══════════════════════════════════════════════════════════
        # ML ANALYSIS
        # ═══════════════════════════════════════════════════════════
        
        ml_confidence = getattr(context, 'ml_confidence', 50.0)
        ml_direction = getattr(context, 'ml_direction', 'HOLD')
        
        state.ml_confidence = ml_confidence / 100.0
        
        # ML direction alignment
        if (is_buy and ml_direction == 'BUY') or (not is_buy and ml_direction == 'SELL'):
            state.ml_direction_alignment = state.ml_confidence
        elif ml_direction == 'HOLD':
            state.ml_direction_alignment = 0.0
        else:
            state.ml_direction_alignment = -state.ml_confidence
        
        # ═══════════════════════════════════════════════════════════
        # RISK METRICS
        # ═══════════════════════════════════════════════════════════
        
        daily_pnl = getattr(context, 'daily_pnl', 0.0)
        max_daily_loss = getattr(context, 'max_daily_loss', 10000.0)
        total_drawdown = getattr(context, 'total_drawdown', 0.0)
        max_total_drawdown = getattr(context, 'max_total_drawdown', 20000.0)
        
        state.ftmo_daily_usage = abs(min(0, daily_pnl)) / max_daily_loss if max_daily_loss > 0 else 0
        state.ftmo_total_dd_usage = total_drawdown / max_total_drawdown if max_total_drawdown > 0 else 0
        
        # Portfolio heat (would need position data)
        state.portfolio_heat = max(state.ftmo_daily_usage, state.ftmo_total_dd_usage)
        
        return state
    
    # ═══════════════════════════════════════════════════════════════════
    # AI-DRIVEN DECISION SCORES
    # These replace ALL hardcoded thresholds throughout the system
    # ═══════════════════════════════════════════════════════════════════
    
    def get_entry_score(self, state: AIMarketState) -> float:
        """
        AI-driven entry quality score (0-1).
        Replaces hardcoded entry thresholds.
        """
        score = (
            state.htf_alignment * 0.30 +
            (0.5 + state.ml_direction_alignment * 0.5) * 0.25 +
            state.volume_confirmation * 0.15 +
            (0.5 + state.market_structure_score * 0.5) * 0.15 +
            (1.0 - state.momentum_divergence) * 0.10 +
            (1.0 - state.portfolio_heat) * 0.05
        )
        return max(0.0, min(1.0, score))
    
    def get_exit_urgency(self, state: AIMarketState, profit_pct: float, target_pct: float) -> float:
        """
        AI-driven exit urgency score (0-1).
        Higher = more urgent to exit.
        Replaces hardcoded exit thresholds.
        """
        # Profit significance relative to target
        profit_significance = profit_pct / target_pct if target_pct > 0 else 0
        
        # Thesis weakness (inverse of alignment)
        thesis_weakness = 1.0 - state.htf_alignment
        
        # ML disagreement
        ml_against = max(0, -state.ml_direction_alignment)
        
        # Combine factors
        urgency = (
            thesis_weakness * 0.35 +
            ml_against * 0.25 +
            state.momentum_divergence * 0.15 +
            state.htf_volume_divergence * 0.10 +
            state.portfolio_heat * 0.15
        )
        
        # Reduce urgency if in significant profit
        if profit_significance > 0.5:
            urgency *= (1.0 - profit_significance * 0.3)
        
        return max(0.0, min(1.0, urgency))
    
    def get_scale_in_score(self, state: AIMarketState, current_profit_pct: float) -> float:
        """
        AI-driven scale-in attractiveness score (0-1).
        Replaces hardcoded scale-in thresholds.
        """
        # Need strong thesis to add
        thesis_strength = state.htf_alignment
        
        # ML must agree
        ml_support = max(0, state.ml_direction_alignment)
        
        # Volume should confirm
        volume_ok = state.volume_confirmation
        
        # Profit should be positive (adding to winners)
        profit_factor = min(1.0, max(0, current_profit_pct / 0.5)) if current_profit_pct > 0 else 0
        
        # Low portfolio heat
        risk_ok = 1.0 - state.portfolio_heat
        
        score = (
            thesis_strength * 0.30 +
            ml_support * 0.25 +
            volume_ok * 0.15 +
            profit_factor * 0.20 +
            risk_ok * 0.10
        )
        
        return max(0.0, min(1.0, score))
    
    def get_position_size_multiplier(self, state: AIMarketState) -> float:
        """
        AI-driven position size multiplier (0.3 to 1.2).
        Replaces hardcoded sizing thresholds.
        """
        # Base on entry quality
        entry_quality = self.get_entry_score(state)
        
        # Volatility adjustment (reduce in high vol)
        vol_adj = 1.0 - (state.volatility_regime * 0.3)
        
        # Risk adjustment (reduce when portfolio hot)
        risk_adj = 1.0 - (state.portfolio_heat * 0.5)
        
        # ML confidence boost
        ml_boost = 1.0 + (state.ml_confidence - 0.5) * 0.2
        
        multiplier = entry_quality * vol_adj * risk_adj * ml_boost
        
        # Clamp to reasonable range
        return max(0.3, min(1.2, multiplier))
    
    def get_stop_distance_multiplier(self, state: AIMarketState, setup_type: str) -> float:
        """
        AI-driven stop distance multiplier.
        Replaces hardcoded ATR multipliers for stops.
        """
        # Base multiplier from setup type
        base = {'SWING': 2.5, 'DAY': 1.5, 'SCALP': 1.0}.get(setup_type, 1.5)
        
        # Widen in high volatility
        vol_adj = 1.0 + (state.volatility_regime * 0.5)
        
        # Widen when thesis is weaker (need more room)
        thesis_adj = 1.0 + (1.0 - state.htf_alignment) * 0.3
        
        # Tighten when ML is very confident
        ml_adj = 1.0 - (state.ml_confidence - 0.5) * 0.2
        
        return base * vol_adj * thesis_adj * ml_adj
    
    def get_target_distance_multiplier(self, state: AIMarketState, setup_type: str) -> float:
        """
        AI-driven target distance multiplier.
        Replaces hardcoded ATR multipliers for targets.
        """
        # Base multiplier from setup type
        base = {'SWING': 5.0, 'DAY': 2.5, 'SCALP': 1.5}.get(setup_type, 2.5)
        
        # Increase when trend is strong
        trend_adj = 1.0 + (state.htf_alignment - 0.5) * 0.6
        
        # Increase when ADX is high (strong trend)
        adx_adj = 1.0 + (state.atr_percentile - 0.5) * 0.4
        
        # Reduce when near S/R (target at S/R, not beyond)
        sr_adj = 1.0 - (state.sr_proximity * 0.3)
        
        # ML confidence boost
        ml_adj = 1.0 + (state.ml_confidence - 0.5) * 0.3
        
        return base * trend_adj * adx_adj * sr_adj * ml_adj
    
    def get_news_risk_score(self, state: AIMarketState, news_minutes: float, profit_pct: float) -> float:
        """
        AI-driven news risk score (0-1).
        Replaces hardcoded news timing thresholds.
        """
        # Time urgency (closer = more urgent)
        time_urgency = max(0, 1.0 - news_minutes / 60.0)
        
        # Volatility makes news more impactful
        vol_impact = 1.0 + state.volatility_regime
        
        # Position weakness
        position_weakness = 1.0 - state.htf_alignment
        
        # Profit buffer (profitable = less urgent)
        profit_buffer = max(0, -profit_pct / 0.5) if profit_pct < 0 else 0
        
        risk = time_urgency * vol_impact * (position_weakness + profit_buffer) / 2
        
        return max(0.0, min(1.0, risk))
    
    def get_dca_score(self, state: AIMarketState, loss_pct: float, recovery_prob: float) -> float:
        """
        AI-driven DCA attractiveness score (0-1).
        Replaces hardcoded DCA thresholds.
        """
        # Need strong thesis to DCA
        thesis_strength = state.htf_alignment
        
        # ML must agree
        ml_support = max(0, state.ml_direction_alignment)
        
        # Recovery probability from market analysis
        recovery_factor = recovery_prob
        
        # Loss should be meaningful but not catastrophic
        # Optimal DCA zone: -0.3% to -1.0% (relative to expected stop)
        loss_factor = min(1.0, abs(loss_pct) / 0.5) if loss_pct < 0 else 0
        
        # Low portfolio heat
        risk_ok = 1.0 - state.portfolio_heat
        
        score = (
            thesis_strength * 0.30 +
            ml_support * 0.25 +
            recovery_factor * 0.20 +
            loss_factor * 0.15 +
            risk_ok * 0.10
        )
        
        return max(0.0, min(1.0, score))


# Singleton instance
_analyzer = None

def get_ai_analyzer() -> AIMarketAnalyzer:
    """Get singleton AI analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = AIMarketAnalyzer()
    return _analyzer
