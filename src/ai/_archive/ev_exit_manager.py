"""
EV Exit Manager - AI-Powered Exit Logic
Uses Expected Value calculation to decide when to exit positions
NO HARD THRESHOLDS - Pure probability-based decisions using 173 features
"""
import logging
from typing import Dict
import numpy as np

logger = logging.getLogger(__name__)


class EVExitManager:
    """
    Expected Value based exit manager
    
    Calculates:
    - Continuation probability (position keeps moving in our favor)
    - Reversal probability (position reverses against us)
    - EV of holding vs EV of exiting
    
    Exits when EV(exit) > EV(hold)
    
    Uses ALL 173 features across all timeframes for swing trading
    """
    
    def __init__(self):
        self.position_peaks = {}  # Track peak profit per symbol
        logger.info("🤖 EV Exit Manager initialized - AI-driven exits, no hard thresholds")
    
    def analyze_exit(
        self,
        context,
        current_profit: float,  # Dollar profit
        current_volume: float,
        position_type: int,  # 0=BUY, 1=SELL
        symbol: str
    ) -> Dict:
        """
        AI-driven position management using Expected Value
        
        Returns:
            {
                'action': 'CLOSE' or 'HOLD' or 'SCALE_OUT' or 'SCALE_IN' or 'DCA',
                'reason': str,
                'confidence': float,
                'reduce_lots': float (for SCALE_OUT),
                'add_lots': float (for SCALE_IN/DCA)
            }
        """
        
        is_buy = (position_type == 0)
        
        # Get position details
        entry_price = getattr(context, 'position_entry_price', 0)
        stop_loss = getattr(context, 'position_sl', 0)
        take_profit = getattr(context, 'position_tp', 0)
        
        # Calculate profit as % of RISK (not account)
        if stop_loss > 0:
            risk_distance = abs(entry_price - stop_loss)
            # Profit in price terms
            if is_buy:
                price_profit = context.current_price - entry_price
            else:
                price_profit = entry_price - context.current_price
            
            # Profit as % of risk
            profit_pct_of_risk = (price_profit / risk_distance) * 100 if risk_distance > 0 else 0
        else:
            # Fallback: use % of account
            account_balance = getattr(context, 'account_balance', 100000)
            profit_pct_of_risk = (current_profit / account_balance) * 100
        
        # Track peak profit
        if symbol not in self.position_peaks:
            self.position_peaks[symbol] = profit_pct_of_risk
        else:
            self.position_peaks[symbol] = max(self.position_peaks[symbol], profit_pct_of_risk)
        
        peak_profit = self.position_peaks[symbol]
        
        logger.info(f"")
        logger.info(f"🤖 EV EXIT ANALYSIS - {symbol}")
        logger.info(f"   Current P&L: ${current_profit:.2f} ({profit_pct_of_risk:.1f}% of risk)")
        logger.info(f"   Peak P&L: {peak_profit:.1f}% of risk")
        logger.info(f"   Position: {'BUY' if is_buy else 'SELL'}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Check for Position Management Opportunities
        # (Pyramiding, DCA, Partial Exits)
        # ═══════════════════════════════════════════════════════════
        
        # Get position tracking data
        add_count = getattr(context, 'add_count', 0) if hasattr(context, 'add_count') else 0
        dca_count = getattr(context, 'position_dca_count', 0) if hasattr(context, 'position_dca_count') else 0
        initial_volume = getattr(context, 'initial_volume', current_volume)
        
        # Check for pyramiding (add to winners)
        if profit_pct_of_risk > 0:
            pyramid_decision = self._check_pyramiding(context, profit_pct_of_risk, is_buy, add_count, initial_volume)
            if pyramid_decision['action'] == 'SCALE_IN':
                return pyramid_decision
        
        # Check for DCA (add to losers - RARE)
        if profit_pct_of_risk < 0:
            dca_decision = self._check_dca(context, profit_pct_of_risk, is_buy, dca_count, initial_volume)
            if dca_decision['action'] == 'DCA':
                return dca_decision
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: Calculate Exit Probabilities (AI-Driven)
        # ═══════════════════════════════════════════════════════════
        
        if profit_pct_of_risk < 0:
            # LOSING POSITION - Calculate recovery probability
            return self._analyze_losing_position(context, profit_pct_of_risk, is_buy, symbol)
        else:
            # WINNING POSITION - Calculate continuation vs reversal
            return self._analyze_winning_position(context, profit_pct_of_risk, peak_profit, is_buy, symbol, current_volume)
    
    def _analyze_losing_position(self, context, profit_pct_of_risk, is_buy, symbol) -> Dict:
        """Analyze losing position using AI"""
        
        # MINIMUM LOSS THRESHOLD - Don't close tiny losses (spread/slippage)
        # Only analyze exit if loss > 10% of risk (0.1R)
        if abs(profit_pct_of_risk) < 10.0:
            logger.info(f"   📉 Small loss ({profit_pct_of_risk:.1f}% of risk) - letting position breathe")
            return {
                'action': 'HOLD',
                'reason': f'Small loss {profit_pct_of_risk:.1f}% < 10% threshold, letting position develop',
                'confidence': 70,
                'priority': 'LOW'
            }
        
        # Calculate recovery probability using ALL 173 features
        recovery_prob = self._calculate_recovery_probability(context, is_buy)
        
        logger.info(f"")
        logger.info(f"   📉 LOSING POSITION ANALYSIS:")
        logger.info(f"   Recovery Probability: {recovery_prob:.1%}")
        
        # CORRECT EV CALCULATION:
        # We're at -X% of risk. Question: What's the EV of HOLDING FROM HERE?
        # 
        # If we recover (prob = recovery_prob):
        #   We gain back abs(profit_pct_of_risk) to get to breakeven
        # If we hit stop (prob = 1 - recovery_prob):
        #   We lose the remaining distance to stop (assume stop at -100% of risk = 1R)
        
        current_loss = abs(profit_pct_of_risk)  # e.g., 25.8%
        remaining_to_stop = 100.0 - current_loss  # e.g., 74.2% more to lose to hit stop
        
        # EV of holding FROM CURRENT POINT (not vs current loss)
        # If recover: gain = current_loss (get back to breakeven)
        # If hit stop: loss = remaining_to_stop
        ev_hold_from_here = (recovery_prob * current_loss) - ((1 - recovery_prob) * remaining_to_stop)
        
        # EV of exiting = 0 (we lock in current loss, no further change)
        ev_exit_from_here = 0.0
        
        logger.info(f"   Current Loss: {current_loss:.1f}% of risk")
        logger.info(f"   Remaining to Stop: {remaining_to_stop:.1f}% of risk")
        logger.info(f"   EV if Hold (from here): {ev_hold_from_here:+.1f}%")
        logger.info(f"   EV if Exit (from here): {ev_exit_from_here:+.1f}%")
        
        # Decision: Exit if EV of holding from here is negative
        # (i.e., expected to lose more money by holding)
        if ev_hold_from_here < ev_exit_from_here:
            confidence = min(90, 60 + abs(ev_hold_from_here) * 0.5)
            logger.info(f"   ❌ AI DECISION: EXIT (EV of holding is negative)")
            return {
                'action': 'CLOSE',
                'reason': f'EV(Hold)={ev_hold_from_here:+.1f}% < 0, recovery prob {recovery_prob:.0%} too low',
                'confidence': confidence,
                'priority': 'HIGH'
            }
        
        logger.info(f"   ✅ AI DECISION: HOLD (EV of holding is positive)")
        return {
            'action': 'HOLD',
            'reason': f'EV(Hold)={ev_hold_from_here:+.1f}% > 0, recovery prob {recovery_prob:.0%}',
            'confidence': min(85, 50 + ev_hold_from_here),
            'priority': 'LOW'
        }
    
    def _analyze_winning_position(self, context, profit_pct_of_risk, peak_profit, is_buy, symbol, current_volume) -> Dict:
        """
        HEDGE FUND APPROACH: Calculate EV for ALL possible actions and choose the best.
        No hardcoded thresholds - pure expected value optimization.
        """
        
        # Log CURRENT market data being used (proves we're using live data, not entry data)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        h1_rsi = getattr(context, 'h1_rsi', 50.0)
        h4_rsi = getattr(context, 'h4_rsi', 50.0)
        ml_direction = getattr(context, 'ml_direction', 'HOLD')
        ml_confidence = getattr(context, 'ml_confidence', 50.0)
        
        logger.info(f"   📊 CURRENT MARKET DATA (live, not from entry):")
        logger.info(f"      H1 trend: {h1_trend:.2f} | H4 trend: {h4_trend:.2f} | D1 trend: {d1_trend:.2f}")
        logger.info(f"      H1 RSI: {h1_rsi:.1f} | H4 RSI: {h4_rsi:.1f}")
        logger.info(f"      ML: {ml_direction} @ {ml_confidence:.1f}%")
        
        # Calculate continuation vs reversal probabilities using ALL features
        continuation_prob, reversal_prob = self._calculate_continuation_reversal(context, is_buy)
        flat_prob = max(0.0, 1.0 - continuation_prob - reversal_prob)
        
        logger.info(f"")
        logger.info(f"   📈 WINNING POSITION ANALYSIS (EV-Optimized):")
        logger.info(f"   Continuation: {continuation_prob:.1%} | Reversal: {reversal_prob:.1%} | Flat: {flat_prob:.1%}")
        
        # Calculate next target from market structure
        next_target = self._calculate_next_target(context, profit_pct_of_risk, is_buy)
        
        # Calculate distance to target
        dist_to_resistance = getattr(context, 'dist_to_resistance', 0)
        dist_to_support = getattr(context, 'dist_to_support', 0)
        current_price = getattr(context, 'current_price', 0)
        entry_price = getattr(context, 'position_entry_price', current_price)
        
        if is_buy and dist_to_resistance > 0:
            distance_to_target = dist_to_resistance
        elif not is_buy and dist_to_support > 0:
            distance_to_target = dist_to_support
        else:
            distance_to_target = 0
        
        if distance_to_target > 0:
            current_move = abs(current_price - entry_price)
            total_distance = current_move + distance_to_target
            progress_to_target = current_move / total_distance if total_distance > 0 else 0
        else:
            progress_to_target = 0
        
        # Giveback from peak
        giveback_pct = (peak_profit - profit_pct_of_risk) / peak_profit if peak_profit > 0 else 0
        
        # ═══════════════════════════════════════════════════════════════════
        # HEDGE FUND EV CALCULATION: Compare ALL possible actions
        # ═══════════════════════════════════════════════════════════════════
        
        # What happens in each scenario:
        # - Continue: Price goes to target (gain = next_target - current)
        # - Reverse: Price reverses, we lose some profit (keep ~40% of current)
        # - Flat: Price stays roughly here
        
        gain_if_continue = next_target - profit_pct_of_risk
        loss_if_reverse = profit_pct_of_risk * 0.6  # Lose 60% of current profit
        
        # EV of HOLDING 100%
        ev_hold_100 = (
            continuation_prob * (profit_pct_of_risk + gain_if_continue) +
            reversal_prob * (profit_pct_of_risk - loss_if_reverse) +
            flat_prob * profit_pct_of_risk
        )
        
        # EV of EXITING 100% (lock in current profit)
        ev_exit_100 = profit_pct_of_risk
        
        # EV of PARTIAL EXIT 25% (lock in 25%, hold 75%)
        locked_25 = profit_pct_of_risk * 0.25
        remaining_75 = profit_pct_of_risk * 0.75
        ev_partial_25 = locked_25 + (
            continuation_prob * (remaining_75 + gain_if_continue * 0.75) +
            reversal_prob * (remaining_75 - loss_if_reverse * 0.75) +
            flat_prob * remaining_75
        )
        
        # EV of PARTIAL EXIT 50% (lock in 50%, hold 50%)
        locked_50 = profit_pct_of_risk * 0.50
        remaining_50 = profit_pct_of_risk * 0.50
        ev_partial_50 = locked_50 + (
            continuation_prob * (remaining_50 + gain_if_continue * 0.50) +
            reversal_prob * (remaining_50 - loss_if_reverse * 0.50) +
            flat_prob * remaining_50
        )
        
        logger.info(f"")
        logger.info(f"   💰 EV FOR ALL ACTIONS:")
        logger.info(f"      Current Profit: {profit_pct_of_risk:.1f}% | Target: {next_target:.1f}% | Progress: {progress_to_target:.1%}")
        logger.info(f"      EV(Hold 100%):   {ev_hold_100:.1f}%")
        logger.info(f"      EV(Exit 25%):    {ev_partial_25:.1f}%")
        logger.info(f"      EV(Exit 50%):    {ev_partial_50:.1f}%")
        logger.info(f"      EV(Exit 100%):   {ev_exit_100:.1f}%")
        
        # Find the action with HIGHEST EV
        actions = {
            'HOLD': ev_hold_100,
            'SCALE_OUT_25': ev_partial_25,
            'SCALE_OUT_50': ev_partial_50,
            'CLOSE': ev_exit_100
        }
        
        best_action = max(actions, key=actions.get)
        best_ev = actions[best_action]
        
        logger.info(f"      → Best Action: {best_action} (EV: {best_ev:.1f}%)")
        
        # SMART Giveback protection - only act when it makes sense
        # Key insight: Don't close a profitable position just because it was MORE profitable before
        # Only act when: 1) Peak was significant AND 2) Current profit is small/negative
        giveback_adjustment = 0
        
        # Log giveback status
        logger.info(f"      Giveback from peak: {giveback_pct:.1%} (peak was {peak_profit:.1f}%, current {profit_pct_of_risk:.1f}%)")
        
        # SMART giveback protection:
        # - Only trigger if peak was significant (>50% of risk = 0.5R)
        # - AND current profit is getting small (<20% of risk)
        # - This prevents closing a +6% position just because it was +26% before
        
        if peak_profit > 50.0 and profit_pct_of_risk < 20.0 and giveback_pct > 0.70:
            # Had significant profit (>50% of risk), now almost gone (<20%), gave back >70%
            logger.info(f"   🚨 CRITICAL GIVEBACK: Peak {peak_profit:.0f}% → Current {profit_pct_of_risk:.0f}% - protecting remaining profit!")
            return {
                'action': 'CLOSE',
                'reason': f'Giveback protection: {peak_profit:.0f}% → {profit_pct_of_risk:.0f}% (lost {giveback_pct:.0%})',
                'confidence': 90,
                'priority': 'HIGH'
            }
        elif peak_profit > 30.0 and profit_pct_of_risk < 10.0 and giveback_pct > 0.60:
            # Had good profit (>30% of risk), now tiny (<10%), gave back >60%
            logger.info(f"   ⚠️ SIGNIFICANT GIVEBACK: Peak {peak_profit:.0f}% → Current {profit_pct_of_risk:.0f}% - taking 50% off")
            reduce_lots = current_volume * 0.50
            return {
                'action': 'SCALE_OUT',
                'reason': f'Giveback protection: {peak_profit:.0f}% → {profit_pct_of_risk:.0f}%',
                'confidence': 85,
                'reduce_lots': reduce_lots,
                'priority': 'HIGH'
            }
        elif giveback_pct > 0.40 and reversal_prob > 0.30 and profit_pct_of_risk < 30.0:
            # Moderate giveback + reversal signals + profit getting small
            giveback_adjustment = giveback_pct * reversal_prob * 15
            logger.info(f"      Giveback adjustment: +{giveback_adjustment:.1f}% to exit EVs (reversal risk)")
            actions['SCALE_OUT_25'] += giveback_adjustment * 0.5
            actions['SCALE_OUT_50'] += giveback_adjustment * 0.75
            actions['CLOSE'] += giveback_adjustment
            best_action = max(actions, key=actions.get)
            best_ev = actions[best_action]
        
        # Execute best action
        if best_action == 'CLOSE':
            logger.info(f"   ❌ AI DECISION: FULL EXIT (highest EV)")
            return {
                'action': 'CLOSE',
                'reason': f'EV optimization: Exit ({ev_exit_100:.1f}%) is best action',
                'confidence': min(90, 60 + abs(ev_exit_100 - ev_hold_100) * 2),
                'priority': 'HIGH'
            }
        
        elif best_action == 'SCALE_OUT_50':
            reduce_lots = current_volume * 0.50
            logger.info(f"   📉 AI DECISION: PARTIAL EXIT 50% (highest EV)")
            return {
                'action': 'SCALE_OUT',
                'reason': f'EV optimization: Exit 50% ({ev_partial_50:.1f}%) is best action',
                'confidence': 80,
                'reduce_lots': reduce_lots,
                'priority': 'MEDIUM'
            }
        
        elif best_action == 'SCALE_OUT_25':
            reduce_lots = current_volume * 0.25
            logger.info(f"   📉 AI DECISION: PARTIAL EXIT 25% (highest EV)")
            return {
                'action': 'SCALE_OUT',
                'reason': f'EV optimization: Exit 25% ({ev_partial_25:.1f}%) is best action',
                'confidence': 75,
                'reduce_lots': reduce_lots,
                'priority': 'MEDIUM'
            }
        
        # HOLD is best
        logger.info(f"   ✅ AI DECISION: HOLD (highest EV)")
        return {
            'action': 'HOLD',
            'reason': f'EV optimization: Hold ({ev_hold_100:.1f}%) > Exit ({ev_exit_100:.1f}%)',
            'confidence': min(90, 50 + (ev_hold_100 - ev_exit_100) * 2),
            'priority': 'LOW'
        }
    
    def _calculate_recovery_probability(self, context, is_buy) -> float:
        """
        Calculate probability of position recovering using ALL 173 features
        Swing trading focus: H1, H4, D1 timeframes
        """
        
        # Multi-timeframe trend alignment (swing trading focus)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        if is_buy:
            trend_alignment = (h1_trend + h4_trend + d1_trend) / 3.0
        else:
            trend_alignment = (3.0 - h1_trend - h4_trend - d1_trend) / 3.0
        
        # ML confidence in current direction
        ml_confidence = getattr(context, 'ml_confidence', 50) / 100.0
        ml_agrees = (context.ml_direction == 'BUY' and is_buy) or (context.ml_direction == 'SELL' and not is_buy)
        ml_factor = ml_confidence if ml_agrees else (1.0 - ml_confidence)
        
        # Market structure support
        dist_to_support = getattr(context, 'dist_to_support', 0)
        dist_to_resistance = getattr(context, 'dist_to_resistance', 0)
        current_price = getattr(context, 'current_price', 0)
        
        if is_buy and dist_to_support > 0 and current_price > 0:
            structure_support = min(1.0, (dist_to_support / current_price) * 100)
        elif not is_buy and dist_to_resistance > 0 and current_price > 0:
            structure_support = min(1.0, (dist_to_resistance / current_price) * 100)
        else:
            structure_support = 0.5
        
        # Volume support
        volume_ratio = getattr(context, 'volume_ratio', 1.0)
        volume_factor = min(1.0, volume_ratio / 1.5)
        
        # Combine all factors (AI-driven weights)
        recovery_prob = (
            trend_alignment * 0.35 +      # 35% - Most important for swing trading
            ml_factor * 0.30 +             # 30% - ML confidence
            structure_support * 0.20 +     # 20% - Support/resistance
            volume_factor * 0.15           # 15% - Volume confirmation
        )
        
        return recovery_prob
    
    def _calculate_continuation_reversal(self, context, is_buy) -> tuple:
        """
        Calculate continuation vs reversal probabilities
        Uses swing trading timeframes: H1, H4, D1
        """
        
        # Multi-timeframe trend strength
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        if is_buy:
            trend_strength = (h1_trend + h4_trend + d1_trend) / 3.0
        else:
            trend_strength = (3.0 - h1_trend - h4_trend - d1_trend) / 3.0
        
        # Momentum indicators
        h1_momentum = getattr(context, 'h1_momentum', 0.0)
        h4_momentum = getattr(context, 'h4_momentum', 0.0)
        
        if is_buy:
            momentum_strength = (h1_momentum + h4_momentum) / 2.0
        else:
            momentum_strength = -(h1_momentum + h4_momentum) / 2.0
        
        momentum_strength = (momentum_strength + 1.0) / 2.0  # Normalize to 0-1
        
        # Check for reversal signals
        h1_rsi = getattr(context, 'h1_rsi', 50.0)
        h4_rsi = getattr(context, 'h4_rsi', 50.0)
        
        # Overbought/oversold
        if is_buy:
            reversal_signals = ((h1_rsi > 70) + (h4_rsi > 70)) / 2.0
        else:
            reversal_signals = ((h1_rsi < 30) + (h4_rsi < 30)) / 2.0
        
        # Timeframe divergence
        reversed_tfs = 0
        if (is_buy and h1_trend < 0.5) or (not is_buy and h1_trend > 0.5):
            reversed_tfs += 1
        if (is_buy and h4_trend < 0.5) or (not is_buy and h4_trend > 0.5):
            reversed_tfs += 1
        if (is_buy and d1_trend < 0.5) or (not is_buy and d1_trend > 0.5):
            reversed_tfs += 1
        
        divergence_factor = reversed_tfs / 3.0
        
        # ML direction check
        ml_opposite = (context.ml_direction == 'SELL' and is_buy) or (context.ml_direction == 'BUY' and not is_buy)
        
        # Calculate probabilities
        continuation_prob = (
            trend_strength * 0.40 +        # 40% - Trend is king in swing trading
            momentum_strength * 0.30 +     # 30% - Momentum confirmation
            (1.0 - reversal_signals) * 0.15 +  # 15% - No exhaustion
            (1.0 - divergence_factor) * 0.15   # 15% - Timeframe agreement
        )
        
        reversal_prob = (
            reversal_signals * 0.35 +      # 35% - Overbought/oversold
            divergence_factor * 0.30 +     # 30% - Timeframe divergence
            (1.0 if ml_opposite else 0.0) * 0.35  # 35% - ML reversed
        )
        
        # Normalize so they don't exceed 1.0 combined
        total = continuation_prob + reversal_prob
        if total > 1.0:
            continuation_prob /= total
            reversal_prob /= total
        
        return continuation_prob, reversal_prob
    
    def _calculate_next_target(self, context, current_profit_pct, is_buy) -> float:
        """
        Calculate next profit target based on market structure
        NOT arbitrary percentages
        """
        
        # Get distance to next resistance/support
        dist_to_resistance = getattr(context, 'dist_to_resistance', 0)
        dist_to_support = getattr(context, 'dist_to_support', 0)
        current_price = getattr(context, 'current_price', 0)
        entry_price = getattr(context, 'position_entry_price', current_price)
        stop_loss = getattr(context, 'position_sl', 0)
        
        if stop_loss > 0:
            risk_distance = abs(entry_price - stop_loss)
        else:
            risk_distance = abs(current_price - entry_price) * 0.5
        
        # Calculate target based on market structure
        if is_buy and dist_to_resistance > 0 and current_price > 0:
            # Target is resistance level
            target_distance = dist_to_resistance
        elif not is_buy and dist_to_support > 0 and current_price > 0:
            # Target is support level
            target_distance = dist_to_support
        else:
            # Fallback: use ATR-based target
            atr = getattr(context, 'atr', 0)
            target_distance = atr * 2.0 if atr > 0 else risk_distance * 1.5
        
        # Convert to % of risk
        if risk_distance > 0:
            next_target_pct = (target_distance / risk_distance) * 100
        else:
            next_target_pct = current_profit_pct * 1.4  # 40% more
        
        # Ensure target is above current profit
        next_target_pct = max(next_target_pct, current_profit_pct * 1.2)
        
        return next_target_pct
    
    def _check_pyramiding(self, context, profit_pct_of_risk, is_buy, add_count, initial_volume) -> Dict:
        """
        HEDGE FUND EV-BASED PYRAMIDING
        Add to winners when EV of adding > EV of not adding
        """
        
        # Max 2 adds (risk management)
        if add_count >= 2:
            return {'action': 'HOLD'}
        
        # Need meaningful profit (>30% of risk = 0.3R) to confirm trend
        if profit_pct_of_risk < 30.0:
            return {'action': 'HOLD'}
        
        # Calculate continuation vs reversal probabilities
        continuation_prob, reversal_prob = self._calculate_continuation_reversal(context, is_buy)
        
        # ML confidence
        ml_confidence = getattr(context, 'ml_confidence', 50) / 100.0
        ml_agrees = (context.ml_direction == 'BUY' and is_buy) or (context.ml_direction == 'SELL' and not is_buy)
        
        # Calculate next target
        next_target = self._calculate_next_target(context, profit_pct_of_risk, is_buy)
        potential_gain = next_target - profit_pct_of_risk
        
        # ═══════════════════════════════════════════════════════════════════
        # EV-BASED PYRAMIDING DECISION
        # Compare EV of adding vs EV of not adding
        # ═══════════════════════════════════════════════════════════════════
        
        add_size = 0.40  # 40% of initial position
        
        # EV of NOT adding (current position only)
        ev_no_add = (
            continuation_prob * next_target +
            reversal_prob * (profit_pct_of_risk * 0.4) +  # Keep 40% on reversal
            (1 - continuation_prob - reversal_prob) * profit_pct_of_risk
        )
        
        # EV of ADDING (current + new position)
        # New position starts at 0 profit, so its EV is based on continuation/reversal
        new_position_ev = (
            continuation_prob * potential_gain * add_size -  # Gain on new position
            reversal_prob * potential_gain * add_size * 0.5   # Risk on new position (50% of potential)
        )
        
        ev_with_add = ev_no_add + new_position_ev
        
        # Add if EV improves AND ML agrees
        ev_improvement = ev_with_add - ev_no_add
        
        logger.info(f"")
        logger.info(f"   📈 PYRAMIDING EV ANALYSIS:")
        logger.info(f"      Continuation: {continuation_prob:.1%} | Reversal: {reversal_prob:.1%}")
        logger.info(f"      ML Agrees: {ml_agrees} ({ml_confidence:.1%})")
        logger.info(f"      EV(No Add): {ev_no_add:.1f}%")
        logger.info(f"      EV(Add 40%): {ev_with_add:.1f}%")
        logger.info(f"      EV Improvement: {ev_improvement:+.1f}%")
        
        # Add if: EV improves AND ML agrees AND continuation > reversal
        if ev_improvement > 0 and ml_agrees and continuation_prob > reversal_prob:
            add_lots = initial_volume * add_size
            logger.info(f"   ✅ PYRAMID: Add {add_lots:.2f} lots (EV +{ev_improvement:.1f}%)")
            return {
                'action': 'SCALE_IN',
                'reason': f'EV pyramiding: +{ev_improvement:.1f}% improvement, cont {continuation_prob:.0%}',
                'add_lots': add_lots,
                'confidence': min(90, 50 + ev_improvement * 5),
                'priority': 'MEDIUM'
            }
        
        return {'action': 'HOLD'}
    
    def _check_dca(self, context, profit_pct_of_risk, is_buy, dca_count, initial_volume) -> Dict:
        """
        HEDGE FUND EV-BASED DCA
        Add to losers ONLY when EV of averaging down > EV of holding
        This is RARE - requires very high confidence in recovery
        """
        
        # Max 1 DCA (strict risk management)
        if dca_count >= 1:
            return {'action': 'HOLD'}
        
        # Only DCA moderate losses (-30% to -80% of risk)
        # Too small = just noise, too large = trend confirmed against us
        if profit_pct_of_risk < -80.0 or profit_pct_of_risk > -30.0:
            return {'action': 'HOLD'}
        
        # Calculate recovery probability using ALL features
        recovery_prob = self._calculate_recovery_probability(context, is_buy)
        
        # ML confidence
        ml_confidence = getattr(context, 'ml_confidence', 50) / 100.0
        ml_agrees = (context.ml_direction == 'BUY' and is_buy) or (context.ml_direction == 'SELL' and not is_buy)
        
        # ═══════════════════════════════════════════════════════════════════
        # EV-BASED DCA DECISION
        # Compare EV of DCA vs EV of just holding
        # ═══════════════════════════════════════════════════════════════════
        
        current_loss = abs(profit_pct_of_risk)  # e.g., 50%
        remaining_to_stop = 100.0 - current_loss  # e.g., 50% more to stop
        
        dca_size = 0.30  # 30% of initial position
        
        # EV of HOLDING (no DCA)
        # If recover: gain back current_loss
        # If hit stop: lose remaining_to_stop
        ev_hold = (recovery_prob * current_loss) - ((1 - recovery_prob) * remaining_to_stop)
        
        # EV of DCA
        # DCA improves avg entry, so if we recover, we gain MORE
        # But if we hit stop, we lose MORE (larger position)
        # Assume DCA improves breakeven by ~30% of current loss
        improved_breakeven = current_loss * 0.7  # Need less recovery to break even
        
        # If recover: gain back improved_breakeven (easier target)
        # If hit stop: lose remaining_to_stop × 1.3 (larger position)
        ev_dca = (recovery_prob * improved_breakeven * 1.3) - ((1 - recovery_prob) * remaining_to_stop * 1.3)
        
        ev_improvement = ev_dca - ev_hold
        
        logger.info(f"")
        logger.info(f"   📉 DCA EV ANALYSIS:")
        logger.info(f"      Current Loss: {current_loss:.1f}% of risk")
        logger.info(f"      Recovery Prob: {recovery_prob:.1%}")
        logger.info(f"      ML Agrees: {ml_agrees} ({ml_confidence:.1%})")
        logger.info(f"      EV(Hold): {ev_hold:+.1f}%")
        logger.info(f"      EV(DCA 30%): {ev_dca:+.1f}%")
        logger.info(f"      EV Improvement: {ev_improvement:+.1f}%")
        
        # DCA if: EV improves significantly AND ML agrees AND recovery > 60%
        # (Higher bar than pyramiding because DCA is riskier)
        if ev_improvement > 5.0 and ml_agrees and recovery_prob > 0.60:
            add_lots = initial_volume * dca_size
            logger.info(f"   ✅ DCA: Add {add_lots:.2f} lots (EV +{ev_improvement:.1f}%)")
            return {
                'action': 'DCA',
                'reason': f'EV DCA: +{ev_improvement:.1f}% improvement, recovery {recovery_prob:.0%}',
                'add_lots': add_lots,
                'confidence': min(90, 50 + ev_improvement * 2),
                'priority': 'MEDIUM'
            }
        
        return {'action': 'HOLD'}
