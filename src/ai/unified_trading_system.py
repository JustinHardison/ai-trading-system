"""
Unified Trading System - Hedge Fund Grade
Clean, simple, effective
Uses ALL 147+ AI features for every decision

SINGLE SOURCE OF TRUTH for:
- Trade type classification (SCALP/DAY/SWING)
- Anti-churn logic (AI-driven, not time-based)
- Entry/exit decisions
- Session awareness (same logic as exit manager)
"""
import logging
import time
from datetime import datetime
import pytz
from typing import Dict, Optional
from .enhanced_context import EnhancedTradingContext
from .ftmo_strategy import get_ftmo_strategy
from .ai_market_analyzer import get_ai_analyzer, AIMarketState
# Position sizing delegated to ElitePositionSizer in api.py

logger = logging.getLogger(__name__)


class UnifiedTradingSystem:
    """
    Multi-Style Trading System - SCALP, DAY, SWING
    
    Philosophy:
    - Classify setup type based on timeframe alignment
    - Adapt ML thresholds, targets, and exit logic per setup type
    - Ensure consistent trading activity for prop firms
    - AI-driven classification and execution
    """
    
    # Setup type configurations - PROFESSIONAL TRADER LOGIC
    # Key insight: Position size is INVERSE to stop distance
    # Wider stops (SWING) = smaller size to maintain same dollar risk
    # Tighter stops (SCALP) = can use larger size
    # AI-DRIVEN SETUP CONFIG
    # NO hardcoded profit targets - targets come from market structure (S/R levels, ATR)
    # Only ATR multipliers for stop/target DISTANCES, not fixed percentages
    # 
    # CRITICAL: Stops must be wide enough to survive normal market noise
    # Using H4 ATR as base ensures stops account for real volatility
    # Targets should be 2-3x stop distance for positive expectancy
    SETUP_CONFIG = {
        'SWING': {
            'ml_threshold': 0.60,       # Need conviction for longer holds
            'position_size_mult': 0.5,  # SMALLER - wide stops need room to breathe
            'stop_atr_mult': 3.0,       # Wide stop - 3.0x H4 ATR (was 2.5)
            'tp_atr_mult': 7.5,         # Big target - 7.5x ATR (2.5:1 R:R)
            'early_exit_tf': 'H4',      # Exit warning from H4
            'patience': 'HIGH',
            'hold_time': '8hrs-5days',
        },
        'DAY': {
            'ml_threshold': 0.57,       # Medium confidence
            'position_size_mult': 1.0,  # Standard size
            'stop_atr_mult': 2.0,       # Medium stop - 2.0x H4 ATR (was 1.5)
            'tp_atr_mult': 4.0,         # Medium target - 4.0x ATR (2:1 R:R)
            'early_exit_tf': 'H1',      # Exit warning from H1
            'patience': 'MEDIUM',
            'hold_time': '2-8hrs',
        },
        'SCALP': {
            'ml_threshold': 0.60,       # Need conviction even for scalps
            'position_size_mult': 1.5,  # LARGER - tight stops, defined risk
            'stop_atr_mult': 1.5,       # Stop - 1.5x H4 ATR (was 1.2 - too tight!)
            'tp_atr_mult': 3.0,         # Target - 3.0x ATR (2:1 R:R)
            'early_exit_tf': 'M15',     # Exit warning from M15 (not M5 - too noisy)
            'patience': 'LOW',
            'hold_time': '15min-2hr',
        }
    }
    
    def __init__(self):
        # Position sizing delegated to ElitePositionSizer in api.py
        # This system focuses on ENTRY/EXIT decisions using all AI features
        
        # Base thresholds (adjusted per setup type)
        self.entry_score_min = 55
        self.entry_ml_min = 0.55       # Base ML - adjusted per setup
        self.exit_score_threshold = 70
        self.dca_score_min = 75
        self.scale_score_min = 75
        
        # FTMO Strategy for session awareness
        self.ftmo_strategy = get_ftmo_strategy()
        
        # ═══════════════════════════════════════════════════════════
        # SESSION AWARENESS - Same logic as EV Exit Manager
        # ═══════════════════════════════════════════════════════════
        self.SESSIONS = {
            'asian': {'start': 0, 'end': 8, 'indices_mult': 0.5, 'forex_mult': 0.7, 'entry_boost': 0.7},
            'london': {'start': 8, 'end': 16, 'indices_mult': 0.8, 'forex_mult': 1.0, 'entry_boost': 1.0},
            'new_york': {'start': 13, 'end': 21, 'indices_mult': 1.0, 'forex_mult': 1.0, 'entry_boost': 1.0},
            'overlap': {'start': 13, 'end': 16, 'indices_mult': 1.2, 'forex_mult': 1.2, 'entry_boost': 1.2},
        }
        
        # ═══════════════════════════════════════════════════════════
        # POSITION STATE TRACKING
        # Tracks setup type, entry conditions, and last actions
        # This is the SINGLE SOURCE OF TRUTH for anti-churn
        # ═══════════════════════════════════════════════════════════
        self.position_state = {}  # symbol -> {setup_type, entry_time, entry_price, last_action, ...}
        self.recent_closes = {}   # symbol -> {time, direction, cont_prob, reason}
        
        # ═══════════════════════════════════════════════════════════
        # LOSS COOLDOWN TRACKING - Prevents rapid re-entry after losses
        # This is CRITICAL for preventing the US500-style disaster where
        # the system re-entered 11 times in 30 minutes, losing each time
        # ═══════════════════════════════════════════════════════════
        self.recent_losses = {}   # symbol -> {count, last_loss_time, total_loss, direction}
    
    def get_session_context(self, symbol: str) -> Dict:
        """
        Get current session context for a symbol.
        Same logic as EV Exit Manager for consistency.
        """
        symbol_lower = symbol.lower().replace('.sim', '').replace('z25', '').replace('g26', '')
        
        # Determine symbol type
        is_index = any(s in symbol_lower for s in ['us30', 'us100', 'us500', 'dax', 'ftse'])
        is_forex = any(s in symbol_lower for s in ['eur', 'gbp', 'jpy', 'aud', 'nzd', 'cad', 'chf'])
        is_gold = 'xau' in symbol_lower or 'gold' in symbol_lower
        
        # Get current UTC hour
        utc_now = datetime.now(pytz.UTC)
        current_hour = utc_now.hour
        
        # Determine session
        if 13 <= current_hour < 16:
            session_name = 'overlap'
            session_config = self.SESSIONS['overlap']
        elif 13 <= current_hour < 21:
            session_name = 'new_york'
            session_config = self.SESSIONS['new_york']
        elif 8 <= current_hour < 16:
            session_name = 'london'
            session_config = self.SESSIONS['london']
        else:
            session_name = 'asian'
            session_config = self.SESSIONS['asian']
        
        # Get multiplier based on symbol type
        if is_index:
            session_mult = session_config['indices_mult']
        elif is_forex:
            session_mult = session_config['forex_mult']
        elif is_gold:
            session_mult = max(0.8, session_config['forex_mult'])
        else:
            session_mult = session_config['forex_mult']
        
        entry_boost = session_config['entry_boost']
        is_optimal = session_mult >= 1.0
        
        return {
            'session_name': session_name,
            'session_mult': session_mult,
            'entry_boost': entry_boost,
            'is_optimal': is_optimal,
            'current_hour_utc': current_hour,
            'symbol_type': 'index' if is_index else ('forex' if is_forex else ('gold' if is_gold else 'other'))
        }
    
    # ═══════════════════════════════════════════════════════════
    # SETUP CLASSIFICATION - SIMPLE
    # ML already analyzed all 200 features. We just classify for TP/SL/size.
    # ═══════════════════════════════════════════════════════════
    
    def _classify_setup(self, ml_direction, ml_confidence, m5, m15, m30, h1, h4, d1):
        """
        Classify setup type based on which timeframes support the ML direction.
        ML decides direction - we just determine SCALP/DAY/SWING for TP/SL/size.
        
        Uses ALL timeframes: M5, M15, M30, H1, H4, D1
        
        SWING: D1 supports (hold for big move, 1-3% target)
        DAY: H4 supports but D1 neutral (medium hold, 0.5-1% target)
        SCALP: Only lower TFs support (quick in/out, 0.2-0.5% target)
        """
        
        # ML must have a direction
        if ml_direction not in ['BUY', 'SELL']:
            # ML says HOLD - check if it has a lean (confidence > 52%)
            if ml_confidence < 0.52:
                return 'SCALP', 'BUY', 1.0  # Default to scalp with ML's lean
            # ML has slight directional bias, use it
        
        direction = ml_direction if ml_direction in ['BUY', 'SELL'] else 'BUY'
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SUPPORT SCORING - NO HARDCODED THRESHOLDS
        # 
        # Instead of binary "supports/doesn't support" with fixed thresholds,
        # calculate a continuous support score for each timeframe.
        # This prevents edge cases where 0.519 fails but 0.520 passes.
        # ═══════════════════════════════════════════════════════════
        
        def support_score(trend, direction):
            """
            Calculate continuous support score (0.0 to 1.0)
            For BUY: trend 0.5 = neutral (0.5 score), trend 1.0 = strong support (1.0 score)
            For SELL: trend 0.5 = neutral (0.5 score), trend 0.0 = strong support (1.0 score)
            """
            if direction == 'BUY':
                # Map 0.0-1.0 trend to 0.0-1.0 support score
                return trend
            else:
                # For SELL, invert: low trend = high support
                return 1.0 - trend
        
        # Calculate support scores for all timeframes
        d1_score = support_score(d1, direction)
        h4_score = support_score(h4, direction)
        h1_score = support_score(h1, direction)
        m30_score = support_score(m30, direction)
        m15_score = support_score(m15, direction)
        m5_score = support_score(m5, direction)
        
        # Weighted HTF score (D1 most important)
        htf_weighted_score = (d1_score * 0.40) + (h4_score * 0.35) + (h1_score * 0.25)
        
        # Weighted LTF score
        ltf_weighted_score = (m30_score * 0.40) + (m15_score * 0.35) + (m5_score * 0.25)
        
        # For backward compatibility, convert to counts using the scores
        # Strong support = score > 0.55, weak support = score > 0.50
        htf_support = sum([d1_score > 0.55, h4_score > 0.55, h1_score > 0.55])
        ltf_support = sum([m30_score > 0.55, m15_score > 0.55, m5_score > 0.55])
        
        # Calculate strength (1.0 - 3.0)
        strength = 1.0 + (htf_support * 0.4) + (ltf_support * 0.15)
        
        # ═══════════════════════════════════════════════════════════
        # CLASSIFY: Multi-timeframe alignment determines trade type
        # 
        # BALANCED approach - D1 alone is NOT enough for SWING
        # Need true multi-timeframe confirmation
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SETUP CLASSIFICATION - PURE SCORING
        # 
        # Calculate scores for each setup type based on market conditions
        # The setup with highest score wins - NO FIXED THRESHOLDS
        # ═══════════════════════════════════════════════════════════
        
        # SWING SCORE: Requires strong D1+H4 alignment
        # Higher when both D1 and H4 strongly support direction
        swing_score = (d1_score * 0.50) + (h4_score * 0.35) + (h1_score * 0.15)
        
        # DAY SCORE: Requires H4+H1 alignment, D1 not against
        # Penalize if D1 is against, reward if H4+H1 aligned
        d1_penalty = max(0, 0.5 - d1_score) * 0.3  # Penalty if D1 against
        day_score = (h4_score * 0.45) + (h1_score * 0.35) + (m30_score * 0.20) - d1_penalty
        
        # SCALP SCORE: Lower TFs matter more, less dependent on HTF
        # Good for quick trades when LTF aligned but HTF mixed
        scalp_score = (m15_score * 0.35) + (m30_score * 0.30) + (h1_score * 0.25) + (h4_score * 0.10)
        
        # Adjust scores based on overall alignment quality
        # If HTF strongly aligned, boost SWING; if LTF aligned, boost SCALP
        htf_alignment_bonus = max(0, htf_weighted_score - 0.5) * 0.2
        ltf_alignment_bonus = max(0, ltf_weighted_score - 0.5) * 0.2
        
        swing_score += htf_alignment_bonus
        scalp_score += ltf_alignment_bonus
        
        # Select setup type with highest score
        scores = {
            'SWING': swing_score,
            'DAY': day_score,
            'SCALP': scalp_score
        }
        
        best_setup = max(scores, key=scores.get)
        
        # Adjust strength based on winning score magnitude
        score_strength = scores[best_setup]
        adjusted_strength = strength * (0.5 + score_strength)
        
        return best_setup, direction, adjusted_strength
    
    # ═══════════════════════════════════════════════════════════
    # POSITION STATE MANAGEMENT
    # Single source of truth for trade type and anti-churn
    # ═══════════════════════════════════════════════════════════
    
    def get_position_setup_type(self, symbol: str) -> Optional[str]:
        """Get the setup type for an existing position (set at entry)."""
        symbol_key = symbol.lower().split('.')[0]
        state = self.position_state.get(symbol_key, {})
        return state.get('setup_type')
    
    def register_entry(self, symbol: str, setup_type: str, direction: str, 
                       entry_price: float, cont_prob: float):
        """Register a new position entry - locks in the setup type."""
        symbol_key = symbol.lower().split('.')[0]
        self.position_state[symbol_key] = {
            'setup_type': setup_type,
            'direction': direction,
            'entry_time': time.time(),
            'entry_price': entry_price,
            'cont_prob_at_entry': cont_prob,
            'last_action': 'ENTRY',
            'last_action_time': time.time(),
            'last_cont_prob': cont_prob
        }
        logger.info(f"   📝 Registered {setup_type} entry for {symbol_key}")
        
        # Clear any recent close for this symbol (we're back in)
        if symbol_key in self.recent_closes:
            del self.recent_closes[symbol_key]
    
    def register_action(self, symbol: str, action: str, cont_prob: float, price: float = 0):
        """Register a position action (SCALE_IN, SCALE_OUT, etc.)."""
        symbol_key = symbol.lower().split('.')[0]
        if symbol_key in self.position_state:
            self.position_state[symbol_key]['last_action'] = action
            self.position_state[symbol_key]['last_action_time'] = time.time()
            self.position_state[symbol_key]['last_cont_prob'] = cont_prob
            if price > 0:
                self.position_state[symbol_key]['last_action_price'] = price
    
    def register_close(self, symbol: str, direction: str, cont_prob: float, reason: str, pnl: float = 0):
        """Register a position close for anti-churn tracking."""
        symbol_key = symbol.lower().split('.')[0]
        self.recent_closes[symbol_key] = {
            'time': time.time(),
            'direction': direction,
            'cont_prob': cont_prob,
            'reason': reason
        }
        # Clear position state
        if symbol_key in self.position_state:
            del self.position_state[symbol_key]
        logger.info(f"   📝 Registered close for {symbol_key} (cont_prob={cont_prob:.1%})")
        
        # Track losses for cooldown
        if pnl < 0:
            self._register_loss(symbol_key, direction, pnl)
        elif pnl > 0:
            # Win resets the loss counter
            self._clear_losses(symbol_key)
    
    def _register_loss(self, symbol_key: str, direction: str, pnl: float):
        """Track consecutive losses for a symbol."""
        now = time.time()
        
        if symbol_key in self.recent_losses:
            loss_info = self.recent_losses[symbol_key]
            # If same direction and within 2 hours, increment counter
            if loss_info['direction'] == direction and (now - loss_info['last_loss_time']) < 7200:
                loss_info['count'] += 1
                loss_info['total_loss'] += abs(pnl)
                loss_info['last_loss_time'] = now
            else:
                # Different direction or too long ago - reset
                self.recent_losses[symbol_key] = {
                    'count': 1,
                    'last_loss_time': now,
                    'total_loss': abs(pnl),
                    'direction': direction
                }
        else:
            self.recent_losses[symbol_key] = {
                'count': 1,
                'last_loss_time': now,
                'total_loss': abs(pnl),
                'direction': direction
            }
        
        loss_info = self.recent_losses[symbol_key]
        logger.warning(f"   ⚠️ LOSS #{loss_info['count']} for {symbol_key} ({direction}): ${abs(pnl):.2f} (total: ${loss_info['total_loss']:.2f})")
    
    def _clear_losses(self, symbol_key: str):
        """Clear loss counter after a win."""
        if symbol_key in self.recent_losses:
            logger.info(f"   ✅ Win clears loss counter for {symbol_key}")
            del self.recent_losses[symbol_key]
    
    def check_loss_cooldown(self, symbol: str, direction: str) -> tuple:
        """
        Check if we should block entry due to recent consecutive losses.
        
        Returns: (allowed: bool, reason: str)
        
        Logic:
        - 1 loss: No cooldown (normal trading)
        - 2 losses: 5 min cooldown OR direction change
        - 3+ losses: 15 min cooldown AND direction change required
        - 5+ losses: 60 min cooldown (circuit breaker level)
        """
        symbol_key = symbol.lower().split('.')[0]
        
        if symbol_key not in self.recent_losses:
            return True, "No recent losses"
        
        loss_info = self.recent_losses[symbol_key]
        loss_count = loss_info['count']
        last_loss_time = loss_info['last_loss_time']
        loss_direction = loss_info['direction']
        total_loss = loss_info['total_loss']
        
        seconds_since_loss = time.time() - last_loss_time
        direction_changed = direction != loss_direction
        
        # 1 loss: Allow immediately
        if loss_count == 1:
            return True, "Single loss - normal trading"
        
        # 2 losses: 5 min cooldown OR direction change
        if loss_count == 2:
            if direction_changed:
                logger.info(f"   🔄 Direction changed after 2 losses - allowing entry")
                return True, "Direction changed after 2 losses"
            if seconds_since_loss >= 300:  # 5 minutes
                return True, f"5 min cooldown passed after 2 losses"
            return False, f"Loss cooldown: 2 losses in {loss_direction}, wait {300 - seconds_since_loss:.0f}s or change direction"
        
        # 3-4 losses: 15 min cooldown AND direction change preferred
        if loss_count <= 4:
            if direction_changed and seconds_since_loss >= 300:
                logger.info(f"   🔄 Direction changed + 5min after {loss_count} losses - allowing entry")
                return True, f"Direction changed + cooldown after {loss_count} losses"
            if seconds_since_loss >= 900:  # 15 minutes
                return True, f"15 min cooldown passed after {loss_count} losses"
            return False, f"Loss cooldown: {loss_count} losses (${total_loss:.0f}), wait {900 - seconds_since_loss:.0f}s"
        
        # 5+ losses: 60 min cooldown (circuit breaker)
        if seconds_since_loss >= 3600:  # 60 minutes
            logger.warning(f"   ⚠️ 60 min cooldown passed after {loss_count} losses - resetting")
            del self.recent_losses[symbol_key]
            return True, f"60 min circuit breaker cooldown passed"
        
        return False, f"CIRCUIT BREAKER: {loss_count} consecutive losses (${total_loss:.0f}), wait {(3600 - seconds_since_loss)/60:.0f} min"
    
    def check_anti_churn_entry(self, symbol: str, current_cont_prob: float, 
                                current_direction: str) -> tuple:
        """
        AI-driven anti-churn check for new entries after close.
        
        Returns: (allowed: bool, reason: str)
        
        Logic:
        - If we just closed, require SIGNIFICANT thesis change to re-enter
        - Thesis change = continuation probability shifted by >20%
        - OR direction reversed (was long, now short signal)
        - This is AI-driven, not time-based
        """
        symbol_key = symbol.lower().split('.')[0]
        
        if symbol_key not in self.recent_closes:
            return True, "No recent close"
        
        close_info = self.recent_closes[symbol_key]
        close_time = close_info['time']
        close_direction = close_info['direction']
        close_cont_prob = close_info['cont_prob']
        
        seconds_since_close = time.time() - close_time
        prob_change = abs(current_cont_prob - close_cont_prob)
        direction_reversed = current_direction != close_direction
        
        # AI-driven conditions for allowing re-entry:
        # 1. Direction reversed (short to long or vice versa) - new thesis
        # 2. Probability shifted significantly (>20%) - market changed
        # NO TIME-BASED OVERRIDE - purely AI-driven
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN ANTI-CHURN (NO HARDCODED TIME LIMITS)
        # 
        # The real fix for flip-flopping is in live_feature_engineer.py:
        # HTF trends (H1, H4, D1) now use COMPLETED bars only, which
        # prevents the direction from changing due to incomplete bar updates.
        # 
        # This anti-churn check is a backup that requires thesis change:
        # - Direction reversal: Allow if thesis changed significantly
        # - Same direction: Allow if thesis changed significantly
        # 
        # NO TIME-BASED BLOCKS - pure AI-driven thesis analysis.
        # ═══════════════════════════════════════════════════════════
        
        # Allow re-entry if thesis changed significantly (>20% probability shift)
        if prob_change >= 0.20:
            del self.recent_closes[symbol_key]
            return True, f"Thesis changed significantly ({prob_change:.1%} shift)"
        
        # Allow direction reversal if it's a genuine reversal (not flip-flopping)
        # A genuine reversal should have some thesis change (>10%)
        if direction_reversed and prob_change >= 0.10:
            del self.recent_closes[symbol_key]
            return True, f"Direction reversed with thesis change ({prob_change:.1%} shift)"
        
        # Block re-entry if thesis hasn't changed enough
        # This prevents churning when the market is indecisive
        return False, f"Anti-churn: Thesis unchanged (prob_change={prob_change:.1%}, need >20% or reversal with >10%)"
    
    def check_anti_churn_action(self, symbol: str, proposed_action: str, 
                                 current_cont_prob: float) -> tuple:
        """
        AI-driven anti-churn check for position actions (SCALE_IN after SCALE_OUT, etc.)
        
        Returns: (allowed: bool, reason: str)
        """
        symbol_key = symbol.lower().split('.')[0]
        
        if symbol_key not in self.position_state:
            return True, "No position state"
        
        state = self.position_state[symbol_key]
        last_action = state.get('last_action', 'HOLD')
        last_cont_prob = state.get('last_cont_prob', 0.5)
        last_action_time = state.get('last_action_time', 0)
        
        seconds_since_action = time.time() - last_action_time
        prob_change = abs(current_cont_prob - last_cont_prob)
        
        # Check for reversal actions
        is_reversal = (
            (last_action in ['SCALE_IN', 'DCA'] and proposed_action in ['SCALE_OUT', 'CLOSE']) or
            (last_action in ['SCALE_OUT'] and proposed_action in ['SCALE_IN', 'DCA'])
        )
        
        if not is_reversal:
            return True, "Not a reversal action"
        
        # For reversals, require thesis change
        if prob_change >= 0.15:
            return True, f"Thesis changed ({prob_change:.1%} shift)"
        
        if seconds_since_action >= 300:  # 5 minutes for position actions
            return True, f"Sufficient time ({seconds_since_action:.0f}s)"
        
        return False, f"Anti-churn: {last_action} was {seconds_since_action:.0f}s ago, prob_change={prob_change:.1%}"
    
    # ═══════════════════════════════════════════════════════════
    # ENTRY DECISION
    # ═══════════════════════════════════════════════════════════
    
    def should_enter_trade(
        self,
        context: EnhancedTradingContext,
        market_analysis: Dict
    ) -> Dict:
        """
        Decide if we should enter a trade
        
        Uses ALL 147 features through context and market_analysis
        
        Returns:
            {
                'should_enter': bool,
                'direction': 'BUY' or 'SELL',
                'lot_size': float,
                'stop_loss': float,
                'take_profit': float,
                'reason': str
            }
        """
        
        logger.info(f"")
        logger.info(f"🎯 ENTRY ANALYSIS - {context.symbol}")
        logger.info(f"   Market Score: {market_analysis['total_score']:.0f}/100")
        logger.info(f"   ML: {context.ml_direction} @ {context.ml_confidence:.1f}%")
        logger.info(f"   Regime: {context.get_market_regime()}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: EXTRACT TIMEFRAME DATA
        # ═══════════════════════════════════════════════════════════
        
        market_score = market_analysis['total_score']
        ml_confidence = context.ml_confidence / 100.0  # Convert to 0-1
        ml_direction = context.ml_direction  # BUY, SELL, or HOLD
        
        # Get all timeframe trends (M5 through D1)
        m5_trend = getattr(context, 'm5_trend', 0.5)
        m15_trend = getattr(context, 'm15_trend', 0.5)
        m30_trend = getattr(context, 'm30_trend', 0.5)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN DIRECTION SELECTION - PURE CONTINUOUS SCORING
        # 
        # NO HARDCODED THRESHOLDS - Use weighted scoring to determine:
        # 1. Best direction based on all timeframe alignment
        # 2. Entry quality score (affects position size, not binary block)
        # 3. Let the AI decide based on continuous analysis
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # SETUP-AWARE DIRECTION SCORING
        # 
        # Different trade types should use different timeframe weights:
        # - SWING: D1 dominant (50%), H4 (25%), H1 (15%), LTF (10%)
        # - DAY: H4 dominant (40%), H1 (30%), D1 (20%), LTF (10%)
        # - SCALP: LTF dominant - M15 (30%), M30 (25%), H1 (25%), H4 (15%), D1 (5%)
        # 
        # First, calculate scores for each setup type to determine which
        # timeframe weighting to use.
        # ═══════════════════════════════════════════════════════════
        
        # Quick setup detection based on which TFs are aligned
        # For BUY: trend > 0.55 = supports, For SELL: trend < 0.45 = supports
        def quick_tf_support(trend, for_buy=True):
            if for_buy:
                return trend > 0.55
            else:
                return trend < 0.45
        
        # Check ML direction to determine which way we're looking
        check_buy = ml_direction == 'BUY' or (ml_direction == 'HOLD' and ml_confidence > 0.52)
        
        d1_supports = quick_tf_support(d1_trend, check_buy)
        h4_supports = quick_tf_support(h4_trend, check_buy)
        h1_supports = quick_tf_support(h1_trend, check_buy)
        m30_supports = quick_tf_support(m30_trend, check_buy)
        m15_supports = quick_tf_support(m15_trend, check_buy)
        
        # Determine likely setup type based on which TFs support
        htf_support_count = sum([d1_supports, h4_supports, h1_supports])
        ltf_support_count = sum([m30_supports, m15_supports])
        
        if d1_supports and h4_supports:
            preliminary_setup = 'SWING'
        elif h4_supports and h1_supports:
            preliminary_setup = 'DAY'
        elif ltf_support_count >= 1 or h1_supports:
            preliminary_setup = 'SCALP'
        else:
            preliminary_setup = 'SCALP'  # Default to most conservative
        
        # Calculate direction scores using SETUP-APPROPRIATE weights
        if preliminary_setup == 'SWING':
            # SWING: D1 dominant
            buy_score = d1_trend * 0.50 + h4_trend * 0.25 + h1_trend * 0.15 + m30_trend * 0.07 + m15_trend * 0.03
            sell_score = (1-d1_trend) * 0.50 + (1-h4_trend) * 0.25 + (1-h1_trend) * 0.15 + (1-m30_trend) * 0.07 + (1-m15_trend) * 0.03
        elif preliminary_setup == 'DAY':
            # DAY: H4 dominant, D1 still matters but less
            buy_score = d1_trend * 0.20 + h4_trend * 0.40 + h1_trend * 0.25 + m30_trend * 0.10 + m15_trend * 0.05
            sell_score = (1-d1_trend) * 0.20 + (1-h4_trend) * 0.40 + (1-h1_trend) * 0.25 + (1-m30_trend) * 0.10 + (1-m15_trend) * 0.05
        else:
            # SCALP: LTF dominant - M15, M30, H1 matter most
            buy_score = d1_trend * 0.05 + h4_trend * 0.15 + h1_trend * 0.25 + m30_trend * 0.25 + m15_trend * 0.30
            sell_score = (1-d1_trend) * 0.05 + (1-h4_trend) * 0.15 + (1-h1_trend) * 0.25 + (1-m30_trend) * 0.25 + (1-m15_trend) * 0.30
        
        # ML influence on direction - scales with confidence and setup type
        # SCALP trades rely more on ML since LTF trends are noisy
        # SWING/DAY trades rely more on HTF trends
        ml_weight = 0.25 if preliminary_setup == 'SCALP' else 0.15
        
        if ml_direction == 'BUY':
            buy_score += ml_confidence * ml_weight
        elif ml_direction == 'SELL':
            sell_score += ml_confidence * ml_weight
        
        # Determine direction based on which score is higher
        if buy_score > sell_score:
            direction = 'BUY'
            direction_confidence = buy_score / (buy_score + sell_score)  # 0.5 to 1.0
        else:
            direction = 'SELL'
            direction_confidence = sell_score / (buy_score + sell_score)  # 0.5 to 1.0
        
        # Log the AI-driven direction selection
        logger.info(f"   🧠 AI Direction Analysis ({preliminary_setup} weights):")
        logger.info(f"      BUY score: {buy_score:.3f} | SELL score: {sell_score:.3f}")
        logger.info(f"      Selected: {direction} (confidence: {direction_confidence:.1%})")
        logger.info(f"      TFs: D1={d1_trend:.2f}, H4={h4_trend:.2f}, H1={h1_trend:.2f}, M30={m30_trend:.2f}, M15={m15_trend:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND GRADE DIRECTION CONFIDENCE - TIMEFRAME AWARE
        # 
        # The confidence threshold depends on WHICH TIMEFRAMES drive the signal:
        # 
        # SWING (D1/H4 driven): D1 doesn't flip often, so 58% is enough
        #   - D1 trend changes maybe once per week
        #   - Lower threshold = more opportunities on strong daily trends
        # 
        # DAY (H4/H1 driven): H4 can flip intraday, need 62%
        #   - H4 trend changes 1-3 times per day
        #   - Medium threshold = balance between opportunity and stability
        # 
        # SCALP (M30/M15 driven): LTF flips frequently, need 68%
        #   - M15/M30 can flip multiple times per hour
        #   - Higher threshold = only enter on very clear LTF signals
        # 
        # This prevents flip-flopping while allowing quality entries
        # ═══════════════════════════════════════════════════════════
        
        # Pre-classify setup to determine appropriate threshold
        # (We'll classify again later for full analysis, but need setup type now)
        def quick_support_score(trend, direction):
            return trend if direction == 'BUY' else 1.0 - trend
        
        d1_support = quick_support_score(d1_trend, direction)
        h4_support = quick_support_score(h4_trend, direction)
        h1_support = quick_support_score(h1_trend, direction)
        
        # Determine which timeframes are driving this signal
        # 
        # IMPORTANT: Thresholds must be achievable given the confidence calculation.
        # With neutral trends (0.50), max confidence is ~50%. With aligned trends (0.60),
        # max confidence is ~55-60%. Thresholds must account for this.
        # 
        # ML adds up to 15% to the score, so with ML agreement:
        # - Neutral trends (0.50) + ML (0.15) = ~55% confidence possible
        # - Aligned trends (0.60) + ML (0.15) = ~62% confidence possible
        # 
        if d1_support > 0.55 and h4_support > 0.50:
            # D1 strongly supports, H4 confirms = SWING setup
            likely_setup = 'SWING'
            min_confidence = 0.53  # D1 aligned = stable signal
        elif h4_support > 0.55 and h1_support > 0.50:
            # H4 strongly supports, H1 confirms = DAY setup
            likely_setup = 'DAY'
            min_confidence = 0.54  # H4 aligned = medium stability
        else:
            # Lower TF driven = SCALP setup
            # With neutral trends (0.50) + ML (0.25), max confidence ~55%
            # Threshold must be achievable: 54% allows trades when ML is confident
            likely_setup = 'SCALP'
            min_confidence = 0.54  # LTF driven = ML must agree for entry
        
        # Additional adjustment: If D1 is AGAINST the direction, require higher confidence
        # This prevents fighting the daily trend on weak signals
        if d1_support < 0.45:
            min_confidence += 0.05  # Fighting D1 = need more conviction
            logger.info(f"   ⚠️ D1 against direction ({d1_support:.2f}) - raising threshold")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN ML CONFIDENCE THRESHOLD ADJUSTMENT
        # 
        # When ML is very confident (>70%), it has analyzed 138+ features
        # including HTF data. If ML sees something the simple trend
        # calculation doesn't, we should give it credit.
        # 
        # This is AI-driven: uses ML confidence, not hardcoded values.
        # The reduction scales with ML confidence above 70%.
        # ═══════════════════════════════════════════════════════════
        
        ml_threshold_reduction = 0.0
        if ml_confidence > 0.70 and ml_direction == direction:
            # ML agrees with direction AND is very confident
            # Reduce threshold proportionally: 70% ML = 0%, 80% ML = 1.5%, 90% ML = 3%
            ml_threshold_reduction = (ml_confidence - 0.70) * 0.15
            min_confidence -= ml_threshold_reduction
            logger.info(f"   🤖 High ML confidence ({ml_confidence:.0%}) agrees with {direction}")
            logger.info(f"      Threshold reduced by {ml_threshold_reduction:.1%} → {min_confidence:.0%}")
        
        if direction_confidence < min_confidence:
            logger.info(f"   ⏸️ Direction confidence too low for {likely_setup}")
            logger.info(f"      {direction_confidence:.1%} < {min_confidence:.0%} threshold")
            logger.info(f"      D1={d1_support:.2f}, H4={h4_support:.2f}, H1={h1_support:.2f}")
            return {'should_enter': False, 'reason': f'Direction unclear ({direction_confidence:.1%} < {min_confidence:.0%} for {likely_setup})'}
        
        # Calculate direction alignment penalty (how much ML disagrees with HTF)
        ml_htf_alignment = 1.0  # Perfect alignment
        if ml_direction == 'BUY' and direction == 'SELL':
            ml_htf_alignment = 0.5  # ML disagrees - reduce confidence
        elif ml_direction == 'SELL' and direction == 'BUY':
            ml_htf_alignment = 0.5  # ML disagrees - reduce confidence
        elif ml_direction == 'HOLD':
            ml_htf_alignment = 0.7  # ML uncertain - slightly reduce confidence
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2A: LOSS COOLDOWN CHECK (CRITICAL - prevents US500-style disasters)
        # If we've had consecutive losses on this symbol, require cooldown
        # ═══════════════════════════════════════════════════════════
        
        loss_cooldown_ok, loss_cooldown_reason = self.check_loss_cooldown(
            context.symbol, direction
        )
        
        if not loss_cooldown_ok:
            logger.warning(f"   🚫 {loss_cooldown_reason}")
            return {'should_enter': False, 'reason': loss_cooldown_reason}
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2B: ANTI-CHURN CHECK (thesis change required after close)
        # AI-driven: requires thesis change, not just time
        # ═══════════════════════════════════════════════════════════
        
        # Get continuation probability for anti-churn comparison
        cont_prob = market_analysis.get('continuation_prob', 0.5)
        
        anti_churn_ok, anti_churn_reason = self.check_anti_churn_entry(
            context.symbol, cont_prob, direction
        )
        
        if not anti_churn_ok:
            logger.warning(f"   🚫 {anti_churn_reason}")
            return {'should_enter': False, 'reason': anti_churn_reason}
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: CLASSIFY SETUP TYPE
        # CRITICAL: Use the FINAL direction (after flip), not ML direction
        # This ensures SWING is selected when D1 supports BUY, not SCALP
        # ═══════════════════════════════════════════════════════════
        
        setup_type, _, setup_strength = self._classify_setup(
            direction, ml_confidence, m5_trend, m15_trend, m30_trend, h1_trend, h4_trend, d1_trend
        )
        
        # Get config for this setup type
        config = self.SETUP_CONFIG[setup_type]
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN ML CONFIDENCE SCORING - NO BINARY THRESHOLDS
        # 
        # Instead of blocking entries below threshold, use ML confidence
        # to scale position size. Low confidence = smaller position.
        # This allows the AI to take trades when it sees opportunity,
        # but with appropriate risk sizing.
        # ═══════════════════════════════════════════════════════════
        
        # ML confidence factor for position sizing (0.5 to 1.5)
        # 50% confidence = 0.5x size, 75% = 1.0x, 100% = 1.5x
        ml_size_factor = 0.5 + (ml_confidence * 1.0)  # 0.5 at 0%, 1.5 at 100%
        
        # Direction confidence also affects sizing
        direction_size_factor = 0.7 + (direction_confidence * 0.6)  # 0.7 at 50%, 1.3 at 100%
        
        # Combined AI confidence for sizing
        ai_confidence_factor = ml_size_factor * direction_size_factor * ml_htf_alignment
        
        logger.info(f"   🧠 AI Confidence Factors:")
        logger.info(f"      ML: {ml_confidence:.1%} → size factor {ml_size_factor:.2f}")
        logger.info(f"      Direction: {direction_confidence:.1%} → size factor {direction_size_factor:.2f}")
        logger.info(f"      ML/HTF alignment: {ml_htf_alignment:.2f}")
        logger.info(f"      Combined AI factor: {ai_confidence_factor:.2f}")
        
        logger.info(f"   🎯 {setup_type} TRADE (strength: {setup_strength:.1f})")
        logger.info(f"      Direction: {direction}")
        logger.info(f"      D1: {d1_trend:.2f}, H4: {h4_trend:.2f}, H1: {h1_trend:.2f}")
        logger.info(f"      Target: {config['tp_atr_mult']:.1f}x ATR (AI-driven from market structure)")
        logger.info(f"      Size mult: {config['position_size_mult']:.1f}x")
        
        # FTMO checks
        if hasattr(context, 'ftmo_violated') and context.ftmo_violated:
            logger.info(f"   ❌ FTMO violated")
            return {'should_enter': False, 'reason': 'FTMO rules violated'}
        
        # ═══════════════════════════════════════════════════════════
        # PORTFOLIO HEALTH CHECK - AI-Driven Entry Gate
        # 
        # Before adding new risk, check:
        # 1. Are existing positions showing weakness? (high vol_div)
        # 2. Is portfolio already in significant drawdown?
        # 3. Are correlated positions all losing?
        # 
        # This prevents adding fuel to the fire when portfolio is stressed
        # ═══════════════════════════════════════════════════════════
        
        # Get portfolio metrics
        daily_pnl = getattr(context, 'daily_pnl', 0.0)
        total_drawdown = getattr(context, 'total_drawdown', 0.0)
        max_daily_loss = getattr(context, 'max_daily_loss', 10000.0)
        max_total_drawdown = getattr(context, 'max_total_drawdown', 20000.0)
        
        # Calculate portfolio stress level (0 to 1)
        daily_stress = abs(min(0, daily_pnl)) / max_daily_loss if max_daily_loss > 0 else 0
        total_stress = total_drawdown / max_total_drawdown if max_total_drawdown > 0 else 0
        portfolio_stress = daily_stress * 0.6 + total_stress * 0.4
        
        # Get H4 volume divergence for this symbol (weakness indicator)
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        logger.info(f"   📊 H4 Volume Divergence: {h4_vol_div:.2f} (0=good, 1=bad)")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PORTFOLIO HEALTH GATE - NO HARDCODED THRESHOLDS
        # 
        # Calculate a risk score that combines portfolio stress with
        # signal quality. Block entry when risk score exceeds confidence.
        # ═══════════════════════════════════════════════════════════
        
        # Risk score: Higher = more dangerous to enter
        # Combines portfolio stress with signal weakness
        entry_risk_score = (
            portfolio_stress * 0.50 +           # Portfolio stress contribution
            h4_vol_div * 0.30 +                 # Volume divergence (weak signal)
            (1.0 - ml_confidence) * 0.20        # ML uncertainty
        )
        
        # Confidence score: Higher = safer to enter
        entry_confidence_score = (
            ml_confidence * 0.50 +              # ML confidence
            (1.0 - h4_vol_div) * 0.30 +         # Volume confirms move
            (1.0 - portfolio_stress) * 0.20     # Portfolio health
        )
        
        # Block entry if risk exceeds confidence
        if entry_risk_score > entry_confidence_score:
            logger.warning(f"   🚫 PORTFOLIO HEALTH CHECK FAILED:")
            logger.warning(f"      Entry Risk Score: {entry_risk_score:.3f}")
            logger.warning(f"      Entry Confidence Score: {entry_confidence_score:.3f}")
            logger.warning(f"      Components: stress={portfolio_stress:.1%}, vol_div={h4_vol_div:.1%}, ML={ml_confidence:.1%}")
            logger.warning(f"      → Blocking new entry - risk exceeds confidence")
            return {'should_enter': False, 'reason': f'Risk ({entry_risk_score:.2f}) > Confidence ({entry_confidence_score:.2f})'}
        
        if portfolio_stress > 0.10:
            logger.info(f"   📊 Portfolio health: risk={entry_risk_score:.3f}, conf={entry_confidence_score:.3f}")
        
        # ═══════════════════════════════════════════════════════════
        # SNIPER ENTRY REQUIREMENTS - Hedge Fund Level
        # 
        # Only take trades with STRONG confluence:
        # 1. D1 must support the direction (primary thesis)
        # 2. H4 must confirm (secondary confirmation)
        # 3. ML must agree with direction
        # 4. Volume divergence must be low (move is real)
        # 
        # This prevents flip-flopping and ensures quality entries
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SNIPER ENTRY SCORING - NO HARDCODED THRESHOLDS
        # 
        # Calculate continuous support scores instead of binary checks
        # Entry approved when total sniper score exceeds rejection score
        # ═══════════════════════════════════════════════════════════
        
        # Calculate support scores (0-1) for each timeframe
        def tf_support_score(trend, direction):
            if direction == 'BUY':
                return trend  # Higher trend = more support for BUY
            else:
                return 1.0 - trend  # Lower trend = more support for SELL
        
        d1_score = tf_support_score(d1_trend, direction)
        h4_score = tf_support_score(h4_trend, direction)
        h1_score = tf_support_score(h1_trend, direction)
        m30_score = tf_support_score(m30_trend, direction)
        m15_score = tf_support_score(m15_trend, direction)
        
        # ═══════════════════════════════════════════════════════════
        # SETUP-APPROPRIATE TIMEFRAME SCORING
        # 
        # Each setup type uses DIFFERENT timeframes for thesis quality:
        # - SCALP: M15, M30, H1 (LTF-driven)
        # - DAY: H1, H4 (MTF-driven)  
        # - SWING: H4, D1 (HTF-driven)
        # ═══════════════════════════════════════════════════════════
        
        if setup_type == 'SCALP':
            # SCALP uses LTF: M15 (40%), M30 (35%), H1 (25%)
            tf_alignment_score = (m15_score * 0.40) + (m30_score * 0.35) + (h1_score * 0.25)
            tf_size_factor = 0.3 + (h1_score * 1.2)  # H1 is highest TF for SCALP
            primary_tfs = [m15_score, m30_score, h1_score]
            tf_names = ['M15', 'M30', 'H1']
        elif setup_type == 'DAY':
            # DAY uses MTF: H1 (45%), H4 (40%), M30 (15%)
            tf_alignment_score = (h1_score * 0.45) + (h4_score * 0.40) + (m30_score * 0.15)
            tf_size_factor = 0.3 + (h4_score * 1.2)  # H4 is highest TF for DAY
            primary_tfs = [h1_score, h4_score, m30_score]
            tf_names = ['H1', 'H4', 'M30']
        else:  # SWING
            # SWING uses HTF: D1 (50%), H4 (35%), H1 (15%)
            tf_alignment_score = (d1_score * 0.50) + (h4_score * 0.35) + (h1_score * 0.15)
            tf_size_factor = 0.3 + (d1_score * 1.2)  # D1 is highest TF for SWING
            primary_tfs = [d1_score, h4_score, h1_score]
            tf_names = ['D1', 'H4', 'H1']
        
        # Log TF analysis for this setup type
        logger.info(f"   📊 {setup_type} TF Alignment: {tf_alignment_score:.2f}")
        logger.info(f"      {tf_names[0]}={primary_tfs[0]:.2f}, {tf_names[1]}={primary_tfs[1]:.2f}, {tf_names[2]}={primary_tfs[2]:.2f}")
        
        # ML agreement score
        ml_agrees = (direction == 'BUY' and ml_direction == 'BUY') or (direction == 'SELL' and ml_direction == 'SELL')
        ml_agreement_score = ml_confidence if ml_agrees else (1.0 - ml_confidence) * 0.5
        
        # Volume confirmation score (low divergence = good)
        # IMPORTANT: If h4_vol_div is not set (default 0.0), volume_score should be 1.0
        # If h4_vol_div is 1.0 (high divergence), volume_score is 0.0
        volume_score = 1.0 - h4_vol_div
        logger.info(f"   📊 Volume Score: {volume_score:.2f} (h4_vol_div={h4_vol_div:.2f})")
        
        # News safety score
        news_imminent = getattr(context, 'news_imminent', False)
        news_minutes = getattr(context, 'news_minutes_until', 999)
        news_score = 0.0 if (news_imminent and news_minutes <= 15) else (0.5 if (news_imminent and news_minutes <= 30) else 1.0)
        
        # ═══════════════════════════════════════════════════════════
        # SNIPER ENTRY SCORE - Weighted combination of all factors
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN ENTRY QUALITY SCORE - AFFECTS SIZING, NOT BLOCKING
        # 
        # Calculate comprehensive entry quality score from all factors.
        # This score determines position size, NOT whether to enter.
        # Low quality = small position, high quality = full position.
        # ═══════════════════════════════════════════════════════════
        
        entry_quality_score = (
            tf_alignment_score * 0.35 +     # Setup-appropriate TF alignment
            ml_agreement_score * 0.30 +      # ML confidence
            volume_score * 0.20 +            # Volume confirms move
            news_score * 0.15                # News safety
        )
        
        # Quality-based size factor (0.3 to 1.5)
        # Score 0.3 = 0.3x size, Score 0.7 = 1.5x size
        quality_size_factor = 0.3 + (entry_quality_score * 1.7)
        
        # ═══════════════════════════════════════════════════════════
        # THESIS QUALITY GATE - Prevent weak trades from opening
        # 
        # Uses SETUP-APPROPRIATE timeframes:
        # - SCALP: M15, M30, H1 must support
        # - DAY: H1, H4 must support
        # - SWING: H4, D1 must support
        # ═══════════════════════════════════════════════════════════
        
        # Count TF support using setup-appropriate timeframes (>0.52 = supports)
        tf_supports = sum([tf > 0.52 for tf in primary_tfs])
        tf_opposes = sum([tf < 0.48 for tf in primary_tfs])
        
        # Calculate entry thesis quality using setup-appropriate TF alignment
        entry_thesis_quality = tf_alignment_score * (1.0 if ml_agrees else 0.7)
        
        # Minimum thesis quality required
        # SCALP needs lower thesis (ML-driven), SWING needs higher (HTF-driven)
        min_thesis = 0.40 if setup_type == 'SCALP' else (0.45 if setup_type == 'DAY' else 0.50)
        
        # Block entry if thesis is too weak
        if entry_thesis_quality < min_thesis:
            # Exception: Allow if ML is very confident (>72%) and at least 1 TF supports
            if ml_confidence > 0.72 and tf_supports >= 1:
                logger.info(f"   ⚠️ Weak thesis ({entry_thesis_quality:.2f}) but ML confident ({ml_confidence:.0%}) with {tf_supports}/3 TF support")
            else:
                logger.warning(f"   🚫 THESIS QUALITY TOO WEAK:")
                logger.warning(f"      Entry thesis: {entry_thesis_quality:.2f} < {min_thesis:.2f} minimum for {setup_type}")
                logger.warning(f"      {setup_type} TFs: {tf_supports}/3 support, {tf_opposes}/3 oppose")
                logger.warning(f"      {tf_names[0]}={primary_tfs[0]:.2f}, {tf_names[1]}={primary_tfs[1]:.2f}, {tf_names[2]}={primary_tfs[2]:.2f}")
                logger.warning(f"      ML: {ml_confidence:.0%} {'agrees' if ml_agrees else 'disagrees'}")
                return {'should_enter': False, 'reason': f'Weak thesis ({entry_thesis_quality:.2f} < {min_thesis:.2f} for {setup_type})'}
        
        # Combined final size factor from all AI analysis
        final_ai_size_factor = (
            ai_confidence_factor *      # ML + direction confidence
            tf_size_factor *            # Setup-appropriate TF support
            quality_size_factor *       # Overall entry quality
            (1.0 - portfolio_stress)    # Portfolio health
        )
        
        # Clamp to reasonable range (0.1 to 2.0)
        final_ai_size_factor = max(0.1, min(2.0, final_ai_size_factor))
        
        logger.info(f"   🎯 AI ENTRY ANALYSIS:")
        logger.info(f"      Entry Quality Score: {entry_quality_score:.3f}")
        logger.info(f"      Entry Thesis Quality: {entry_thesis_quality:.2f} (min: {min_thesis:.2f} for {setup_type})")
        logger.info(f"      {setup_type} TF Alignment: {tf_alignment_score:.2f} ({tf_names[0]}={primary_tfs[0]:.2f}, {tf_names[1]}={primary_tfs[1]:.2f}, {tf_names[2]}={primary_tfs[2]:.2f})")
        logger.info(f"      {setup_type} TF Support: {tf_supports}/3 support, {tf_opposes}/3 oppose")
        logger.info(f"      ML Agreement: {ml_agreement_score:.2f} | Volume: {volume_score:.2f} | News: {news_score:.2f}")
        logger.info(f"      Final AI Size Factor: {final_ai_size_factor:.2f}x")
        
        logger.info(f"   ✅ {setup_type} ENTRY APPROVED (thesis: {entry_thesis_quality:.2f})")
        logger.info(f"   📊 Position size will be scaled by {final_ai_size_factor:.2f}x based on AI analysis")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Direction already determined by setup classification
        # ═══════════════════════════════════════════════════════════
        
        # direction already set from _classify_setup
        is_buy = (direction == 'BUY')
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Calculate stop loss and take profit
        # DYNAMIC R:R based on market conditions and ML confidence
        # ═══════════════════════════════════════════════════════════
        
        current_price = context.current_price
        symbol = context.symbol.upper() if hasattr(context, 'symbol') else ''
        
        # Get ATR with multiple fallbacks
        # CRITICAL: h1_volatility and h4_volatility are already in PRICE UNITS (like ATR)
        # Do NOT multiply by current_price!
        atr = getattr(context, 'atr', 0)
        if atr <= 0:
            atr = getattr(context, 'mt5_atr_20', 0)
        if atr <= 0:
            # h1_volatility is already in price units (ATR-like), NOT a percentage
            atr = getattr(context, 'h1_volatility', 0)
        if atr <= 0:
            # Last resort: symbol-specific ATR fallbacks based on typical volatility
            if 'XAU' in symbol or 'GOLD' in symbol:
                atr = current_price * 0.008  # Gold: ~$34 for $4250
            elif 'US30' in symbol or 'DOW' in symbol:
                atr = current_price * 0.005  # Dow: ~200 points
            elif 'US100' in symbol or 'NAS' in symbol:
                atr = current_price * 0.006  # Nasdaq: ~150 points
            elif 'OIL' in symbol:
                atr = current_price * 0.015  # Oil: ~$0.90
            elif 'JPY' in symbol:
                atr = current_price * 0.004  # JPY pairs: ~60 pips
            else:
                atr = current_price * 0.005  # Default: 0.5%
        logger.info(f"   ATR: {atr:.5f} (for {symbol})")
        
        # Get spread to account for entry cost
        spread = context.spread if hasattr(context, 'spread') else (current_price * 0.0001)
        
        # Get market regime
        regime = context.get_market_regime() if hasattr(context, 'get_market_regime') else "UNKNOWN"
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN DYNAMIC STOP LOSS
        # Based on: Market structure, multi-TF volatility, ML confidence, regime
        # NO hardcoded symbol-specific rules - pure market analysis
        # ═══════════════════════════════════════════════════════════
        
        # Get multi-timeframe volatility for smarter stop placement
        h1_volatility = getattr(context, 'h1_volatility', atr)
        h4_volatility = getattr(context, 'h4_volatility', atr)
        
        # Use the HIGHER timeframe volatility for stop - avoids noise
        # H4 volatility captures the "real" move size, not M1 noise
        effective_volatility = max(atr, h1_volatility, h4_volatility)
        
        # AI-driven stop multiplier based on market conditions
        # Higher ML confidence = tighter stop (more conviction)
        # Lower ML confidence = wider stop (less certain)
        confidence_factor = 1.0 - ((ml_confidence - 0.5) * 0.5)  # 0.75 at 100%, 1.25 at 50%
        
        # Regime factor
        if regime == "TRENDING" or regime == "TRENDING_UP" or regime == "TRENDING_DOWN":
            regime_factor = 0.8  # Tighter in clear trends
        elif regime == "RANGING":
            regime_factor = 1.2  # Wider in ranges (more noise)
        else:  # VOLATILE
            regime_factor = 1.5  # Widest in volatile (protect capital)
        
        # Market score factor - higher score = more conviction = tighter stop
        score_factor = 1.0 - ((market_score - 50) / 100 * 0.3)  # 0.85 at 100, 1.15 at 50
        
        # ═══════════════════════════════════════════════════════════
        # SETUP-SPECIFIC STOP/TARGET FROM CONFIG
        # Uses ATR multipliers defined per setup type
        # SCALP: Tight stops (0.8x ATR), quick targets (1.2x ATR)
        # DAY: Medium stops (1.5x ATR), medium targets (2.5x ATR)
        # SWING: Wide stops (2.5x ATR), big targets (5x ATR) - room to breathe
        # ═══════════════════════════════════════════════════════════
        
        setup_stop_mult = config['stop_atr_mult']
        setup_target_mult = config['tp_atr_mult']
        
        # AI adjustments to base multipliers
        # Higher ML confidence = can tighten slightly (more conviction)
        # Lower ML confidence = widen slightly (less certain)
        confidence_adj = 1.0 - ((ml_confidence - 0.55) * 0.3)  # 0.85 at 70%, 1.0 at 55%
        
        # Regime adjustments
        if regime == "VOLATILE":
            regime_adj = 1.3  # Widen in volatile markets
        elif regime == "RANGING":
            regime_adj = 1.1  # Slightly wider in ranges
        else:
            regime_adj = 1.0  # Normal in trends
        
        # Combined AI-driven multiplier
        ai_multiplier = setup_stop_mult * confidence_adj * regime_adj
        
        # Minimum stop distance based on setup type
        # These are FLOORS - stops should never be tighter than this
        # CRITICAL: Too tight = stopped out by noise, too wide = poor R:R
        min_stop_mult = {'SCALP': 1.0, 'DAY': 1.5, 'SWING': 2.0}[setup_type]
        min_stop_distance = effective_volatility * min_stop_mult
        
        # Calculate stop distance
        stop_distance = max(min_stop_distance, effective_volatility * ai_multiplier)
        
        stop_loss = current_price - stop_distance if is_buy else current_price + stop_distance
        
        logger.info(f"   📊 {setup_type} Stop Calc: ML={ml_confidence:.0%} Regime={regime}")
        logger.info(f"   📊 Factors: conf_adj={confidence_adj:.2f} regime_adj={regime_adj:.2f} base={setup_stop_mult:.1f}x ATR")
        logger.info(f"   📊 Effective Vol: {effective_volatility:.5f}")
        
        # ═══════════════════════════════════════════════════════════
        # TARGET CALCULATION - S/R BASED (HEDGE FUND GRADE)
        # 
        # Institutional approach:
        # 1. Find nearest S/R level in the direction of profit
        # 2. Set target AT or NEAR that level
        # 3. Use ATR as fallback if no S/R available
        # 4. Adjust based on setup type and market conditions
        # ═══════════════════════════════════════════════════════════
        
        # Get S/R distances (as % of price)
        h4_dist_support = getattr(context, 'h4_dist_to_support', 0)
        h4_dist_resistance = getattr(context, 'h4_dist_to_resistance', 0)
        d1_dist_support = getattr(context, 'd1_dist_to_support', 0)
        d1_dist_resistance = getattr(context, 'd1_dist_to_resistance', 0)
        
        # Select S/R based on setup type (stronger levels for longer holds)
        if setup_type == 'SCALP':
            dist_to_support = h4_dist_support
            dist_to_resistance = h4_dist_resistance
        else:  # DAY/SWING - use D1 S/R (stronger levels)
            dist_to_support = d1_dist_support if d1_dist_support > 0 else h4_dist_support
            dist_to_resistance = d1_dist_resistance if d1_dist_resistance > 0 else h4_dist_resistance
        
        # Calculate structure-based target
        # For LONG: Target is resistance level
        # For SHORT: Target is support level
        if is_buy:
            if dist_to_resistance > 0:
                # Target at resistance, minus small buffer (0.1% before level)
                structure_target_pct = max(0.1, dist_to_resistance - 0.1)
                structure_target_distance = (structure_target_pct / 100.0) * current_price
                target_method = "RESISTANCE"
            else:
                structure_target_distance = 0
                target_method = "ATR"
        else:
            if dist_to_support > 0:
                # Target at support, minus small buffer
                structure_target_pct = max(0.1, dist_to_support - 0.1)
                structure_target_distance = (structure_target_pct / 100.0) * current_price
                target_method = "SUPPORT"
            else:
                structure_target_distance = 0
                target_method = "ATR"
        
        # ATR-based target as fallback
        base_tp_mult = setup_target_mult
        strength_adj = 1.0 + (setup_strength - 1.0) * 0.1  # Up to +20% for strength 3.0
        ml_adj = 1.0 + max(0, (ml_confidence - 0.55) * 0.5)  # Up to +22% at 100% conf
        tp_multiplier = base_tp_mult * strength_adj * ml_adj
        atr_target_distance = effective_volatility * tp_multiplier
        
        # Use structure-based target if available and reasonable
        # Structure target should be at least 1 ATR away (avoid tiny targets)
        # and not more than 3x the ATR target (avoid unrealistic targets)
        min_target = effective_volatility * 1.0  # At least 1 ATR
        max_target = atr_target_distance * 3.0   # At most 3x ATR target
        
        if structure_target_distance > min_target and structure_target_distance < max_target:
            tp_distance = structure_target_distance
            logger.info(f"   🎯 Target: {target_method} @ {structure_target_pct:.2f}% ({tp_distance:.5f})")
        else:
            tp_distance = atr_target_distance
            target_method = "ATR"
            logger.info(f"   🎯 Target: ATR-based ({tp_multiplier:.1f}x ATR = {tp_distance:.5f})")
        
        take_profit = current_price + tp_distance if is_buy else current_price - tp_distance
        
        logger.info(f"   📍 S/R: support={dist_to_support:.2f}%, resistance={dist_to_resistance:.2f}%")
        
        # Calculate R:R for logging
        target_rr = tp_distance / stop_distance if stop_distance > 0 else 1.5
        
        # Calculate profit target as percentage
        profit_target_pct = tp_distance / current_price * 100
        
        logger.info(f"   📏 ATR: {atr:.5f} | Spread: {spread:.5f} | Regime: {regime}")
        logger.info(f"   🛑 Stop: {stop_distance:.5f} ({ai_multiplier:.2f}x ATR)")
        logger.info(f"   🎯 Target: {tp_distance:.5f} ({tp_multiplier:.1f}x ATR, {target_rr:.1f}:1 R:R, {profit_target_pct:.2f}%)")
        logger.info(f"      Adjustments: strength={strength_adj:.2f}x ml={ml_adj:.2f}x")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Position sizing DELEGATED to ElitePositionSizer
        # ═══════════════════════════════════════════════════════════
        # ElitePositionSizer in api.py handles ALL position sizing with:
        # - Portfolio correlation analysis
        # - CVaR tail risk sizing
        # - Full 138-feature context analysis
        # - FTMO strategy integration
        # - Dynamic risk budgeting
        #
        # We return placeholder lot_size=1.0, Elite Sizer will override
        # ═══════════════════════════════════════════════════════════
        
        tick_size = context.tick_size if hasattr(context, 'tick_size') else 0.01
        stop_distance_ticks = stop_distance / tick_size
        trade_quality = market_score / 100.0
        
        logger.info(f"   🎯 Trade Quality: {trade_quality:.2f} (from market score {market_score:.0f})")
        logger.info(f"   📊 Position sizing delegated to ElitePositionSizer")
        
        # Placeholder - ElitePositionSizer will calculate actual size
        lot_size = 1.0  # Will be overridden by Elite Sizer
        
        logger.info(f"")
        logger.info(f"   ✅ ENTRY APPROVED (AI-DRIVEN):")
        logger.info(f"   Setup Type: {setup_type} (strength: {setup_strength:.1f})")
        logger.info(f"   Direction: {direction}")
        logger.info(f"   ML Confidence: {ml_confidence:.1%}")
        logger.info(f"   Market Score: {market_score:.0f}/100")
        logger.info(f"   Trade Quality: {trade_quality:.2f}")
        logger.info(f"   Entry: {current_price:.5f}")
        logger.info(f"   Stop: {stop_loss:.5f} ({stop_distance_ticks:.0f} ticks)")
        logger.info(f"   Target: {take_profit:.5f} ({profit_target_pct:.2f}%)")
        logger.info(f"   → Position size will be calculated by ElitePositionSizer")
        
        # Apply position size multiplier based on setup type
        size_mult = config['position_size_mult']
        
        return {
            'should_enter': True,
            'direction': direction,
            'lot_size': lot_size,  # Placeholder - Elite Sizer will override
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trade_quality': trade_quality,
            'setup_type': setup_type,
            'setup_strength': setup_strength,
            'position_size_mult': size_mult * final_ai_size_factor,  # AI-driven size adjustment
            'ai_size_factor': final_ai_size_factor,  # Pass through for Elite Sizer
            'entry_quality_score': entry_quality_score,  # For logging/analysis
            'direction_confidence': direction_confidence,  # How confident in direction
            'stop_atr_mult': config['stop_atr_mult'],  # AI-driven stop distance
            'tp_atr_mult': config['tp_atr_mult'],      # AI-driven target distance
            'reason': f"{setup_type} setup: {direction} @ {ml_confidence:.0%} ML (quality: {entry_quality_score:.2f})"
        }
    
    # ═══════════════════════════════════════════════════════════
    # EXIT DECISION
    # ═══════════════════════════════════════════════════════════
    
    def should_exit_trade(
        self,
        context: EnhancedTradingContext,
        market_analysis: Dict,
        current_profit_pct: float
    ) -> Dict:
        """
        Decide if we should exit a trade
        
        DELEGATES to IntelligentPositionManager which uses EV Exit Manager
        This ensures ONE exit system, not multiple conflicting ones
        
        Returns:
            {
                'should_exit': bool,
                'reason': str,
                'exit_score': float
            }
        """
        
        # Import here to avoid circular dependency
        try:
            from src.ai.intelligent_position_manager import IntelligentPositionManager
        except ImportError:
            from .intelligent_position_manager import IntelligentPositionManager
        
        # Use the shared position manager instance to preserve peak tracking
        # DO NOT create a new instance - that resets position_peaks!
        if not hasattr(self, '_position_manager') or self._position_manager is None:
            self._position_manager = IntelligentPositionManager()
            logger.info("🤖 Created shared position manager for unified system")
        
        # Call analyze_position which uses EV Exit Manager
        decision = self._position_manager.analyze_position(context=context)
        
        # Convert to unified format - MUST pass through modify_stop for stop loss management!
        should_exit = (decision['action'] == 'CLOSE')
        
        return {
            'should_exit': should_exit,
            'reason': decision.get('reason', 'No action'),
            'exit_score': decision.get('confidence', 0.0),
            'action': decision.get('action', 'HOLD'),
            'reduce_lots': decision.get('reduce_lots', 0.0),
            'modify_stop': decision.get('modify_stop', False),
            'recommended_stop': decision.get('recommended_stop', 0),
            'dynamic_stop': decision.get('dynamic_stop', {})
        }
    
    # ═══════════════════════════════════════════════════════════
    # POSITION MANAGEMENT (PYRAMIDING & DCA)
    # ═══════════════════════════════════════════════════════════
    
    def should_add_to_position(
        self,
        context: EnhancedTradingContext,
        market_analysis: Dict,
        current_profit_pct: float,
        current_volume: float
    ) -> Dict:
        """
        Decide if should add to position (pyramid winner or DCA loser)
        
        Returns:
            {
                'should_add': bool,
                'add_lots': float,
                'type': 'PYRAMID' or 'DCA',
                'reason': str
            }
        """
        from .position_state_tracker import get_position_tracker
        
        tracker = get_position_tracker()
        symbol = getattr(context, 'symbol', 'UNKNOWN')
        position = tracker.get_position(symbol)
        
        if not position:
            return {'should_add': False, 'reason': 'Position not tracked'}
        
        # Determine if winning or losing
        is_winning = current_profit_pct > 0.3
        is_losing = current_profit_pct < -0.3
        
        if is_winning:
            return self._check_pyramid(context, market_analysis, position, current_profit_pct)
        elif is_losing:
            return self._check_dca(context, market_analysis, position, current_profit_pct)
        else:
            return {'should_add': False, 'reason': 'Position too small to add'}
    
    def _check_pyramid(self, context, market_analysis, position, current_profit_pct) -> Dict:
        """Check if should add to winning position"""
        from .position_state_tracker import get_position_tracker
        
        tracker = get_position_tracker()
        symbol = position['symbol']
        account_balance = getattr(context, 'account_balance', 100000)
        
        # Check if can add
        can_add, reason = tracker.can_add_to_winner(symbol, account_balance)
        if not can_add:
            return {'should_add': False, 'reason': reason}
        
        # Calculate AI score for adding
        ml_confidence = getattr(context, 'ml_confidence', 50) / 100.0
        market_score = market_analysis.get('total_score', 50)
        
        # Check H1/H4/D1 alignment
        is_buy = (position['direction'] == 'BUY')
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        if is_buy:
            alignment_score = (h1_trend + h4_trend + d1_trend) / 3.0
        else:
            alignment_score = (3.0 - h1_trend - h4_trend - d1_trend) / 3.0
        
        # Check distance to target
        target_price = position['target_price']
        current_price = getattr(context, 'current_price', 0)
        entry_price = position['avg_entry']
        
        if target_price > 0 and current_price > 0:
            total_distance = abs(target_price - entry_price)
            remaining_distance = abs(target_price - current_price)
            progress_to_target = 1.0 - (remaining_distance / total_distance) if total_distance > 0 else 1.0
        else:
            progress_to_target = 0.5
        
        # AI SCORE for pyramiding
        pyramid_score = (
            (ml_confidence * 100 * 0.3) +
            (market_score * 0.3) +
            (alignment_score * 100 * 0.2) +
            ((1.0 - progress_to_target) * 100 * 0.2)  # More room = better
        )
        
        logger.info(f"")
        logger.info(f"📈 PYRAMID CHECK:")
        logger.info(f"   ML Confidence: {ml_confidence*100:.1f}%")
        logger.info(f"   Market Score: {market_score:.0f}")
        logger.info(f"   Alignment: {alignment_score*100:.0f}%")
        logger.info(f"   Progress to Target: {progress_to_target*100:.0f}%")
        logger.info(f"   → Pyramid Score: {pyramid_score:.0f}/100")
        
        # Decision threshold: 70+
        if pyramid_score >= 70:
            add_lots = position['initial_lots'] * 0.4  # 40% of initial
            return {
                'should_add': True,
                'add_lots': add_lots,
                'type': 'PYRAMID',
                'reason': f'Pyramid score {pyramid_score:.0f}/100 - Adding to winner'
            }
        
        return {'should_add': False, 'reason': f'Pyramid score {pyramid_score:.0f} < 70'}
    
    def _check_dca(self, context, market_analysis, position, current_profit_pct) -> Dict:
        """Check if should add to losing position (DCA)"""
        from .position_state_tracker import get_position_tracker
        
        tracker = get_position_tracker()
        symbol = position['symbol']
        
        # Check if can DCA
        can_dca, reason = tracker.can_dca(symbol)
        if not can_dca:
            return {'should_add': False, 'reason': reason}
        
        # NOTE: DCA thresholds are checked in EV Exit Manager using % of RISK
        # The EV Exit Manager will only return DCA if:
        # - Loss is between -30% and -80% of RISK (not account)
        # - DCA score > 75%
        # We defer to EV Exit Manager for the actual DCA decision
        
        # Calculate AI score for DCA
        ml_confidence = getattr(context, 'ml_confidence', 50) / 100.0
        market_score = market_analysis.get('total_score', 50)
        
        # Check H1/H4/D1 alignment
        is_buy = (position['direction'] == 'BUY')
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        if is_buy:
            alignment_score = (h1_trend + h4_trend + d1_trend) / 3.0
        else:
            alignment_score = (3.0 - h1_trend - h4_trend - d1_trend) / 3.0
        
        # Calculate recovery probability using same formula as EV Exit Manager
        # recovery_prob = trend_alignment * 0.35 + ml_factor * 0.30 + structure * 0.20 + volume * 0.15
        ml_agrees = (context.ml_direction == 'BUY' and is_buy) or (context.ml_direction == 'SELL' and not is_buy)
        ml_factor = ml_confidence if ml_agrees else (1.0 - ml_confidence)
        volume_factor = min(1.0, getattr(context, 'volume_ratio', 1.0) / 1.5)
        structure_support = 0.5  # Default
        
        recovery_prob = (
            alignment_score * 0.35 +
            ml_factor * 0.30 +
            structure_support * 0.20 +
            volume_factor * 0.15
        )
        
        # AI SCORE for DCA
        dca_score = (
            (recovery_prob * 100 * 0.4) +
            (ml_confidence * 100 * 0.3) +
            (market_score * 0.3)
        )
        
        logger.info(f"")
        logger.info(f"📉 DCA CHECK:")
        logger.info(f"   Loss: {current_profit_pct:.2f}%")
        logger.info(f"   ML Confidence: {ml_confidence*100:.1f}%")
        logger.info(f"   Market Score: {market_score:.0f}")
        logger.info(f"   Alignment: {alignment_score*100:.0f}%")
        logger.info(f"   Recovery Prob: {recovery_prob*100:.0f}%")
        logger.info(f"   → DCA Score: {dca_score:.0f}/100")
        
        # Decision threshold: 75+ (higher than pyramid, more conservative)
        if dca_score >= 75:
            add_lots = position['initial_lots'] * 0.3  # 30% of initial
            return {
                'should_add': True,
                'add_lots': add_lots,
                'type': 'DCA',
                'reason': f'DCA score {dca_score:.0f}/100 - AI confident in recovery'
            }
        
        return {'should_add': False, 'reason': f'DCA score {dca_score:.0f} < 75'}
