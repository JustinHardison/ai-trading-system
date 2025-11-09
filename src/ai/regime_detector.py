"""
Market Regime Detection - Hedge Fund Grade
AI-powered regime classification using multiple indicators

Based on institutional approaches:
- Hidden Markov Models concept (simplified for real-time)
- Multi-factor regime scoring
- Regime persistence and transition detection
- Cross-asset regime confirmation
"""
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications"""
    TRENDING_STRONG = "TRENDING_STRONG"      # Strong directional move
    TRENDING_WEAK = "TRENDING_WEAK"          # Weak but directional
    RANGING_TIGHT = "RANGING_TIGHT"          # Low volatility consolidation
    RANGING_WIDE = "RANGING_WIDE"            # High volatility but no direction
    VOLATILE_BREAKOUT = "VOLATILE_BREAKOUT"  # Volatility expansion, potential breakout
    VOLATILE_REVERSAL = "VOLATILE_REVERSAL"  # Volatility with reversal signals
    RISK_OFF = "RISK_OFF"                    # Flight to safety
    RISK_ON = "RISK_ON"                      # Risk appetite high
    TRANSITION = "TRANSITION"                # Regime changing


@dataclass
class RegimeState:
    """Current regime state with confidence"""
    regime: MarketRegime
    confidence: float  # 0-1
    duration_minutes: int
    trend_direction: str  # 'UP', 'DOWN', 'NEUTRAL'
    volatility_percentile: float  # 0-100
    momentum_score: float  # -1 to 1
    risk_appetite: float  # 0-1
    regime_stability: float  # 0-1 (how stable is current regime)


class RegimeDetector:
    """
    AI-powered market regime detection
    
    Uses multiple factors to classify market state:
    1. Trend strength (ADX, moving average alignment)
    2. Volatility regime (ATR percentile, Bollinger width)
    3. Momentum (RSI, MACD divergence)
    4. Market structure (higher highs/lows)
    5. Volume patterns (accumulation/distribution)
    6. Cross-asset signals (risk-on/risk-off indicators)
    """
    
    def __init__(self):
        # Historical regime tracking
        self.regime_history: deque = deque(maxlen=1000)
        self.current_regime: Optional[RegimeState] = None
        self.regime_start_time: datetime = datetime.now()
        
        # Volatility history for percentile calculation
        self.volatility_history: deque = deque(maxlen=500)
        
        # Regime transition matrix (probability of transitioning between regimes)
        # Based on historical market behavior
        self.transition_matrix = {
            MarketRegime.TRENDING_STRONG: {
                MarketRegime.TRENDING_STRONG: 0.70,
                MarketRegime.TRENDING_WEAK: 0.15,
                MarketRegime.VOLATILE_REVERSAL: 0.10,
                MarketRegime.RANGING_TIGHT: 0.05,
            },
            MarketRegime.TRENDING_WEAK: {
                MarketRegime.TRENDING_STRONG: 0.20,
                MarketRegime.TRENDING_WEAK: 0.40,
                MarketRegime.RANGING_TIGHT: 0.25,
                MarketRegime.RANGING_WIDE: 0.15,
            },
            MarketRegime.RANGING_TIGHT: {
                MarketRegime.RANGING_TIGHT: 0.50,
                MarketRegime.VOLATILE_BREAKOUT: 0.25,
                MarketRegime.TRENDING_WEAK: 0.20,
                MarketRegime.RANGING_WIDE: 0.05,
            },
            MarketRegime.RANGING_WIDE: {
                MarketRegime.RANGING_WIDE: 0.40,
                MarketRegime.TRENDING_WEAK: 0.25,
                MarketRegime.VOLATILE_BREAKOUT: 0.20,
                MarketRegime.RANGING_TIGHT: 0.15,
            },
            MarketRegime.VOLATILE_BREAKOUT: {
                MarketRegime.TRENDING_STRONG: 0.40,
                MarketRegime.VOLATILE_REVERSAL: 0.25,
                MarketRegime.VOLATILE_BREAKOUT: 0.20,
                MarketRegime.RANGING_WIDE: 0.15,
            },
            MarketRegime.VOLATILE_REVERSAL: {
                MarketRegime.TRENDING_WEAK: 0.30,
                MarketRegime.RANGING_WIDE: 0.30,
                MarketRegime.VOLATILE_REVERSAL: 0.25,
                MarketRegime.VOLATILE_BREAKOUT: 0.15,
            },
        }
        
        # Regime-specific trading parameters
        self.regime_parameters = {
            MarketRegime.TRENDING_STRONG: {
                'position_size_mult': 1.2,
                'stop_mult': 1.5,  # Wider stops in trends
                'target_mult': 2.0,  # Larger targets
                'scale_in_allowed': True,
                'scale_out_early': False,
                'patience': 'HIGH',
            },
            MarketRegime.TRENDING_WEAK: {
                'position_size_mult': 1.0,
                'stop_mult': 1.2,
                'target_mult': 1.5,
                'scale_in_allowed': True,
                'scale_out_early': False,
                'patience': 'MEDIUM',
            },
            MarketRegime.RANGING_TIGHT: {
                'position_size_mult': 0.7,
                'stop_mult': 0.8,  # Tighter stops in ranges
                'target_mult': 1.0,  # Smaller targets
                'scale_in_allowed': False,
                'scale_out_early': True,
                'patience': 'LOW',
            },
            MarketRegime.RANGING_WIDE: {
                'position_size_mult': 0.8,
                'stop_mult': 1.0,
                'target_mult': 1.2,
                'scale_in_allowed': False,
                'scale_out_early': True,
                'patience': 'LOW',
            },
            MarketRegime.VOLATILE_BREAKOUT: {
                'position_size_mult': 0.9,
                'stop_mult': 1.3,
                'target_mult': 1.8,
                'scale_in_allowed': True,
                'scale_out_early': False,
                'patience': 'MEDIUM',
            },
            MarketRegime.VOLATILE_REVERSAL: {
                'position_size_mult': 0.6,
                'stop_mult': 1.0,
                'target_mult': 1.0,
                'scale_in_allowed': False,
                'scale_out_early': True,
                'patience': 'LOW',
            },
            MarketRegime.RISK_OFF: {
                'position_size_mult': 0.5,
                'stop_mult': 0.8,
                'target_mult': 0.8,
                'scale_in_allowed': False,
                'scale_out_early': True,
                'patience': 'LOW',
            },
            MarketRegime.RISK_ON: {
                'position_size_mult': 1.1,
                'stop_mult': 1.2,
                'target_mult': 1.5,
                'scale_in_allowed': True,
                'scale_out_early': False,
                'patience': 'MEDIUM',
            },
            MarketRegime.TRANSITION: {
                'position_size_mult': 0.7,
                'stop_mult': 1.0,
                'target_mult': 1.0,
                'scale_in_allowed': False,
                'scale_out_early': False,
                'patience': 'MEDIUM',
            },
        }
    
    def detect_regime(
        self,
        context,  # EnhancedTradingContext
        cross_asset_data: Optional[Dict] = None
    ) -> RegimeState:
        """
        Detect current market regime using all available data
        
        Args:
            context: EnhancedTradingContext with all market data
            cross_asset_data: Optional cross-asset signals (VIX, safe havens, etc.)
            
        Returns:
            RegimeState with regime classification and confidence
        """
        
        # ═══════════════════════════════════════════════════════════
        # FACTOR 1: TREND STRENGTH (ADX + MA Alignment)
        # ═══════════════════════════════════════════════════════════
        
        h4_adx = getattr(context, 'h4_adx', 25.0)
        d1_adx = getattr(context, 'd1_adx', 25.0)
        htf_adx = getattr(context, 'htf_adx', 25.0)
        
        # Trend alignment across timeframes
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        # Calculate trend strength score (0-1)
        adx_score = (h4_adx + d1_adx) / 2 / 100  # Normalize to 0-1
        
        # Trend alignment: how aligned are the timeframes?
        trends = [h1_trend, h4_trend, d1_trend]
        trend_alignment = 1.0 - np.std(trends) * 2  # Low std = high alignment
        trend_alignment = max(0, min(1, trend_alignment))
        
        # Trend direction
        avg_trend = np.mean(trends)
        if avg_trend > 0.6:
            trend_direction = 'UP'
        elif avg_trend < 0.4:
            trend_direction = 'DOWN'
        else:
            trend_direction = 'NEUTRAL'
        
        trend_strength = (adx_score * 0.6 + trend_alignment * 0.4)
        
        # ═══════════════════════════════════════════════════════════
        # FACTOR 2: VOLATILITY REGIME
        # ═══════════════════════════════════════════════════════════
        
        h1_volatility = getattr(context, 'h1_volatility', 0.01)
        h4_volatility = getattr(context, 'h4_volatility', 0.01)
        vol_expanding = getattr(context, 'vol_expanding', 0.0)
        
        # Update volatility history
        current_vol = (h1_volatility + h4_volatility) / 2
        self.volatility_history.append(current_vol)
        
        # Calculate volatility percentile
        if len(self.volatility_history) >= 20:
            vol_percentile = (sum(1 for v in self.volatility_history if v < current_vol) 
                            / len(self.volatility_history) * 100)
        else:
            vol_percentile = 50.0
        
        # Volatility regime score
        if vol_percentile > 80:
            vol_regime = 'HIGH'
            vol_score = 0.9
        elif vol_percentile > 60:
            vol_regime = 'ELEVATED'
            vol_score = 0.7
        elif vol_percentile < 20:
            vol_regime = 'LOW'
            vol_score = 0.2
        elif vol_percentile < 40:
            vol_regime = 'COMPRESSED'
            vol_score = 0.3
        else:
            vol_regime = 'NORMAL'
            vol_score = 0.5
        
        # ═══════════════════════════════════════════════════════════
        # FACTOR 3: MOMENTUM
        # ═══════════════════════════════════════════════════════════
        
        h4_rsi = getattr(context, 'h4_rsi', 50.0)
        d1_rsi = getattr(context, 'd1_rsi', 50.0)
        h4_momentum = getattr(context, 'h4_momentum', 0.0)
        d1_momentum = getattr(context, 'd1_momentum', 0.0)
        
        # Momentum score (-1 to 1)
        rsi_momentum = ((h4_rsi + d1_rsi) / 2 - 50) / 50  # -1 to 1
        price_momentum = (h4_momentum + d1_momentum) / 2
        
        momentum_score = rsi_momentum * 0.4 + price_momentum * 0.6
        momentum_score = max(-1, min(1, momentum_score))
        
        # ═══════════════════════════════════════════════════════════
        # FACTOR 4: MARKET STRUCTURE
        # ═══════════════════════════════════════════════════════════
        
        h4_structure = getattr(context, 'h4_market_structure', 0.0)
        d1_structure = getattr(context, 'd1_market_structure', 0.0)
        
        # Structure score (-1 to 1): positive = bullish structure, negative = bearish
        structure_score = (h4_structure * 0.4 + d1_structure * 0.6)
        
        # ═══════════════════════════════════════════════════════════
        # FACTOR 5: VOLUME PATTERNS
        # ═══════════════════════════════════════════════════════════
        
        h4_volume_divergence = getattr(context, 'h4_volume_divergence', 0.0)
        accumulation = getattr(context, 'accumulation', 0.0)
        distribution = getattr(context, 'distribution', 0.0)
        
        # Volume health: low divergence + accumulation = healthy
        volume_health = (1.0 - h4_volume_divergence) * 0.5 + accumulation * 0.3 - distribution * 0.2
        volume_health = max(0, min(1, volume_health))
        
        # ═══════════════════════════════════════════════════════════
        # FACTOR 6: RISK APPETITE (Cross-Asset)
        # ═══════════════════════════════════════════════════════════
        
        risk_appetite = 0.5  # Default neutral
        
        if cross_asset_data:
            # VIX-based risk (if available)
            vix = cross_asset_data.get('vix', 20)
            if vix > 30:
                risk_appetite = 0.2  # Risk-off
            elif vix > 25:
                risk_appetite = 0.35
            elif vix < 15:
                risk_appetite = 0.8  # Risk-on
            elif vix < 18:
                risk_appetite = 0.65
            
            # Gold vs Stocks (safe haven indicator)
            gold_strength = cross_asset_data.get('gold_strength', 0.5)
            stock_strength = cross_asset_data.get('stock_strength', 0.5)
            
            if gold_strength > 0.7 and stock_strength < 0.4:
                risk_appetite = min(risk_appetite, 0.3)  # Risk-off signal
            elif stock_strength > 0.7 and gold_strength < 0.4:
                risk_appetite = max(risk_appetite, 0.7)  # Risk-on signal
        
        # ═══════════════════════════════════════════════════════════
        # REGIME CLASSIFICATION
        # ═══════════════════════════════════════════════════════════
        
        regime_scores = {}
        
        # TRENDING_STRONG: High ADX + aligned trends + good momentum
        regime_scores[MarketRegime.TRENDING_STRONG] = (
            (1.0 if htf_adx > 30 else htf_adx / 30) * 0.35 +
            trend_alignment * 0.30 +
            abs(momentum_score) * 0.20 +
            volume_health * 0.15
        )
        
        # TRENDING_WEAK: Moderate ADX + some alignment
        regime_scores[MarketRegime.TRENDING_WEAK] = (
            (1.0 if 20 < htf_adx < 30 else 0.5) * 0.30 +
            trend_alignment * 0.25 +
            (0.5 if abs(momentum_score) < 0.5 else 0.3) * 0.25 +
            volume_health * 0.20
        )
        
        # RANGING_TIGHT: Low ADX + low volatility + no direction
        regime_scores[MarketRegime.RANGING_TIGHT] = (
            (1.0 if htf_adx < 20 else (30 - htf_adx) / 10) * 0.35 +
            (1.0 if vol_percentile < 30 else 0.3) * 0.30 +
            (1.0 - trend_alignment) * 0.20 +
            (1.0 - abs(momentum_score)) * 0.15
        )
        
        # RANGING_WIDE: Low ADX + high volatility
        regime_scores[MarketRegime.RANGING_WIDE] = (
            (1.0 if htf_adx < 25 else 0.4) * 0.30 +
            (1.0 if vol_percentile > 60 else 0.3) * 0.35 +
            (1.0 - trend_alignment) * 0.20 +
            (1.0 - volume_health) * 0.15
        )
        
        # VOLATILE_BREAKOUT: Expanding volatility + structure break
        regime_scores[MarketRegime.VOLATILE_BREAKOUT] = (
            vol_expanding * 0.35 +
            (1.0 if vol_percentile > 70 else vol_percentile / 70) * 0.25 +
            abs(structure_score) * 0.25 +
            abs(momentum_score) * 0.15
        )
        
        # VOLATILE_REVERSAL: High volatility + momentum divergence
        regime_scores[MarketRegime.VOLATILE_REVERSAL] = (
            (1.0 if vol_percentile > 70 else 0.3) * 0.30 +
            h4_volume_divergence * 0.30 +
            (1.0 if abs(h4_rsi - 50) > 20 else 0.3) * 0.25 +
            (1.0 - volume_health) * 0.15
        )
        
        # RISK_OFF: Low risk appetite
        regime_scores[MarketRegime.RISK_OFF] = (
            (1.0 - risk_appetite) * 0.50 +
            (1.0 if vol_percentile > 70 else 0.3) * 0.30 +
            (1.0 - volume_health) * 0.20
        )
        
        # RISK_ON: High risk appetite
        regime_scores[MarketRegime.RISK_ON] = (
            risk_appetite * 0.50 +
            volume_health * 0.30 +
            (1.0 if vol_percentile < 50 else 0.4) * 0.20
        )
        
        # Find best regime
        best_regime = max(regime_scores, key=regime_scores.get)
        best_score = regime_scores[best_regime]
        
        # Check for regime stability
        second_best_score = sorted(regime_scores.values(), reverse=True)[1]
        regime_stability = best_score - second_best_score
        
        # If scores are too close, mark as TRANSITION
        if regime_stability < 0.1:
            best_regime = MarketRegime.TRANSITION
            regime_stability = 0.3
        
        # Calculate duration
        duration_minutes = 0
        if self.current_regime and self.current_regime.regime == best_regime:
            duration_minutes = int((datetime.now() - self.regime_start_time).total_seconds() / 60)
        else:
            self.regime_start_time = datetime.now()
        
        # Create regime state
        new_state = RegimeState(
            regime=best_regime,
            confidence=best_score,
            duration_minutes=duration_minutes,
            trend_direction=trend_direction,
            volatility_percentile=vol_percentile,
            momentum_score=momentum_score,
            risk_appetite=risk_appetite,
            regime_stability=regime_stability
        )
        
        # Log regime change
        if self.current_regime is None or self.current_regime.regime != best_regime:
            logger.info(f"📊 REGIME DETECTED: {best_regime.value}")
            logger.info(f"   Confidence: {best_score:.2f}, Stability: {regime_stability:.2f}")
            logger.info(f"   Trend: {trend_direction}, Vol%: {vol_percentile:.0f}, Momentum: {momentum_score:.2f}")
        
        # Update history
        self.regime_history.append((datetime.now(), new_state))
        self.current_regime = new_state
        
        return new_state
    
    def get_regime_parameters(self, regime: MarketRegime = None) -> Dict:
        """
        Get trading parameters for current or specified regime
        """
        if regime is None:
            regime = self.current_regime.regime if self.current_regime else MarketRegime.TRANSITION
        
        return self.regime_parameters.get(regime, self.regime_parameters[MarketRegime.TRANSITION])
    
    def get_regime_trading_bias(self) -> Dict:
        """
        Get trading bias based on current regime
        
        Returns actionable trading guidance
        """
        if not self.current_regime:
            return {
                'bias': 'NEUTRAL',
                'confidence': 0.5,
                'action': 'Wait for regime clarity'
            }
        
        regime = self.current_regime.regime
        params = self.get_regime_parameters(regime)
        
        # Determine bias
        if regime in [MarketRegime.TRENDING_STRONG, MarketRegime.TRENDING_WEAK]:
            bias = self.current_regime.trend_direction
            action = f"Trade with {bias} trend, use wider stops"
        elif regime in [MarketRegime.RANGING_TIGHT, MarketRegime.RANGING_WIDE]:
            bias = 'NEUTRAL'
            action = "Fade extremes, use tight stops, quick profits"
        elif regime == MarketRegime.VOLATILE_BREAKOUT:
            bias = self.current_regime.trend_direction
            action = "Trade breakout direction, manage risk carefully"
        elif regime == MarketRegime.VOLATILE_REVERSAL:
            bias = 'COUNTER_TREND'
            action = "Look for reversal entries, tight stops"
        elif regime == MarketRegime.RISK_OFF:
            bias = 'DEFENSIVE'
            action = "Reduce exposure, favor safe havens"
        elif regime == MarketRegime.RISK_ON:
            bias = 'AGGRESSIVE'
            action = "Favor risk assets, larger positions"
        else:
            bias = 'NEUTRAL'
            action = "Wait for regime clarity"
        
        return {
            'regime': regime.value,
            'bias': bias,
            'confidence': self.current_regime.confidence,
            'stability': self.current_regime.regime_stability,
            'duration_minutes': self.current_regime.duration_minutes,
            'action': action,
            'parameters': params
        }
    
    def should_reduce_exposure(self) -> Tuple[bool, str]:
        """
        Check if current regime suggests reducing exposure
        """
        if not self.current_regime:
            return False, "No regime data"
        
        regime = self.current_regime.regime
        
        # High volatility regimes
        if regime in [MarketRegime.VOLATILE_REVERSAL, MarketRegime.RISK_OFF]:
            return True, f"Regime {regime.value} suggests caution"
        
        # Unstable regime
        if self.current_regime.regime_stability < 0.15:
            return True, "Regime unstable - reduce exposure"
        
        # Very high volatility
        if self.current_regime.volatility_percentile > 85:
            return True, f"Volatility at {self.current_regime.volatility_percentile:.0f}th percentile"
        
        return False, "Regime stable"


# Global instance
_regime_detector = None

def get_regime_detector() -> RegimeDetector:
    """Get global regime detector instance"""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector()
    return _regime_detector
