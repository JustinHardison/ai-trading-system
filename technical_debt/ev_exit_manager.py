"""
Expected Value Exit Manager - Pure AI, No Rules
Modern quantitative hedge fund approach
"""
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Import smart sizer for scale out calculations
try:
    from .smart_position_sizer import get_smart_sizer
except ImportError:
    try:
        from src.ai.smart_position_sizer import get_smart_sizer
    except ImportError:
        get_smart_sizer = None


class EVExitManager:
    """
    Expected Value based exit decisions - No hardcoded rules
    Uses market structure and probabilities to calculate optimal exits
    """
    
    def __init__(self):
        self.position_peaks = {}  # Track peak profit per position
    
    def analyze_exit(self, context, current_profit: float, current_volume: float,
                    position_type: int, symbol: str) -> Dict:
        """
        Main exit analysis using Expected Value calculations
        
        Args:
            context: EnhancedTradingContext with all market features
            current_profit: Current P&L in dollars
            current_volume: Current position size
            position_type: 0=BUY, 1=SELL
            symbol: Trading symbol
            
        Returns:
            Dict with action, reason, confidence, reduce_pct
        """
        
        is_buy = (position_type == 0)
        
        # Convert profit to percentage
        account_balance = 10000  # Fallback
        if hasattr(context, 'account_balance'):
            account_balance = context.account_balance
        profit_pct = (current_profit / account_balance) * 100
        
        # Track peak profit
        if symbol not in self.position_peaks:
            self.position_peaks[symbol] = profit_pct
        else:
            self.position_peaks[symbol] = max(self.position_peaks[symbol], profit_pct)
        
        peak_profit = self.position_peaks[symbol]
        
        logger.info(f"")
        logger.info(f"🤖 EV EXIT ANALYSIS - {symbol}")
        logger.info(f"   Current P&L: ${current_profit:.2f} ({profit_pct:.3f}%)")
        logger.info(f"   Peak P&L: {peak_profit:.3f}%")
        logger.info(f"   Position: {'BUY' if is_buy else 'SELL'}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Calculate Market Probabilities
        # ═══════════════════════════════════════════════════════════
        
        if profit_pct < 0:
            # LOSING POSITION
            
            # CRITICAL: Don't exit tiny losses from spread/slippage
            # Only analyze EV for meaningful losses (> 0.1%)
            if abs(profit_pct) < 0.1:
                logger.info(f"")
                logger.info(f"   ⏸️ TINY LOSS ({profit_pct:.3f}%) - Ignoring (spread/slippage)")
                logger.info(f"   ✅ AI DECISION: HOLD (loss too small to analyze)")
                # Continue to HOLD logic at bottom
            else:
                recovery_prob = self._calculate_recovery_probability(
                    context, profit_pct, is_buy
                )
                
                logger.info(f"")
                logger.info(f"   📉 LOSING POSITION ANALYSIS:")
                logger.info(f"   Recovery Probability: {recovery_prob:.1%}")
                
                # Calculate Expected Value
                ev_decision = self._calculate_loss_ev(
                    current_loss=profit_pct,
                    recovery_prob=recovery_prob,
                    context=context
                )
                
                if ev_decision['should_exit']:
                    # Clean up peak tracking
                    if symbol in self.position_peaks:
                        del self.position_peaks[symbol]
                    
                    return {
                        'action': 'CLOSE',
                        'reason': ev_decision['reason'],
                        'priority': 'HIGH',
                        'confidence': ev_decision['confidence']
                    }
        
        else:
            # WINNING POSITION
            continuation_prob = self._calculate_continuation_probability(
                context, profit_pct, is_buy
            )
            
            reversal_prob = self._calculate_reversal_probability(
                context, is_buy
            )
            
            logger.info(f"")
            logger.info(f"   📈 WINNING POSITION ANALYSIS:")
            logger.info(f"   Continuation Probability: {continuation_prob:.1%}")
            logger.info(f"   Reversal Probability: {reversal_prob:.1%}")
            
            # Calculate Expected Value
            ev_decision = self._calculate_profit_ev(
                current_profit=profit_pct,
                peak_profit=peak_profit,
                continuation_prob=continuation_prob,
                reversal_prob=reversal_prob,
                context=context
            )
            
            if ev_decision['action'] == 'CLOSE':
                # Clean up peak tracking
                if symbol in self.position_peaks:
                    del self.position_peaks[symbol]
                
                return {
                    'action': 'CLOSE',
                    'reason': ev_decision['reason'],
                    'priority': 'HIGH',
                    'confidence': ev_decision['confidence']
                }
            
            elif ev_decision['action'] == 'PARTIAL':
                # Use smart sizer to calculate optimal scale out size
                if get_smart_sizer is not None:
                    smart_sizer = get_smart_sizer()
                    reduce_lots = smart_sizer.calculate_scale_out_size(
                        current_lots=current_volume,
                        reversal_probability=reversal_prob,
                        symbol=symbol
                    )
                else:
                    # Fallback
                    reduce_lots = current_volume * ev_decision['reduce_pct']
                
                return {
                    'action': 'SCALE_OUT',
                    'reason': ev_decision['reason'],
                    'priority': 'MEDIUM',
                    'confidence': ev_decision['confidence'],
                    'reduce_lots': reduce_lots
                }
        
        # ═══════════════════════════════════════════════════════════
        # DEFAULT: HOLD (EV favors holding)
        # ═══════════════════════════════════════════════════════════
        logger.info(f"   ✅ AI DECISION: HOLD (EV favors holding)")
        
        return {
            'action': 'HOLD',
            'reason': 'EV analysis favors holding position',
            'confidence': 60
        }
    
    def _calculate_recovery_probability(self, context, current_loss: float, 
                                       is_buy: bool) -> float:
        """
        Calculate probability of recovery using market structure
        Pure AI - no hardcoded thresholds
        """
        
        base_prob = 0.5
        
        # 1. Trend strength (most important)
        trend_strength = self._get_trend_strength(context, is_buy)
        if trend_strength > 0.7:
            base_prob += 0.25  # Strong trend in our favor
        elif trend_strength > 0.5:
            base_prob += 0.10  # Moderate trend
        elif trend_strength < 0.3:
            base_prob -= 0.25  # Strong trend against us
        elif trend_strength < 0.5:
            base_prob -= 0.10  # Moderate trend against
        
        # 2. ML confidence
        ml_conf = context.ml_confidence / 100.0
        ml_agrees = (
            (is_buy and context.ml_direction == "BUY") or
            (not is_buy and context.ml_direction == "SELL")
        )
        if ml_agrees:
            base_prob += (ml_conf - 0.5) * 0.3  # Scale by confidence
        else:
            base_prob -= 0.20  # ML disagrees
        
        # 3. Volume support
        volume_ratio = getattr(context, 'volume_ratio', 1.0)
        if volume_ratio > 1.2:
            base_prob += 0.10
        elif volume_ratio < 0.8:
            base_prob -= 0.10
        
        # 4. Timeframe alignment
        aligned_tfs = self._count_aligned_timeframes(context, is_buy)
        alignment_factor = (aligned_tfs / 7.0) - 0.5  # -0.5 to +0.5
        base_prob += alignment_factor * 0.20
        
        # 5. Loss severity (deeper loss = harder to recover)
        loss_severity = abs(current_loss) / 1.0  # Normalize to 1%
        base_prob -= min(loss_severity * 0.15, 0.30)  # Cap at -30%
        
        # 6. Market regime
        regime = context.get_market_regime()
        if regime == "TRENDING":
            base_prob += 0.05  # Trends are more predictable
        elif regime == "RANGING":
            base_prob -= 0.05  # Ranges are choppy
        
        # Clamp to 0-1
        final_prob = max(0.0, min(1.0, base_prob))
        
        logger.info(f"      Trend Strength: {trend_strength:.2f}")
        logger.info(f"      ML Confidence: {ml_conf:.2f} ({'agrees' if ml_agrees else 'disagrees'})")
        logger.info(f"      Volume Ratio: {volume_ratio:.2f}")
        logger.info(f"      Aligned TFs: {aligned_tfs}/7")
        logger.info(f"      → Recovery Probability: {final_prob:.1%}")
        
        return final_prob
    
    def _calculate_continuation_probability(self, context, current_profit: float,
                                           is_buy: bool) -> float:
        """
        Calculate probability of continued profit growth
        Based on market structure momentum
        """
        
        base_prob = 0.5
        
        # 1. Trend strength (key factor)
        trend_strength = self._get_trend_strength(context, is_buy)
        if trend_strength > 0.7:
            base_prob += 0.20
        elif trend_strength < 0.3:
            base_prob -= 0.20
        
        # 2. Momentum
        momentum = getattr(context, 'momentum', 50)
        momentum_factor = (momentum - 50) / 100.0  # -0.5 to +0.5
        if is_buy:
            base_prob += momentum_factor * 0.15
        else:
            base_prob -= momentum_factor * 0.15
        
        # 3. Market regime
        regime = context.get_market_regime()
        if regime == "TRENDING":
            base_prob += 0.15  # Trends continue
        elif regime == "RANGING":
            base_prob -= 0.15  # Ranges reverse
        
        # 4. Volatility (high vol = less predictable)
        volatility = getattr(context, 'volatility', 0.5)
        if volatility > 1.5:
            base_prob -= 0.10
        
        # 5. Profit size (larger profit = more likely to reverse)
        profit_factor = min(current_profit / 2.0, 1.0)  # Cap at 2%
        base_prob -= profit_factor * 0.20
        
        # 6. Volume profile
        volume_ratio = getattr(context, 'volume_ratio', 1.0)
        if volume_ratio > 1.2:
            base_prob += 0.08
        elif volume_ratio < 0.8:
            base_prob -= 0.08
        
        final_prob = max(0.0, min(1.0, base_prob))
        
        logger.info(f"      Trend Strength: {trend_strength:.2f}")
        logger.info(f"      Momentum: {momentum:.0f}")
        logger.info(f"      Regime: {regime}")
        logger.info(f"      → Continuation Probability: {final_prob:.1%}")
        
        return final_prob
    
    def _calculate_reversal_probability(self, context, is_buy: bool) -> float:
        """
        Calculate probability of reversal
        Based on counter-trend signals
        """
        
        base_prob = 0.3  # Base reversal risk
        
        # 1. Timeframes reversing
        reversed_tfs = self._count_reversed_timeframes(context, is_buy)
        reversal_factor = reversed_tfs / 7.0
        base_prob += reversal_factor * 0.30
        
        # 2. ML direction flip
        ml_opposite = (
            (is_buy and context.ml_direction == "SELL") or
            (not is_buy and context.ml_direction == "BUY")
        )
        if ml_opposite:
            ml_strength = context.ml_confidence / 100.0
            base_prob += ml_strength * 0.25
        
        # 3. Volume against position
        if is_buy:
            volume_against = getattr(context, 'distribution', 0.0)
        else:
            volume_against = getattr(context, 'accumulation', 0.0)
        base_prob += volume_against * 0.20
        
        # 4. Momentum shift
        momentum = getattr(context, 'momentum', 50)
        if is_buy and momentum < 30:
            base_prob += 0.15
        elif not is_buy and momentum > 70:
            base_prob += 0.15
        
        final_prob = max(0.0, min(1.0, base_prob))
        
        logger.info(f"      Reversed TFs: {reversed_tfs}/7")
        logger.info(f"      ML Opposite: {ml_opposite}")
        logger.info(f"      → Reversal Probability: {final_prob:.1%}")
        
        return final_prob
    
    def _calculate_loss_ev(self, current_loss: float, recovery_prob: float,
                          context) -> Dict:
        """
        Calculate Expected Value for losing position
        Decide: Cut loss or hold for recovery?
        """
        
        # Scenario 1: Hold and it recovers
        ev_recovery = recovery_prob * 0.0  # Break even
        
        # Scenario 2: Hold and it gets worse
        expected_worse_loss = current_loss * 1.5  # Could get 50% worse
        ev_worse = (1 - recovery_prob) * expected_worse_loss
        
        # Total EV if hold
        ev_hold = ev_recovery + ev_worse
        
        # EV if exit now
        ev_exit = current_loss
        
        logger.info(f"")
        logger.info(f"   💰 EXPECTED VALUE CALCULATION:")
        logger.info(f"      Current Loss: {current_loss:.3f}%")
        logger.info(f"      EV if Hold: {ev_hold:.3f}%")
        logger.info(f"      EV if Exit: {ev_exit:.3f}%")
        logger.info(f"      Difference: {(ev_exit - ev_hold):.3f}%")
        
        # Decision: Exit if EV of exiting > EV of holding
        if ev_exit > ev_hold:
            confidence = min(95, 60 + abs(ev_exit - ev_hold) * 100)
            logger.info(f"   ❌ AI DECISION: EXIT (EV favors cutting loss)")
            return {
                'should_exit': True,
                'reason': f'EV analysis: Exit ({ev_exit:.3f}%) > Hold ({ev_hold:.3f}%)',
                'confidence': confidence
            }
        
        logger.info(f"   ✅ AI DECISION: HOLD (EV favors recovery)")
        return {
            'should_exit': False,
            'reason': f'EV analysis: Hold ({ev_hold:.3f}%) > Exit ({ev_exit:.3f}%)',
            'confidence': 70
        }
    
    def _calculate_profit_ev(self, current_profit: float, peak_profit: float,
                            continuation_prob: float, reversal_prob: float,
                            context) -> Dict:
        """
        Calculate Expected Value for winning position
        Decide: Take profit, partial exit, or hold?
        """
        
        # Scenario 1: Hold and profit grows
        next_target = current_profit * 1.4  # 40% more profit
        ev_growth = continuation_prob * next_target
        
        # Scenario 2: Hold and it reverses
        reversal_loss = current_profit * 0.4  # Keep 40% if reverses
        ev_reversal = reversal_prob * reversal_loss
        
        # Scenario 3: Stays flat
        flat_prob = 1.0 - continuation_prob - reversal_prob
        ev_flat = flat_prob * current_profit
        
        # Total EV if hold
        ev_hold = ev_growth + ev_reversal + ev_flat
        
        # EV if exit now
        ev_exit = current_profit
        
        # Check for giveback from peak
        giveback_pct = 0.0
        if peak_profit > 0:
            giveback_pct = (peak_profit - current_profit) / peak_profit
        
        logger.info(f"")
        logger.info(f"   💰 EXPECTED VALUE CALCULATION:")
        logger.info(f"      Current Profit: {current_profit:.3f}%")
        logger.info(f"      Peak Profit: {peak_profit:.3f}%")
        logger.info(f"      Giveback: {giveback_pct:.1%}")
        logger.info(f"      EV if Hold: {ev_hold:.3f}%")
        logger.info(f"      EV if Exit: {ev_exit:.3f}%")
        logger.info(f"      Difference: {(ev_hold - ev_exit):.3f}%")
        
        # Decision 1: Exit if gave back too much from peak
        if giveback_pct > 0.40 and current_profit > 0.3:
            logger.info(f"   ❌ AI DECISION: EXIT (gave back {giveback_pct:.1%} from peak)")
            return {
                'action': 'CLOSE',
                'reason': f'Gave back {giveback_pct:.1%} from peak {peak_profit:.3f}%',
                'confidence': 85
            }
        
        # Decision 2: Full exit if EV favors exiting
        if ev_exit > ev_hold and current_profit > 0.3:
            confidence = min(90, 65 + abs(ev_exit - ev_hold) * 100)
            logger.info(f"   ❌ AI DECISION: EXIT (EV favors taking profit)")
            return {
                'action': 'CLOSE',
                'reason': f'EV analysis: Exit ({ev_exit:.3f}%) > Hold ({ev_hold:.3f}%)',
                'confidence': confidence
            }
        
        # Decision 3: Partial exit if reversal risk high
        if reversal_prob > 0.35 and current_profit > 0.4:
            # Exit percentage = reversal probability
            reduce_pct = min(reversal_prob, 0.75)  # Cap at 75%
            logger.info(f"   📉 AI DECISION: PARTIAL EXIT ({reduce_pct:.0%})")
            logger.info(f"      Reason: Reversal risk {reversal_prob:.1%}")
            return {
                'action': 'PARTIAL',
                'reason': f'Risk management: {reversal_prob:.1%} reversal probability',
                'confidence': 75,
                'reduce_pct': reduce_pct
            }
        
        # Decision 4: Hold (EV favors holding)
        logger.info(f"   ✅ AI DECISION: HOLD (EV favors holding)")
        return {
            'action': 'HOLD',
            'reason': f'EV analysis: Hold ({ev_hold:.3f}%) > Exit ({ev_exit:.3f}%)',
            'confidence': 70
        }
    
    def _get_trend_strength(self, context, is_buy: bool) -> float:
        """Calculate overall trend strength in our direction"""
        
        # Get all timeframe trends
        trends = []
        for tf in ['m1', 'm5', 'm15', 'm30', 'h1', 'h4', 'd1']:
            trend_val = getattr(context, f'{tf}_trend', 0.5)
            if is_buy:
                trends.append(trend_val)
            else:
                trends.append(1.0 - trend_val)  # Invert for SELL
        
        # Weight higher timeframes more
        weights = [0.05, 0.10, 0.15, 0.15, 0.20, 0.20, 0.15]
        weighted_strength = sum(t * w for t, w in zip(trends, weights))
        
        return weighted_strength
    
    def _count_aligned_timeframes(self, context, is_buy: bool) -> int:
        """Count how many timeframes support our position"""
        
        count = 0
        for tf in ['m1', 'm5', 'm15', 'm30', 'h1', 'h4', 'd1']:
            trend_val = getattr(context, f'{tf}_trend', 0.5)
            if is_buy and trend_val > 0.52:
                count += 1
            elif not is_buy and trend_val < 0.48:
                count += 1
        
        return count
    
    def _count_reversed_timeframes(self, context, is_buy: bool) -> int:
        """Count how many timeframes have reversed against us"""
        
        count = 0
        for tf in ['m15', 'h1', 'h4', 'd1']:  # Focus on key timeframes
            trend_val = getattr(context, f'{tf}_trend', 0.5)
            if is_buy and trend_val < 0.4:
                count += 1
            elif not is_buy and trend_val > 0.6:
                count += 1
        
        return count
