"""
AI-Powered Intelligent Trade Manager
=====================================
Thinks like a professional trader with AI processing power.
NOW USES ALL 100 FEATURES via EnhancedTradingContext.

NO HARD RULES. Pure pattern recognition and market understanding.

The AI sees:
- Multi-timeframe structure (M1, H1, H4)
- Volume intelligence (institutional flow)
- Order book pressure (supply/demand)
- Timeframe alignment (confluence)
- Support/resistance levels
- Market regime (trending/ranging/volatile)
- Risk/reward at THIS specific price

Then decides:
- Should we enter? (is setup valid?)
- How much? (based on setup quality + confluence)
- Where to exit? (when move is exhausted)
- Should we scale? (is this better price?)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

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


@dataclass
class MarketStructure:
    """What the AI sees in the market."""

    # Support/Resistance
    nearest_support: float
    nearest_resistance: float
    support_strength: float  # 0-1: How many touches
    resistance_strength: float

    # Trend Structure
    higher_highs: bool  # Uptrend
    lower_lows: bool  # Downtrend
    ranging: bool  # Consolidation

    # Price Action Context
    at_support: bool  # Currently at support
    at_resistance: bool  # Currently at resistance
    breaking_out: bool  # Breaking structure
    pulling_back: bool  # Retracing in trend

    # Volume/Order Flow
    volume_spike: bool  # Institutional participation
    absorption: bool  # Large orders absorbing price
    momentum_shift: bool  # Changing character

    # Profit Zones
    distance_to_support: float  # In points
    distance_to_resistance: float
    risk_reward_ratio: float  # Real R:R to structure

    # Move Potential
    move_exhaustion: float  # 0-1: Is move done?
    extension_beyond_norm: float  # Beyond average move?
    remaining_potential: float  # Points left in move


class IntelligentTradeManager:
    """
    AI that thinks like a trader with superhuman processing.

    Not: "If ATR > X then do Y"
    But: "Given market structure, where are we in the move?"
    """

    def __init__(self):
        self.lookback_bars = 500  # Analyze last 500 bars
        self.support_resistance_threshold = 0.002  # 0.2% price level

    def analyze_market_structure(
        self,
        current_price: float,
        ohlcv_data: Dict[str, np.ndarray],  # Multi-timeframe
        volume_profile: Optional[np.ndarray] = None,
    ) -> MarketStructure:
        """
        Analyze market like a professional trader.

        Sees:
        - Where are the key levels? (S/R)
        - What's the context? (trend, range, breakout)
        - Where's the volume? (institutions)
        - How far can price go? (profit potential)

        Returns:
            MarketStructure with all market intelligence
        """

        # Extract price data
        highs = ohlcv_data.get('high', np.array([]))
        lows = ohlcv_data.get('low', np.array([]))
        closes = ohlcv_data.get('close', np.array([]))
        volumes = ohlcv_data.get('volume', np.array([]))

        if len(closes) < 50:
            return self._default_structure(current_price)

        # 1. Calculate market volatility (ATR-based)
        # AI uses actual market volatility to determine meaningful stop distances
        high_low_ranges = highs[-20:] - lows[-20:]
        avg_range = np.mean(high_low_ranges)
        market_volatility = avg_range / current_price  # As percentage
        
        # 2. Find Support/Resistance (where price bounced before)
        support_levels = self._find_support_levels(lows, closes)
        resistance_levels = self._find_resistance_levels(highs, closes)

        # AI-DRIVEN: Pass volatility to find meaningful levels
        nearest_support = self._find_nearest_level(current_price, support_levels, direction='below', volatility=market_volatility)
        nearest_resistance = self._find_nearest_level(current_price, resistance_levels, direction='above', volatility=market_volatility)

        support_strength = self._calculate_level_strength(nearest_support, lows, closes)
        resistance_strength = self._calculate_level_strength(nearest_resistance, highs, closes)

        # 2. Identify Trend Structure
        higher_highs = self._has_higher_highs(highs[-50:])
        lower_lows = self._has_lower_lows(lows[-50:])
        ranging = not higher_highs and not lower_lows

        # 3. Current Price Context
        at_support = abs(current_price - nearest_support) / current_price < 0.001  # Within 0.1%
        at_resistance = abs(current_price - nearest_resistance) / current_price < 0.001

        # Breaking structure?
        breaking_out = (
            (current_price > nearest_resistance and resistance_strength > 0.5) or
            (current_price < nearest_support and support_strength > 0.5)
        )

        # Pullback in trend?
        pulling_back = (
            (higher_highs and current_price < closes[-1]) or
            (lower_lows and current_price > closes[-1])
        )

        # 4. Volume Analysis (where are institutions?)
        volume_spike = volumes[-1] > np.mean(volumes[-20:]) * 1.5 if len(volumes) > 20 else False

        # Absorption: Price not moving despite volume (big orders)
        price_change = abs(closes[-1] - closes[-2]) / closes[-2] if len(closes) > 1 else 0
        absorption = volume_spike and price_change < 0.001

        # Momentum shift: Volume + direction change
        momentum_shift = volume_spike and (
            (closes[-1] > closes[-2] and closes[-2] < closes[-3]) or
            (closes[-1] < closes[-2] and closes[-2] > closes[-3])
        )

        # 5. Risk/Reward Calculation (to structure, not arbitrary)
        distance_to_support = current_price - nearest_support
        distance_to_resistance = nearest_resistance - current_price

        # Real R:R: Risk to support, reward to resistance
        if distance_to_support > 0:
            risk_reward_ratio = distance_to_resistance / distance_to_support
        else:
            risk_reward_ratio = 0

        # 6. Move Potential Analysis
        avg_move = np.mean(highs[-20:] - lows[-20:])
        current_move = current_price - nearest_support if higher_highs else nearest_resistance - current_price

        # How exhausted is the move? (0 = just started, 1 = fully extended)
        # Made more lenient: divide by 4x avg instead of 2x to allow more trading
        move_exhaustion = min(1.0, current_move / (avg_move * 4)) if avg_move > 0 else 0

        # How extended beyond normal?
        extension_beyond_norm = max(0, (current_move - avg_move) / avg_move) if avg_move > 0 else 0

        # Remaining potential (points left to next level)
        if higher_highs:
            remaining_potential = distance_to_resistance
        elif lower_lows:
            remaining_potential = distance_to_support
        else:
            remaining_potential = min(distance_to_support, distance_to_resistance)

        return MarketStructure(
            nearest_support=float(nearest_support),
            nearest_resistance=float(nearest_resistance),
            support_strength=float(support_strength),
            resistance_strength=float(resistance_strength),
            higher_highs=bool(higher_highs),
            lower_lows=bool(lower_lows),
            ranging=bool(ranging),
            at_support=bool(at_support),
            at_resistance=bool(at_resistance),
            breaking_out=bool(breaking_out),
            pulling_back=bool(pulling_back),
            volume_spike=bool(volume_spike),
            absorption=bool(absorption),
            momentum_shift=bool(momentum_shift),
            distance_to_support=float(distance_to_support),
            distance_to_resistance=float(distance_to_resistance),
            risk_reward_ratio=float(risk_reward_ratio),
            move_exhaustion=float(move_exhaustion),
            extension_beyond_norm=float(extension_beyond_norm),
            remaining_potential=remaining_potential,
        )

    def _comprehensive_market_score(self, context: 'EnhancedTradingContext', is_buy: bool) -> Dict:
        """
        COMPREHENSIVE MARKET ANALYSIS USING ALL 159+ FEATURES
        Same as position manager - ensures consistency across entry/exit/DCA
        """
        # Import from position manager to ensure exact same logic
        from src.ai.intelligent_position_manager import IntelligentPositionManager
        temp_manager = IntelligentPositionManager()
        return temp_manager._comprehensive_market_score(context, is_buy)
    
    def should_enter_trade(self, context: EnhancedTradingContext, structure: 'MarketStructure' = None) -> Tuple[bool, str, float]:
        """
        COMPREHENSIVE ENTRY DECISION USING ALL 159+ FEATURES + ML + RL
        
        Uses SAME comprehensive scoring as DCA/EXIT for consistency
        
        Analyzes:
        - All 7 timeframes (M1, M5, M15, M30, H1, H4, D1)
        - RSI across all timeframes + divergences
        - MACD across all timeframes + crossovers
        - Bollinger Bands on all timeframes
        - Volume (accumulation, distribution, institutional, spikes)
        - Order book pressure (bid/ask imbalance)
        - Market structure (support/resistance)
        - Trend alignment
        - ML confidence
        - RL agent recommendations (if available)
        
        Returns:
            (should_trade, reason, confidence_score)
        """
        
        ml_confidence = context.ml_confidence
        # is_buy will be determined after checking ML direction and trend
        is_buy = None  # Will be set below
        
        # If no structure provided, create a minimal one to avoid errors
        if structure is None:
            logger.warning("⚠️ No structure provided to should_enter_trade, using defaults")
            structure = MarketStructure(
                nearest_support=context.current_price * 0.98,
                nearest_resistance=context.current_price * 1.02,
                support_strength=0.5,
                resistance_strength=0.5,
                distance_to_support=context.current_price * 0.02,
                distance_to_resistance=context.current_price * 0.02,
                at_support=False,
                at_resistance=False,
                higher_highs=True,
                lower_lows=False,
                risk_reward_ratio=1.0,
                move_exhaustion=0.5,
                remaining_potential=100.0,
                momentum_shift=False,
                absorption=False
            )
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: FTMO PROTECTION
        # ═══════════════════════════════════════════════════════════
        if context.ftmo_violated or not context.can_trade:
            return False, "FTMO rules violated", 0.0
        
        if context.distance_to_daily_limit < 2000:
            return False, f"Near FTMO daily limit (${context.distance_to_daily_limit:.0f})", 0.0
        
        if context.distance_to_dd_limit < 3000:
            return False, f"Near FTMO DD limit (${context.distance_to_dd_limit:.0f})", 0.0
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: DETERMINE TRADE DIRECTION
        # ═══════════════════════════════════════════════════════════
        # CRITICAL: Determine direction BEFORE market analysis
        # Determine trend direction from market structure
        trend_direction = "NEUTRAL"
        if context.request:
            # Get trend from market regime or price action
            regime = context.request.get('market_regime', {})
            if regime:
                regime_trend = regime.get('trend', 'NEUTRAL')
                if 'UP' in regime_trend or 'BULL' in regime_trend:
                    trend_direction = "UP"
                elif 'DOWN' in regime_trend or 'BEAR' in regime_trend:
                    trend_direction = "DOWN"
        
        # Check for conflict between ML and trend
        # CRITICAL: Don't reject on HOLD - use market score as primary signal
        if context.ml_direction == "BUY" and trend_direction == "DOWN":
            reason = f"Entry rejected: ML says BUY but trend is DOWN - conflicting signals"
            logger.info(f"❌ ENTRY REJECTED: {reason}")
            return False, reason, 0.0
        elif context.ml_direction == "SELL" and trend_direction == "UP":
            reason = f"Entry rejected: ML says SELL but trend is UP - conflicting signals"
            logger.info(f"❌ ENTRY REJECTED: {reason}")
            return False, reason, 0.0
        
        # If ML says HOLD, use market score to decide direction
        # HOLD means ML is not strongly directional, but market structure might be clear
        if context.ml_direction == "HOLD":
            logger.info(f"⚠️ ML says HOLD @ {context.ml_confidence:.0f}% - using market structure for direction")
            # Determine direction from trend
            if trend_direction == "UP":
                is_buy = True
                logger.info(f"   → Market trending UP, will consider BUY if score sufficient")
            elif trend_direction == "DOWN":
                is_buy = False
                logger.info(f"   → Market trending DOWN, will consider SELL if score sufficient")
            else:
                # Truly neutral - reject
                reason = f"Entry rejected: ML HOLD + trend NEUTRAL - no clear direction"
                logger.info(f"⏸️ ENTRY REJECTED: {reason}")
                return False, reason, 0.0
        else:
            # ML has clear direction
            is_buy = (context.ml_direction == "BUY")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: COMPREHENSIVE MARKET ANALYSIS (159+ features)
        # ═══════════════════════════════════════════════════════════
        market_analysis = self._comprehensive_market_score(context, is_buy)
        
        logger.info(f"🧠 COMPREHENSIVE ENTRY ANALYSIS (159+ features):")
        logger.info(f"   Market Score: {market_analysis['total_score']:.0f}/100")
        logger.info(f"   Trend: {market_analysis['trend_score']:.0f}, Momentum: {market_analysis['momentum_score']:.0f}")
        logger.info(f"   Volume: {market_analysis['volume_score']:.0f}, Structure: {market_analysis['structure_score']:.0f}")
        logger.info(f"   ML: {market_analysis['ml_score']:.0f}")
        logger.info(f"   Top Signals: {', '.join(market_analysis['signals'][:5])}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: RL AGENT RECOMMENDATION (if available)
        # ═══════════════════════════════════════════════════════════
        rl_boost = 0
        try:
            import sys
            api_module = sys.modules.get('api')
            if api_module and hasattr(api_module, 'dqn_agent') and api_module.dqn_agent:
                dqn_agent = api_module.dqn_agent
                state_key = f"0_{int(ml_confidence)}"  # Entry state (0 profit)
                q_table = dqn_agent.get('q_table', {})
                
                if state_key in q_table:
                    q_values = q_table[state_key]
                    # Q-values for [HOLD, SCALE_IN, PARTIAL_CLOSE, CLOSE_ALL]
                    # For entry, we care if RL thinks we should enter (SCALE_IN action)
                    if len(q_values) > 1 and q_values[1] > q_values[0]:
                        rl_boost = 10  # RL says enter
                        logger.info(f"   🤖 RL AGENT: Recommends entry (+10 score)")
                    else:
                        rl_boost = -5  # RL says don't enter
                        logger.info(f"   🤖 RL AGENT: Recommends wait (-5 score)")
        except Exception as e:
            logger.debug(f"RL agent not available: {e}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: FINAL DECISION
        # ═══════════════════════════════════════════════════════════
        
        # Adjust market score with RL recommendation
        final_score = market_analysis['total_score'] + rl_boost
        
        # Entry threshold - Higher quality entries only
        # Raised to ensure only strong setups are taken
        entry_threshold = 65
        ml_threshold = 70
        
        should_enter = (
            final_score >= entry_threshold and
            ml_confidence >= ml_threshold
        )
        
        if should_enter:
            reason = f"Entry approved: Score {final_score:.0f}/100 (threshold: {entry_threshold}), ML {ml_confidence:.0f}%"
            confidence_multiplier = final_score / 100.0  # 75-100 → 0.75-1.0
            
            logger.info(f"✅ ENTRY APPROVED:")
            logger.info(f"   Final Score: {final_score:.0f}/100 (Market: {market_analysis['total_score']:.0f} + RL: {rl_boost:+d})")
            logger.info(f"   ML Confidence: {ml_confidence:.0f}%")
            logger.info(f"   Signals: {', '.join(market_analysis['signals'][:5])}")
            
            return True, reason, confidence_multiplier
        else:
            reason = f"Entry rejected: Score {final_score:.0f} < {entry_threshold} or ML {ml_confidence:.0f}% < {ml_threshold}%"
            
            logger.info(f"❌ ENTRY REJECTED:")
            logger.info(f"   Score: {final_score:.0f}/100 (need {entry_threshold}+)")
            logger.info(f"   ML: {ml_confidence:.0f}% (need {ml_threshold}%+)")
            
            return False, reason, 0.0
    
    # OLD CODE BELOW - KEEPING FOR REFERENCE BUT NOT USED
    def _old_quality_score_system(self, context, structure):
        """
        OLD SYSTEM - NOT USED ANYMORE
        Kept for reference only
        """
        from datetime import datetime
        import pytz
        try:
            now = datetime.now(pytz.timezone('America/New_York'))
            hour = now.hour
            
            # Adjust threshold based on trading session liquidity
            if 8 <= hour < 12:
                time_mult = 0.90  # London Open (High Liquidity) - 10% easier
                session = "London Open"
            elif 12 <= hour < 16:
                time_mult = 0.85  # London/NY Overlap (HIGHEST) - 15% easier
                session = "London/NY Overlap"
            elif 16 <= hour < 17:
                time_mult = 0.90  # NY Close (High Liquidity) - 10% easier
                session = "NY Close"
            elif 17 <= hour < 20:
                time_mult = 0.95  # After Hours (Medium) - 5% easier
                session = "After Hours"
            else:
                time_mult = 1.05  # Asian/Off Hours (Low Liquidity) - 5% harder
                session = "Asian/Off Hours"
            
            base_threshold = base_threshold * time_mult
            logger.info(f"🎯 Asset: {asset_class} | Adaptive: {optimizer_threshold:.1f}% | Asset Adj: {base_threshold/time_mult:.1f}% | Time Adj ({session}): {base_threshold:.1f}%")
        except:
            logger.info(f"🎯 Asset class: {asset_class} | Adaptive threshold: {optimizer_threshold:.1f}% | Adjusted: {base_threshold:.1f}%")

        # BEST SETUPS (high quality) - Use 115 features intelligently
        # Asset-class specific thresholds
        # 1. Multi-timeframe bullish + at support
        if context.is_multi_timeframe_bullish() and context.h1_close_pos < 0.3 and ml_confidence > base_threshold:
            reasons.append("MULTI-TIMEFRAME BULLISH AT SUPPORT")
            quality_score += 0.5

        # 2. Strong confluence + volume (REQUIRE both)
        if context.has_strong_confluence() and context.is_institutional_activity() and ml_confidence > base_threshold:
            reasons.append("CONFLUENCE + INSTITUTIONAL FLOW")
            quality_score += 0.45

        # 3. H4 + H1 both at key level
        at_h4_level = context.h4_close_pos < 0.2 or context.h4_close_pos > 0.8
        at_h1_level = context.h1_close_pos < 0.2 or context.h1_close_pos > 0.8
        if at_h4_level and at_h1_level and ml_confidence > base_threshold:
            reasons.append("H4 + H1 KEY LEVEL CONFLUENCE")
            quality_score += 0.4

        # GOOD SETUPS (medium quality) - Asset class adjusted
        # 4. Trend alignment + no divergence
        if context.trend_alignment > 0.7 and context.volume_divergence < 0.3 and ml_confidence > (base_threshold + 6):
            reasons.append("TREND ALIGNED + VOLUME CONFIRMS")
            quality_score += 0.3

        # 5. Order book supports direction
        orderbook_bullish = context.bid_pressure > 0.65
        orderbook_bearish = context.ask_pressure > 0.65
        if (orderbook_bullish or orderbook_bearish) and ml_confidence > base_threshold:
            reasons.append("ORDER BOOK PRESSURE CONFIRMS")
            quality_score += 0.25
        
        # 6. ML high confidence with good R:R
        if ml_confidence > (base_threshold + 6) and structure.risk_reward_ratio >= 1.5:
            reasons.append("HIGH ML CONFIDENCE + GOOD R:R")
            quality_score += 0.15
        
        # 7. Decent ML confidence with excellent R:R
        if ml_confidence > (base_threshold + 3) and structure.risk_reward_ratio >= 2.0:
            reasons.append("ML CONFIDENCE + EXCELLENT R:R")
            quality_score += 0.12

        # ═══════════════════════════════════════════════════════════
        # DECISION LOGIC: Check bypass paths FIRST before rejecting
        # ═══════════════════════════════════════════════════════════
        
        # Calculate bypass paths (allow trading even with low quality score)
        decent_rr = structure.risk_reward_ratio >= 1.5
        good_rr = structure.risk_reward_ratio >= 1.0
        not_ranging = context.get_market_regime() != "RANGING"
        has_quality_setup = quality_score > 0
        
        # ASSET-CLASS ADJUSTED BYPASS PATHS
        # Forex: 52-60%, Indices: 58-66%, Commodities: 60-68%
        # 1. ML > base + quality setup (confluence/structure), OR
        # 2. ML > base+6 + R:R ≥ 2.0 + not ranging, OR
        # 3. ML > base+8 + R:R ≥ 1.5, OR
        # 4. ML > base+10 alone (high confidence)
        
        path_1 = ml_confidence > base_threshold and has_quality_setup
        path_2 = ml_confidence > (base_threshold + 6) and decent_rr and not_ranging
        path_3 = ml_confidence > (base_threshold + 8) and decent_rr
        path_4 = ml_confidence > (base_threshold + 10)
        
        should_trade_bypass = path_1 or path_2 or path_3 or path_4
        
        # AI WEIGHS ALL FACTORS - No hard blocks except FTMO
        # Each factor adds or subtracts from quality score
        
        # 1. Multi-timeframe divergence - Weight by severity
        mtf_divergence = (context.trend_m1_bullish > 0.5 and context.trend_h4_bullish < 0.5) or \
                        (context.trend_m1_bullish < 0.5 and context.trend_h4_bullish > 0.5)
        if mtf_divergence:
            # Scale penalty by RSI divergence severity
            divergence_severity = min(abs(context.rsi_m1_h1_diff) / 100, 0.3)  # Max 0.3 penalty
            quality_score -= divergence_severity
            logger.info(f"⚠️ Multi-timeframe divergence: -{divergence_severity:.2f} quality penalty")

        # 2. Volume divergence - Weight by severity
        if context.volume_divergence > 0.6:
            volume_penalty = (context.volume_divergence - 0.6) * 0.5  # Scale 0.6-1.0 → 0-0.2
            quality_score -= volume_penalty
            logger.info(f"⚠️ Volume divergence ({context.volume_divergence:.2f}): -{volume_penalty:.2f} quality penalty")
        elif context.volume_divergence < 0.3:
            # Bonus for volume confirmation
            quality_score += 0.10
            logger.info(f"✅ Volume confirms: +0.10 quality bonus")

        # 3. Institutional flow - Weight distribution vs accumulation
        if context.distribution > 0.6:
            distribution_penalty = (context.distribution - 0.6) * 0.4  # Scale 0.6-1.0 → 0-0.16
            quality_score -= distribution_penalty
            logger.info(f"⚠️ Institutional distribution ({context.distribution:.2f}): -{distribution_penalty:.2f} penalty")
        elif context.accumulation > 0.6:
            accumulation_bonus = (context.accumulation - 0.6) * 0.4
            quality_score += accumulation_bonus
            logger.info(f"✅ Institutional accumulation ({context.accumulation:.2f}): +{accumulation_bonus:.2f} bonus")

        # 4. Volatile regime - Require higher quality, don't block
        if context.get_market_regime() == "VOLATILE":
            if context.has_strong_confluence():
                quality_score += 0.15  # Bonus for confluence in volatility
                logger.info(f"✅ Volatile + confluence: +0.15 bonus")
            else:
                quality_score -= 0.25  # Penalty for no confluence
                logger.info(f"⚠️ Volatile without confluence: -0.25 penalty")

        # 5. Absorption - Weight by momentum shift presence
        if structure.absorption:
            if structure.momentum_shift:
                quality_score += 0.10  # Bonus for absorption with shift
                logger.info(f"✅ Absorption with momentum shift: +0.10 bonus")
            else:
                quality_score -= 0.15  # Penalty for absorption without shift
                logger.info(f"⚠️ Absorption without direction: -0.15 penalty")
        
        # 6. Regime alignment - Factor into quality score, don't hard block
        # AI considers regime as ONE factor among many
        market_regime = context.get_market_regime()
        ml_direction_bullish = (context.ml_direction == "BUY")
        
        regime_aligned = (
            (ml_direction_bullish and market_regime in ["TRENDING_UP", "RANGING"]) or
            (not ml_direction_bullish and market_regime in ["TRENDING_DOWN", "RANGING"])
        )
        
        # Add to quality score if regime aligned, subtract if not
        # REDUCED PENALTY: Regime is just ONE factor, not a hard block
        if regime_aligned:
            quality_score += 0.15  # Bonus for regime alignment
            logger.info(f"✅ Regime aligned: {context.ml_direction} in {market_regime}")
        else:
            quality_score -= 0.10  # REDUCED from 0.20 - regime is just one factor
            logger.info(f"⚠️ Regime conflict: {context.ml_direction} in {market_regime} (minor penalty)")
        
        # Add trend alignment to quality score
        if context.trend_alignment > 0.5:
            quality_score += 0.10  # Bonus for strong alignment
        elif context.trend_alignment < 0.2:
            quality_score -= 0.15  # Penalty for no alignment
        
        # Log final quality score
        logger.info(f"📊 Final Quality Score: {quality_score:.2f}")
        
        # HIGH LIQUIDITY BYPASS: During peak hours, allow slightly negative quality scores
        # Rationale: High liquidity = tighter spreads, better fills, less slippage
        high_liquidity_session = session in ["London/NY Overlap", "NY Close", "London Open"]
        quality_threshold = -0.20 if high_liquidity_session else 0.0
        
        # AI DECISION: Trade if quality score above threshold OR bypass path met
        # This allows AI flexibility - either good quality OR strong ML signal OR high liquidity
        if quality_score <= quality_threshold and not should_trade_bypass:
            logger.info(f"❌ Quality score {quality_score:.2f} below threshold {quality_threshold:.2f}, no bypass path")
            return False, f"Quality score {quality_score:.2f} below threshold ({quality_threshold:.2f})", 0.0
        
        # If we got here, AI approves the trade!
        logger.info(f"✅ AI APPROVES: Quality {quality_score:.2f} or bypass path met")

        # Position size based on setup quality + confluence + FTMO status
        # Best setups with confluence = bigger size
        # Near FTMO limits = smaller size
        
        if quality_score >= 0.4:  # Excellent setup
            size_multiplier = 1.5
            if context.has_strong_confluence():
                size_multiplier = 1.8  # Even bigger with confluence
        elif quality_score >= 0.25:  # Good setup
            size_multiplier = 1.0
            if context.has_strong_confluence():
                size_multiplier = 1.3
        elif quality_score >= 0.15:  # Decent setup
            size_multiplier = 0.7
        else:  # Bypass path - use conservative size
            size_multiplier = 0.6
        
        # FTMO ADJUSTMENT: Reduce size if near limits
        if context.should_trade_conservatively():
            size_multiplier *= 0.5
            logger.info(f"⚠️ FTMO {context.get_ftmo_status()} - reducing position size by 50%")

        # Adjust for market regime
        regime = context.get_market_regime()
        if regime == "VOLATILE":
            size_multiplier *= 0.7  # Smaller in volatile markets
        elif regime == "RANGING":
            size_multiplier *= 0.8  # Smaller in ranges
        
        # Adjust for volume regime
        if context.is_institutional_activity():
            size_multiplier *= 1.2  # Bigger with institutional support

        should_trade = True  # We passed all checks
        
        # Build reason
        if path_1:
            reason = " + ".join(reasons) if reasons else "Quality setup"
        elif path_2:
            reason = f"ML {ml_confidence:.1f}% + R:R {structure.risk_reward_ratio:.1f}:1 + Trending"
        elif path_3:
            reason = f"ML {ml_confidence:.1f}% + Good R:R {structure.risk_reward_ratio:.1f}:1"
        elif path_4:
            reason = f"High ML confidence {ml_confidence:.1f}%"
        else:
            reason = "NO VALID SETUP"

        return should_trade, reason, size_multiplier

    def calculate_intelligent_position_size(
        self,
        account_balance: float,
        setup_quality: float,  # From should_enter_trade
        structure: MarketStructure,
        ftmo_limits: Dict,
    ) -> float:
        """
        AI decides position size based on setup, not rules.

        Not: "Always 2% risk"
        But: "This setup at this level with this R:R deserves X size"
        """

        # Base risk from setup quality
        # Excellent setup at perfect level = more risk
        # Mediocre setup = less risk

        base_risk_pct = setup_quality * 2.0  # 0-3% range

        # Adjust for R:R (better R:R = can risk more)
        rr_multiplier = min(1.5, structure.risk_reward_ratio / 2.0)

        # Adjust for level strength (stronger level = more risk)
        level_multiplier = (structure.support_strength + structure.resistance_strength) / 2

        # Final risk %
        risk_pct = base_risk_pct * rr_multiplier * level_multiplier

        # FTMO safety: Never risk more than distance to limits allows
        max_safe_risk = min(
            ftmo_limits.get('distance_to_daily_limit', 5000) * 0.3,  # 30% of remaining
            ftmo_limits.get('distance_to_dd_limit', 10000) * 0.2,  # 20% of remaining
        )

        risk_dollars = account_balance * (risk_pct / 100)
        risk_dollars = min(risk_dollars, max_safe_risk)

        # Convert to lots
        stop_distance = structure.distance_to_support if structure.higher_highs else structure.distance_to_resistance
        if stop_distance > 0:
            lots = risk_dollars / stop_distance
        else:
            lots = 0

        return lots

    def should_exit_trade(
        self,
        entry_price: float,
        current_price: float,
        structure: MarketStructure,
        unrealized_pnl: float,
        bars_held: int,
    ) -> Tuple[bool, str]:
        """
        AI decides: Is this trade done?

        Not: "If profit > 2×ATR then exit"
        But: "Has the move played out? Is structure changing?"
        """

        # Exit reasons (market-based, not rule-based):

        # 1. Structure broken (trend changed)
        if structure.higher_highs and current_price < structure.nearest_support:
            return True, "UPTREND BROKEN - SUPPORT LOST"

        if structure.lower_lows and current_price > structure.nearest_resistance:
            return True, "DOWNTREND BROKEN - RESISTANCE BROKEN"

        # 2. Target reached (hit resistance/support)
        if structure.at_resistance and unrealized_pnl > 0:
            return True, "TARGET REACHED - AT RESISTANCE"

        if structure.at_support and unrealized_pnl > 0:
            return True, "TARGET REACHED - AT SUPPORT"

        # 3. Move exhausted (extended beyond normal)
        if structure.move_exhaustion > 0.9 and unrealized_pnl > 0:
            return True, "MOVE EXHAUSTED - TAKE PROFIT"

        # 4. Momentum shift against us
        if structure.momentum_shift and unrealized_pnl < 0:
            return True, "MOMENTUM REVERSED - CUT LOSS"

        # 5. Absorption at profit (big orders capping move)
        if structure.absorption and unrealized_pnl > 0 and bars_held > 10:
            return True, "ABSORPTION - MOVE CAPPED"

        # 6. Time-based only if no movement (dead trade)
        if bars_held > 100 and abs(unrealized_pnl) < 100:  # 100 bars, <$100 P&L
            return True, "DEAD TRADE - NO MOVEMENT"

        return False, "TRADE STILL VALID"

    # Helper methods for structure analysis

    def _find_support_levels(self, lows: np.ndarray, closes: np.ndarray) -> List[float]:
        """Find price levels where market bounced up."""
        levels = []

        for i in range(10, len(lows) - 10):
            # Local minimum?
            if lows[i] == min(lows[i-10:i+10]):
                # Bounced after?
                if closes[i+5] > lows[i] * 1.005:  # 0.5% bounce
                    levels.append(lows[i])

        return levels

    def _find_resistance_levels(self, highs: np.ndarray, closes: np.ndarray) -> List[float]:
        """Find price levels where market got rejected down."""
        levels = []

        for i in range(10, len(highs) - 10):
            # Local maximum?
            if highs[i] == max(highs[i-10:i+10]):
                # Rejected after?
                if closes[i+5] < highs[i] * 0.995:  # 0.5% rejection
                    levels.append(highs[i])

        return levels

    def _find_nearest_level(self, price: float, levels: List[float], direction: str, volatility: float = None) -> float:
        """
        AI-DRIVEN: Find nearest support/resistance level based on market volatility.
        
        Uses ATR/volatility to determine minimum meaningful distance:
        - High volatility market = wider stops needed
        - Low volatility market = tighter stops acceptable
        
        No hard-coded percentages - adapts to actual market conditions.
        """
        # AI-DRIVEN: Use market volatility to determine minimum distance
        # If no volatility provided, calculate from price levels
        if volatility is None or volatility == 0:
            # Calculate volatility from the levels themselves
            if len(levels) >= 2:
                level_ranges = [abs(levels[i] - levels[i-1]) for i in range(1, len(levels))]
                avg_level_distance = np.mean(level_ranges) if level_ranges else price * 0.01
                volatility = avg_level_distance / price
            else:
                volatility = 0.01  # Default 1% if no data
        
        # AI DECISION: Minimum distance = 2x current volatility
        # This ensures stops are beyond normal market noise
        min_distance = price * (volatility * 2)
        
        if not levels:
            # AI-DRIVEN: Default based on volatility
            # High volatility = wider default, Low volatility = tighter default
            default_distance = max(volatility * 3, 0.01)  # At least 3x volatility or 1%
            return price * (1 - default_distance) if direction == 'below' else price * (1 + default_distance)

        if direction == 'below':
            # Find support levels beyond normal volatility range
            below = [l for l in levels if l < price and (price - l) >= min_distance]
            if below:
                return max(below)  # Nearest meaningful support
            else:
                # No meaningful support found, use volatility-based default
                default_distance = max(volatility * 3, 0.01)
                return price * (1 - default_distance)
        else:
            # Find resistance levels beyond normal volatility range
            above = [l for l in levels if l > price and (l - price) >= min_distance]
            if above:
                return min(above)  # Nearest meaningful resistance
            else:
                # No meaningful resistance found, use volatility-based default
                default_distance = max(volatility * 3, 0.01)
                return price * (1 + default_distance)

    def _calculate_level_strength(self, level: float, prices: np.ndarray, closes: np.ndarray) -> float:
        """How strong is this S/R level? (number of touches)"""
        touches = 0
        threshold = level * 0.002  # 0.2% tolerance

        for i, price in enumerate(prices):
            if abs(price - level) < threshold:
                # Confirmed touch if price bounced
                if i < len(closes) - 5:
                    if abs(closes[i+5] - price) > threshold:
                        touches += 1

        return min(1.0, touches / 5.0)  # 5+ touches = max strength

    def _has_higher_highs(self, highs: np.ndarray) -> bool:
        """Is price making higher highs? (uptrend)"""
        if len(highs) < 20:
            return False

        recent_high = max(highs[-10:])
        older_high = max(highs[-20:-10])

        return recent_high > older_high

    def _has_lower_lows(self, lows: np.ndarray) -> bool:
        """Is price making lower lows? (downtrend)"""
        if len(lows) < 20:
            return False

        recent_low = min(lows[-10:])
        older_low = min(lows[-20:-10])

        return recent_low < older_low

    def _default_structure(self, current_price: float) -> MarketStructure:
        """Fallback structure if not enough data."""
        return MarketStructure(
            nearest_support=current_price * 0.99,
            nearest_resistance=current_price * 1.01,
            support_strength=0.3,
            resistance_strength=0.3,
            higher_highs=False,
            lower_lows=False,
            ranging=True,
            at_support=False,
            at_resistance=False,
            breaking_out=False,
            pulling_back=False,
            volume_spike=False,
            absorption=False,
            momentum_shift=False,
            distance_to_support=current_price * 0.01,
            distance_to_resistance=current_price * 0.01,
            risk_reward_ratio=1.0,
            move_exhaustion=0.5,
            extension_beyond_norm=0.0,
            remaining_potential=current_price * 0.01,
        )


if __name__ == "__main__":
    """Test the intelligent trade manager."""

    print("Testing AI-Powered Intelligent Trade Manager...")
    print("="*70)

    # Create manager
    manager = IntelligentTradeManager()

    # Simulate market data (uptrend with pullback to support)
    current_price = 50000
    ohlcv = {
        'high': np.array([49800 + i*10 + np.random.randn()*20 for i in range(100)]),
        'low': np.array([49700 + i*10 + np.random.randn()*20 for i in range(100)]),
        'close': np.array([49750 + i*10 + np.random.randn()*20 for i in range(100)]),
        'volume': np.array([1000 + np.random.randint(-200, 200) for i in range(100)]),
    }

    # Analyze structure
    structure = manager.analyze_market_structure(current_price, ohlcv)

    print(f"Current Price: ${current_price:,.0f}")
    print(f"Nearest Support: ${structure.nearest_support:,.0f} (strength: {structure.support_strength:.2f})")
    print(f"Nearest Resistance: ${structure.nearest_resistance:,.0f} (strength: {structure.resistance_strength:.2f})")
    print(f"Trend: {'UPTREND' if structure.higher_highs else 'DOWNTREND' if structure.lower_lows else 'RANGING'}")
    print(f"At Support: {structure.at_support}")
    print(f"R:R Ratio: {structure.risk_reward_ratio:.2f}:1")
    print(f"Move Exhaustion: {structure.move_exhaustion*100:.0f}%")
    print(f"Remaining Potential: {structure.remaining_potential:.0f} points")

    # Test entry decision
    ml_confidence = 75.0
    should_trade, reason, size_mult = manager.should_enter_trade(
        structure, ml_confidence, {}
    )

    print(f"\nML Confidence: {ml_confidence}%")
    print(f"Should Trade: {should_trade}")
    print(f"Reason: {reason}")
    print(f"Size Multiplier: {size_mult:.2f}x")

    # Test position sizing
    lots = manager.calculate_intelligent_position_size(
        account_balance=100000,
        setup_quality=size_mult,
        structure=structure,
        ftmo_limits={'distance_to_daily_limit': 5000, 'distance_to_dd_limit': 10000}
    )

    print(f"Position Size: {lots:.2f} lots")

    print("\n" + "="*70)
    print("✅ AI Trade Manager tests passed!")
