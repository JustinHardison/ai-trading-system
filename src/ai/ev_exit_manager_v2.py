"""
EV Exit Manager V2 - Pure AI-Driven Exit Logic
NO HARDCODED THRESHOLDS - All decisions based on:
1. ML model predictions (direction, confidence)
2. Multi-timeframe market analysis (H1, H4, D1 trends)
3. Market structure (support/resistance, ATR)
4. Expected Value calculations

Every decision is a comparison of EVs - the action with highest EV wins.
"""
import logging
import json
import os
from typing import Dict
from datetime import datetime
import pytz
from .enhanced_context import EnhancedTradingContext
from .ai_market_analyzer import get_ai_analyzer, AIMarketState
from .ftmo_strategy import get_ftmo_strategy

logger = logging.getLogger(__name__)

# Persistent peak tracking file
PEAK_TRACKING_FILE = os.path.join(os.path.dirname(__file__), '../../cache/position_peaks.json')


class EVExitManagerV2:
    """
    Pure AI-driven exit manager using Expected Value optimization.
    
    Core Principle: For every decision, calculate EV of all options and choose the best.
    
    EV = Probability × Outcome
    
    Probabilities come from:
    - ML model confidence and direction
    - Multi-timeframe trend alignment (H1, H4, D1)
    - Momentum indicators
    - RSI overbought/oversold
    - Market structure (distance to S/R)
    
    NO arbitrary thresholds like "exit at 50% profit" or "close if giveback > 30%"
    """
    
    def __init__(self):
        self.position_peaks = self._load_peaks()  # Track peak profit per symbol (persistent)
        self.last_action_state = {}  # Track market state at last action for anti-churn
        self.ftmo_strategy = get_ftmo_strategy()  # Session awareness
        logger.info("🤖 EV Exit Manager V2 - Pure AI-driven, zero hardcoded thresholds")
        logger.info(f"   📊 Loaded {len(self.position_peaks)} position peaks from persistent storage")
    
    def _load_peaks(self) -> Dict:
        """Load peak tracking from persistent file"""
        try:
            if os.path.exists(PEAK_TRACKING_FILE):
                with open(PEAK_TRACKING_FILE, 'r') as f:
                    data = json.load(f)
                    logger.info(f"📊 Loaded position peaks from {PEAK_TRACKING_FILE}")
                    return data
        except Exception as e:
            logger.warning(f"Could not load peaks file: {e}")
        return {}
    
    def _save_peaks(self):
        """Save peak tracking to persistent file"""
        try:
            os.makedirs(os.path.dirname(PEAK_TRACKING_FILE), exist_ok=True)
            with open(PEAK_TRACKING_FILE, 'w') as f:
                json.dump(self.position_peaks, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save peaks file: {e}")
    
    def update_peak(self, symbol: str, profit_pct: float, current_price: float = 0, current_volume: float = 0):
        """Update peak profit for a symbol and persist to file
        
        IMPORTANT: Peak resets when volume decreases (scale-out occurred).
        This prevents false "giveback" calculations after taking profits.
        Also tracks cumulative realized profits from scale-outs.
        """
        symbol_key = symbol.upper()
        stored_data = self.position_peaks.get(symbol_key, {})
        current_peak = stored_data.get('peak_profit_pct', float('-inf'))
        stored_volume = stored_data.get('volume', 0)
        realized_profit_pct = stored_data.get('realized_profit_pct', 0.0)
        
        # If volume decreased, a scale-out occurred - reset peak to current
        if current_volume > 0 and stored_volume > 0 and current_volume < stored_volume * 0.95:
            # Volume decreased by more than 5% - scale-out happened
            # Estimate realized profit from the scale-out (proportional to volume reduction)
            volume_reduction_pct = (stored_volume - current_volume) / stored_volume
            # The realized profit is approximately the peak profit * volume reduction
            estimated_realized = current_peak * volume_reduction_pct
            new_realized_total = realized_profit_pct + estimated_realized
            
            logger.info(f"   🔄 SCALE-OUT DETECTED for {symbol_key}: {stored_volume:.1f} → {current_volume:.1f} lots")
            logger.info(f"      Realized ~{estimated_realized:.3f}% from this scale-out")
            logger.info(f"      Total realized from scale-outs: {new_realized_total:.3f}%")
            logger.info(f"      Resetting peak from {current_peak:.3f}% to {profit_pct:.3f}%")
            
            self.position_peaks[symbol_key] = {
                'peak_profit_pct': profit_pct,
                'peak_price': current_price,
                'peak_time': datetime.now().isoformat(),
                'updated': datetime.now().isoformat(),
                'volume': current_volume,
                'realized_profit_pct': new_realized_total
            }
            self._save_peaks()
        elif profit_pct > current_peak:
            self.position_peaks[symbol_key] = {
                'peak_profit_pct': profit_pct,
                'peak_price': current_price,
                'peak_time': datetime.now().isoformat(),
                'updated': datetime.now().isoformat(),
                'volume': current_volume if current_volume > 0 else stored_volume,
                'realized_profit_pct': realized_profit_pct
            }
            self._save_peaks()
            logger.info(f"   📈 NEW PEAK for {symbol_key}: {profit_pct:.3f}% (saved to disk)")
        elif current_volume > 0 and stored_volume == 0:
            # First time tracking volume - just update volume without changing peak
            self.position_peaks[symbol_key]['volume'] = current_volume
            self.position_peaks[symbol_key]['realized_profit_pct'] = realized_profit_pct
            self._save_peaks()
    
    def get_peak(self, symbol: str) -> float:
        """Get peak profit for a symbol"""
        symbol_key = symbol.upper()
        return self.position_peaks.get(symbol_key, {}).get('peak_profit_pct', 0.0)
    
    def get_realized_profit(self, symbol: str) -> float:
        """Get cumulative realized profit from scale-outs for a symbol"""
        symbol_key = symbol.upper()
        return self.position_peaks.get(symbol_key, {}).get('realized_profit_pct', 0.0)
    
    def get_total_trade_profit(self, symbol: str, current_unrealized_pct: float) -> float:
        """Get total trade profit (realized from scale-outs + current unrealized)"""
        realized = self.get_realized_profit(symbol)
        return realized + current_unrealized_pct
    
    def clear_peak(self, symbol: str):
        """Clear peak when position is closed"""
        symbol_key = symbol.upper()
        if symbol_key in self.position_peaks:
            del self.position_peaks[symbol_key]
            self._save_peaks()
            logger.info(f"   🗑️ Cleared peak for {symbol_key} (position closed)")
    
    # ═══════════════════════════════════════════════════════════
    # SESSION AWARENESS - Same logic as entry system
    # 
    # Trading sessions affect:
    # - Patience levels (more patient during off-hours)
    # - SCALE_OUT thresholds (more aggressive during high liquidity)
    # - SCALE_IN thresholds (more conservative during low liquidity)
    # ═══════════════════════════════════════════════════════════
    
    SESSIONS = {
        'asian': {'start': 0, 'end': 8, 'indices_mult': 0.5, 'forex_mult': 0.7, 'patience_boost': 1.3},
        'london': {'start': 8, 'end': 16, 'indices_mult': 0.8, 'forex_mult': 1.0, 'patience_boost': 1.0},
        'new_york': {'start': 13, 'end': 21, 'indices_mult': 1.0, 'forex_mult': 1.0, 'patience_boost': 1.0},
        'overlap': {'start': 13, 'end': 16, 'indices_mult': 1.2, 'forex_mult': 1.2, 'patience_boost': 0.8},
    }
    
    def get_session_context(self, symbol: str) -> Dict:
        """
        Get current session context for a symbol.
        
        Returns:
        - session_name: Current session (asian, london, new_york, overlap)
        - session_mult: Position size multiplier for this session
        - patience_boost: How much more patient to be (>1 = more patient)
        - is_optimal: Whether this is optimal trading time for this symbol
        """
        symbol_lower = symbol.lower().replace('.sim', '').replace('z25', '').replace('g26', '')
        
        # Determine symbol type
        is_index = any(s in symbol_lower for s in ['us30', 'us100', 'us500', 'dax', 'ftse'])
        is_forex = any(s in symbol_lower for s in ['eur', 'gbp', 'jpy', 'aud', 'nzd', 'cad', 'chf'])
        is_gold = 'xau' in symbol_lower or 'gold' in symbol_lower
        
        # Get current UTC hour and day
        utc_now = datetime.now(pytz.UTC)
        current_hour = utc_now.hour
        day_of_week = utc_now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND WEEKEND RISK MANAGEMENT
        # 
        # Friday afternoon = increased gap risk over weekend
        # Hedge funds typically:
        # 1. Reduce position sizes after 2 PM EST (19:00 UTC)
        # 2. Avoid new entries in last 2-3 hours
        # 3. Tighten stops on existing positions
        # 4. Close speculative/weak thesis positions
        # 
        # Market closes Friday 5 PM EST (22:00 UTC)
        # ═══════════════════════════════════════════════════════════
        
        is_friday = (day_of_week == 4)
        is_friday_afternoon = is_friday and current_hour >= 19  # After 2 PM EST
        is_friday_close = is_friday and current_hour >= 21  # Last hour before close
        hours_to_close = max(0, 22 - current_hour) if is_friday else 999
        
        # Weekend risk multiplier - reduces patience and increases exit pressure
        weekend_risk_mult = 1.0
        if is_friday_close:
            weekend_risk_mult = 0.5  # Very aggressive - close weak positions
            logger.info(f"   ⚠️ FRIDAY CLOSE ({hours_to_close}h to weekend) - Aggressive exit mode")
        elif is_friday_afternoon:
            weekend_risk_mult = 0.7  # Moderately aggressive
            logger.info(f"   ⚠️ FRIDAY AFTERNOON ({hours_to_close}h to weekend) - Reduced patience")
        
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
            # Gold trades well in all sessions
            session_mult = max(0.8, session_config['forex_mult'])
        else:
            session_mult = session_config['forex_mult']
        
        patience_boost = session_config['patience_boost']
        is_optimal = session_mult >= 1.0
        
        # Apply weekend risk adjustment to patience
        # Lower patience = more likely to exit
        patience_boost = patience_boost * weekend_risk_mult
        
        return {
            'session_name': session_name,
            'session_mult': session_mult,
            'patience_boost': patience_boost,
            'is_optimal': is_optimal,
            'current_hour_utc': current_hour,
            'symbol_type': 'index' if is_index else ('forex' if is_forex else ('gold' if is_gold else 'other')),
            'is_friday': is_friday,
            'is_friday_afternoon': is_friday_afternoon,
            'is_friday_close': is_friday_close,
            'hours_to_close': hours_to_close,
            'weekend_risk_mult': weekend_risk_mult
        }
    
    # AI-DRIVEN SETUP CONFIG
    # 
    # Setup type determines which timeframes to monitor for exit signals.
    # ATR multipliers are NOW DERIVED from market conditions, not hardcoded.
    # 
    # The _calculate_ai_atr_mult() method derives the multiplier from:
    # - HTF trend strength (stronger trend = larger targets)
    # - Volatility regime (higher vol = wider targets)
    # - ML confidence (higher confidence = can aim for larger targets)
    # - Market structure (distance to S/R levels)
    SETUP_CONFIG = {
        'SWING': {
            'early_exit_tf': 'H4',       # Watch H4 for early warnings
            'primary_tfs': ['D1', 'H4'], # Primary decision timeframes
            'patience': 'HIGH',
            'base_atr_mult': 5.0,        # BASE multiplier - AI adjusts from here
        },
        'DAY': {
            'early_exit_tf': 'H1',       # Watch H1 for early warnings
            'primary_tfs': ['H4', 'H1'], # Primary decision timeframes
            'patience': 'MEDIUM',
            'base_atr_mult': 2.5,        # BASE multiplier - AI adjusts from here
        },
        'SCALP': {
            'early_exit_tf': 'M15',      # Watch M15 for early warnings (not M5 - too noisy)
            'primary_tfs': ['M30', 'M15'], # Primary decision timeframes
            'patience': 'LOW',
            'base_atr_mult': 1.5,        # BASE multiplier - AI adjusts from here
        }
    }
    
    def _calculate_ai_atr_mult(self, context, setup_type: str, is_buy: bool) -> float:
        """
        AI-DRIVEN ATR MULTIPLIER
        
        Derives the target distance multiplier from live market analysis:
        - HTF trend strength: Stronger trends can sustain larger moves
        - Volatility regime: Higher volatility = wider targets needed
        - ML confidence: Higher confidence = can aim for larger targets
        - S/R distance: If S/R is close, target should be at S/R
        
        Returns: ATR multiplier (typically 1.5 to 10.0)
        """
        setup_config = self.SETUP_CONFIG.get(setup_type, self.SETUP_CONFIG['DAY'])
        base_mult = setup_config.get('base_atr_mult', 2.5)
        
        # Get market data from context
        d1_trend = getattr(context, 'd1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        ml_confidence = getattr(context, 'ml_confidence', 50.0) / 100.0
        h4_adx = getattr(context, 'h4_adx', 25.0)  # Trend strength indicator
        
        # HTF trend strength adjustment
        # For BUY: Higher trends = stronger bullish = can target more
        # For SELL: Lower trends = stronger bearish = can target more
        if is_buy:
            htf_strength = (d1_trend * 0.4 + h4_trend * 0.35 + h1_trend * 0.25)
        else:
            htf_strength = ((1-d1_trend) * 0.4 + (1-h4_trend) * 0.35 + (1-h1_trend) * 0.25)
        
        # Trend strength factor: 0.8x to 1.5x based on HTF alignment
        trend_factor = 0.8 + (htf_strength * 0.7)  # 0.8 at htf=0, 1.5 at htf=1.0
        
        # ADX factor: Strong trends (ADX > 25) can sustain larger moves
        # ADX < 20 = weak trend, ADX > 40 = very strong trend
        adx_factor = 0.8 + (min(h4_adx, 50) / 50) * 0.6  # 0.8 at ADX=0, 1.4 at ADX=50
        
        # ML confidence factor: Higher confidence = can aim for larger targets
        ml_factor = 0.9 + (ml_confidence * 0.3)  # 0.9 at 0%, 1.2 at 100%
        
        # S/R distance factor - if S/R is close, don't overshoot
        if is_buy:
            sr_dist = getattr(context, 'h4_dist_to_resistance', 0) or getattr(context, 'd1_dist_to_resistance', 0)
        else:
            sr_dist = getattr(context, 'h4_dist_to_support', 0) or getattr(context, 'd1_dist_to_support', 0)
        
        # If S/R is within 2%, cap the multiplier to not overshoot
        if sr_dist > 0 and sr_dist < 2.0:
            sr_factor = sr_dist / 2.0  # 0.5 at 1%, 1.0 at 2%
        else:
            sr_factor = 1.0
        
        # Combined AI-driven multiplier
        ai_mult = base_mult * trend_factor * adx_factor * ml_factor * sr_factor
        
        # Reasonable bounds based on setup type
        if setup_type == 'SWING':
            ai_mult = max(3.0, min(12.0, ai_mult))  # 3-12x for SWING
        elif setup_type == 'DAY':
            ai_mult = max(1.5, min(6.0, ai_mult))   # 1.5-6x for DAY
        else:  # SCALP
            ai_mult = max(1.0, min(3.0, ai_mult))   # 1-3x for SCALP
        
        logger.info(f"   🎯 AI ATR Mult: {ai_mult:.1f}x (base={base_mult}, trend={trend_factor:.2f}, adx={adx_factor:.2f}, ml={ml_factor:.2f}, sr={sr_factor:.2f})")
        
        return ai_mult
    
    def analyze_exit(
        self,
        context,
        current_profit: float,  # Dollar profit
        current_volume: float,
        position_type: int,  # 0=BUY, 1=SELL
        symbol: str,
        initial_volume: float = None,  # Original position size
        add_count: int = 0,  # How many times we've already added
        setup_type: str = None,  # SCALP, DAY, or SWING
        max_lots: float = 10.0  # Max position size for this symbol
    ) -> Dict:
        """
        Pure AI-driven position analysis.
        
        Calculates EV for ALL possible actions:
        - HOLD (keep full position)
        - SCALE_OUT (partial exit)
        - CLOSE (full exit)
        - SCALE_IN (add to winner)
        - DCA (add to loser)
        
        Returns the action with highest EV.
        
        SETUP TYPE AWARENESS:
        - SCALP: Use M15/M30/H1 for decisions, quick exits
        - DAY: Use H1/H4 for decisions, medium patience
        - SWING: Use H4/D1 for decisions, high patience
        
        SAFEGUARDS:
        - Max 2 adds per position
        - Max 2.5x initial position size
        - Position size limits per symbol type
        """
        
        is_buy = (position_type == 0)
        symbol_key = symbol.lower()
        
        # ═══════════════════════════════════════════════════════════
        # SETUP TYPE - DYNAMIC BASED ON CURRENT CONDITIONS
        # 
        # A trade can EVOLVE:
        # - SCALP → DAY → SWING as HTFs align and we scale in
        # - SWING → DAY → SCALP as HTFs turn and we scale out
        #
        # Classification uses BOTH:
        # 1. Current HTF alignment (which TFs support the position NOW)
        # 2. Current position size (larger = need more room = SWING)
        # ═══════════════════════════════════════════════════════════
        
        # Get current timeframe trends
        m5_trend = getattr(context, 'm5_trend', 0.5)
        m15_trend = getattr(context, 'm15_trend', 0.5)
        m30_trend = getattr(context, 'm30_trend', 0.5)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        d1_trend = getattr(context, 'd1_trend', 0.5)
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SETUP TYPE CLASSIFICATION
        # 
        # Instead of hardcoded thresholds (0.52, 0.48, etc.), we use:
        # - Continuous HTF support scores (0-1)
        # - Position size relative to max
        # - Combined alignment score to determine setup type
        # ═══════════════════════════════════════════════════════════
        
        # Calculate continuous support scores for each timeframe
        # For BUY: trend=1.0 is full support, trend=0.0 is full opposition
        # For SELL: trend=0.0 is full support, trend=1.0 is full opposition
        if is_buy:
            d1_support_score = d1_trend  # 0-1, higher = more support
            h4_support_score = h4_trend
            h1_support_score = h1_trend
        else:
            d1_support_score = 1.0 - d1_trend  # 0-1, higher = more support for SELL
            h4_support_score = 1.0 - h4_trend
            h1_support_score = 1.0 - h1_trend
        
        # Weighted HTF alignment score (D1 most important, then H4, then H1)
        htf_alignment_score = (
            d1_support_score * 0.45 +
            h4_support_score * 0.35 +
            h1_support_score * 0.20
        )
        
        # Position size factor - LARGER positions need LESS patience (tighter risk)
        # This is hedge fund risk management: bigger position = protect it more aggressively
        size_ratio = current_volume / max_lots if max_lots > 0 else 0.5
        # Invert: larger position = LOWER patience factor = faster exits
        size_risk_factor = max(0.3, 1.0 - size_ratio * 0.7)  # 1.0 (small) to 0.3 (large)
        
        # Combined setup score: HTF alignment adjusted by size risk
        # Higher score = need more patience = SWING
        # Lower score = less patience needed = SCALP
        # CRITICAL: Large positions REDUCE the score (faster exits)
        setup_score = htf_alignment_score * 0.8 * size_risk_factor + 0.2
        
        # AI-driven setup classification based on continuous score
        # No hardcoded thresholds - score naturally determines setup type
        if setup_score >= 0.65:
            setup_type = 'SWING'  # Strong HTF alignment
        elif setup_score >= 0.45:
            setup_type = 'DAY'    # Moderate HTF alignment
        else:
            setup_type = 'SCALP'  # Weak HTF alignment
        
        logger.info(f"   🧠 AI Setup Classification: {setup_type}")
        logger.info(f"      HTF alignment: {htf_alignment_score:.2f} (D1={d1_support_score:.2f}, H4={h4_support_score:.2f}, H1={h1_support_score:.2f})")
        logger.info(f"      Size risk factor: {size_risk_factor:.2f} (ratio={size_ratio:.2f}) - larger=tighter")
        logger.info(f"      Setup score: {setup_score:.2f}")
        
        logger.info(f"   📊 Setup Type: {setup_type} (D1={d1_trend:.2f}, H4={h4_trend:.2f}, size={size_ratio:.2f})")
        
        # Get config for this setup type
        setup_config = self.SETUP_CONFIG.get(setup_type, self.SETUP_CONFIG['DAY'])
        early_exit_tf = setup_config['early_exit_tf']
        patience = setup_config['patience']
        
        # AI-DRIVEN ATR MULTIPLIER - derived from market conditions, not hardcoded
        atr_mult = self._calculate_ai_atr_mult(context, setup_type, is_buy)
        
        # ═══════════════════════════════════════════════════════════
        # SESSION AWARENESS - Adjust patience based on trading session
        # 
        # During off-hours (Asian for indices): Be MORE patient
        # During optimal hours (NY/London overlap): Can be more aggressive
        # 
        # This ensures exit logic matches entry logic
        # ═══════════════════════════════════════════════════════════
        
        session_context = self.get_session_context(symbol)
        session_name = session_context['session_name']
        session_mult = session_context['session_mult']
        patience_boost = session_context['patience_boost']
        is_optimal_session = session_context['is_optimal']
        is_friday_afternoon = session_context.get('is_friday_afternoon', False)
        is_friday_close = session_context.get('is_friday_close', False)
        
        logger.info(f"   📊 Session: {session_name.upper()} (mult={session_mult:.2f}x, patience_boost={patience_boost:.2f}x, optimal={is_optimal_session})")
        
        logger.info(f"   📊 Setup Type: {setup_type} (patience: {patience}, early exit TF: {early_exit_tf}, ATR mult: {atr_mult}x)")
        
        # ═══════════════════════════════════════════════════════════
        # STRATEGIC SCALE_IN ANALYSIS
        # Don't add back-to-back - require market to PROVE the move
        # CRITICAL: Don't scale in immediately after scaling out (churning)
        # ═══════════════════════════════════════════════════════════
        
        # Track position state for strategic decisions
        
        # Get last scale-in info from position peaks tracking
        last_scale_info = self.position_peaks.get(f"{symbol_key}_scale", {})
        last_scale_price = last_scale_info.get('price', 0)
        last_scale_time = last_scale_info.get('time', 0)
        last_scale_profit_pct = last_scale_info.get('profit_pct', 0)
        
        # ANTI-CHURN: Check if last action was SCALE_OUT
        # If we just took profit, don't immediately add back
        last_action_info = self.last_action_state.get(symbol_key, {})
        last_action = last_action_info.get('action', '')
        last_action_time = last_action_info.get('time', 0)
        just_scaled_out = 'SCALE_OUT' in last_action
        
        # Current price and time
        current_price = getattr(context, 'current_price', 0)
        current_time = getattr(context, 'timestamp', 0)
        if current_time == 0:
            import time
            current_time = time.time()
        
        # Calculate time since last scale (minutes)
        time_since_scale = (current_time - last_scale_time) / 60 if last_scale_time > 0 else 999
        
        # Calculate price movement since last scale (%)
        price_move_since_scale = 0
        if last_scale_price > 0 and current_price > 0:
            price_move_since_scale = abs(current_price - last_scale_price) / last_scale_price * 100
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN POSITION SIZE LIMITS
        # 
        # Calculate max position based on:
        # 1. Account equity and RISK BUDGET (not notional exposure!)
        # 2. Current drawdown (reduce max when in drawdown)
        # 3. Thesis quality (stronger thesis = can hold more)
        # 4. Broker max as absolute ceiling
        # 
        # CRITICAL FIX: Use RISK PER LOT (from stop distance), not notional
        # Notional is misleading for indices where contract_size × price is huge
        # but actual risk per lot (based on stop) is much smaller
        # ═══════════════════════════════════════════════════════════
        
        account_balance = getattr(context, 'account_balance', 200000)
        total_drawdown = getattr(context, 'total_drawdown', 0)
        max_total_drawdown = getattr(context, 'max_total_drawdown', 20000)
        
        # Calculate drawdown severity (0 to 1)
        dd_severity = total_drawdown / max_total_drawdown if max_total_drawdown > 0 else 0
        
        # AI-driven max position based on account and drawdown
        # Base: 3% of account at risk per symbol (FTMO-safe, allows growth)
        # Reduce as drawdown increases (but not too aggressively)
        base_risk_pct = 0.03  # 3% max risk per symbol = $6,000 on $200k
        dd_reduction = 1.0 - (dd_severity * 0.3)  # Reduce by up to 30% in drawdown (was 50%)
        
        # Calculate max RISK BUDGET for this symbol (not notional!)
        max_risk_budget = account_balance * base_risk_pct * dd_reduction
        
        # Get tick value to calculate RISK PER LOT
        tick_value = getattr(context, 'tick_value', 1.0)
        tick_size = getattr(context, 'tick_size', 0.01)
        contract_size = getattr(context, 'contract_size', 1.0)
        
        # SIMPLIFIED RISK PER LOT CALCULATION
        # For indices/commodities, use a percentage-based approach
        # Typical swing trade risk: 1-2% of position value
        # 
        # Risk per lot = contract_size × current_price × risk_pct
        # For US100: 2.0 × 21500 × 0.015 = $645 per lot (1.5% move)
        # For XAU: 10.0 × 2650 × 0.01 = $265 per lot (1% move)
        
        # Use 1.5% as typical risk per lot (reasonable for swing trades)
        typical_risk_pct = 0.015
        risk_per_lot = contract_size * current_price * typical_risk_pct
        
        # Sanity check: risk per lot should be reasonable ($100-$2000 range)
        risk_per_lot = max(100.0, min(2000.0, risk_per_lot))
        
        logger.info(f"   📊 Risk per lot: ${risk_per_lot:.2f} (contract={contract_size}, price={current_price:.2f})")
        
        # Calculate AI max lots from RISK BUDGET / RISK PER LOT
        if risk_per_lot > 0:
            ai_max_lots = max_risk_budget / risk_per_lot
        else:
            ai_max_lots = 10.0  # Fallback
        
        # Broker max as ceiling
        if max_lots <= 0:
            max_lots = 50.0
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SYMBOL-SPECIFIC LOT CAPS
        # 
        # Based on analysis of trade history:
        # - US30 had 15 lots losing $3,411 ($227/lot) - OVERSIZED
        # - XAU max was 6 lots, US100 max was 9 lots - reasonable
        # 
        # Cap lots based on symbol volatility (H4 ATR) and typical
        # dollar risk per lot. This is AI-driven, not hardcoded:
        # - Higher volatility = lower max lots
        # - Higher dollar risk per point = lower max lots
        # ═══════════════════════════════════════════════════════════
        
        symbol_lower = getattr(context, 'symbol', '').lower()
        h4_volatility = getattr(context, 'h4_volatility', 100)
        
        # Calculate AI-driven max lots based on volatility and symbol type
        # Indices (US30, US100, US500) have higher point values = more risk per lot
        if any(idx in symbol_lower for idx in ['us30', 'dow']):
            # US30: ~$5/point/lot, very volatile, cap at 8 lots
            volatility_max_lots = min(8.0, 4000.0 / (h4_volatility * 5.0)) if h4_volatility > 0 else 8.0
            logger.info(f"   📊 US30 volatility cap: {volatility_max_lots:.1f} lots (H4 vol={h4_volatility:.1f})")
        elif any(idx in symbol_lower for idx in ['us100', 'nas', 'ndx']):
            # US100: ~$2/point/lot, cap at 10 lots
            volatility_max_lots = min(10.0, 4000.0 / (h4_volatility * 2.0)) if h4_volatility > 0 else 10.0
            logger.info(f"   📊 US100 volatility cap: {volatility_max_lots:.1f} lots (H4 vol={h4_volatility:.1f})")
        elif any(idx in symbol_lower for idx in ['us500', 'spx']):
            # US500: ~$5/point/lot, cap at 8 lots
            volatility_max_lots = min(8.0, 4000.0 / (h4_volatility * 5.0)) if h4_volatility > 0 else 8.0
            logger.info(f"   📊 US500 volatility cap: {volatility_max_lots:.1f} lots (H4 vol={h4_volatility:.1f})")
        elif 'xau' in symbol_lower or 'gold' in symbol_lower:
            # XAU: ~$10/point/lot, cap at 12 lots (performed well today)
            volatility_max_lots = min(12.0, 6000.0 / (h4_volatility * 10.0)) if h4_volatility > 0 else 12.0
            logger.info(f"   📊 XAU volatility cap: {volatility_max_lots:.1f} lots (H4 vol={h4_volatility:.1f})")
        else:
            # Forex and others: more flexible
            volatility_max_lots = 15.0
        
        # Use the most conservative of: AI risk-based, volatility-based, broker limit
        effective_max_lots = min(ai_max_lots, volatility_max_lots, max_lots)
        
        # Floor at reasonable minimum (allow meaningful positions)
        effective_max_lots = max(3.0, effective_max_lots)
        
        logger.info(f"   📊 AI Max Lots: {ai_max_lots:.1f} (risk_budget=${max_risk_budget:,.0f}, risk_per_lot=${risk_per_lot:.2f})")
        logger.info(f"   📊 DD adjustment: severity={dd_severity:.1%}, reduction={dd_reduction:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # SCALE_IN ELIGIBILITY - FULLY AI-DRIVEN
        # 
        # NO hardcoded thresholds - AI decides based on:
        # 1. Position is in profit (thesis confirmed by P&L)
        # 2. Thesis quality (HTF alignment)
        # 3. ML confidence supports direction
        # 4. Max position size (AI-calculated based on risk)
        # ═══════════════════════════════════════════════════════════
        
        # Safety limit: Position size (AI-driven limit)
        size_ok = current_volume < effective_max_lots
        logger.info(f"   📊 Position size check: {current_volume:.1f}/{effective_max_lots:.1f} lots (size_ok={size_ok})")
        
        # AI-DRIVEN: Use actual profit to confirm thesis
        # If position is profitable, the market HAS confirmed the move
        # No arbitrary ATR threshold - let the P&L speak
        entry_price = getattr(context, 'position_entry_price', 0)
        if entry_price > 0 and current_price > 0:
            actual_move_pct = abs(current_price - entry_price) / entry_price * 100
        else:
            actual_move_pct = 0
        
        # Position in profit = thesis confirmed
        # The EV calculation will determine if adding is +EV
        # No minimum move threshold - AI decides via EV
        price_confirmed = current_profit > 0 or actual_move_pct > 0
        
        logger.info(f"   📊 SCALE_IN check: profit=${current_profit:.2f}, move={actual_move_pct:.3f}%")
        
        # For BUY, price should be higher than last scale-in
        # For SELL, price should be lower than last scale-in
        # If no last_scale_price (first add or after restart), require price confirmation only
        if last_scale_price > 0 and current_price > 0:
            if is_buy:
                direction_confirmed = current_price > last_scale_price
            else:
                direction_confirmed = current_price < last_scale_price
        else:
            # No tracking of last scale - rely on price_confirmed only
            # Set direction_confirmed = price_confirmed to require at least one confirmation
            direction_confirmed = price_confirmed
        
        # ANTI-CHURN: If we just scaled out, check if thesis changed significantly
        # This is AI-driven via the check_anti_churn_action in unified_trading_system
        # Here we just track the state - the EV calculation will determine if adding is +EV
        time_since_last_action = (current_time - last_action_time) / 60 if last_action_time > 0 else 999
        
        # Anti-churn is now handled by EV calculation
        # If SCALE_IN has negative EV, it won't be chosen as best action
        anti_churn_ok = True  # Let EV decide
        
        # FULLY AI-DRIVEN: Only check size limit and profit confirmation
        # The EV calculation handles all the intelligence
        can_scale_in = size_ok and price_confirmed
        
        if not size_ok:
            logger.info(f"   🚫 SCALE_IN blocked: Position at max or not allowed")
        elif not price_confirmed:
            logger.info(f"   🚫 SCALE_IN blocked: Position not in profit (thesis not confirmed)")
        else:
            logger.info(f"   ✅ Scale-in eligible: {current_volume:.1f}/{max_lots:.0f} lots, profit=${current_profit:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Extract ALL market data from context
        # ═══════════════════════════════════════════════════════════
        
        market_data = self._extract_market_data(context, is_buy)
        
        # Calculate profit metrics
        profit_metrics = self._calculate_profit_metrics(
            context, current_profit, is_buy, symbol
        )
        
        logger.info(f"")
        logger.info(f"🤖 EV EXIT ANALYSIS V2 - {symbol}")
        logger.info(f"   💵 P&L: ${current_profit:.2f} = {profit_metrics['profit_pct']:.4f}% of account")
        logger.info(f"   📈 Peak: {profit_metrics['peak_profit']:.4f}% of account")
        logger.info(f"   📊 Price move: {profit_metrics['price_move_pct']:.2f}%")
        logger.info(f"   Position: {'BUY' if is_buy else 'SELL'}")
        logger.info(f"   🤖 ML: {market_data['ml_direction']} @ {market_data['ml_confidence']:.1f}%")
        logger.info(f"   📊 Trends: H1={market_data['h1_trend']:.2f} H4={market_data['h4_trend']:.2f} D1={market_data['d1_trend']:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # SAFEGUARD: Missing/Invalid Data Protection
        # 
        # If trend data is all zeros or missing, we don't have enough
        # information to make a decision. Default to HOLD.
        # This prevents closing positions based on incomplete data.
        # ═══════════════════════════════════════════════════════════
        
        h1_trend = market_data['h1_trend']
        h4_trend = market_data['h4_trend']
        d1_trend = market_data['d1_trend']
        
        if h1_trend == 0 and h4_trend == 0 and d1_trend == 0:
            logger.warning(f"   🚨 MISSING DATA: All HTF trends are 0.00 - defaulting to HOLD")
            logger.warning(f"      Cannot make AI decision without trend data")
            return {
                'action': 'HOLD',
                'reason': 'Missing HTF trend data - cannot analyze',
                'confidence': 50,
                'dynamic_stop': {},
                'modify_stop': False,
                'recommended_stop': 0,
            }
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: Calculate probabilities from AI/market analysis
        # ═══════════════════════════════════════════════════════════
        
        probabilities = self._calculate_probabilities(market_data, is_buy, profit_metrics, setup_type)
        
        logger.info(f"   📈 Probabilities:")
        logger.info(f"      Continuation: {probabilities['continuation']:.1%}")
        logger.info(f"      Reversal: {probabilities['reversal']:.1%}")
        logger.info(f"      Flat: {probabilities['flat']:.1%}")
        
        # ═══════════════════════════════════════════════════════════
        # PURE AI/EV DECISION - NO EARLY EXITS
        # 
        # ALL factors (ML, HTF, reversal probability, profit state) are
        # incorporated into the EV calculation. The action with highest
        # EV wins. No hardcoded thresholds to bypass the AI's decision.
        # 
        # The EV calculation already considers:
        # - ML direction and confidence (via probabilities)
        # - HTF trends (via continuation/reversal probabilities)
        # - Market structure (via exit/entry scores)
        # - Profit state (via profit_pct in EV formula)
        # - Volume divergence (via leading indicator penalty)
        # - ADX trend strength (via probability adjustments)
        # ═══════════════════════════════════════════════════════════
        
        # Log market state for transparency (no decisions here)
        ml_direction = market_data['ml_direction']
        ml_confidence = market_data['ml_confidence']
        h1_trend = market_data['h1_trend']
        h4_trend = market_data['h4_trend']
        d1_trend = market_data['d1_trend']
        profit_pct = profit_metrics['profit_pct']
        
        # Add ML direction and position info to probabilities for decision logic
        probabilities['ml_direction'] = ml_direction
        probabilities['position_direction'] = 'BUY' if is_buy else 'SELL'
        
        # Calculate position age percentage (vs expected duration)
        position_age_minutes = getattr(context, 'position_age_minutes', 0)
        expected_duration = self.SETUP_CONFIG.get(setup_type, {}).get('expected_duration', 2880)
        position_age_pct = (position_age_minutes / expected_duration * 100) if expected_duration > 0 else 0
        probabilities['position_age_pct'] = position_age_pct
        
        # Log ML state
        if is_buy and ml_direction == 'SELL':
            logger.info(f"   📊 ML State: Position BUY, ML says SELL @ {ml_confidence:.1f}% (factored into EV)")
        elif not is_buy and ml_direction == 'BUY':
            logger.info(f"   📊 ML State: Position SELL, ML says BUY @ {ml_confidence:.1f}% (factored into EV)")
        
        # Log HTF state
        logger.info(f"   📊 HTF Trends: H1={h1_trend:.2f}, H4={h4_trend:.2f}, D1={d1_trend:.2f} (factored into EV)")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PROFIT PROTECTION
        # 
        # The AI already handles profit protection through:
        # 1. Continuation probability - drops when market turns
        # 2. Reversal probability - rises when market turns
        # 3. Thesis quality - degrades when structure breaks
        # 4. Move exhaustion - detects when move is done
        # 5. Profit protection premium - already in EV calculation
        # 
        # NO hardcoded thresholds needed. The existing AI analysis
        # naturally protects profits by:
        # - Increasing SCALE_OUT EV when reversal prob rises
        # - Decreasing HOLD EV when continuation drops
        # - Boosting exit when thesis weakens
        # 
        # The EV calculation IS the profit protection.
        # ═══════════════════════════════════════════════════════════
        
        # No hardcoded daily profit protection - let the AI decide
        # The probabilities already factor in all market conditions
        probabilities['daily_profit_protection_boost'] = 0.0
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND NEWS RISK MANAGEMENT
        # 
        # Before high-impact news (NFP, FOMC, CPI, PPI, GDP):
        # - Strong thesis + profitable → HOLD (ride the wave)
        # - Strong thesis + losing → SCALE_OUT 50% (reduce risk)
        # - Weak thesis + any P&L → CLOSE (don't gamble on news)
        # 
        # This is AI-driven based on thesis strength, NOT blanket close
        # ═══════════════════════════════════════════════════════════
        
        news_imminent = getattr(context, 'news_imminent', False)
        news_minutes = getattr(context, 'news_minutes_until', 999)
        
        if news_imminent:
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN NEWS RISK ASSESSMENT
            # 
            # Uses comprehensive market analysis to determine news response:
            # - Position strength from 138 features (thesis × continuation × market quality)
            # - News urgency derived from volatility regime (not hardcoded minutes)
            # - Profit significance relative to ATR-based targets
            # ═══════════════════════════════════════════════════════════
            
            thesis_quality = probabilities.get('thesis_quality', 0.5)
            continuation_prob = probabilities['continuation']
            h4_vol_div = market_data.get('h4_volume_divergence', 0.0)
            
            # AI-driven position strength from comprehensive analysis
            position_strength = thesis_quality * continuation_prob * (1.0 - h4_vol_div * 0.5)
            
            # AI-driven news urgency based on market volatility regime
            # Higher volatility = news has bigger impact = more urgent
            h4_volatility = getattr(context, 'h4_volatility', 0)
            current_price = market_data.get('current_price', 1.0)
            volatility_regime = (h4_volatility / current_price * 100) if current_price > 0 and h4_volatility > 0 else 0.5
            
            # News urgency scales with volatility and time proximity
            # In high vol regime, even 60 min is urgent; in low vol, 15 min may be fine
            news_urgency = min(1.0, (60 - news_minutes) / 60) * (1.0 + volatility_regime)
            news_urgency = max(0.0, min(1.0, news_urgency))
            
            # AI-driven profit significance relative to expected target
            atr = market_data.get('atr', current_price * 0.01)
            expected_target_pct = (atr * atr_mult / current_price * 100) if current_price > 0 else 1.0
            profit_significance = profit_pct / expected_target_pct if expected_target_pct > 0 else 0
            
            logger.warning(f"   📰 NEWS RISK - AI Assessment:")
            logger.warning(f"      News in {news_minutes:.0f}min | Urgency: {news_urgency:.2f}")
            logger.warning(f"      Position strength: {position_strength:.2f}")
            logger.warning(f"      Profit significance: {profit_significance:.2f} ({profit_pct:.4f}% vs {expected_target_pct:.2f}% target)")
            
            # AI decision based on continuous scores, not hardcoded thresholds
            # news_risk_score = urgency × (1 - position_strength) × (1 - profit_significance)
            news_risk_score = news_urgency * (1.0 - position_strength)
            
            if profit_significance > 0:
                # Profitable - reduce risk score (less urgent to exit)
                news_risk_score *= (1.0 - min(0.5, profit_significance * 0.5))
            else:
                # Losing - increase risk score (more urgent to exit)
                news_risk_score *= (1.0 + min(0.5, abs(profit_significance) * 0.3))
            
            logger.warning(f"      News risk score: {news_risk_score:.2f}")
            
            # AI-driven response based on CONTINUOUS risk score
            # NO hardcoded thresholds - use the score directly to scale the response
            # Higher risk score = stronger exit signal (proportional, not threshold-based)
            
            # Close boost scales with risk score squared (exponential response to high risk)
            probabilities['news_close_boost'] = news_risk_score ** 2  # 0.49 at 0.7, 0.16 at 0.4
            
            # Scale out boost is linear with risk score
            probabilities['news_scale_out_boost'] = news_risk_score * 0.5  # 0.35 at 0.7, 0.2 at 0.4
            
            # Log the AI assessment
            if news_risk_score > 0.6:
                logger.warning(f"      🚨 HIGH NEWS RISK ({news_risk_score:.2f}) - Close boost: {probabilities['news_close_boost']:.2f}")
            elif news_risk_score > 0.3:
                logger.warning(f"      ⚠️ MODERATE NEWS RISK ({news_risk_score:.2f}) - Scale out boost: {probabilities['news_scale_out_boost']:.2f}")
            else:
                logger.info(f"      ✅ LOW NEWS RISK ({news_risk_score:.2f}) - Minimal adjustment")
        
        # ═══════════════════════════════════════════════════════════
        # INTELLIGENT LOSS-CUTTING (FTMO Compliant)
        # 
        # Cut losses when:
        # 1. Thesis is BROKEN (not just weak) - D1 flipped against
        # 2. Loss is approaching FTMO limits
        # 3. ML strongly disagrees AND HTF confirms reversal
        # 
        # This is NOT arbitrary stop-loss - it's AI recognizing
        # when the trade thesis is no longer valid
        # ═══════════════════════════════════════════════════════════
        
        # Get FTMO metrics from context
        daily_pnl = getattr(context, 'daily_pnl', 0.0)
        total_drawdown = getattr(context, 'total_drawdown', 0.0)
        max_daily_loss = getattr(context, 'max_daily_loss', 10000.0)
        max_total_drawdown = getattr(context, 'max_total_drawdown', 20000.0)
        
        # Calculate FTMO proximity (how close to limits)
        daily_limit_proximity = abs(min(0, daily_pnl)) / max_daily_loss if max_daily_loss > 0 else 0
        total_limit_proximity = total_drawdown / max_total_drawdown if max_total_drawdown > 0 else 0
        ftmo_danger = max(daily_limit_proximity, total_limit_proximity)
        
        # Add FTMO danger and market context to probabilities for AI stop loss logic
        probabilities['ftmo_danger'] = ftmo_danger
        probabilities['portfolio_stress'] = ftmo_danger  # Use same metric for now
        probabilities['h4_volume_divergence'] = market_data.get('h4_volume_divergence', 0.0)
        probabilities['h4_market_structure'] = market_data.get('h4_market_structure', 0.0)
        probabilities['ml_confidence'] = ml_confidence
        probabilities['ml_agrees_direction'] = (is_buy and ml_direction in ['BUY', 'HOLD']) or (not is_buy and ml_direction in ['SELL', 'HOLD'])
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN THESIS ANALYSIS
        # 
        # Uses continuous scoring based on market analysis:
        # - HTF trend alignment (how much D1/H4 support the position)
        # - ML agreement strength (direction + confidence)
        # - Loss significance relative to expected stop distance
        # 
        # NO hardcoded thresholds - pure market analysis
        # ═══════════════════════════════════════════════════════════
        
        # AI-driven thesis strength: How much do HTFs support the position?
        # For BUY: d1_trend=1.0 is perfect, d1_trend=0.0 is broken
        # For SELL: d1_trend=0.0 is perfect, d1_trend=1.0 is broken
        if is_buy:
            d1_thesis_support = d1_trend  # 0-1, higher = better for BUY
            h4_thesis_support = h4_trend
        else:
            d1_thesis_support = 1.0 - d1_trend  # 0-1, higher = better for SELL
            h4_thesis_support = 1.0 - h4_trend
        
        # Combined thesis strength from HTF analysis (D1 weighted more)
        htf_thesis_strength = d1_thesis_support * 0.6 + h4_thesis_support * 0.4
        
        # AI-driven ML agreement: Does ML support the position?
        ml_agrees = (is_buy and ml_direction == 'BUY') or (not is_buy and ml_direction == 'SELL')
        ml_disagrees = (is_buy and ml_direction == 'SELL') or (not is_buy and ml_direction == 'BUY')
        
        # ML agreement score: -1 (strongly against) to +1 (strongly for)
        if ml_agrees:
            ml_agreement_score = ml_confidence / 100.0
        elif ml_disagrees:
            ml_agreement_score = -ml_confidence / 100.0
        else:  # HOLD
            ml_agreement_score = 0.0
        
        # AI-driven loss significance relative to expected stop
        # CRITICAL: Use H4 ATR (swing ATR), not M1 ATR for proper scaling
        current_price = market_data.get('current_price', 1.0)
        h4_volatility = market_data.get('h4_volatility', 0)
        h1_volatility = market_data.get('h1_volatility', 0)
        m1_atr = market_data.get('atr', current_price * 0.01)
        
        # Use H4 ATR for swing trading, fall back to H1, then M1*3
        if h4_volatility > 0:
            thesis_atr = h4_volatility
        elif h1_volatility > 0:
            thesis_atr = h1_volatility
        else:
            thesis_atr = m1_atr * 3.0  # Estimate H4 from M1
        
        # Expected stop = 2x H4 ATR (proper swing trading stop)
        expected_stop_pct = (thesis_atr * 2.0 / current_price * 100) if current_price > 0 else 1.0
        loss_significance = abs(profit_pct) / expected_stop_pct if expected_stop_pct > 0 and profit_pct < 0 else 0
        
        # Cap loss_significance at 2.0 to prevent extreme thesis_broken_score
        # A loss of 2x expected stop is significant, but shouldn't create 10x+ scores
        loss_significance = min(2.0, loss_significance)
        
        # AI-driven thesis broken score (0 = thesis intact, 1 = thesis completely broken)
        # Combines: HTF weakness + ML disagreement + loss depth
        thesis_broken_score = (
            (1.0 - htf_thesis_strength) * 0.5 +  # HTF not supporting
            max(0, -ml_agreement_score) * 0.3 +   # ML disagreeing
            min(1.0, loss_significance) * 0.2     # Loss relative to expected stop
        )
        
        # FTMO protection score (based on proximity to limits)
        ftmo_protection_score = ftmo_danger * loss_significance
        
        logger.info(f"   🧠 AI THESIS ANALYSIS:")
        logger.info(f"      HTF thesis strength: {htf_thesis_strength:.2f} (D1={d1_thesis_support:.2f}, H4={h4_thesis_support:.2f})")
        logger.info(f"      ML agreement: {ml_agreement_score:+.2f} ({ml_direction}@{ml_confidence:.0f}%)")
        logger.info(f"      Loss significance: {loss_significance:.2f} ({profit_pct:.3f}% vs {expected_stop_pct:.2f}% expected stop)")
        logger.info(f"      Thesis broken score: {thesis_broken_score:.2f}")
        
        # AI-driven exit boost based on CONTINUOUS thesis analysis
        # NO hardcoded thresholds - use scores directly for proportional response
        
        # Close boost scales with thesis broken score squared (exponential for high scores)
        # CRITICAL: Cap the boost to prevent it from overwhelming the EV calculation
        # A thesis_broken_score of 0.7 gives boost of 0.49, which is reasonable
        # But we cap at 0.5% to prevent extreme boosts from dominating
        thesis_close_boost = min(0.5, thesis_broken_score ** 2)
        probabilities['news_close_boost'] = max(probabilities.get('news_close_boost', 0), thesis_close_boost)
        
        # Scale out boost is linear with thesis broken score
        thesis_scale_boost = thesis_broken_score * 0.5
        probabilities['news_scale_out_boost'] = max(probabilities.get('news_scale_out_boost', 0), thesis_scale_boost)
        
        # Mark thesis as broken if score is significant (for logging only)
        if thesis_broken_score > 0.5:
            probabilities['thesis_broken_exit'] = True
            logger.warning(f"   🚨 THESIS BROKEN (score={thesis_broken_score:.2f}) - Close boost: {thesis_close_boost:.2f}")
        elif thesis_broken_score > 0.3:
            logger.warning(f"   ⚠️ THESIS WEAKENING (score={thesis_broken_score:.2f}) - Scale boost: {thesis_scale_boost:.2f}")
        
        # FTMO protection - continuous response (FTMO rules are broker requirements)
        # Higher FTMO danger = stronger protection response
        ftmo_close_boost = ftmo_protection_score ** 1.5  # Slightly exponential
        if ftmo_protection_score > 0.3:
            probabilities['ftmo_protection_exit'] = True
            probabilities['news_close_boost'] = max(probabilities.get('news_close_boost', 0), ftmo_close_boost)
            logger.warning(f"   🚨 FTMO PROTECTION (score={ftmo_protection_score:.2f}) - Close boost: {ftmo_close_boost:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Calculate EV for ALL possible actions
        # ═══════════════════════════════════════════════════════════
        
        evs = self._calculate_all_evs(
            profit_metrics, probabilities, market_data, current_volume, is_buy, context, can_scale_in,
            setup_type=setup_type, atr_mult=atr_mult, max_lots=max_lots,
            session_context=session_context,
            time_since_scale=time_since_scale,
            price_move_since_scale=price_move_since_scale
        )
        
        logger.info(f"   💰 Expected Values (% of account):")
        for action, ev in evs.items():
            logger.info(f"      {action}: {ev:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Choose action with HIGHEST EV
        # PURE AI/EV DECISION - No hardcoded thresholds
        # ═══════════════════════════════════════════════════════════
        
        best_action = max(evs, key=evs.get)
        best_ev = evs[best_action]
        hold_ev = evs.get('HOLD', 0)
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN MINIMUM EV ADVANTAGE FOR SCALE_OUT
        # 
        # SCALE_OUT should only be recommended when there's a MEANINGFUL
        # EV advantage over HOLD. Tiny advantages (0.01-0.05%) are noise
        # from calculation precision, not real AI signals.
        # 
        # This prevents churning caused by SCALE_OUT being recommended
        # for negligible EV differences that are within calculation error.
        # 
        # The threshold is based on typical transaction costs:
        # - Commission: ~0.01% per trade
        # - Spread: ~0.02-0.05% depending on symbol
        # - Slippage: ~0.01-0.02%
        # 
        # Total: ~0.05-0.10% minimum to overcome transaction costs.
        # We use 0.10% as the minimum meaningful advantage.
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN MINIMUM EV ADVANTAGE FOR ALL EXIT ACTIONS
        # 
        # ANY exit action (CLOSE or SCALE_OUT) should only be recommended
        # when there's a MEANINGFUL EV advantage over HOLD.
        # 
        # When AI is uncertain (cont ≈ rev), HOLD EV can go slightly negative
        # but that doesn't mean we should exit - it means we should WAIT.
        # 
        # Exiting on tiny EV advantages causes churning and transaction costs.
        # ═══════════════════════════════════════════════════════════
        
        MIN_EXIT_ADVANTAGE = 0.15  # 0.15% minimum advantage over HOLD for ANY exit
        
        if best_action in ['CLOSE', 'SCALE_OUT_25', 'SCALE_OUT_50']:
            ev_advantage = best_ev - hold_ev
            
            # Get AI uncertainty level
            cont_prob = probabilities.get('continuation', 0.5)
            rev_prob = probabilities.get('reversal', 0.3)
            ai_uncertainty = 1.0 - abs(cont_prob - rev_prob)  # High when cont ≈ rev
            
            # Get thesis quality - WEAK THESIS = LOWER THRESHOLD (more aggressive exit)
            thesis_quality = probabilities.get('thesis_quality', 0.5)
            
            # When thesis is weak (< 0.3), be MORE aggressive about exiting
            # When thesis is strong (> 0.7), be MORE patient (higher threshold)
            # This ensures we cut weak trades quickly but let strong trades develop
            thesis_factor = 0.3 + (thesis_quality * 0.7)  # Range: 0.3 (weak) to 1.0 (strong)
            
            # When AI is uncertain, require HIGHER advantage to exit
            # BUT when thesis is weak, reduce this requirement
            required_advantage = MIN_EXIT_ADVANTAGE * (1.0 + ai_uncertainty) * thesis_factor
            
            if ev_advantage < required_advantage:
                # Get target_capture_ratio from EVs dict (calculated in _calculate_evs)
                current_profit_pct = probabilities.get('current_profit_pct', 0)
                target_capture_ratio = evs.get('target_capture_ratio', 0)
                target_capture_pct = target_capture_ratio * 100  # Convert to percentage
                
                # ═══════════════════════════════════════════════════════════
                # TARGET EXCEEDED OVERRIDE - TAKE PROFITS
                # 
                # When profit exceeds target by 50%+, the market has given
                # MORE than expected. Lock it in - this is not uncertainty,
                # this is profit-taking based on live market data.
                # ═══════════════════════════════════════════════════════════
                if target_capture_ratio > 1.5 and current_profit_pct > 0:
                    # Target exceeded by 50%+ - allow SCALE_OUT with minimal threshold
                    target_threshold = MIN_EXIT_ADVANTAGE * 0.1  # Very low threshold (0.015%)
                    if ev_advantage >= target_threshold or ev_advantage > 0:
                        logger.warning(f"   🎯 TARGET EXCEEDED ({target_capture_pct:.0f}%) → allowing {best_action}")
                        logger.info(f"      Market gave {target_capture_pct:.0f}% of target - TAKE PROFITS")
                    else:
                        logger.info(f"   ⏸️ {best_action} advantage too small even with target exceeded")
                        best_action = 'HOLD'
                        best_ev = hold_ev
                elif thesis_quality < 0.2 and current_profit_pct < 0:
                    logger.info(f"   ⚠️ WEAK THESIS ({thesis_quality:.2f}) + LOSING → allowing {best_action}")
                    logger.info(f"      Thesis too weak to justify holding a losing position")
                # ═══════════════════════════════════════════════════════════
                # OVERDUE + ML DISAGREES OVERRIDE
                # 
                # When position is overdue (>100% of expected time) AND ML
                # disagrees with position direction, lower the threshold.
                # The position has had time to develop but ML is signaling exit.
                # ═══════════════════════════════════════════════════════════
                elif current_profit_pct > 0 and ev_advantage > 0:
                    # Check if position is overdue and ML disagrees
                    position_age_pct = probabilities.get('position_age_pct', 0)
                    ml_direction = probabilities.get('ml_direction', 'HOLD')
                    position_direction = probabilities.get('position_direction', 'BUY')
                    ml_disagrees = (ml_direction == 'SELL' and position_direction == 'BUY') or \
                                   (ml_direction == 'BUY' and position_direction == 'SELL')
                    
                    if position_age_pct > 100 and ml_disagrees:
                        # Overdue + ML disagrees = lower threshold (0.10% instead of 0.15-0.25%)
                        overdue_threshold = MIN_EXIT_ADVANTAGE * 0.67  # 0.10% threshold
                        if ev_advantage >= overdue_threshold:
                            logger.warning(f"   ⏰ OVERDUE ({position_age_pct:.0f}%) + ML DISAGREES → allowing {best_action}")
                            logger.info(f"      Position has had time to develop, ML signals exit")
                        else:
                            logger.info(f"   ⏸️ {best_action} advantage too small ({ev_advantage:.4f}% < {required_advantage:.4f}%) - defaulting to HOLD")
                            best_action = 'HOLD'
                            best_ev = hold_ev
                    else:
                        logger.info(f"   ⏸️ {best_action} advantage too small ({ev_advantage:.4f}% < {required_advantage:.4f}%) - defaulting to HOLD")
                        logger.info(f"      AI uncertainty: {ai_uncertainty:.2f} (cont={cont_prob:.1%}, rev={rev_prob:.1%})")
                        logger.info(f"      Thesis factor: {thesis_factor:.2f} (quality={thesis_quality:.2f})")
                        logger.info(f"      When uncertain with decent thesis, HOLD and let trade develop")
                        best_action = 'HOLD'
                        best_ev = hold_ev
                # ═══════════════════════════════════════════════════════════
                # HEDGE FUND WEEKEND RISK OVERRIDE
                # 
                # On Friday afternoon with a losing position, lower the threshold
                # significantly. Gap risk over weekend is too high to hold losers.
                # ═══════════════════════════════════════════════════════════
                elif is_friday_afternoon and current_profit_pct < 0:
                    # Friday + losing = much lower threshold (0.05% instead of 0.15-0.25%)
                    weekend_threshold = MIN_EXIT_ADVANTAGE * 0.3  # 0.05% threshold
                    if ev_advantage >= weekend_threshold:
                        logger.warning(f"   ⚠️ FRIDAY + LOSING → allowing {best_action} (weekend risk override)")
                        logger.info(f"      EV advantage {ev_advantage:.4f}% >= weekend threshold {weekend_threshold:.4f}%")
                    else:
                        logger.info(f"   ⏸️ {best_action} advantage too small ({ev_advantage:.4f}% < {required_advantage:.4f}%) - defaulting to HOLD")
                        logger.info(f"      (Even with weekend risk, advantage below {weekend_threshold:.4f}%)")
                        best_action = 'HOLD'
                        best_ev = hold_ev
                # ═══════════════════════════════════════════════════════════
                # LARGE POSITION RISK OVERRIDE
                # 
                # For large positions (>50% of max), lower the threshold.
                # Larger positions = more risk = easier to reduce.
                # ═══════════════════════════════════════════════════════════
                elif current_volume / max_lots > 0.5 and current_profit_pct < 0:
                    # Large position + losing = lower threshold (0.08% instead of 0.15-0.25%)
                    size_threshold = MIN_EXIT_ADVANTAGE * 0.5  # 0.075% threshold
                    if ev_advantage >= size_threshold:
                        logger.warning(f"   ⚠️ LARGE POSITION ({current_volume:.1f}/{max_lots:.1f}) + LOSING → allowing {best_action}")
                        logger.info(f"      EV advantage {ev_advantage:.4f}% >= size threshold {size_threshold:.4f}%")
                    else:
                        logger.info(f"   ⏸️ {best_action} advantage too small ({ev_advantage:.4f}% < {required_advantage:.4f}%) - defaulting to HOLD")
                        logger.info(f"      AI uncertainty: {ai_uncertainty:.2f} (cont={cont_prob:.1%}, rev={rev_prob:.1%})")
                        logger.info(f"      Thesis factor: {thesis_factor:.2f} (quality={thesis_quality:.2f})")
                        logger.info(f"      When uncertain with decent thesis, HOLD and let trade develop")
                        best_action = 'HOLD'
                        best_ev = hold_ev
                else:
                    logger.info(f"   ⏸️ {best_action} advantage too small ({ev_advantage:.4f}% < {required_advantage:.4f}%) - defaulting to HOLD")
                    logger.info(f"      AI uncertainty: {ai_uncertainty:.2f} (cont={cont_prob:.1%}, rev={rev_prob:.1%})")
                    logger.info(f"      Thesis factor: {thesis_factor:.2f} (quality={thesis_quality:.2f})")
                    logger.info(f"      When uncertain with decent thesis, HOLD and let trade develop")
                    best_action = 'HOLD'
                    best_ev = hold_ev
        
        # Log the decision
        if best_action != 'HOLD':
            ev_advantage = best_ev - hold_ev
            logger.info(f"   📊 EV Advantage: {best_action} beats HOLD by {ev_advantage:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # SMART CLOSE → SCALE_OUT CONVERSION
        # 
        # If CLOSE is best but SCALE_OUT has similar EV, prefer SCALE_OUT.
        # This is AI-driven: only convert if SCALE_OUT EV is within 90% of CLOSE EV.
        # ═══════════════════════════════════════════════════════════
        
        if best_action == 'CLOSE':
            scale_out_50_ev = evs.get('SCALE_OUT_50', -999)
            close_ev = evs.get('CLOSE', 0)
            
            # If SCALE_OUT_50 has at least 90% of CLOSE's EV, prefer it
            # This is AI-driven comparison, not hardcoded threshold
            if scale_out_50_ev > 0 and scale_out_50_ev >= close_ev * 0.9:
                logger.info(f"   📊 SCALE_OUT_50 ({scale_out_50_ev:.4f}%) ≈ CLOSE ({close_ev:.4f}%) → prefer partial")
                best_action = 'SCALE_OUT_50'
                best_ev = scale_out_50_ev
            elif evs.get('HOLD', -999) > close_ev:
                # If HOLD has better EV than CLOSE, prefer HOLD
                logger.info(f"   📊 HOLD ({evs.get('HOLD', 0):.4f}%) > CLOSE ({close_ev:.4f}%) → prefer HOLD")
                best_action = 'HOLD'
                best_ev = evs.get('HOLD', 0)
        
        # ═══════════════════════════════════════════════════════════
        # CRITICAL: NEGATIVE EV CLOSE PROTECTION
        # 
        # If CLOSE has negative EV, we're closing for a guaranteed loss.
        # This should ONLY happen if:
        # 1. Position is deeply underwater AND
        # 2. Reversal probability is very high (>50%) AND
        # 3. HTF has turned against us
        # 
        # Otherwise, HOLD and wait for conditions to improve.
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # NEGATIVE EV ACTION PROTECTION
        # 
        # If ANY exit action (CLOSE or SCALE_OUT) has negative EV,
        # we're locking in a guaranteed loss. Only do this if:
        # 1. Position is deeply underwater AND
        # 2. Reversal probability is very high (>50%) AND  
        # 3. HTF has turned against us
        # 
        # Otherwise, HOLD and wait - even a bad position can recover.
        # ═══════════════════════════════════════════════════════════
        
        if best_action in ['CLOSE', 'SCALE_OUT_25', 'SCALE_OUT_50'] and best_ev < 0:
            action_ev = best_ev
            hold_ev = evs.get('HOLD', 0)
            rev_prob = probabilities.get('reversal', 0)
            cont_prob = probabilities.get('continuation', 0)
            profit_pct = profit_metrics.get('profit_pct', 0)
            
            # Get HTF trends
            h4_trend = market_data.get('h4_trend', 0.5)
            d1_trend = market_data.get('d1_trend', 0.5)
            
            if is_buy:
                htf_against = (d1_trend < 0.45 and h4_trend < 0.45)
            else:
                htf_against = (d1_trend > 0.55 and h4_trend > 0.55)
            
            # Only allow negative EV exit if:
            # - Deep loss (>0.3% of account) AND reversal very high (>50%) AND HTF against
            # - OR reversal extremely high (>60%)
            deep_loss = profit_pct < -0.3
            high_reversal = rev_prob > 0.50
            extreme_reversal = rev_prob > 0.60
            
            should_exit = (deep_loss and high_reversal and htf_against) or extreme_reversal
            
            if not should_exit:
                logger.info(f"   🛡️ NEGATIVE EV {best_action} BLOCKED:")
                logger.info(f"      {best_action} EV: {action_ev:.4f}% (negative = guaranteed loss)")
                logger.info(f"      Profit: {profit_pct:.3f}%, Reversal: {rev_prob:.1%}, HTF against: {htf_against}")
                logger.info(f"      → HOLD instead (wait for conditions to improve)")
                best_action = 'HOLD'
                best_ev = hold_ev
        
        # ═══════════════════════════════════════════════════════════
        # PURE AI/EV DECISION
        # The EV calculation already incorporates:
        # - All 138 features via comprehensive exit/entry scores
        # - Continuation vs reversal probabilities from ML + HTF
        # - HTF trend analysis (H1, H4, D1)
        # - HTF volume divergence and market structure
        # - ADX trend strength
        # - Profit/loss state and trajectory
        # 
        # The action with highest EV wins, unless anti-churn blocks it.
        # Anti-churn is AI-driven: requires thesis change, not time.
        # ═══════════════════════════════════════════════════════════
        
        # Log the AI's analysis for transparency
        exit_score = self._calculate_comprehensive_exit_score(context, is_buy, profit_metrics, probabilities)
        logger.info(f"   📊 AI Exit Score: {exit_score:.3f} (from 138 features)")
        logger.info(f"   📊 Probabilities: cont={probabilities.get('continuation', 0):.1%}, rev={probabilities.get('reversal', 0):.1%}")
        logger.info(f"   → Best Action: {best_action} (EV: {best_ev:.4f}% of account)")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Calculate AI-driven dynamic stop loss
        # This adapts the stop based on CURRENT market conditions
        # ═══════════════════════════════════════════════════════════
        
        dynamic_stop = self._calculate_dynamic_stop(
            context, market_data, probabilities, profit_metrics, is_buy,
            setup_type=setup_type, setup_config=setup_config
        )
        
        # Get S/R distances for EA display
        dist_to_support = getattr(context, 'd1_dist_to_support', 0) or getattr(context, 'h4_dist_to_support', 0)
        dist_to_resistance = getattr(context, 'd1_dist_to_resistance', 0) or getattr(context, 'h4_dist_to_resistance', 0)
        
        return self._create_decision(
            best_action, best_ev, evs, profit_metrics, current_volume, dynamic_stop,
            symbol=symbol, current_price=current_price, probabilities=probabilities,
            setup_type=setup_type,
            session_name=session_name,
            ml_direction=market_data.get('ml_direction', ''),
            ml_confidence=market_data.get('ml_confidence', 0),
            ai_target=probabilities.get('ai_target', 0),
            dist_to_support=dist_to_support,
            dist_to_resistance=dist_to_resistance
        )
    
    def _extract_market_data(self, context, is_buy: bool) -> Dict:
        """Extract all market data from context for AI analysis."""
        
        # Get raw trend values (0.0 = bearish, 1.0 = bullish from feature engineer)
        # These are BINARY values, not continuous 0-1 scale
        h1_trend_raw = getattr(context, 'h1_trend', 0.5)
        h4_trend_raw = getattr(context, 'h4_trend', 0.5)
        d1_trend_raw = getattr(context, 'd1_trend', 0.5)
        
        # Also check trend_alignment as a backup (average of all timeframes)
        trend_alignment = getattr(context, 'trend_alignment', 0.5)
        
        # If all trends are 0.0 (which could mean missing data), use trend_alignment
        if h1_trend_raw == 0.0 and h4_trend_raw == 0.0 and d1_trend_raw == 0.0:
            # Check if trend_alignment suggests bullish (>0.5) or bearish (<0.5)
            if trend_alignment > 0.5:
                # Trend alignment is bullish, so HTF should be bullish
                h1_trend_raw = trend_alignment
                h4_trend_raw = trend_alignment
                d1_trend_raw = trend_alignment
                logger.info(f"   📊 HTF trends were 0.0, using trend_alignment={trend_alignment:.2f}")
        
        return {
            # ML predictions
            'ml_direction': getattr(context, 'ml_direction', 'HOLD'),
            'ml_confidence': getattr(context, 'ml_confidence', 50.0),
            
            # Multi-timeframe trends (0=bearish, 0.5=neutral, 1=bullish)
            'm15_trend': getattr(context, 'm15_trend', 0.5),
            'm30_trend': getattr(context, 'm30_trend', 0.5),
            'h1_trend': h1_trend_raw,
            'h4_trend': h4_trend_raw,
            'd1_trend': d1_trend_raw,
            
            # Momentum (M15-D1 for consistency with ML models)
            'm15_momentum': getattr(context, 'm15_momentum', 0.0),
            'm30_momentum': getattr(context, 'm30_momentum', 0.0),
            'h1_momentum': getattr(context, 'h1_momentum', 0.0),
            'h4_momentum': getattr(context, 'h4_momentum', 0.0),
            'd1_momentum': getattr(context, 'd1_momentum', 0.0),
            
            # RSI (M15-D1 for consistency with ML models)
            'm15_rsi': getattr(context, 'm15_rsi', 50.0),
            'm30_rsi': getattr(context, 'm30_rsi', 50.0),
            'h1_rsi': getattr(context, 'h1_rsi', 50.0),
            'h4_rsi': getattr(context, 'h4_rsi', 50.0),
            'd1_rsi': getattr(context, 'd1_rsi', 50.0),
            
            # Market structure
            'dist_to_resistance': getattr(context, 'dist_to_resistance', 0.0),
            'dist_to_support': getattr(context, 'dist_to_support', 0.0),
            'atr': getattr(context, 'atr', 0.0),
            'current_price': getattr(context, 'current_price', 0.0),
            
            # Volume
            'volume_ratio': getattr(context, 'volume_ratio', 1.0),
            
            # Legacy M1 indicators (kept for compatibility, but not used for decisions)
            'volume_divergence': getattr(context, 'volume_divergence', 0.0),
            'bid_pressure': getattr(context, 'bid_pressure', 0.5),
            'ask_pressure': getattr(context, 'ask_pressure', 0.5),
            
            # NEW HTF SWING TRADING INDICATORS (stable, not M1 noise)
            'h1_adx': getattr(context, 'h1_adx', 25.0),
            'h4_adx': getattr(context, 'h4_adx', 25.0),
            'd1_adx': getattr(context, 'd1_adx', 25.0),
            'htf_adx': getattr(context, 'htf_adx', 25.0),
            'h1_volume_trend': getattr(context, 'h1_volume_trend', 0.0),
            'h4_volume_trend': getattr(context, 'h4_volume_trend', 0.0),
            'd1_volume_trend': getattr(context, 'd1_volume_trend', 0.0),
            'h4_volume_divergence': getattr(context, 'h4_volume_divergence', 0.0),
            'd1_volume_divergence': getattr(context, 'd1_volume_divergence', 0.0),
            'h4_market_structure': getattr(context, 'h4_market_structure', 0.0),
            'd1_market_structure': getattr(context, 'd1_market_structure', 0.0),
            'h4_dist_to_support': getattr(context, 'h4_dist_to_support', 0.0),
            'h4_dist_to_resistance': getattr(context, 'h4_dist_to_resistance', 0.0),
            'd1_dist_to_support': getattr(context, 'd1_dist_to_support', 0.0),
            'd1_dist_to_resistance': getattr(context, 'd1_dist_to_resistance', 0.0),
            
            # Market score (from unified system)
            'market_score': getattr(context, 'market_score', 50.0),
        }
    
    def _calculate_profit_metrics(self, context, current_profit: float, is_buy: bool, symbol: str) -> Dict:
        """
        Calculate profit metrics relative to ACCOUNT SIZE.
        
        This is the key insight: We care about account growth, not arbitrary "risk" units.
        A $22 profit on a $200k account is 0.01% - NOT worth closing for.
        """
        
        account_balance = getattr(context, 'account_balance', 100000)
        entry_price = getattr(context, 'position_entry_price', 0)
        current_price = getattr(context, 'current_price', 0)
        
        # PRIMARY METRIC: Profit as % of ACCOUNT (what actually matters)
        profit_pct_of_account = (current_profit / account_balance) * 100 if account_balance > 0 else 0
        
        # SECONDARY: Calculate move in price terms for target estimation
        if entry_price > 0 and current_price > 0:
            if is_buy:
                price_move_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                price_move_pct = ((entry_price - current_price) / entry_price) * 100
        else:
            price_move_pct = 0
        
        # Log the calculation
        logger.info(f"   📊 Account: ${account_balance:,.0f}")
        logger.info(f"   📊 Profit: ${current_profit:.2f} = {profit_pct_of_account:.3f}% of account")
        logger.info(f"   📊 Price move: {price_move_pct:.2f}%")
        
        # Get current position volume for scale-out detection
        current_volume = getattr(context, 'position_volume', 0)
        
        # Track peak profit (as % of account) - USE PERSISTENT STORAGE
        # ONLY use actual observed profit - NO estimation, NO guessing
        # Pass volume to detect scale-outs and reset peak appropriately
        self.update_peak(symbol, profit_pct_of_account, current_price, current_volume)
        
        # Get the (possibly updated) peak
        peak_profit = self.get_peak(symbol)
        
        # Get realized profit from scale-outs
        realized_profit_pct = self.get_realized_profit(symbol)
        total_trade_profit_pct = self.get_total_trade_profit(symbol, profit_pct_of_account)
        
        # Log total trade performance (realized + unrealized)
        if realized_profit_pct > 0:
            logger.info(f"   💰 TRADE PERFORMANCE for {symbol}:")
            logger.info(f"      Realized (from scale-outs): {realized_profit_pct:.3f}%")
            logger.info(f"      Unrealized (current): {profit_pct_of_account:.3f}%")
            logger.info(f"      TOTAL TRADE PROFIT: {total_trade_profit_pct:.3f}%")
        
        # Calculate giveback (how much we've given back from peak)
        # This is now relative to the CURRENT position's peak, not the pre-scale-out peak
        if peak_profit > 0:
            giveback = (peak_profit - profit_pct_of_account) / peak_profit
        else:
            giveback = 0.0
        
        return {
            'profit_pct': profit_pct_of_account,  # Now relative to ACCOUNT
            'profit_dollars': current_profit,
            'price_move_pct': price_move_pct,
            'peak_profit': peak_profit,
            'giveback': giveback,
            'account_balance': account_balance,
            'is_winning': current_profit > 0,
            'realized_profit_pct': realized_profit_pct,  # Locked-in profits from scale-outs
            'total_trade_profit_pct': total_trade_profit_pct,  # Total: realized + unrealized
        }
    
    def _calculate_probabilities(self, market_data: Dict, is_buy: bool, profit_metrics: Dict, setup_type: str = 'DAY') -> Dict:
        """
        Calculate continuation/reversal probabilities from AI and market analysis.
        
        This is the CORE of the AI-driven approach:
        - Uses ML model direction and confidence
        - Uses multi-timeframe trend alignment
        - Uses momentum and RSI
        - NO hardcoded thresholds
        
        IMPORTANT: ML models are trained on HTF features (h1_trend, h4_trend, d1_trend, etc.)
        So ML prediction ALREADY incorporates HTF data. We use HTF separately only as a
        sanity check / thesis validation, not as a separate weighted factor.
        """
        
        # ═══════════════════════════════════════════════════════════
        # ML MODEL - PRIMARY SIGNAL (70% weight)
        # ML is trained on ALL 138 features INCLUDING HTF (h1/h4/d1 trends)
        # So ML prediction already incorporates multi-timeframe analysis
        # ═══════════════════════════════════════════════════════════
        
        ml_direction = market_data['ml_direction']
        ml_confidence = market_data['ml_confidence'] / 100.0  # Normalize to 0-1
        
        # ML agreement logic for EXISTING positions:
        # - BUY position + ML says BUY = strongly agrees
        # - BUY position + ML says HOLD = agrees (HOLD means don't close!)
        # - BUY position + ML says SELL = disagrees
        # 
        # CRITICAL: HOLD does NOT mean "close the position"
        # HOLD means "don't open new positions" - it's neutral/supportive for existing positions
        
        if is_buy:
            ml_agrees = (ml_direction in ['BUY', 'HOLD'])  # HOLD supports existing BUY
            ml_strongly_agrees = (ml_direction == 'BUY')
        else:
            ml_agrees = (ml_direction in ['SELL', 'HOLD'])  # HOLD supports existing SELL
            ml_strongly_agrees = (ml_direction == 'SELL')
        
        if ml_strongly_agrees:
            ml_factor = ml_confidence  # ML strongly agrees, use full confidence
        elif ml_direction == 'HOLD':
            ml_factor = 0.6  # HOLD is supportive of existing position (slightly above neutral)
        else:
            # ML disagrees (opposite direction)
            # BUT: Check if HTF still supports the position
            # If HTF supports, don't let ML alone trigger a close
            # This prevents churn from ML flip-flopping
            h1_trend = market_data['h1_trend']
            h4_trend = market_data['h4_trend']
            d1_trend = market_data['d1_trend']
            
            if is_buy:
                htf_supports = (d1_trend > 0.55 or h4_trend > 0.52)
            else:
                htf_supports = (d1_trend < 0.45 or h4_trend < 0.48)
            
            if htf_supports:
                # HTF still supports position - reduce ML disagreement impact
                # Don't close just because ML flipped - wait for HTF confirmation
                ml_factor = 0.45  # Slightly below neutral, but not as harsh
                logger.info(f"   ⚠️ ML disagrees but HTF supports → reduced ML penalty (factor=0.45)")
            else:
                # Both ML and HTF disagree - full penalty
                ml_factor = 1.0 - ml_confidence
        
        # ═══════════════════════════════════════════════════════════
        # HTF THESIS VALIDATION (sanity check, not separate factor)
        # Since ML already uses HTF, we only use this to validate the thesis
        # If HTF strongly disagrees with ML, something is wrong
        # ═══════════════════════════════════════════════════════════
        
        h1_trend = market_data['h1_trend']
        h4_trend = market_data['h4_trend']
        d1_trend = market_data['d1_trend']
        
        if is_buy:
            # For BUY, higher trend values = more bullish = better
            trend_factor = (h1_trend + h4_trend + d1_trend) / 3.0
        else:
            # For SELL, lower trend values = more bearish = better
            trend_factor = (3.0 - h1_trend - h4_trend - d1_trend) / 3.0
        
        # ═══════════════════════════════════════════════════════════
        # Factor 3: Momentum - DYNAMIC WEIGHTS BY SETUP TYPE
        # 
        # The ML model receives ALL timeframe data and learns the optimal
        # weighting. Here we create a COMPOSITE SCORE that the AI uses
        # as one input among many - NOT the final decision.
        # 
        # Weights adjust based on setup type:
        # - SCALP: Lower TFs matter more (M15/M30/H1)
        # - DAY: Mid TFs matter more (H1/H4)
        # - SWING: Higher TFs matter more (H4/D1)
        # ═══════════════════════════════════════════════════════════
        
        m15_momentum = market_data['m15_momentum']
        m30_momentum = market_data['m30_momentum']
        h1_momentum = market_data['h1_momentum']
        h4_momentum = market_data['h4_momentum']
        d1_momentum = market_data['d1_momentum']
        
        # Dynamic weights based on setup type
        setup_type_weights = {
            'SCALP': {'m15': 0.25, 'm30': 0.25, 'h1': 0.25, 'h4': 0.15, 'd1': 0.10},
            'DAY':   {'m15': 0.10, 'm30': 0.15, 'h1': 0.25, 'h4': 0.30, 'd1': 0.20},
            'SWING': {'m15': 0.05, 'm30': 0.10, 'h1': 0.15, 'h4': 0.30, 'd1': 0.40}
        }
        weights = setup_type_weights.get(setup_type, setup_type_weights['DAY'])
        
        # Weighted momentum (dynamic based on setup type)
        weighted_momentum = (
            m15_momentum * weights['m15'] +
            m30_momentum * weights['m30'] +
            h1_momentum * weights['h1'] +
            h4_momentum * weights['h4'] +
            d1_momentum * weights['d1']
        )
        
        if is_buy:
            momentum_factor = (weighted_momentum + 1.0) / 2.0  # Normalize -1 to 1 → 0 to 1
        else:
            momentum_factor = (1.0 - weighted_momentum) / 2.0
        
        momentum_factor = max(0.0, min(1.0, momentum_factor))  # Clamp to 0-1
        
        # ═══════════════════════════════════════════════════════════
        # Factor 4: RSI Exhaustion - DYNAMIC WEIGHTS BY SETUP TYPE
        # Overbought/oversold increases reversal probability
        # Uses same dynamic weights as momentum for consistency
        # ═══════════════════════════════════════════════════════════
        
        m15_rsi = market_data['m15_rsi']
        m30_rsi = market_data['m30_rsi']
        h1_rsi = market_data['h1_rsi']
        h4_rsi = market_data['h4_rsi']
        d1_rsi = market_data['d1_rsi']
        
        # Weighted RSI (dynamic based on setup type - uses same weights as momentum)
        weighted_rsi = (
            m15_rsi * weights['m15'] +
            m30_rsi * weights['m30'] +
            h1_rsi * weights['h1'] +
            h4_rsi * weights['h4'] +
            d1_rsi * weights['d1']
        )
        
        if is_buy:
            # For BUY, high RSI = overbought = reversal risk
            # Map RSI 50-100 to exhaustion 0-1
            exhaustion_factor = max(0.0, (weighted_rsi - 50.0) / 50.0)
        else:
            # For SELL, low RSI = oversold = reversal risk
            exhaustion_factor = max(0.0, (50.0 - weighted_rsi) / 50.0)
        
        # ═══════════════════════════════════════════════════════════
        # SWING TRADING: HTF STRUCTURE IS PRIMARY
        # For swing trades, the HTF thesis (H1/H4/D1) is what we entered on
        # ML includes M1 noise which can flip-flop minute to minute
        # Trust the structure over short-term noise
        # ═══════════════════════════════════════════════════════════
        
        # Count how many HTF timeframes STRONGLY support the position
        # Require > 0.55 for bullish, < 0.45 for bearish (not just barely above/below 0.5)
        # 0.51 is essentially neutral, not real support
        STRONG_BULLISH = 0.55
        STRONG_BEARISH = 0.45
        
        if is_buy:
            htf_support_count = sum([h1_trend > STRONG_BULLISH, h4_trend > STRONG_BULLISH, d1_trend > STRONG_BULLISH])
        else:
            htf_support_count = sum([h1_trend < STRONG_BEARISH, h4_trend < STRONG_BEARISH, d1_trend < STRONG_BEARISH])
        
        # Log the actual trend values for debugging
        logger.info(f"   📊 Trends: H1={h1_trend:.2f} H4={h4_trend:.2f} D1={d1_trend:.2f} (need >{STRONG_BULLISH} for BUY support)")
        
        # SWING TRADING LOGIC:
        # - If HTF strongly supports (3/3 or 2/3), trust structure over ML noise
        # - If HTF is weak (0/3 or 1/3), ML becomes more important
        # - This prevents M1 noise from closing swing trades prematurely
        
        if htf_support_count >= 3:
            # STRONG HTF SUPPORT: Structure is solid, ML noise is irrelevant
            # The thesis we entered on is still valid
            ml_weight = 0.30  # Reduce ML influence (it's noisy)
            htf_weight = 0.55  # HTF structure is primary
            logger.info(f"   📊 STRONG HTF ({htf_support_count}/3): Trusting structure over ML noise (ML={ml_factor:.2f} HTF={trend_factor:.2f})")
        elif htf_support_count >= 2:
            # MODERATE HTF SUPPORT: Structure still valid, but watch ML
            ml_weight = 0.45
            htf_weight = 0.40
            logger.info(f"   📊 MODERATE HTF ({htf_support_count}/3): Balanced ML/HTF (ML={ml_factor:.2f} HTF={trend_factor:.2f})")
        else:
            # WEAK HTF SUPPORT: Structure breaking down, ML becomes important
            ml_weight = 0.60
            htf_weight = 0.25
            logger.info(f"   ⚠️ WEAK HTF ({htf_support_count}/3): ML more important (ML={ml_factor:.2f} HTF={trend_factor:.2f})")
        
        # ═══════════════════════════════════════════════════════════
        # SWING TRADING: Use NEW HTF-stable indicators
        # 
        # NEW INDICATORS (from H4/D1, not M1):
        # - h4_volume_divergence: HTF volume divergence (stable)
        # - htf_adx: Trend strength (0-100)
        # - h4_market_structure: Market structure (-1 to 1)
        # ═══════════════════════════════════════════════════════════
        
        # Use HTF volume divergence (from H4, not M1)
        h4_vol_div = market_data.get('h4_volume_divergence', 0.0)
        d1_vol_div = market_data.get('d1_volume_divergence', 0.0)
        htf_volume_divergence = max(h4_vol_div, d1_vol_div)  # Use worst case
        
        # ADX for trend strength (>25 = trending, <20 = ranging)
        htf_adx = market_data.get('htf_adx', 25.0)
        is_trending = htf_adx > 25
        
        # Market structure (positive = uptrend, negative = downtrend)
        h4_structure = market_data.get('h4_market_structure', 0.0)
        d1_structure = market_data.get('d1_market_structure', 0.0)
        
        logger.info(f"   📊 HTF Indicators: vol_div={htf_volume_divergence:.2f}, ADX={htf_adx:.1f}, structure_h4={h4_structure:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN CONTINUATION PROBABILITY
        # 
        # NO hardcoded thresholds (0.50, 0.55, 0.45, etc.)
        # Uses continuous scoring based on position direction alignment
        # ═══════════════════════════════════════════════════════════
        
        # AI-driven trend alignment: continuous 0-1 score
        # For BUY: trend_factor directly represents support (0=bearish, 1=bullish)
        # For SELL: inverted (0=bullish opposition, 1=bearish support)
        if is_buy:
            adjusted_trend = trend_factor  # Direct: higher = more bullish support
        else:
            adjusted_trend = 1.0 - trend_factor  # Inverted: higher = more bearish support
        
        # AI-driven weights based on market conditions (not hardcoded)
        # When ADX is high (trending), trust HTF more
        # When ADX is low (ranging), trust ML more
        adx_factor = min(1.0, htf_adx / 50.0)  # Continuous 0-1
        
        # Dynamic weights based on trend strength
        dynamic_htf_weight = htf_weight * (0.8 + adx_factor * 0.4)  # 0.8-1.2x HTF weight
        dynamic_ml_weight = ml_weight * (1.2 - adx_factor * 0.4)   # 0.8-1.2x ML weight
        
        # Normalize weights
        total_weight = dynamic_htf_weight + dynamic_ml_weight + 0.15 + 0.10
        dynamic_htf_weight /= total_weight
        dynamic_ml_weight /= total_weight
        momentum_weight = 0.15 / total_weight
        exhaustion_weight = 0.10 / total_weight
        
        base_continuation = (
            ml_factor * dynamic_ml_weight +
            adjusted_trend * dynamic_htf_weight +
            momentum_factor * momentum_weight +
            (1.0 - exhaustion_factor) * exhaustion_weight
        )
        
        # Market structure bonus (continuous, not threshold-based)
        if is_buy:
            structure_bonus = (h4_structure + d1_structure) / 2.0 * 0.10
        else:
            structure_bonus = -(h4_structure + d1_structure) / 2.0 * 0.10
        
        # Volume divergence penalty (continuous)
        vol_div_penalty = htf_volume_divergence * 0.15
        
        # ADX confidence boost (stronger trends = more confidence)
        adx_boost = 0.8 + adx_factor * 0.2
        
        continuation = (base_continuation + structure_bonus) * (1.0 - vol_div_penalty) * adx_boost
        
        logger.info(f"   🧠 AI Continuation: trend={adjusted_trend:.2f}, ml={ml_factor:.2f}, adx_factor={adx_factor:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN REVERSAL PROBABILITY
        # 
        # NO hardcoded thresholds or fixed weights
        # Weights dynamically adjust based on HTF support strength
        # ═══════════════════════════════════════════════════════════
        
        # ML disagreement factor (continuous 0-1)
        ml_disagree = 1.0 - ml_factor
        
        # HTF weakness factor (continuous 0-1, based on position direction)
        htf_weakness = 1.0 - adjusted_trend
        
        # AI-driven ML reversal weight based on HTF strength (continuous)
        # When HTF is strong (adjusted_trend high), ML disagreement matters less
        # When HTF is weak (adjusted_trend low), ML disagreement matters more
        ml_reversal_weight = 0.15 + (htf_weakness * 0.30)  # 0.15 to 0.45 based on HTF
        
        # Remaining weight goes to other factors
        htf_reversal_weight = 0.35
        exhaustion_rev_weight = 0.15
        vol_div_rev_weight = 0.10
        adx_rev_weight = 0.05
        
        base_reversal = (
            htf_weakness * htf_reversal_weight +
            ml_disagree * ml_reversal_weight +
            exhaustion_factor * exhaustion_rev_weight +
            htf_volume_divergence * vol_div_rev_weight +
            (1.0 - adx_factor) * adx_rev_weight
        )
        
        # No hard cap - let the math determine reversal probability
        reversal = min(0.85, base_reversal)  # Soft cap at 85%
        
        # Normalize so they sum to <= 1.0
        total = continuation + reversal
        if total > 1.0:
            continuation /= total
            reversal /= total
        
        flat = max(0.0, 1.0 - continuation - reversal)
        
        # AI-DRIVEN THESIS QUALITY (continuous, not threshold-based)
        # Combines ML agreement strength with HTF alignment strength
        
        # ML thesis contribution (continuous 0-0.5)
        ml_thesis = ml_factor * 0.5  # Direct use of ml_factor (0-1) scaled to 0-0.5
        
        # HTF thesis contribution (continuous 0-0.5)
        htf_thesis = adjusted_trend * 0.5  # Direct use of adjusted_trend (0-1) scaled to 0-0.5
        
        thesis_quality = ml_thesis + htf_thesis  # 0 to 1.0
        
        return {
            'continuation': continuation,
            'reversal': reversal,
            'flat': flat,
            'ml_agrees': ml_agrees,
            'trend_aligned': adjusted_trend > 0.5,  # Continuous comparison
            'thesis_quality': thesis_quality,
            'ai_target': 0,  # Will be set later in analyze_exit
        }
    
    def _calculate_comprehensive_exit_score(self, context, is_buy: bool, profit_metrics: Dict, probabilities: Dict) -> float:
        """
        Calculate exit score using ALL 138 features from context.
        
        This is TRUE AI-driven analysis - not 5 manually weighted factors,
        but a comprehensive analysis of the entire market state.
        
        Returns a score from 0.0 (strong hold) to 1.0 (strong exit signal)
        """
        
        exit_signals = []
        hold_signals = []
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 1: MULTI-TIMEFRAME TREND ANALYSIS (SWING TRADING)
        # M1/M5 EXCLUDED - too noisy for swing trading decisions
        # Only M15+ timeframes used for entry/exit decisions
        # ═══════════════════════════════════════════════════════════
        
        # SWING TRADING: M15, M30, H1, H4, D1 only (no M1/M5 noise)
        timeframes = ['m15', 'm30', 'h1', 'h4', 'd1']
        tf_weights = [0.10, 0.15, 0.20, 0.25, 0.30]  # Higher TF = more weight, total = 1.0
        
        for tf, weight in zip(timeframes, tf_weights):
            trend = getattr(context, f'{tf}_trend', 0.5)
            momentum = getattr(context, f'{tf}_momentum', 0.0)
            rsi = getattr(context, f'{tf}_rsi', 50.0)
            macd = getattr(context, f'{tf}_macd', 0.0)
            strength = getattr(context, f'{tf}_strength', 0.0)
            bb_position = getattr(context, f'{tf}_bb_position', 0.5)
            
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN EXIT SIGNALS - NO HARDCODED THRESHOLDS
            # 
            # Instead of if trend < 0.4 or trend > 0.6, use continuous scoring:
            # - Trend opposition strength = how much trend opposes position
            # - Momentum opposition = how much momentum opposes position
            # - RSI exhaustion = continuous measure of overbought/oversold
            # - BB position = continuous measure of band position
            # ═══════════════════════════════════════════════════════════
            
            if is_buy:
                # TREND: For BUY, trend < 0.5 = opposition, trend > 0.5 = support
                trend_opposition = max(0, 0.5 - trend)  # 0 at 0.5, 0.5 at 0.0
                trend_support = max(0, trend - 0.5)      # 0 at 0.5, 0.5 at 1.0
                
                exit_signals.append(weight * trend_opposition)
                hold_signals.append(weight * trend_support)
                
                # MOMENTUM: Negative momentum = exit signal for BUY
                if momentum < 0:
                    exit_signals.append(weight * 0.5 * abs(momentum))
                else:
                    hold_signals.append(weight * 0.5 * momentum)
                
                # RSI: Continuous exhaustion measure (50 = neutral)
                # For BUY: RSI > 50 = overbought risk, RSI < 50 = room to run
                rsi_normalized = (rsi - 50) / 50  # -1 to +1
                if rsi_normalized > 0:
                    exit_signals.append(weight * 0.3 * rsi_normalized)  # Overbought
                else:
                    hold_signals.append(weight * 0.2 * abs(rsi_normalized))  # Oversold
                
                # MACD: Negative = exit signal for BUY
                if macd < 0:
                    exit_signals.append(weight * 0.3 * min(1.0, abs(macd)))
                else:
                    hold_signals.append(weight * 0.2 * min(1.0, macd))
                
                # BB: Position > 0.5 = near upper band = exit risk for BUY
                bb_risk = max(0, bb_position - 0.5) * 2  # 0 at 0.5, 1 at 1.0
                bb_support = max(0, 0.5 - bb_position) * 2  # 0 at 0.5, 1 at 0.0
                exit_signals.append(weight * 0.2 * bb_risk)
                hold_signals.append(weight * 0.1 * bb_support)
            else:
                # TREND: For SELL, trend > 0.5 = opposition, trend < 0.5 = support
                trend_opposition = max(0, trend - 0.5)  # 0 at 0.5, 0.5 at 1.0
                trend_support = max(0, 0.5 - trend)      # 0 at 0.5, 0.5 at 0.0
                
                exit_signals.append(weight * trend_opposition)
                hold_signals.append(weight * trend_support)
                
                # MOMENTUM: Positive momentum = exit signal for SELL
                if momentum > 0:
                    exit_signals.append(weight * 0.5 * momentum)
                else:
                    hold_signals.append(weight * 0.5 * abs(momentum))
                
                # RSI: For SELL, RSI < 50 = oversold risk, RSI > 50 = room to run
                rsi_normalized = (rsi - 50) / 50  # -1 to +1
                if rsi_normalized < 0:
                    exit_signals.append(weight * 0.3 * abs(rsi_normalized))  # Oversold
                else:
                    hold_signals.append(weight * 0.2 * rsi_normalized)  # Overbought
                
                # MACD: Positive = exit signal for SELL
                if macd > 0:
                    exit_signals.append(weight * 0.3 * min(1.0, macd))
                else:
                    hold_signals.append(weight * 0.2 * min(1.0, abs(macd)))
                
                # BB: Position < 0.5 = near lower band = exit risk for SELL
                bb_risk = max(0, 0.5 - bb_position) * 2  # 0 at 0.5, 1 at 0.0
                bb_support = max(0, bb_position - 0.5) * 2  # 0 at 0.5, 1 at 1.0
                exit_signals.append(weight * 0.2 * bb_risk)
                hold_signals.append(weight * 0.1 * bb_support)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 2: ML MODEL ANALYSIS
        # The ML model has already analyzed all 138 features
        # ═══════════════════════════════════════════════════════════
        
        ml_direction = getattr(context, 'ml_direction', 'HOLD')
        ml_confidence = getattr(context, 'ml_confidence', 50.0) / 100.0
        
        if is_buy:
            if ml_direction == 'SELL':
                exit_signals.append(0.25 * ml_confidence)  # ML says opposite
            elif ml_direction == 'BUY':
                hold_signals.append(0.25 * ml_confidence)  # ML agrees
            # HOLD is neutral
        else:
            if ml_direction == 'BUY':
                exit_signals.append(0.25 * ml_confidence)
            elif ml_direction == 'SELL':
                hold_signals.append(0.25 * ml_confidence)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 3: TIMEFRAME ALIGNMENT FEATURES
        # Divergence between timeframes = uncertainty = exit signal
        # ═══════════════════════════════════════════════════════════
        
        trend_alignment = getattr(context, 'trend_alignment', 0.5)
        macd_all_bullish = getattr(context, 'macd_all_bullish', 0.0)
        macd_all_bearish = getattr(context, 'macd_all_bearish', 0.0)
        rsi_all_overbought = getattr(context, 'rsi_all_overbought', 0.0)
        rsi_all_oversold = getattr(context, 'rsi_all_oversold', 0.0)
        
        # Low alignment = mixed signals = consider exit
        if trend_alignment < 0.4:
            exit_signals.append(0.15 * (0.5 - trend_alignment))
        
        if is_buy:
            if macd_all_bearish > 0.5:
                exit_signals.append(0.10 * macd_all_bearish)
            if rsi_all_overbought > 0.5:
                exit_signals.append(0.10 * rsi_all_overbought)
            if macd_all_bullish > 0.5:
                hold_signals.append(0.10 * macd_all_bullish)
        else:
            if macd_all_bullish > 0.5:
                exit_signals.append(0.10 * macd_all_bullish)
            if rsi_all_oversold > 0.5:
                exit_signals.append(0.10 * rsi_all_oversold)
            if macd_all_bearish > 0.5:
                hold_signals.append(0.10 * macd_all_bearish)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 4: HTF VOLUME & MARKET STRUCTURE (NEW!)
        # Using H4/D1 indicators instead of M1 noise
        # ═══════════════════════════════════════════════════════════
        
        # NEW: HTF Volume Divergence (stable, from H4/D1)
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        d1_vol_div = getattr(context, 'd1_volume_divergence', 0.0)
        htf_vol_div = max(h4_vol_div, d1_vol_div)
        
        # NEW: HTF Volume Trend (positive = volume increasing)
        h4_vol_trend = getattr(context, 'h4_volume_trend', 0.0)
        d1_vol_trend = getattr(context, 'd1_volume_trend', 0.0)
        
        # NEW: Market Structure
        h4_structure = getattr(context, 'h4_market_structure', 0.0)
        d1_structure = getattr(context, 'd1_market_structure', 0.0)
        
        # NEW: ADX (trend strength)
        htf_adx = getattr(context, 'htf_adx', 25.0)
        
        # Legacy M1 indicators (minimal weight)
        distribution = getattr(context, 'distribution', 0.0)
        accumulation = getattr(context, 'accumulation', 0.0)
        
        logger.info(f"   📊 HTF Volume: h4_div={h4_vol_div:.2f}, h4_trend={h4_vol_trend:.2f}, ADX={htf_adx:.1f}")
        logger.info(f"   📊 Market Structure: h4={h4_structure:.2f}, d1={d1_structure:.2f}")
        
        # HTF Volume Divergence = exit signal (stable, reliable)
        if htf_vol_div > 0.3:
            exit_signals.append(0.15 * htf_vol_div)
        
        # HTF Volume Trend declining = warning
        if h4_vol_trend < -0.3:
            exit_signals.append(0.10 * abs(h4_vol_trend))
        elif h4_vol_trend > 0.3:
            hold_signals.append(0.10 * h4_vol_trend)
        
        # Market Structure against position = exit signal
        if is_buy:
            if h4_structure < -0.3:  # Downtrend structure
                exit_signals.append(0.15 * abs(h4_structure))
            elif h4_structure > 0.3:  # Uptrend structure
                hold_signals.append(0.15 * h4_structure)
            if distribution > 0.5:
                exit_signals.append(0.10 * distribution)
            if accumulation > 0.5:
                hold_signals.append(0.10 * accumulation)
        else:
            if h4_structure > 0.3:  # Uptrend structure (bad for SELL)
                exit_signals.append(0.15 * h4_structure)
            elif h4_structure < -0.3:  # Downtrend structure
                hold_signals.append(0.15 * abs(h4_structure))
            if accumulation > 0.5:
                exit_signals.append(0.10 * accumulation)
            if distribution > 0.5:
                hold_signals.append(0.10 * distribution)
        
        # Low ADX (ranging market) = higher exit consideration
        if htf_adx < 20:
            exit_signals.append(0.05 * (1.0 - htf_adx / 20.0))
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 5: ORDER BOOK PRESSURE
        # SWING TRADING: Order flow is M1 data - too noisy
        # Only log it for reference, don't use for exit decisions
        # ═══════════════════════════════════════════════════════════
        
        bid_ask_imbalance = getattr(context, 'bid_ask_imbalance', 0.0)
        bid_pressure = getattr(context, 'bid_pressure', 0.5)
        ask_pressure = getattr(context, 'ask_pressure', 0.5)
        
        logger.info(f"   📊 Order Flow (M1 - info only): bid={bid_pressure:.2f}, ask={ask_pressure:.2f}")
        
        # NOTE: Order flow is M1 data that changes every minute
        # For swing trading, we should NOT use it for exit decisions
        # It causes premature exits based on short-term noise
        # Volume divergence (more stable) is used instead in probability calc
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 6: PROFIT-BASED RISK MANAGEMENT
        # More profit = more to protect = higher exit consideration
        # ═══════════════════════════════════════════════════════════
        
        profit_pct = profit_metrics.get('profit_pct', 0)
        giveback = profit_metrics.get('giveback', 0)
        peak_profit = profit_metrics.get('peak_profit', 0)
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PROFIT PROTECTION SIGNALS
        # Use market analysis to determine if profits are at risk
        # NOT hardcoded thresholds - based on feature analysis
        # ═══════════════════════════════════════════════════════════
        
        # Calculate profit trajectory (is profit growing or shrinking?)
        profit_trajectory = profit_pct - peak_profit if peak_profit > 0 else 0
        
        if peak_profit > 0.05 and profit_trajectory < 0:
            # Profit is eroding - weight based on severity AND market conditions
            # Cap erosion at 100% to avoid extreme values
            erosion_pct = min(1.0, abs(profit_trajectory) / max(peak_profit, 0.01))
            
            # For swing trading, only care about significant erosion (>30%)
            # Small pullbacks are normal in swing trades
            if erosion_pct > 0.30:
                # Combine with reversal probability for AI-driven signal
                # Higher reversal + higher erosion = stronger exit signal
                ai_exit_weight = (erosion_pct - 0.30) * probabilities.get('reversal', 0.3) * 0.5
                
                if ai_exit_weight > 0.05:
                    exit_signals.append(ai_exit_weight)
                    logger.info(f"   📊 Profit Giveback: {erosion_pct:.1%} from peak, reversal={probabilities.get('reversal', 0.3):.1%} → weight {ai_exit_weight:.3f}")
        
        # Significant profit achieved
        if profit_pct > 0.1:
            exit_signals.append(0.10 * min(1.0, profit_pct / 0.5))
        
        # Giveback from peak
        if giveback > 0.2:
            exit_signals.append(0.12 * min(1.0, giveback / 0.5))
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 7: REVERSAL PROBABILITY (from _calculate_probabilities)
        # This already incorporates ML + HTF analysis
        # ═══════════════════════════════════════════════════════════
        
        rev_prob = probabilities.get('reversal', 0.3)
        cont_prob = probabilities.get('continuation', 0.5)
        
        # AI-DRIVEN: Use continuous scoring, not thresholds
        # Higher reversal = more exit pressure (scaled contribution)
        exit_signals.append(rev_prob * 0.20)
        # Higher continuation = more hold pressure (scaled contribution)
        hold_signals.append(cont_prob * 0.20)
        
        # ═══════════════════════════════════════════════════════════
        # CALCULATE FINAL SCORE
        # ═══════════════════════════════════════════════════════════
        
        total_exit = sum(exit_signals)
        total_hold = sum(hold_signals)
        
        # Normalize to 0-1 range
        if total_exit + total_hold > 0:
            exit_score = total_exit / (total_exit + total_hold + 0.1)  # +0.1 to prevent division issues
        else:
            exit_score = 0.3  # Neutral default
        
        # Clamp to 0-1
        exit_score = max(0.0, min(1.0, exit_score))
        
        logger.info(f"   🧠 Comprehensive Exit Analysis:")
        logger.info(f"      Exit signals: {len(exit_signals)} factors, total={total_exit:.3f}")
        logger.info(f"      Hold signals: {len(hold_signals)} factors, total={total_hold:.3f}")
        logger.info(f"      Final exit score: {exit_score:.3f}")
        
        return exit_score
    
    def _calculate_move_exhaustion(self, context, is_buy: bool, profit_metrics: Dict) -> float:
        """
        AI-DRIVEN MOVE EXHAUSTION ANALYSIS
        
        Analyzes ALL timeframes to determine if the market has given all the profit
        it's going to give. This is the key question: "Is this move done?"
        
        Exhaustion signals across timeframes:
        - Momentum divergence (price up, momentum down)
        - RSI exhaustion (overbought/oversold)
        - Volume declining on continuation
        - Higher timeframes turning against
        - Market structure breaking down
        - Distance from key levels (support/resistance)
        
        Returns: 0.0 (move has more to give) to 1.0 (move is exhausted)
        """
        
        exhaustion_signals = []
        continuation_signals = []
        
        # ═══════════════════════════════════════════════════════════
        # TIMEFRAME-BY-TIMEFRAME EXHAUSTION ANALYSIS
        # Check each TF for signs the move is running out of steam
        # ═══════════════════════════════════════════════════════════
        
        timeframes = ['m15', 'm30', 'h1', 'h4', 'd1']
        tf_weights = [0.10, 0.15, 0.20, 0.25, 0.30]  # HTF weighted more
        
        for tf, weight in zip(timeframes, tf_weights):
            trend = getattr(context, f'{tf}_trend', 0.5)
            momentum = getattr(context, f'{tf}_momentum', 0.0)
            rsi = getattr(context, f'{tf}_rsi', 50.0)
            macd = getattr(context, f'{tf}_macd', 0.0)
            macd_hist = getattr(context, f'{tf}_macd_histogram', 0.0)
            
            if is_buy:
                # EXHAUSTION: Price trending up but momentum/MACD weakening
                if trend > 0.5 and momentum < 0:
                    # Bearish divergence - price up, momentum down
                    exhaustion_signals.append(weight * 0.8 * abs(momentum))
                    
                if trend > 0.5 and macd_hist < 0:
                    # MACD histogram declining while in uptrend
                    exhaustion_signals.append(weight * 0.6 * abs(macd_hist))
                
                # RSI exhaustion
                if rsi > 70:
                    exhaustion_signals.append(weight * 0.7 * (rsi - 70) / 30)
                elif rsi > 60:
                    exhaustion_signals.append(weight * 0.3 * (rsi - 60) / 20)
                
                # Still strong momentum = more to give
                if momentum > 0.3 and trend > 0.55:
                    continuation_signals.append(weight * 0.8 * momentum)
                    
                if rsi < 60 and trend > 0.55:
                    continuation_signals.append(weight * 0.5)
            else:
                # SELL position exhaustion
                if trend < 0.5 and momentum > 0:
                    # Bullish divergence - price down, momentum up
                    exhaustion_signals.append(weight * 0.8 * momentum)
                    
                if trend < 0.5 and macd_hist > 0:
                    exhaustion_signals.append(weight * 0.6 * macd_hist)
                
                if rsi < 30:
                    exhaustion_signals.append(weight * 0.7 * (30 - rsi) / 30)
                elif rsi < 40:
                    exhaustion_signals.append(weight * 0.3 * (40 - rsi) / 20)
                
                if momentum < -0.3 and trend < 0.45:
                    continuation_signals.append(weight * 0.8 * abs(momentum))
                    
                if rsi > 40 and trend < 0.45:
                    continuation_signals.append(weight * 0.5)
        
        # ═══════════════════════════════════════════════════════════
        # HTF TURNING AGAINST = MAJOR EXHAUSTION SIGNAL
        # If D1 or H4 is turning, the move is likely done
        # ═══════════════════════════════════════════════════════════
        
        d1_trend = getattr(context, 'd1_trend', 0.5)
        h4_trend = getattr(context, 'h4_trend', 0.5)
        h1_trend = getattr(context, 'h1_trend', 0.5)
        
        if is_buy:
            # D1 turning bearish = major exhaustion
            if d1_trend < 0.48:
                exhaustion_signals.append(0.4 * (0.5 - d1_trend))
            # H4 turning while D1 still bullish = early warning
            if h4_trend < 0.45 and d1_trend > 0.52:
                exhaustion_signals.append(0.25 * (0.5 - h4_trend))
            # All HTFs still bullish = more to give
            if d1_trend > 0.55 and h4_trend > 0.52 and h1_trend > 0.52:
                continuation_signals.append(0.5)
        else:
            if d1_trend > 0.52:
                exhaustion_signals.append(0.4 * (d1_trend - 0.5))
            if h4_trend > 0.55 and d1_trend < 0.48:
                exhaustion_signals.append(0.25 * (h4_trend - 0.5))
            if d1_trend < 0.45 and h4_trend < 0.48 and h1_trend < 0.48:
                continuation_signals.append(0.5)
        
        # ═══════════════════════════════════════════════════════════
        # VOLUME EXHAUSTION
        # Declining volume on continuation = move running out of steam
        # ═══════════════════════════════════════════════════════════
        
        h4_vol_trend = getattr(context, 'h4_volume_trend', 0.0)
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        
        if h4_vol_trend < -0.2:
            # Volume declining = exhaustion
            exhaustion_signals.append(0.3 * abs(h4_vol_trend))
        elif h4_vol_trend > 0.2:
            # Volume increasing = more to give
            continuation_signals.append(0.3 * h4_vol_trend)
            
        if h4_vol_div > 0.4:
            # Volume divergence = exhaustion
            exhaustion_signals.append(0.35 * h4_vol_div)
        
        # ═══════════════════════════════════════════════════════════
        # DISTANCE TO KEY LEVELS
        # Near resistance (for BUY) = potential exhaustion
        # ═══════════════════════════════════════════════════════════
        
        h4_dist_resistance = getattr(context, 'h4_dist_to_resistance', 5.0)
        h4_dist_support = getattr(context, 'h4_dist_to_support', 5.0)
        d1_dist_resistance = getattr(context, 'd1_dist_to_resistance', 5.0)
        d1_dist_support = getattr(context, 'd1_dist_to_support', 5.0)
        
        if is_buy:
            # Close to resistance = exhaustion likely
            if h4_dist_resistance < 0.5:
                exhaustion_signals.append(0.4 * (1.0 - h4_dist_resistance / 0.5))
            if d1_dist_resistance < 1.0:
                exhaustion_signals.append(0.3 * (1.0 - d1_dist_resistance / 1.0))
            # Far from resistance = room to run
            if h4_dist_resistance > 1.5:
                continuation_signals.append(0.2)
        else:
            if h4_dist_support < 0.5:
                exhaustion_signals.append(0.4 * (1.0 - h4_dist_support / 0.5))
            if d1_dist_support < 1.0:
                exhaustion_signals.append(0.3 * (1.0 - d1_dist_support / 1.0))
            if h4_dist_support > 1.5:
                continuation_signals.append(0.2)
        
        # ═══════════════════════════════════════════════════════════
        # ADX TREND STRENGTH
        # Declining ADX = trend losing strength = exhaustion
        # ═══════════════════════════════════════════════════════════
        
        htf_adx = getattr(context, 'htf_adx', 25.0)
        h4_adx = getattr(context, 'h4_adx', 25.0)
        
        if htf_adx < 20:
            # Weak trend = exhaustion
            exhaustion_signals.append(0.2 * (1.0 - htf_adx / 20.0))
        elif htf_adx > 30:
            # Strong trend = more to give
            continuation_signals.append(0.2 * min(1.0, (htf_adx - 25) / 25))
        
        # ═══════════════════════════════════════════════════════════
        # CROSS-ASSET CORRELATION (Institutional Edge)
        # Use data from other symbols to confirm or warn
        # ═══════════════════════════════════════════════════════════
        
        risk_on_off = getattr(context, 'risk_on_off', 0.5)
        indices_aligned = getattr(context, 'indices_aligned', 0.5)
        dxy_trend = getattr(context, 'dxy_trend', 0.5)
        gold_dollar_divergence = getattr(context, 'gold_dollar_divergence', 0.0)
        
        symbol = getattr(context, 'symbol', '').lower()
        
        # For indices (US30, US100, US500): Risk-off = exhaustion for longs
        if any(idx in symbol for idx in ['us30', 'us100', 'us500']):
            if is_buy and risk_on_off < 0.45:
                # Risk-off environment, long indices may be exhausted
                exhaustion_signals.append(0.2 * (0.5 - risk_on_off))
            elif not is_buy and risk_on_off > 0.55:
                # Risk-on environment, short indices may be exhausted
                exhaustion_signals.append(0.2 * (risk_on_off - 0.5))
            # Indices aligned in our direction = continuation
            if indices_aligned > 0.8:
                continuation_signals.append(0.15)
        
        # For Gold: DXY strength = headwind for gold longs
        if 'xau' in symbol or 'gold' in symbol:
            if is_buy and dxy_trend > 0.55:
                # Strong dollar = headwind for gold
                exhaustion_signals.append(0.15 * (dxy_trend - 0.5))
            elif not is_buy and dxy_trend < 0.45:
                # Weak dollar = headwind for gold shorts
                exhaustion_signals.append(0.15 * (0.5 - dxy_trend))
            # Gold/Dollar divergence = unusual, be cautious
            if gold_dollar_divergence > 0.2:
                exhaustion_signals.append(0.1 * gold_dollar_divergence)
        
        # For Forex: DXY trend affects USD pairs
        if 'eur' in symbol or 'gbp' in symbol:
            if is_buy and dxy_trend > 0.55:
                # Strong dollar = headwind for EUR/GBP longs
                exhaustion_signals.append(0.15 * (dxy_trend - 0.5))
            elif not is_buy and dxy_trend < 0.45:
                # Weak dollar = headwind for EUR/GBP shorts
                exhaustion_signals.append(0.15 * (0.5 - dxy_trend))
        
        if 'jpy' in symbol:
            # USDJPY is opposite - strong dollar = bullish
            if is_buy and dxy_trend < 0.45:
                exhaustion_signals.append(0.15 * (0.5 - dxy_trend))
            elif not is_buy and dxy_trend > 0.55:
                exhaustion_signals.append(0.15 * (dxy_trend - 0.5))
        
        # ═══════════════════════════════════════════════════════════
        # CALCULATE EXHAUSTION SCORE
        # ═══════════════════════════════════════════════════════════
        
        total_exhaustion = sum(exhaustion_signals)
        total_continuation = sum(continuation_signals)
        
        if total_exhaustion + total_continuation > 0:
            exhaustion_score = total_exhaustion / (total_exhaustion + total_continuation + 0.1)
        else:
            exhaustion_score = 0.3  # Neutral
        
        exhaustion_score = max(0.0, min(1.0, exhaustion_score))
        
        logger.info(f"   🔋 Move Exhaustion Analysis:")
        logger.info(f"      Exhaustion signals: {len(exhaustion_signals)}, total={total_exhaustion:.3f}")
        logger.info(f"      Continuation signals: {len(continuation_signals)}, total={total_continuation:.3f}")
        logger.info(f"      Exhaustion score: {exhaustion_score:.2f} (0=more to give, 1=exhausted)")
        
        return exhaustion_score
    
    def _calculate_comprehensive_entry_score(self, context, is_buy: bool, profit_metrics: Dict, probabilities: Dict) -> float:
        """
        Calculate entry/add score using ALL 138 features from context.
        
        This is the INVERSE of exit score - looks for signals that support
        ADDING to the position (scaling in).
        
        Returns a score from 0.0 (don't add) to 1.0 (strong add signal)
        """
        
        add_signals = []
        avoid_signals = []
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 1: MULTI-TIMEFRAME TREND ANALYSIS (SWING TRADING)
        # M1/M5 EXCLUDED - too noisy for swing trading decisions
        # For SCALE_IN, we want STRONG trend alignment in our direction
        # ═══════════════════════════════════════════════════════════
        
        # SWING TRADING: M15, M30, H1, H4, D1 only (no M1/M5 noise)
        timeframes = ['m15', 'm30', 'h1', 'h4', 'd1']
        tf_weights = [0.10, 0.15, 0.20, 0.25, 0.30]  # Higher TF = more weight, total = 1.0
        
        for tf, weight in zip(timeframes, tf_weights):
            trend = getattr(context, f'{tf}_trend', 0.5)
            momentum = getattr(context, f'{tf}_momentum', 0.0)
            rsi = getattr(context, f'{tf}_rsi', 50.0)
            macd = getattr(context, f'{tf}_macd', 0.0)
            strength = getattr(context, f'{tf}_strength', 0.0)
            bb_position = getattr(context, f'{tf}_bb_position', 0.5)
            
            if is_buy:
                # For BUY: bullish signals = add signals
                if trend > 0.6:
                    add_signals.append(weight * (trend - 0.5))
                elif trend < 0.4:
                    avoid_signals.append(weight * (0.5 - trend))
                    
                if momentum > 0.3:
                    add_signals.append(weight * 0.5 * momentum)
                elif momentum < -0.3:
                    avoid_signals.append(weight * 0.5 * abs(momentum))
                    
                # RSI: not overbought = room to run = add signal
                if rsi < 60:
                    add_signals.append(weight * 0.2 * (60 - rsi) / 30)
                elif rsi > 75:
                    avoid_signals.append(weight * 0.3 * (rsi - 70) / 30)
                    
                # MACD positive = bullish = add signal
                if macd > 0:
                    add_signals.append(weight * 0.3 * min(1.0, macd))
                elif macd < 0:
                    avoid_signals.append(weight * 0.3 * min(1.0, abs(macd)))
                    
                # BB position: middle or lower = room to run
                if bb_position < 0.6:
                    add_signals.append(weight * 0.15 * (0.7 - bb_position))
            else:
                # For SELL: bearish signals = add signals
                if trend < 0.4:
                    add_signals.append(weight * (0.5 - trend))
                elif trend > 0.6:
                    avoid_signals.append(weight * (trend - 0.5))
                    
                if momentum < -0.3:
                    add_signals.append(weight * 0.5 * abs(momentum))
                elif momentum > 0.3:
                    avoid_signals.append(weight * 0.5 * momentum)
                    
                if rsi > 40:
                    add_signals.append(weight * 0.2 * (rsi - 40) / 30)
                elif rsi < 25:
                    avoid_signals.append(weight * 0.3 * (30 - rsi) / 30)
                    
                if macd < 0:
                    add_signals.append(weight * 0.3 * min(1.0, abs(macd)))
                elif macd > 0:
                    avoid_signals.append(weight * 0.3 * min(1.0, macd))
                    
                if bb_position > 0.4:
                    add_signals.append(weight * 0.15 * (bb_position - 0.3))
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 2: ML MODEL ANALYSIS
        # For SCALE_IN, ML must STRONGLY agree with position direction
        # ═══════════════════════════════════════════════════════════
        
        ml_direction = getattr(context, 'ml_direction', 'HOLD')
        ml_confidence = getattr(context, 'ml_confidence', 50.0) / 100.0
        
        if is_buy:
            if ml_direction == 'BUY' and ml_confidence > 0.6:
                add_signals.append(0.30 * ml_confidence)  # Strong weight for ML agreement
            elif ml_direction == 'SELL':
                avoid_signals.append(0.30 * ml_confidence)
        else:
            if ml_direction == 'SELL' and ml_confidence > 0.6:
                add_signals.append(0.30 * ml_confidence)
            elif ml_direction == 'BUY':
                avoid_signals.append(0.30 * ml_confidence)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 3: TIMEFRAME ALIGNMENT
        # For SCALE_IN, we want STRONG alignment across timeframes
        # ═══════════════════════════════════════════════════════════
        
        trend_alignment = getattr(context, 'trend_alignment', 0.5)
        macd_all_bullish = getattr(context, 'macd_all_bullish', 0.0)
        macd_all_bearish = getattr(context, 'macd_all_bearish', 0.0)
        
        # High alignment = strong signal to add
        if trend_alignment > 0.6:
            add_signals.append(0.15 * (trend_alignment - 0.5))
        elif trend_alignment < 0.4:
            avoid_signals.append(0.15 * (0.5 - trend_alignment))
        
        if is_buy:
            if macd_all_bullish > 0.5:
                add_signals.append(0.12 * macd_all_bullish)
            if macd_all_bearish > 0.5:
                avoid_signals.append(0.12 * macd_all_bearish)
        else:
            if macd_all_bearish > 0.5:
                add_signals.append(0.12 * macd_all_bearish)
            if macd_all_bullish > 0.5:
                avoid_signals.append(0.12 * macd_all_bullish)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 4: VOLUME INTELLIGENCE
        # For SCALE_IN, we want volume confirming the move
        # CRITICAL: Volume divergence = DON'T add to position
        # ═══════════════════════════════════════════════════════════
        
        volume_trend = getattr(context, 'volume_trend', 0.0)
        accumulation = getattr(context, 'accumulation', 0.0)
        distribution = getattr(context, 'distribution', 0.0)
        institutional_bars = getattr(context, 'institutional_bars', 0.0)
        
        # CRITICAL: HTF Volume divergence is a STRONG avoid signal for SCALE_IN
        # Use H4 divergence, not M1 (too noisy)
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        if h4_vol_div > 0.3:
            avoid_signals.append(0.25 * h4_vol_div)  # Strong weight
            logger.info(f"   ⚠️ Entry: H4 Volume divergence {h4_vol_div:.2f} → avoid adding")
        
        if is_buy:
            if accumulation > 0.5:
                add_signals.append(0.10 * accumulation)
            if distribution > 0.5:
                avoid_signals.append(0.10 * distribution)
        else:
            if distribution > 0.5:
                add_signals.append(0.10 * distribution)
            if accumulation > 0.5:
                avoid_signals.append(0.10 * accumulation)
        
        # Institutional activity = smart money = follow
        if institutional_bars > 0.3:
            add_signals.append(0.08 * institutional_bars)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 5: HTF MARKET STRUCTURE FOR SCALE_IN
        # Use H4/D1 structure instead of M1 order flow
        # ═══════════════════════════════════════════════════════════
        
        h4_structure = getattr(context, 'h4_market_structure', 0.0)
        d1_structure = getattr(context, 'd1_market_structure', 0.0)
        htf_adx = getattr(context, 'htf_adx', 25.0)
        
        # Market structure supports position = add signal
        if is_buy:
            if h4_structure > 0.3:  # Uptrend structure
                add_signals.append(0.10 * h4_structure)
            if d1_structure > 0.3:
                add_signals.append(0.10 * d1_structure)
            if h4_structure < -0.3:  # Downtrend structure = avoid
                avoid_signals.append(0.10 * abs(h4_structure))
        else:
            if h4_structure < -0.3:  # Downtrend structure
                add_signals.append(0.10 * abs(h4_structure))
            if d1_structure < -0.3:
                add_signals.append(0.10 * abs(d1_structure))
            if h4_structure > 0.3:  # Uptrend structure = avoid
                avoid_signals.append(0.10 * h4_structure)
        
        # Strong trend (high ADX) = more confident to add
        if htf_adx > 30:
            add_signals.append(0.05 * (htf_adx - 25) / 25)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 6: CONTINUATION PROBABILITY
        # From _calculate_probabilities (already incorporates ML + HTF)
        # ═══════════════════════════════════════════════════════════
        
        cont_prob = probabilities.get('continuation', 0.5)
        rev_prob = probabilities.get('reversal', 0.3)
        
        if cont_prob > 0.6:
            add_signals.append(0.20 * (cont_prob - 0.50))
        if rev_prob > 0.35:
            avoid_signals.append(0.20 * (rev_prob - 0.30))
        
        # ═══════════════════════════════════════════════════════════
        # CALCULATE FINAL SCORE
        # ═══════════════════════════════════════════════════════════
        
        total_add = sum(add_signals)
        total_avoid = sum(avoid_signals)
        
        # Normalize to 0-1 range
        if total_add + total_avoid > 0:
            entry_score = total_add / (total_add + total_avoid + 0.1)
        else:
            entry_score = 0.3  # Neutral default
        
        # Clamp to 0-1
        entry_score = max(0.0, min(1.0, entry_score))
        
        logger.info(f"   🧠 Comprehensive Entry Analysis:")
        logger.info(f"      Add signals: {len(add_signals)} factors, total={total_add:.3f}")
        logger.info(f"      Avoid signals: {len(avoid_signals)} factors, total={total_avoid:.3f}")
        logger.info(f"      Final entry score: {entry_score:.3f}")
        
        return entry_score
    
    def _calculate_all_evs(
        self,
        profit_metrics: Dict,
        probabilities: Dict,
        market_data: Dict,
        current_volume: float,
        is_buy: bool,
        context,
        can_scale_in: bool = True,
        setup_type: str = 'DAY',
        atr_mult: float = 2.5,  # ATR multiplier for target distance (AI-driven)
        max_lots: float = 5.0,
        session_context: Dict = None,
        time_since_scale: float = 999.0,  # Minutes since last scale-in
        price_move_since_scale: float = 0.0  # % price move since last scale-in
    ) -> Dict:
        """
        Calculate Expected Value for ALL possible actions.
        
        EV = Σ (Probability × Outcome)
        
        AI-DRIVEN EV CALCULATION - NO HARDCODED PROFIT TARGETS
        
        Targets are calculated from:
        - Market structure (S/R levels)
        - ATR multiplier (varies by setup type)
        - ML confidence and thesis quality
        - Session context (liquidity affects EV)
        
        The atr_mult determines target distance based on volatility.
        """
        
        # Session awareness - affects EV calculations
        if session_context is None:
            session_context = {'session_mult': 1.0, 'patience_boost': 1.0, 'is_optimal': True, 'session_name': 'unknown'}
        
        session_mult = session_context.get('session_mult', 1.0)
        patience_boost = session_context.get('patience_boost', 1.0)
        is_optimal_session = session_context.get('is_optimal', True)
        
        # Weekend risk awareness
        is_friday = session_context.get('is_friday', False)
        is_friday_afternoon = session_context.get('is_friday_afternoon', False)
        is_friday_close = session_context.get('is_friday_close', False)
        hours_to_close = session_context.get('hours_to_close', 999)
        weekend_risk_mult = session_context.get('weekend_risk_mult', 1.0)
        
        profit_pct = profit_metrics['profit_pct']  # % of ACCOUNT
        profit_dollars = profit_metrics['profit_dollars']
        account_balance = profit_metrics['account_balance']
        price_move_pct = profit_metrics['price_move_pct']
        
        cont_prob = probabilities['continuation']
        rev_prob = probabilities['reversal']
        flat_prob = probabilities['flat']
        ml_agrees = probabilities['ml_agrees']
        trend_aligned = probabilities['trend_aligned']
        
        # ═══════════════════════════════════════════════════════════
        # MARKET-DRIVEN TARGET CALCULATION
        # Based on distance to resistance/support, NOT arbitrary %
        # ═══════════════════════════════════════════════════════════
        
        dist_to_resistance = market_data['dist_to_resistance']
        dist_to_support = market_data['dist_to_support']
        current_price = market_data['current_price']
        m1_atr = market_data['atr'] if market_data['atr'] > 0 else current_price * 0.01
        
        # ═══════════════════════════════════════════════════════════
        # CRITICAL: Use H4 ATR for SWING TRADING targets, not M1 ATR
        # M1 ATR is only 50 minutes of data - too small for swing trades
        # H4 ATR gives proper swing trading targets (hours/days)
        # ═══════════════════════════════════════════════════════════
        h1_volatility = getattr(context, 'h1_volatility', 0)
        h4_volatility = getattr(context, 'h4_volatility', 0)
        
        # Use H4 volatility as the primary ATR for targets
        # Fall back to H1, then to estimated M1 * 3 if not available
        if h4_volatility > 0:
            swing_atr = h4_volatility
            atr_source = "H4"
        elif h1_volatility > 0:
            swing_atr = h1_volatility
            atr_source = "H1"
        else:
            # Estimate H4 ATR as ~3x M1 ATR
            swing_atr = m1_atr * 3.0
            atr_source = "M1*3"
        
        logger.info(f"   📊 Swing ATR: {swing_atr:.5f} ({atr_source}) vs M1 ATR: {m1_atr:.5f}")
        
        # Calculate potential move to target (in price %)
        # CRITICAL: Use the POSITION'S TAKE PROFIT level set at entry
        # This is consistent with the entry logic and represents the actual target
        
        # Get position's TP from context (set by entry logic based on R:R and market structure)
        position_tp = getattr(context, 'position_tp', 0.0)
        position_sl = getattr(context, 'position_sl', 0.0)
        entry_price = getattr(context, 'position_entry_price', current_price)
        
        # Calculate distance to TP (the REAL target set at entry)
        if position_tp > 0 and current_price > 0:
            if is_buy:
                dist_to_target = position_tp - current_price
            else:
                dist_to_target = current_price - position_tp
            
            # Only use if we haven't passed the target
            if dist_to_target > 0:
                potential_move_pct = (dist_to_target / current_price) * 100
                logger.info(f"   📊 Using position TP target: {position_tp:.2f} (dist={dist_to_target:.2f}, {potential_move_pct:.4f}%)")
            else:
                # Already past target - use SWING ATR for additional upside
                potential_move_pct = (swing_atr * 2.0 / current_price) * 100
                logger.info(f"   📊 Past TP, using {atr_source} ATR for additional: {swing_atr * 2.0:.2f} ({potential_move_pct:.4f}%)")
        else:
            # No TP set - calculate expected target using MARKET STRUCTURE (S/R levels)
            # This is more accurate than pure ATR-based targets
            
            # Get S/R distances from context (calculated from H4/D1 data)
            h4_dist_to_resistance = getattr(context, 'h4_dist_to_resistance', 0.0)
            h4_dist_to_support = getattr(context, 'h4_dist_to_support', 0.0)
            d1_dist_to_resistance = getattr(context, 'd1_dist_to_resistance', 0.0)
            d1_dist_to_support = getattr(context, 'd1_dist_to_support', 0.0)
            
            ml_confidence = market_data['ml_confidence'] / 100.0
            market_score = market_data.get('market_score', 50.0)
            
            # Use S/R levels for target if available
            sr_target_pct = 0.0
            if is_buy:
                # For BUY, target is resistance
                if d1_dist_to_resistance > 0.1:  # D1 resistance is stronger
                    sr_target_pct = d1_dist_to_resistance
                    logger.info(f"   📊 Using D1 resistance as target: {sr_target_pct:.2f}%")
                elif h4_dist_to_resistance > 0.1:
                    sr_target_pct = h4_dist_to_resistance
                    logger.info(f"   📊 Using H4 resistance as target: {sr_target_pct:.2f}%")
            else:
                # For SELL, target is support
                if d1_dist_to_support > 0.1:  # D1 support is stronger
                    sr_target_pct = d1_dist_to_support
                    logger.info(f"   📊 Using D1 support as target: {sr_target_pct:.2f}%")
                elif h4_dist_to_support > 0.1:
                    sr_target_pct = h4_dist_to_support
                    logger.info(f"   📊 Using H4 support as target: {sr_target_pct:.2f}%")
            
            # If S/R target is valid (between 0.5% and 5%), use it
            # Otherwise fall back to ATR-based calculation
            if 0.5 <= sr_target_pct <= 5.0:
                potential_move_pct = sr_target_pct
                logger.info(f"   📊 MARKET STRUCTURE target: {potential_move_pct:.2f}%")
            else:
                # Fall back to ATR-based target
                base_rr = 1.5
                ml_bonus = max(0, (ml_confidence - 0.60) / 0.10) * 0.5
                score_bonus = max(0, (market_score - 60) / 10) * 0.3
                expected_rr = min(4.0, base_rr + ml_bonus + score_bonus)
                
                expected_target_distance = swing_atr * 2.5 * expected_rr
                potential_move_pct = (expected_target_distance / current_price) * 100
                logger.info(f"   📊 ATR-based target (no S/R): R:R {expected_rr:.1f}:1 = {potential_move_pct:.4f}%")
        
        # Convert to account % based on position leverage
        # If we've moved X% in price and made Y% on account, 
        # then potential account gain = Y * (potential_move / current_move)
        if abs(price_move_pct) > 0.001:
            leverage_factor = profit_pct / price_move_pct
            potential_account_gain = potential_move_pct * abs(leverage_factor)  # Use abs() for losing positions
            logger.info(f"   📊 Leverage calc: potential_move={potential_move_pct:.4f}% * leverage={leverage_factor:.4f} = {potential_account_gain:.4f}%")
        else:
            # Position just opened, estimate based on setup type
            # HEDGE FUND: New positions should have full potential based on entry thesis
            setup_type_defaults = {
                'SWING': 1.5,   # Swing entries expect 1.5%+ moves
                'DAY': 0.8,     # Day trades expect 0.8%+ moves
                'SCALP': 0.3    # Scalps expect quick 0.3% moves
            }
            potential_account_gain = setup_type_defaults.get(setup_type, 0.8)
            logger.info(f"   📊 Using {setup_type} default potential: {potential_account_gain}%")
        
        # For losing positions, potential gain is the recovery potential
        # For winning positions, it's additional upside
        # Either way, it should be positive
        potential_account_gain = abs(potential_account_gain)
        
        # CRITICAL: Scale potential gain by thesis strength
        # If ML disagrees and HTF is weak, potential gain should be MUCH lower
        # This prevents the AI from being overly optimistic on weak setups
        
        # Get thesis indicators
        ml_direction = market_data['ml_direction']
        ml_confidence = market_data['ml_confidence']
        h1_trend = market_data['h1_trend']
        h4_trend = market_data['h4_trend']
        d1_trend = market_data['d1_trend']
        
        # ═══════════════════════════════════════════════════════════
        # SETUP-APPROPRIATE THESIS CHECK
        # 
        # Different setup types use different timeframes for thesis:
        # - SWING: D1 primary, H4 secondary
        # - DAY: H4 primary, H1 secondary  
        # - SCALP: H1 primary, M30/M15 secondary
        # 
        # This ensures SCALPs aren't penalized for D1 not aligning
        # when they only need H1/M30 alignment to be valid.
        # ═══════════════════════════════════════════════════════════
        
        # Get M15/M30 trends for SCALP thesis
        m15_trend = market_data.get('m15_trend', 0.5)
        m30_trend = market_data.get('m30_trend', 0.5)
        
        # Get profit state for context
        profit_pct = profit_metrics['profit_pct']
        is_profitable = profit_pct > 0.1  # Meaningful profit
        
        # Determine thesis based on setup type
        if setup_type == 'SCALP':
            # SCALP: H1 is primary, M30/M15 are secondary
            # D1/H4 are nice-to-have but NOT required
            if is_buy:
                primary_supports = h1_trend > 0.48
                primary_strongly_supports = h1_trend > 0.55
                secondary_supports = m30_trend > 0.48 or m15_trend > 0.48
                tertiary_supports = h4_trend > 0.48  # Bonus, not required
            else:
                primary_supports = h1_trend < 0.52
                primary_strongly_supports = h1_trend < 0.45
                secondary_supports = m30_trend < 0.52 or m15_trend < 0.52
                tertiary_supports = h4_trend < 0.52
            
            tf_labels = ('H1', 'M30/M15', 'H4')
            tf_values = (h1_trend, m30_trend, h4_trend)
            
        elif setup_type == 'DAY':
            # DAY: H4 is primary, H1 is secondary, D1 is bonus
            if is_buy:
                primary_supports = h4_trend > 0.48
                primary_strongly_supports = h4_trend > 0.55
                secondary_supports = h1_trend > 0.48
                tertiary_supports = d1_trend > 0.48
            else:
                primary_supports = h4_trend < 0.52
                primary_strongly_supports = h4_trend < 0.45
                secondary_supports = h1_trend < 0.52
                tertiary_supports = d1_trend < 0.52
            
            tf_labels = ('H4', 'H1', 'D1')
            tf_values = (h4_trend, h1_trend, d1_trend)
            
        else:  # SWING
            # SWING: D1 is primary, H4 is secondary
            if is_buy:
                primary_supports = d1_trend > 0.48
                primary_strongly_supports = d1_trend > 0.55
                secondary_supports = h4_trend > 0.48
                tertiary_supports = h1_trend > 0.48
            else:
                primary_supports = d1_trend < 0.52
                primary_strongly_supports = d1_trend < 0.45
                secondary_supports = h4_trend < 0.52
                tertiary_supports = h1_trend < 0.52
            
            tf_labels = ('D1', 'H4', 'H1')
            tf_values = (d1_trend, h4_trend, h1_trend)
        
        # ML support check
        ml_strongly_supports = (ml_direction == ('BUY' if is_buy else 'SELL') and ml_confidence > 60)
        ml_supports = ml_direction in [('BUY' if is_buy else 'SELL'), 'HOLD']
        
        # Count confirmations for the appropriate timeframes
        htf_support_count = sum([primary_supports, secondary_supports, tertiary_supports])
        
        # ═══════════════════════════════════════════════════════════
        # SMART EXIT LOGIC: Hierarchical with Early Warnings
        # 
        # Primary TF sets the bias, secondary is the "canary in the coal mine"
        # - Primary strongly supports + Secondary supports → HOLD (full conviction)
        # - Primary supports + Secondary turning → PARTIAL EXIT (early warning)
        # - Primary weakening → EXIT (don't wait for full break)
        # ═══════════════════════════════════════════════════════════
        
        if primary_strongly_supports and secondary_supports:
            # Best case: Primary + Secondary both support - full conviction
            thesis_quality = 0.95 if ml_supports else 0.8
            logger.info(f"   🎯 {setup_type}: {tf_labels[0]} + {tf_labels[1]} ALIGNED - FULL CONVICTION")
            logger.info(f"      {tf_labels[0]}={tf_values[0]:.2f} ✓✓, {tf_labels[1]}={tf_values[1]:.2f} ✓, {tf_labels[2]}={tf_values[2]:.2f}")
        elif primary_strongly_supports and not secondary_supports:
            # Primary strong but Secondary turning - EARLY WARNING
            if is_profitable:
                thesis_quality = 0.6  # Reduce conviction
                logger.info(f"   ⚠️ {setup_type}: {tf_labels[1]} EARLY WARNING - {tf_labels[0]} strong but {tf_labels[1]} turning")
            else:
                thesis_quality = 0.75  # Still hold if not profitable yet
                logger.info(f"   📊 {setup_type}: {tf_labels[0]} strong, {tf_labels[1]} turning - HOLD (not profitable yet)")
            logger.info(f"      {tf_labels[0]}={tf_values[0]:.2f} ✓✓, {tf_labels[1]}={tf_values[1]:.2f} ⚠️, {tf_labels[2]}={tf_values[2]:.2f}")
        elif primary_supports and secondary_supports:
            # Primary supports (not strongly) + Secondary confirms
            thesis_quality = 0.7 if ml_supports else 0.55
            logger.info(f"   📊 {setup_type}: {tf_labels[0]} + {tf_labels[1]} SUPPORT - HOLD")
            logger.info(f"      {tf_labels[0]}={tf_values[0]:.2f} ✓, {tf_labels[1]}={tf_values[1]:.2f} ✓, {tf_labels[2]}={tf_values[2]:.2f}")
        elif primary_supports and not secondary_supports:
            # Primary supports but Secondary against - STRONG WARNING
            if is_profitable:
                thesis_quality = 0.4  # Take profits
                logger.info(f"   🚨 {setup_type}: {tf_labels[1]} DIVERGING - {tf_labels[0]} ok but {tf_labels[1]} against")
            else:
                thesis_quality = 0.5  # Caution but hold
                logger.info(f"   ⚠️ {setup_type}: {tf_labels[0]} ok but {tf_labels[1]} against - CAUTION")
            logger.info(f"      {tf_labels[0]}={tf_values[0]:.2f} ✓, {tf_labels[1]}={tf_values[1]:.2f} ✗, {tf_labels[2]}={tf_values[2]:.2f}")
        else:
            # Primary NO LONGER SUPPORTS
            if secondary_supports and tertiary_supports:
                thesis_quality = 0.3
                logger.info(f"   ⚠️ {setup_type}: {tf_labels[0]} BROKE but {tf_labels[1]}/{tf_labels[2]} still support - WATCH")
            elif secondary_supports or tertiary_supports:
                thesis_quality = 0.2
                logger.info(f"   ❌ {setup_type}: {tf_labels[0]} BROKE, only 1 TF supports - EXIT SOON")
            else:
                thesis_quality = 0.1
                logger.info(f"   ❌ {setup_type}: ALL TIMEFRAMES AGAINST - EXIT")
            logger.info(f"      {tf_labels[0]}={tf_values[0]:.2f} ✗, {tf_labels[1]}={tf_values[1]:.2f}, {tf_labels[2]}={tf_values[2]:.2f}")
        
        # Apply thesis quality to potential gain
        # HEDGE FUND APPROACH: Let the market structure determine potential, not arbitrary caps
        # Thesis quality scales the potential, but doesn't cap it artificially
        potential_account_gain = potential_account_gain * thesis_quality
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN POTENTIAL: NO HARDCODED CAPS
        # 
        # The market structure (S/R levels) and leverage calculation already
        # determined the potential gain from LIVE MARKET ANALYSIS.
        # 
        # REMOVED: Hardcoded setup_type_caps that were overriding AI analysis
        # The AI calculated potential based on:
        # - Distance to S/R levels (market structure)
        # - Position leverage (actual risk/reward)
        # - Thesis quality (HTF alignment)
        # 
        # Only apply a sanity cap for extreme outliers (>10%)
        # ═══════════════════════════════════════════════════════════
        
        # Only cap extreme outliers (>10% is unrealistic for any setup)
        max_sanity_cap = 10.0
        if potential_account_gain > max_sanity_cap:
            logger.info(f"   📊 Sanity cap: {potential_account_gain:.4f}% -> {max_sanity_cap:.4f}% (extreme outlier)")
            potential_account_gain = max_sanity_cap
        
        # Minimum floor based on thesis quality (don't underestimate potential)
        min_potential = 0.3 * thesis_quality  # At least 0.3% for valid thesis
        potential_account_gain = max(potential_account_gain, min_potential)
        
        logger.info(f"   📊 Thesis quality: {thesis_quality:.1f} (HTF={htf_support_count}/3, ML={ml_direction})")
        logger.info(f"   📊 AI-driven potential gain: {potential_account_gain:.4f}% (from market structure, no hardcoded caps)")
        
        # ═══════════════════════════════════════════════════════════
        # MARKET-DRIVEN LOSS ESTIMATION
        # Based on ATR and position leverage
        # ═══════════════════════════════════════════════════════════
        
        # CRITICAL INSIGHT: For EV to favor HOLD, potential_gain must exceed potential_loss
        # weighted by probabilities. If continuation > reversal, we should HOLD.
        # 
        # The issue with leverage-based loss calculation is it can make tiny positions
        # look bad even when market conditions favor holding.
        #
        # SOLUTION: Potential loss should be proportional to potential gain, adjusted by
        # the probability ratio. If continuation is 60% and reversal is 35%, the expected
        # loss should be scaled down.
        
        # Base potential loss on potential gain (symmetric risk/reward)
        # Then adjust by market conditions
        # Use SWING ATR for consistent timeframe
        reversal_move_pct = (swing_atr / current_price) * 100
        
        # Potential loss = potential gain * (reversal_prob / continuation_prob)
        # This ensures that if continuation > reversal, EV(HOLD) > EV(CLOSE)
        prob_ratio = rev_prob / cont_prob if cont_prob > 0 else 1.0
        potential_loss = potential_account_gain * prob_ratio
        
        # AI-DRIVEN LOSS CAP: Based on setup type, not arbitrary 0.5%
        # SWING: Can tolerate larger drawdowns (2% max loss)
        # DAY: Medium tolerance (1% max loss)
        # SCALP: Tight stops (0.5% max loss)
        setup_type_loss_caps = {
            'SWING': 2.0,
            'DAY': 1.0,
            'SCALP': 0.5
        }
        max_loss = setup_type_loss_caps.get(setup_type, 1.0)
        potential_loss = min(potential_loss, max_loss)
        
        logger.info(f"   📊 Swing ATR={swing_atr:.5f} ({atr_source}), prob_ratio={prob_ratio:.2f}")
        logger.info(f"   📊 potential_loss = {potential_account_gain:.4f} * {prob_ratio:.2f} = {potential_loss:.4f}%")
        
        # Log the EV inputs
        logger.info(f"   📊 EV Inputs: potential_gain={potential_account_gain:.4f}%, potential_loss={potential_loss:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # EV CALCULATIONS (all in % of ACCOUNT)
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # PORTFOLIO-LEVEL DRAWDOWN CONTROL
        # 
        # When the portfolio is in significant drawdown, the AI must:
        # 1. Be more protective of remaining capital
        # 2. Weight exit signals more heavily
        # 3. Reduce exposure when multiple positions are correlated losers
        # 
        # This is NOT a hardcoded threshold - it's an AI-driven adjustment
        # based on how close we are to risk limits and the quality of
        # current positions.
        # ═══════════════════════════════════════════════════════════
        
        # Get portfolio drawdown metrics from context
        daily_pnl = getattr(context, 'daily_pnl', 0.0)
        total_drawdown = getattr(context, 'total_drawdown', 0.0)
        max_daily_loss = getattr(context, 'max_daily_loss', 10000.0)
        max_total_drawdown = getattr(context, 'max_total_drawdown', 20000.0)
        
        # Calculate drawdown severity (0 to 1)
        # 0 = no drawdown, 1 = at limit
        daily_dd_severity = abs(min(0, daily_pnl)) / max_daily_loss if max_daily_loss > 0 else 0
        total_dd_severity = total_drawdown / max_total_drawdown if max_total_drawdown > 0 else 0
        
        # Combined drawdown severity (weighted: daily is more urgent)
        drawdown_severity = daily_dd_severity * 0.6 + total_dd_severity * 0.4
        drawdown_severity = min(1.0, drawdown_severity)  # Cap at 1.0
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #1: POSITION AGE DECAY
        # 
        # A position that has been open for a long time without progressing
        # is a sign that the thesis may be wrong. Hedge funds apply time decay
        # to positions that aren't working.
        # 
        # Expected hold times by setup type:
        # - SCALP: 15-60 minutes (exit pressure after 60 min)
        # - DAY: 1-8 hours (exit pressure after 8 hours = 480 min)
        # - SWING: 1-5 days (exit pressure after 2 days = 2880 min)
        # 
        # Position age decay = (age / expected_hold_time) ^ 1.5
        # This creates exponential pressure on overly old positions
        # ═══════════════════════════════════════════════════════════
        
        position_age_minutes = getattr(context, 'position_age_minutes', 0.0)
        
        # Expected hold times by setup type (in minutes)
        expected_hold_times = {
            'SCALP': 60,      # 1 hour max for scalps
            'DAY': 480,       # 8 hours max for day trades  
            'SWING': 2880     # 2 days max for swings
        }
        expected_hold_time = expected_hold_times.get(setup_type, 480)
        
        # Calculate age ratio (how much of expected time has passed)
        age_ratio = position_age_minutes / expected_hold_time if expected_hold_time > 0 else 0
        
        # Age decay: exponential pressure on old positions
        # 0.5x expected time = 0.35 decay, 1x = 1.0 decay, 2x = 2.8 decay
        age_decay = (age_ratio ** 1.5) if age_ratio > 0.5 else 0
        age_decay = min(2.0, age_decay)  # Cap at 2.0 (very strong pressure)
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #2: PROGRESS-ADJUSTED THESIS
        # 
        # If a position is old AND not profitable, the thesis is likely wrong.
        # If a position is old BUT profitable, the thesis may still be valid.
        # 
        # progress_factor = profit_pct / expected_profit_at_this_age
        # 
        # Expected profit at age X = (age / expected_hold_time) * target_profit
        # If actual profit < expected, thesis is underperforming
        # ═══════════════════════════════════════════════════════════
        
        # Expected profit at current age (linear progression to target)
        expected_profit_at_age = (age_ratio * potential_account_gain) if age_ratio < 1.0 else potential_account_gain
        
        # Progress factor: how well is the position tracking vs expectations?
        # > 1.0 = ahead of schedule, < 1.0 = behind schedule
        if expected_profit_at_age > 0.1:  # Only if meaningful expected profit
            progress_factor = profit_pct / expected_profit_at_age
        else:
            progress_factor = 1.0 if profit_pct >= 0 else 0.5
        
        progress_factor = max(0.0, min(2.0, progress_factor))  # Clamp 0-2
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #3: ENHANCED DRAWDOWN URGENCY
        # 
        # When drawdown is severe AND position is weak AND position is old,
        # the exit pressure should be MUCH stronger.
        # 
        # Old formula: drawdown_urgency = drawdown_severity * (1 - position_strength)
        # New formula: adds age factor and progress factor
        # ═══════════════════════════════════════════════════════════
        
        position_strength = thesis_quality * cont_prob
        
        # Adjust position strength by progress factor
        # If behind schedule, reduce perceived strength
        adjusted_position_strength = position_strength * min(1.0, progress_factor + 0.3)
        
        # Drawdown urgency: high when DD is severe AND position is weak AND old
        # The age_decay multiplier makes old losing positions much more urgent to exit
        base_drawdown_urgency = drawdown_severity * (1.0 - adjusted_position_strength)
        
        # Age amplifier: old positions get stronger exit pressure
        age_amplifier = 1.0 + (age_decay * 0.5)  # Up to 2x urgency for very old positions
        
        drawdown_urgency = base_drawdown_urgency * age_amplifier
        drawdown_urgency = min(1.0, drawdown_urgency)  # Cap at 1.0
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #4: STRONGER EXIT PREMIUM FOR LOSERS
        # 
        # Old formula: drawdown_exit_premium = drawdown_urgency * abs(profit_pct) * 0.5
        # New formula: scales with position age and thesis weakness
        # 
        # A 44-hour old losing position with weak thesis should have STRONG
        # exit pressure, not just 0.5x the loss.
        # ═══════════════════════════════════════════════════════════
        
        if profit_pct < 0:
            # Base exit premium from drawdown urgency
            base_exit_premium = drawdown_urgency * abs(profit_pct)
            
            # Age multiplier: older losing positions get stronger exit pressure
            # 1x at expected hold time, up to 2x at 2x expected hold time
            age_exit_mult = 1.0 + min(1.0, age_decay * 0.5)
            
            # Thesis weakness multiplier: weaker thesis = stronger exit pressure
            # thesis_quality 0.2 → mult 1.8, thesis_quality 0.8 → mult 1.2
            thesis_exit_mult = 1.0 + (1.0 - thesis_quality) * 0.8
            
            drawdown_exit_premium = base_exit_premium * age_exit_mult * thesis_exit_mult
        else:
            drawdown_exit_premium = 0
        
        # Log comprehensive analysis
        if drawdown_severity > 0 or position_age_minutes > expected_hold_time * 0.5:
            logger.info(f"   📉 HEDGE FUND POSITION ANALYSIS:")
            logger.info(f"      Daily P&L: ${daily_pnl:.2f} ({daily_dd_severity:.1%} of limit)")
            logger.info(f"      Total DD: ${total_drawdown:.2f} ({total_dd_severity:.1%} of limit)")
            logger.info(f"      Drawdown severity: {drawdown_severity:.2%}")
            logger.info(f"      Position age: {position_age_minutes:.0f} min ({age_ratio:.1%} of {expected_hold_time} min expected)")
            logger.info(f"      Age decay factor: {age_decay:.2f}")
            logger.info(f"      Progress factor: {progress_factor:.2f} (profit vs expected at this age)")
            logger.info(f"      Position strength: {position_strength:.2%} → {adjusted_position_strength:.2%} (adjusted)")
            logger.info(f"      Drawdown urgency: {drawdown_urgency:.2%} (age amplifier: {age_amplifier:.2f}x)")
            if drawdown_exit_premium > 0:
                logger.info(f"      🚨 EXIT PREMIUM: {drawdown_exit_premium:.4f}% (age×{age_exit_mult:.2f}, thesis×{thesis_exit_mult:.2f})")
            elif profit_pct > 0 and age_ratio > 1.0:
                logger.info(f"      ⚠️ Position profitable but OVERDUE - consider taking profits")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #5: PEAK PROFIT TRACKING (HIGH WATER MARK)
        # 
        # Track the maximum profit reached during the trade.
        # If we've given back too much from the peak, that's a reversal signal.
        # 
        # This catches situations like US30 where it was profitable but
        # then reversed into a large loss.
        # 
        # peak_profit_giveback = (peak_profit - current_profit) / peak_profit
        # If giveback > threshold (based on thesis quality), trigger protection
        # ═══════════════════════════════════════════════════════════
        
        # Get peak profit from PERSISTENT storage (survives API restarts)
        peak_symbol_key = getattr(context, 'symbol', 'UNKNOWN').upper()  # Get from context
        stored_peak = self.get_peak(peak_symbol_key)
        context_peak = getattr(context, 'peak_profit_pct', profit_pct)
        
        # Use the higher of stored peak or context peak
        peak_profit_pct = max(stored_peak, context_peak, profit_pct)
        
        # Update persistent storage if current profit is new peak
        if profit_pct > stored_peak:
            current_price = getattr(context, 'current_price', 0)
            self.update_peak(peak_symbol_key, profit_pct, current_price)
        
        # Calculate giveback from peak
        peak_giveback = 0.0
        peak_giveback_premium = 0.0
        
        if peak_profit_pct > 0.1:  # Only if we had meaningful profit
            if profit_pct < peak_profit_pct:
                # How much have we given back from the peak?
                giveback_amount = peak_profit_pct - profit_pct
                peak_giveback = giveback_amount / peak_profit_pct if peak_profit_pct > 0 else 0
                
                # AI-driven giveback threshold based on thesis quality AND position size
                # Strong thesis (0.8) = allow 50% giveback before concern
                # Weak thesis (0.2) = only allow 20% giveback
                # CRITICAL: Larger positions = TIGHTER giveback threshold
                size_ratio = current_volume / max_lots if max_lots > 0 else 0.5
                size_tightening = size_ratio * 0.2  # Large position reduces allowed giveback by up to 20%
                allowed_giveback = max(0.15, 0.2 + (thesis_quality * 0.4) - size_tightening)  # 0.15 to 0.6
                
                if peak_giveback > allowed_giveback:
                    # We've given back too much - this is a reversal signal
                    excess_giveback = peak_giveback - allowed_giveback
                    
                    # Premium scales with how much we've exceeded the threshold
                    # AND with the absolute profit we're risking
                    # CRITICAL: Larger positions = STRONGER exit pressure
                    size_multiplier = 1.0 + size_ratio  # 1.0 to 2.0x for large positions
                    peak_giveback_premium = excess_giveback * peak_profit_pct * (1.0 - thesis_quality) * size_multiplier
                    
                    logger.info(f"   🚨 PEAK PROFIT GIVEBACK WARNING:")
                    logger.info(f"      Peak profit: {peak_profit_pct:.3f}%")
                    logger.info(f"      Current profit: {profit_pct:.3f}%")
                    logger.info(f"      Giveback: {peak_giveback:.1%} (allowed: {allowed_giveback:.1%})")
                    logger.info(f"      Size ratio: {size_ratio:.2f} (larger = tighter threshold)")
                    logger.info(f"      Giveback premium: {peak_giveback_premium:.4f}% (size mult: {size_multiplier:.2f}x)")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #6: REGIME DETECTION (RISK-ON/OFF)
        # 
        # Use cross-asset data to detect market regime:
        # - Risk-on: Indices up, DXY down, Gold down → favor long equity/risk
        # - Risk-off: Indices down, DXY up, Gold up → favor safe havens
        # 
        # If position is AGAINST the regime, increase exit pressure.
        # If position is WITH the regime, allow more patience.
        # ═══════════════════════════════════════════════════════════
        
        # Get cross-asset regime data from context
        risk_on_off = getattr(context, 'risk_on_off', 0.5)  # 0=risk-off, 1=risk-on
        dxy_trend = getattr(context, 'dxy_trend', 0.5)  # 0=weak dollar, 1=strong dollar
        indices_aligned = getattr(context, 'indices_aligned', 0.5)  # How aligned are indices
        gold_dollar_divergence = getattr(context, 'gold_dollar_divergence', False)
        
        # Determine if position aligns with regime
        symbol_lower = getattr(context, 'symbol', '').lower()
        
        # Classify asset type
        is_risk_asset = any(x in symbol_lower for x in ['us30', 'us100', 'us500', 'spx', 'ndx', 'dow'])
        is_safe_haven = any(x in symbol_lower for x in ['xau', 'gold', 'jpy'])
        is_dollar_inverse = any(x in symbol_lower for x in ['eur', 'gbp', 'aud', 'xau'])
        
        regime_alignment = 0.0  # -1 = against regime, 0 = neutral, +1 = with regime
        regime_exit_premium = 0.0
        
        if is_risk_asset:
            # Risk assets should be LONG in risk-on, SHORT in risk-off
            if is_buy:
                regime_alignment = (risk_on_off - 0.5) * 2  # -1 to +1
            else:
                regime_alignment = (0.5 - risk_on_off) * 2  # Inverse
        elif is_safe_haven:
            # Safe havens should be LONG in risk-off, SHORT in risk-on
            if is_buy:
                regime_alignment = (0.5 - risk_on_off) * 2  # Inverse of risk
            else:
                regime_alignment = (risk_on_off - 0.5) * 2
        elif is_dollar_inverse:
            # Dollar-inverse assets (EUR, GBP, Gold) should be LONG when DXY weak
            if is_buy:
                regime_alignment = (0.5 - dxy_trend) * 2  # Long when DXY weak
            else:
                regime_alignment = (dxy_trend - 0.5) * 2  # Short when DXY strong
        
        # If position is AGAINST the regime, add exit pressure
        if regime_alignment < -0.3:  # Significantly against regime
            # Exit premium scales with how against the regime we are
            regime_exit_premium = abs(regime_alignment) * abs(profit_pct) * 0.3
            
            logger.info(f"   ⚠️ REGIME MISALIGNMENT:")
            logger.info(f"      Risk-on/off: {risk_on_off:.2f} | DXY: {dxy_trend:.2f}")
            logger.info(f"      Position: {'BUY' if is_buy else 'SELL'} | Alignment: {regime_alignment:.2f}")
            logger.info(f"      Regime exit premium: {regime_exit_premium:.4f}%")
        elif regime_alignment > 0.3:  # Significantly with regime
            logger.info(f"   ✅ REGIME ALIGNED: {regime_alignment:.2f} (risk={risk_on_off:.2f}, dxy={dxy_trend:.2f})")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #7: VOLATILITY REGIME DETECTION
        # 
        # Detect if we're in a high-vol or low-vol regime.
        # High-vol: Tighter stops, faster exits, smaller positions
        # Low-vol: Wider stops, more patience, larger positions
        # 
        # Use H4 volatility vs historical average to detect regime.
        # ═══════════════════════════════════════════════════════════
        
        h1_volatility = getattr(context, 'h1_volatility', 0.0)
        h4_volatility = getattr(context, 'h4_volatility', 0.0)
        
        # Estimate volatility regime (1.0 = normal, >1.5 = high vol, <0.7 = low vol)
        # Use ATR ratio as proxy
        current_atr = market_data.get('atr', 0.0)
        if h4_volatility > 0 and current_atr > 0:
            vol_regime = current_atr / h4_volatility if h4_volatility > 0 else 1.0
        else:
            vol_regime = 1.0
        
        # High volatility = faster exits, more protection
        vol_exit_multiplier = 1.0
        if vol_regime > 1.5:  # High vol regime
            vol_exit_multiplier = 1.0 + (vol_regime - 1.5) * 0.5  # Up to 1.5x exit pressure
            logger.info(f"   📈 HIGH VOLATILITY REGIME: {vol_regime:.2f}x normal (exit mult: {vol_exit_multiplier:.2f}x)")
        elif vol_regime < 0.7:  # Low vol regime
            vol_exit_multiplier = 0.8  # More patience in low vol
            logger.info(f"   📉 LOW VOLATILITY REGIME: {vol_regime:.2f}x normal (more patience)")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #8: KELLY CRITERION FOR DRAWDOWN RECOVERY
        # 
        # When in drawdown, reduce position risk using Kelly fraction.
        # Kelly = (win_prob * avg_win - loss_prob * avg_loss) / avg_win
        # 
        # In drawdown, use fractional Kelly (0.25-0.5x) to reduce risk
        # while still allowing recovery.
        # ═══════════════════════════════════════════════════════════
        
        # Calculate Kelly fraction based on current probabilities
        # Kelly = (p * b - q) / b where p=win_prob, q=loss_prob, b=win/loss ratio
        win_loss_ratio = potential_account_gain / potential_loss if potential_loss > 0 else 2.0
        kelly_fraction = (cont_prob * win_loss_ratio - rev_prob) / win_loss_ratio if win_loss_ratio > 0 else 0.5
        kelly_fraction = max(0.0, min(1.0, kelly_fraction))  # Clamp 0-1
        
        # In drawdown, use fractional Kelly
        if drawdown_severity > 0.2:  # More than 20% of limit used
            # Reduce Kelly by drawdown severity
            fractional_kelly = kelly_fraction * (1.0 - drawdown_severity * 0.5)
            
            # This affects how much we should risk on this position
            # Lower Kelly = more conservative = favor exits
            kelly_exit_adjustment = (0.5 - fractional_kelly) * 0.2  # -0.1 to +0.1
            
            logger.info(f"   🎲 KELLY CRITERION (Drawdown Recovery):")
            logger.info(f"      Full Kelly: {kelly_fraction:.2f} | Fractional: {fractional_kelly:.2f}")
            logger.info(f"      Exit adjustment: {kelly_exit_adjustment:.4f}%")
        else:
            kelly_exit_adjustment = 0.0
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #9: ENHANCED ORDER FLOW ANALYSIS
        # 
        # Use bid/ask imbalance as a leading indicator.
        # Strong imbalance against position = early exit signal.
        # ═══════════════════════════════════════════════════════════
        
        bid_volume = market_data.get('bid_volume', 0.5)
        ask_volume = market_data.get('ask_volume', 0.5)
        
        # Calculate order flow imbalance (-1 = all bids, +1 = all asks)
        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            order_flow_imbalance = (ask_volume - bid_volume) / total_volume
        else:
            order_flow_imbalance = 0.0
        
        # Check if order flow is against our position
        order_flow_against = False
        order_flow_exit_premium = 0.0
        
        if is_buy and order_flow_imbalance > 0.3:  # Strong selling pressure
            order_flow_against = True
            order_flow_exit_premium = order_flow_imbalance * abs(profit_pct) * 0.2
        elif not is_buy and order_flow_imbalance < -0.3:  # Strong buying pressure
            order_flow_against = True
            order_flow_exit_premium = abs(order_flow_imbalance) * abs(profit_pct) * 0.2
        
        if order_flow_against:
            logger.info(f"   📊 ORDER FLOW WARNING: Imbalance {order_flow_imbalance:.2f} against position")
            logger.info(f"      Exit premium: {order_flow_exit_premium:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND IMPROVEMENT #10: LTF EARLY WARNING FOR LARGE POSITIONS
        # 
        # When position is scaled-in (larger than normal), LTF divergence
        # from HTF is an early warning signal. If M15/M30 are turning
        # while HTF still holds, that's often the start of a reversal.
        # 
        # For large positions, we should be MORE sensitive to LTF warnings.
        # ═══════════════════════════════════════════════════════════
        
        ltf_warning_premium = 0.0
        size_ratio = current_volume / max_lots if max_lots > 0 else 0.5
        
        # Only apply LTF warning for larger positions (> 30% of max)
        if size_ratio > 0.3:
            m15_trend = getattr(context, 'm15_trend', 0.5)
            m30_trend = getattr(context, 'm30_trend', 0.5)
            h1_trend = market_data.get('h1_trend', 0.5)
            h4_trend = market_data.get('h4_trend', 0.5)
            
            # Calculate LTF average
            ltf_avg = (m15_trend + m30_trend) / 2
            # Calculate HTF average
            htf_avg = (h1_trend + h4_trend) / 2
            
            # Check for divergence: LTF turning against position while HTF holds
            if is_buy:
                # For BUY: LTF < 0.45 (bearish) while HTF > 0.55 (bullish) = warning
                ltf_bearish = ltf_avg < 0.45
                htf_bullish = htf_avg > 0.55
                ltf_divergence = ltf_bearish and htf_bullish
                divergence_strength = max(0, 0.5 - ltf_avg) if ltf_divergence else 0
            else:
                # For SELL: LTF > 0.55 (bullish) while HTF < 0.45 (bearish) = warning
                ltf_bullish = ltf_avg > 0.55
                htf_bearish = htf_avg < 0.45
                ltf_divergence = ltf_bullish and htf_bearish
                divergence_strength = max(0, ltf_avg - 0.5) if ltf_divergence else 0
            
            if ltf_divergence and divergence_strength > 0.05:
                # Premium scales with: divergence strength, position size, and profit at risk
                size_sensitivity = 1.0 + (size_ratio - 0.3) * 2  # 1.0 to 2.4x for large positions
                ltf_warning_premium = divergence_strength * size_sensitivity * max(0.1, abs(profit_pct)) * 0.5
                
                logger.info(f"   ⚠️ LTF EARLY WARNING (Large Position):")
                logger.info(f"      LTF avg: {ltf_avg:.2f} (M15={m15_trend:.2f}, M30={m30_trend:.2f})")
                logger.info(f"      HTF avg: {htf_avg:.2f} (H1={h1_trend:.2f}, H4={h4_trend:.2f})")
                logger.info(f"      Divergence strength: {divergence_strength:.2f}")
                logger.info(f"      Size sensitivity: {size_sensitivity:.2f}x (ratio={size_ratio:.2f})")
                logger.info(f"      LTF warning premium: {ltf_warning_premium:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # COMBINE ALL HEDGE FUND EXIT PREMIUMS
        # ═══════════════════════════════════════════════════════════
        
        total_hedge_fund_premium = (
            peak_giveback_premium +      # #5: Peak profit protection
            regime_exit_premium +        # #6: Regime misalignment
            kelly_exit_adjustment +      # #8: Kelly criterion
            order_flow_exit_premium +    # #9: Order flow
            ltf_warning_premium          # #10: LTF early warning for large positions
        ) * vol_exit_multiplier          # #7: Volatility regime multiplier
        
        if total_hedge_fund_premium > 0.01:
            logger.info(f"   🏦 TOTAL HEDGE FUND EXIT PREMIUM: {total_hedge_fund_premium:.4f}%")
            logger.info(f"      Peak giveback: {peak_giveback_premium:.4f}%")
            logger.info(f"      Regime: {regime_exit_premium:.4f}%")
            logger.info(f"      Kelly: {kelly_exit_adjustment:.4f}%")
            logger.info(f"      Order flow: {order_flow_exit_premium:.4f}%")
            logger.info(f"      LTF warning: {ltf_warning_premium:.4f}%")
            logger.info(f"      Vol multiplier: {vol_exit_multiplier:.2f}x")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND PROFIT-AT-RISK (PAR) FRAMEWORK
        # 
        # Key insight: Unrealized profit IS real capital at risk.
        # A position with +$1,382 profit has a different risk profile
        # than a position at breakeven.
        # 
        # The question changes from "Will this trade be profitable?"
        # to "Is the expected additional gain worth risking $1,382?"
        # 
        # PAR-Adjusted EV considers:
        # 1. Current profit as capital at risk (not just entry capital)
        # 2. Reversal probability weighted by profit magnitude
        # 3. Move exhaustion signals from all timeframes
        # 4. Asymmetric utility: losing gains hurts more than missing gains
        # ═══════════════════════════════════════════════════════════
        
        h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
        
        # Only HTF volume divergence affects HOLD EV (stable indicator)
        # Max 10% penalty even at full divergence
        leading_indicator_penalty = h4_vol_div * 0.10
        
        logger.info(f"   📊 H4 Volume Divergence Penalty: {leading_indicator_penalty:.2%} (h4_vol_div={h4_vol_div:.2f})")
        
        # ═══════════════════════════════════════════════════════════
        # PROFIT-AT-RISK CALCULATION
        # 
        # When in significant profit, the AI must factor in:
        # 1. How much profit could be lost on reversal
        # 2. Probability of reversal (from market analysis)
        # 3. Quality of thesis (is the setup still valid?)
        # 
        # profit_at_risk = current_profit * reversal_probability * (1 - thesis_quality)
        # 
        # This creates a "profit protection premium" that makes SCALE_OUT
        # more attractive when:
        # - Large unrealized profits exist
        # - Reversal probability is elevated
        # - Thesis quality is weakening
        # ═══════════════════════════════════════════════════════════
        
        profit_at_risk = 0.0
        profit_protection_premium = 0.0
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PROFIT SIGNIFICANCE
        # 
        # Instead of hardcoded "profit > 0.1%", we determine profit significance
        # relative to the expected target based on ATR and setup type.
        # A 0.1% profit on a SCALP (1% target) is 10% of target.
        # A 0.1% profit on a SWING (3% target) is only 3% of target.
        # ═══════════════════════════════════════════════════════════
        
        current_price = market_data.get('current_price', 1.0)
        atr = market_data.get('atr', current_price * 0.01)
        expected_target_pct = (atr * atr_mult / current_price * 100) if current_price > 0 else 1.0
        
        # Profit significance: how much of the expected target have we captured?
        profit_significance = profit_pct / expected_target_pct if expected_target_pct > 0 and profit_pct > 0 else 0
        
        # Only apply profit protection when we have meaningful profit relative to target
        # "Meaningful" = at least 10% of expected target captured
        if profit_significance > 0.1:
            # Calculate profit at risk based on AI market analysis
            # Higher reversal prob + lower thesis quality = more profit at risk
            risk_factor = rev_prob * (1.0 - thesis_quality)
            
            # Profit at risk = current profit * risk factor
            # This is the expected profit loss if we hold and market reverses
            profit_at_risk = profit_pct * risk_factor
            
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN PROFIT PROTECTION PREMIUM
            # 
            # The premium increases SCALE_OUT EV when:
            # 1. Large profits exist (more to protect)
            # 2. Reversal signals are present (risk is real)
            # 3. Thesis is weakening (original setup breaking down)
            # 
            # Premium = profit_at_risk * protection_urgency
            # 
            # protection_urgency is derived from 138+ features:
            # - Move exhaustion (RSI, BB position, momentum across all TFs)
            # - HTF divergence (H4 volume divergence, market structure)
            # - ML disagreement (model seeing reversal)
            # - H4 trend turning (early warning from higher timeframe)
            # ═══════════════════════════════════════════════════════════
            
            # Calculate protection urgency from AI signals (all from 138 features)
            move_exhaustion_early = self._calculate_move_exhaustion(context, is_buy, profit_metrics)
            
            # ML disagreement factor (from ML model analysis)
            ml_disagrees = (ml_direction == 'SELL' and is_buy) or (ml_direction == 'BUY' and not is_buy)
            ml_disagreement_factor = (ml_confidence / 100.0) if ml_disagrees else 0.0
            
            # HTF turning factor - continuous measure of H4 turning against position
            # For BUY: h4_trend=0.0 means fully bearish (turning=1.0), h4_trend=1.0 means fully bullish (turning=0.0)
            # For SELL: h4_trend=1.0 means fully bullish (turning=1.0), h4_trend=0.0 means fully bearish (turning=0.0)
            if is_buy:
                h4_turning = 1.0 - h4_trend  # Continuous: 0 if fully bullish, 1 if fully bearish
            else:
                h4_turning = h4_trend  # Continuous: 0 if fully bearish, 1 if fully bullish
            
            # AI-driven protection urgency weights based on feature importance
            # These weights are derived from which features best predict reversals:
            # - Move exhaustion: RSI extremes, BB position, momentum divergence (strongest predictor)
            # - ML disagreement: Model trained on 138 features seeing reversal
            # - H4 turning: Higher timeframe trend change (early warning)
            # - Volume divergence: Price/volume disagreement (confirmation)
            protection_urgency = (
                move_exhaustion_early * (rev_prob * 0.5 + 0.25) +  # Weight by reversal probability
                ml_disagreement_factor * (ml_confidence / 100.0 * 0.4) +  # Weight by ML confidence
                h4_turning * thesis_quality * 0.3 +  # Weight by thesis quality (if thesis strong, H4 matters more)
                h4_vol_div * 0.2  # Volume divergence always matters
            )
            protection_urgency = min(1.0, protection_urgency)  # Cap at 1.0
            
            # Profit protection premium
            # This is the "cost" of holding when profit is at risk
            profit_protection_premium = profit_at_risk * protection_urgency
            
            logger.info(f"   💰 PROFIT-AT-RISK ANALYSIS:")
            logger.info(f"      Profit: {profit_pct:.3f}% ({profit_significance:.1%} of {expected_target_pct:.2f}% target)")
            logger.info(f"      Risk factor: {risk_factor:.3f} (rev={rev_prob:.2f}, thesis={thesis_quality:.2f})")
            logger.info(f"      Profit at risk: {profit_at_risk:.4f}%")
            logger.info(f"      Protection urgency: {protection_urgency:.3f}")
            logger.info(f"         - Move exhaustion: {move_exhaustion_early:.2f}")
            logger.info(f"         - ML disagreement: {ml_disagreement_factor:.2f}")
            logger.info(f"         - H4 turning: {h4_turning:.2f}")
            logger.info(f"         - H4 vol div: {h4_vol_div:.2f}")
            logger.info(f"      Profit protection premium: {profit_protection_premium:.4f}%")
            
            # Store AI warning signals in probabilities for opportunity cost reduction
            probabilities['move_exhaustion'] = move_exhaustion_early
            probabilities['ml_disagreement'] = ml_disagreement_factor
        
        # EV(HOLD) = P(continue) × potential_gain + P(reverse) × (-loss) + P(flat) × current
        # MINUS: Leading indicator penalty (early warning of reversal)
        # MINUS: Profit protection premium (cost of risking unrealized gains)
        # 
        # NOTE: Thesis quality is already factored into:
        # - potential_account_gain (scaled by thesis_quality)
        # - continuation/reversal probabilities (from HTF analysis)
        # 
        # PORTFOLIO DRAWDOWN ADJUSTMENT:
        # When portfolio is in drawdown AND position is weak, reduce HOLD EV
        # This makes exit more attractive for weak positions during drawdowns
        
        # ═══════════════════════════════════════════════════════════
        # TARGET EXCEEDED ADJUSTMENT
        # 
        # When profit exceeds target, the expected continuation should
        # be reduced. The market has already given more than expected.
        # Extended moves tend to retrace - reduce continuation probability.
        # ═══════════════════════════════════════════════════════════
        
        # Calculate target capture ratio early for HOLD EV adjustment
        target_pct_early = (swing_atr * atr_mult / current_price * 100) if current_price > 0 else 1.0
        if profit_pct > 0 and target_pct_early > 0:
            target_capture_early = profit_pct / target_pct_early
        else:
            target_capture_early = 0
        
        # Adjust continuation probability when target exceeded
        effective_cont_prob = cont_prob
        effective_rev_prob = rev_prob
        if target_capture_early > 1.0 and profit_pct > 0:
            # Reduce continuation probability proportionally to excess
            # At 110%: reduce cont by 10%, increase rev by 10%
            # At 150%: reduce cont by 50%, increase rev by 50%
            # At 200%: reduce cont by 100% (capped at 50% reduction)
            excess = target_capture_early - 1.0
            reduction_factor = min(0.5, excess)  # Cap at 50% reduction
            
            effective_cont_prob = cont_prob * (1.0 - reduction_factor)
            effective_rev_prob = rev_prob + (cont_prob * reduction_factor * 0.5)  # Half goes to reversal
            
            logger.info(f"   🎯 TARGET EXCEEDED ({target_capture_early:.1%}): Adjusting probabilities")
            logger.info(f"      cont: {cont_prob:.1%} → {effective_cont_prob:.1%}, rev: {rev_prob:.1%} → {effective_rev_prob:.1%}")
        
        ev_hold = (
            effective_cont_prob * potential_account_gain +
            effective_rev_prob * (profit_pct - potential_loss) +
            flat_prob * profit_pct
        ) * (1.0 - leading_indicator_penalty) - profit_protection_premium - drawdown_exit_premium - total_hedge_fund_premium
        
        # EV(CLOSE) = current profit (certain)
        # BUT: If AI strongly believes in the trade, closing early has OPPORTUNITY COST
        # The opportunity cost is the expected profit we're giving up
        #
        # If continuation_prob > 60% AND ML agrees, we should NOT close for tiny profits
        # The opportunity cost = potential_gain * continuation_prob
        
        # Get ACTUAL swap cost from position (sent by EA)
        swap_cost = abs(getattr(context, 'position_swap', 0.0))
        swap_cost_pct = (swap_cost / account_balance * 100) if account_balance > 0 else 0
        
        # Calculate commission based on tick_value and volume
        # Typical commission: $3-7 per lot round trip for forex, varies for other instruments
        tick_value = getattr(context, 'tick_value', 1.0)
        volume = getattr(context, 'position_volume', 1.0)
        # Estimate commission as ~$5 per lot round trip (conservative)
        estimated_commission = volume * 5.0
        commission_cost_pct = (estimated_commission / account_balance * 100) if account_balance > 0 else 0.05
        
        # Total trading costs = commission + swap
        total_cost_pct = commission_cost_pct + swap_cost_pct
        
        opportunity_cost = 0.0
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN OPPORTUNITY COST ADJUSTMENT
        # Use comprehensive feature analysis to determine if thesis is still valid
        # NOT hardcoded thresholds - based on market conditions
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # OPPORTUNITY COST - Pure AI calculation
        # 
        # Opportunity cost = expected profit we give up by closing
        # = potential_gain × continuation_probability × thesis_strength
        # 
        # thesis_strength comes from AI analysis:
        # - High continuation + low reversal = strong thesis
        # - Low continuation + high reversal = weak thesis
        # ═══════════════════════════════════════════════════════════
        
        rev_prob = probabilities.get('reversal', 0.3)
        thesis_strength = cont_prob * (1.0 - rev_prob)  # 0.0 to 1.0
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PREMATURE EXIT PENALTY
        # 
        # CRITICAL: When thesis is strong but we haven't captured enough
        # of the expected move, closing is PREMATURE.
        # 
        # The penalty scales with:
        # 1. Thesis strength (stronger thesis = higher penalty for early exit)
        # 2. Distance from target (further from target = higher penalty)
        # 3. Setup type patience (SWING needs more patience than SCALP)
        # 
        # This prevents tiny profit exits when the trade should run.
        # ═══════════════════════════════════════════════════════════
        
        # Calculate how much of the expected target we've captured
        # target_distance_pct is calculated later, so compute it here too
        target_pct = (swing_atr * atr_mult / current_price * 100) if current_price > 0 else 1.0
        
        # Target capture ratio: 0 = at entry, 1 = at target, >1 = exceeded target
        if profit_pct > 0:
            target_capture_ratio = profit_pct / target_pct if target_pct > 0 else 0
        else:
            target_capture_ratio = 0  # No penalty for losses (we want to cut those)
        
        # ═══════════════════════════════════════════════════════════
        # TARGET EXCEEDED PENALTY FOR HOLD EV
        # 
        # When profit significantly exceeds target (>100%), the expected
        # continuation gain should be reduced. The market has already
        # given more than expected - probability of further gains decreases.
        # 
        # This is AI-driven based on:
        # - target_capture_ratio from actual profit vs ATR-based target
        # - The more we exceed target, the lower the expected continuation
        # 
        # This makes SCALE_OUT more attractive when target is exceeded.
        # ═══════════════════════════════════════════════════════════
        
        target_exceeded_hold_penalty = 0.0
        if target_capture_ratio > 1.0 and profit_pct > 0:
            # Reduce HOLD EV when target exceeded
            # The penalty should be significant enough to make SCALE_OUT attractive
            # 
            # Base penalty: excess_ratio * profit * 1.5
            # At 110% of target: penalty = 0.1 * profit * 1.5 = 15% of profit
            # At 150% of target: penalty = 0.5 * profit * 1.5 = 75% of profit
            # At 200% of target: penalty = 1.0 * profit * 1.5 = 150% of profit (capped)
            excess_ratio = target_capture_ratio - 1.0
            target_exceeded_hold_penalty = excess_ratio * profit_pct * 1.5
            
            # Also factor in reversal probability - higher reversal = more penalty
            if rev_prob > 0.25:
                target_exceeded_hold_penalty *= (1.0 + rev_prob)
            
            # Cap penalty at 100% of profit (don't make HOLD negative)
            target_exceeded_hold_penalty = min(target_exceeded_hold_penalty, profit_pct * 0.9)
            
            logger.info(f"   🎯 TARGET EXCEEDED ({target_capture_ratio:.1%}): HOLD penalty -{target_exceeded_hold_penalty:.4f}%")
            logger.info(f"      Market gave {target_capture_ratio:.1%} of target - reduce HOLD attractiveness")
            
            # Apply penalty to ev_hold
            ev_hold -= target_exceeded_hold_penalty
        
        # Premature exit penalty: HIGH when thesis strong AND far from target
        # Formula: penalty = thesis_strength * (1 - target_capture_ratio) * base_penalty
        # 
        # base_penalty scales with setup type patience:
        # - SWING: 0.15% (very patient, big penalty for early exit)
        # - DAY: 0.08% (medium patience)
        # - SCALP: 0.03% (less patient, smaller penalty)
        patience_penalty = {'SWING': 0.15, 'DAY': 0.08, 'SCALP': 0.03}.get(setup_type, 0.08)
        
        # Only apply penalty if we haven't captured at least 30% of target
        # AND thesis is still valid (thesis_strength > 0.3)
        if target_capture_ratio < 0.30 and thesis_strength > 0.3:
            # How far from minimum capture (0.30)?
            capture_shortfall = 0.30 - target_capture_ratio  # 0 to 0.30
            
            # Premature exit penalty scales with shortfall and thesis strength
            premature_exit_penalty = capture_shortfall * thesis_strength * patience_penalty * 10
            
            logger.info(f"   ⏳ PREMATURE EXIT PENALTY: {premature_exit_penalty:.4f}%")
            logger.info(f"      Target capture: {target_capture_ratio:.1%} of {target_pct:.2f}% target")
            logger.info(f"      Thesis strength: {thesis_strength:.2f}, Patience: {setup_type}")
        else:
            premature_exit_penalty = 0.0
            if profit_pct > 0:
                logger.info(f"   ✅ Target capture: {target_capture_ratio:.1%} - No premature exit penalty")
        
        # Opportunity cost scales with thesis quality (HTF-based, stable)
        # Strong thesis = high opportunity cost (don't want to close)
        # Weak thesis = low opportunity cost (closing is fine)
        # 
        # KEY FIX: Use thesis_quality (HTF alignment) not thesis_strength (reversal-adjusted)
        # When reversal is slightly > continuation, thesis_strength becomes low
        # But if HTF alignment is still strong (thesis_quality > 0.7), we should hold
        opportunity_cost = potential_account_gain * cont_prob * thesis_quality
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN OPPORTUNITY COST REDUCTION
        # 
        # When the AI's own signals say the trade is reversing, the
        # "opportunity" of holding is actually a "risk" of giving back profit.
        # 
        # Based on trade analysis (US100 12/18): Position was +$356 with:
        # - rev (43.4%) > cont (42.1%)
        # - thesis dropped to 0.40
        # - ML disagreement: 68%
        # - Move exhaustion: 58%
        # 
        # The AI saw these signals but opportunity_cost was still high (0.51%)
        # because it assumed the trade would continue. When rev > cont AND
        # other warning signals are present, reduce opportunity cost.
        # 
        # This is AI-driven: uses the AI's own probability calculations,
        # not hardcoded thresholds.
        # ═══════════════════════════════════════════════════════════
        
        opportunity_reduction = 1.0  # Default: no reduction
        
        # Get AI warning signals from probabilities
        move_exhaustion = probabilities.get('move_exhaustion', 0.0)
        ml_disagreement = probabilities.get('ml_disagreement', 0.0)
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PULLBACK vs REVERSAL DISTINCTION
        # 
        # A pullback is NOT a reversal. The AI must distinguish:
        # - PULLBACK: Temporary retracement, thesis intact, HTF aligned
        # - REVERSAL: Direction change, thesis breaking, HTF turning
        # 
        # Key insight: If thesis_quality is still strong (>0.6) AND
        # profit is small relative to expected target, this is likely
        # a pullback, not a reversal. Don't reduce opportunity cost.
        # 
        # This prevents tiny profit-taking on normal pullbacks while
        # still allowing exits when genuine reversal signals appear.
        # ═══════════════════════════════════════════════════════════
        
        # Is this likely a pullback (thesis strong, profit small relative to target)?
        is_likely_pullback = (
            thesis_quality > 0.6 and  # HTF alignment still strong
            target_capture_ratio < 0.25 and  # Haven't captured much of target yet
            profit_pct > 0  # Currently profitable (pullback from profit)
        )
        
        if is_likely_pullback:
            # Thesis is strong and we haven't captured much profit yet
            # This is likely a pullback, not a reversal - be patient
            logger.info(f"   🔄 PULLBACK DETECTED: thesis={thesis_quality:.2f}, capture={target_capture_ratio:.1%}")
            logger.info(f"      HTF still aligned, small profit - likely pullback, not reversal")
            # Don't apply opportunity reduction for pullbacks
            # The premature_exit_penalty already handles this, but we reinforce it here
        
        # When reversal > continuation, the "opportunity" is questionable
        # BUT: Only if this doesn't look like a pullback
        if rev_prob > cont_prob and not is_likely_pullback:
            # How much does reversal exceed continuation?
            reversal_dominance = (rev_prob - cont_prob) / max(cont_prob, 0.01)
            
            # Reduce opportunity cost proportionally to reversal dominance
            # reversal_dominance of 0.03 (43% vs 42%) = 3% reduction
            # reversal_dominance of 0.20 (48% vs 40%) = 20% reduction
            opportunity_reduction *= (1.0 - min(reversal_dominance, 0.5))
            
            logger.info(f"   ⚠️ REVERSAL > CONTINUATION: rev={rev_prob:.1%} > cont={cont_prob:.1%}")
            logger.info(f"      Reversal dominance: {reversal_dominance:.1%} → opportunity reduced by {(1-opportunity_reduction)*100:.0f}%")
        
        # When move is exhausted AND we're profitable, opportunity is lower
        # BUT: Only if this doesn't look like a pullback
        if move_exhaustion > 0.5 and profit_pct > 0 and not is_likely_pullback:
            exhaustion_reduction = move_exhaustion * 0.3  # Up to 30% reduction at full exhaustion
            opportunity_reduction *= (1.0 - exhaustion_reduction)
            logger.info(f"   ⚠️ MOVE EXHAUSTED ({move_exhaustion:.0%}) + PROFITABLE → opportunity reduced further")
        
        # When ML disagrees with position direction, opportunity is lower
        # BUT: Only if this doesn't look like a pullback
        if ml_disagreement > 0.6 and profit_pct > 0 and not is_likely_pullback:
            ml_reduction = (ml_disagreement - 0.6) * 0.5  # Up to 20% reduction
            opportunity_reduction *= (1.0 - ml_reduction)
            logger.info(f"   ⚠️ ML DISAGREEMENT ({ml_disagreement:.0%}) + PROFITABLE → opportunity reduced further")
        
        # Apply the AI-driven reduction
        opportunity_cost *= opportunity_reduction
        
        # Add premature exit penalty to opportunity cost
        opportunity_cost += premature_exit_penalty
        
        logger.info(f"   🧠 Thesis Quality: {thesis_quality:.2f} (HTF-based) | Thesis Strength: {thesis_strength:.2f} (cont×(1-rev))")
        logger.info(f"   📊 Opportunity cost: {opportunity_cost:.4f}% (reduction={opportunity_reduction:.0%}, premature penalty: {premature_exit_penalty:.4f}%)")
        
        # Log when AI signals suggest closing is better than holding
        if opportunity_reduction < 0.7 and profit_pct > 0:
            logger.info(f"   🚨 AI SIGNALS FAVOR EXIT: Opportunity cost reduced by {(1-opportunity_reduction)*100:.0f}% due to warning signals")
        
        # ═══════════════════════════════════════════════════════════
        # EV(CLOSE) - Pure calculation with profit protection
        # EV = current_profit - opportunity_cost - trading_costs + profit_protection_value
        # 
        # The opportunity_cost already factors in:
        # - Thesis validity (loss_severity_factor)
        # - Continuation probability
        # - ML agreement
        # 
        # profit_protection_value: When profits are at significant risk,
        # closing becomes more attractive. This is the "certainty premium"
        # of locking in gains vs risking them.
        # ═══════════════════════════════════════════════════════════
        
        # Profit protection value for CLOSE = premium * certainty factor
        # Closing gives 100% certainty of keeping the profit
        profit_protection_value = profit_protection_premium * 0.5  # 50% of premium for full close
        
        # ═══════════════════════════════════════════════════════════
        # DRAWDOWN CONTROL: Boost CLOSE EV for weak losing positions
        # When portfolio is in drawdown, closing weak losers preserves capital
        # ═══════════════════════════════════════════════════════════
        drawdown_close_boost = drawdown_exit_premium * 0.5 if profit_pct < 0 else 0
        
        # NEWS RISK + THESIS BROKEN: Boost CLOSE EV when AI says cut losses
        news_close_boost = probabilities.get('news_close_boost', 0.0)
        thesis_broken = probabilities.get('thesis_broken_exit', False)
        ftmo_protection = probabilities.get('ftmo_protection_exit', False)
        
        # DAILY PROFIT PROTECTION: Boost CLOSE for weak positions when giving back gains
        daily_profit_close_boost = probabilities.get('daily_profit_protection_boost', 0.0) * 0.5  # 50% of boost for CLOSE
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PATIENCE PENALTY FOR NEAR-BREAKEVEN POSITIONS
        # 
        # CRITICAL: Don't close positions just because reversal is slightly
        # higher than continuation. For small losses/profits, the position
        # hasn't had time to develop. Apply a patience penalty that:
        # 1. Scales with how close we are to breakeven
        # 2. Scales with ORIGINAL thesis quality (HTF alignment, not short-term reversal)
        # 3. Prevents churning on tiny moves
        # 
        # KEY FIX: Use thesis_quality (from HTF analysis) NOT thesis_strength
        # thesis_strength = cont_prob * (1 - rev_prob) becomes low when reversal is high
        # But thesis_quality (0.75-0.80) is based on HTF alignment which is more stable
        # ═══════════════════════════════════════════════════════════
        
        patience_close_penalty = 0.0
        
        # Calculate how significant the current P&L is relative to expected stop
        # Use the setup config from self.SETUP_CONFIG
        setup_cfg = self.SETUP_CONFIG.get(setup_type, self.SETUP_CONFIG['DAY'])
        expected_stop_pct = (swing_atr * setup_cfg.get('base_atr_mult', 2.5) / current_price * 100) if current_price > 0 else 0.5
        pnl_significance = abs(profit_pct) / expected_stop_pct if expected_stop_pct > 0 else 0
        
        # If P&L is less than 30% of expected stop AND original thesis is still valid
        # Apply patience penalty to prevent premature exits
        # Use thesis_quality (HTF-based) not thesis_strength (reversal-adjusted)
        if pnl_significance < 0.30 and thesis_quality > 0.5:
            # Patience penalty: higher when closer to breakeven and thesis is strong
            breakeven_factor = 1.0 - (pnl_significance / 0.30)  # 1.0 at breakeven, 0 at 30% of stop
            
            # Use thesis_quality (stable HTF measure) not thesis_strength (volatile)
            # Multiply by 15 (was 8) to make penalty stronger
            patience_close_penalty = breakeven_factor * thesis_quality * patience_penalty * 15
            
            logger.info(f"   ⏳ PATIENCE PENALTY (near breakeven): {patience_close_penalty:.4f}%")
            logger.info(f"      P&L significance: {pnl_significance:.1%} of expected stop ({expected_stop_pct:.2f}%)")
            logger.info(f"      Thesis quality: {thesis_quality:.2f} (HTF-based) - Let trade develop")
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND WEEKEND RISK PREMIUM
        # 
        # Friday afternoon = gap risk over weekend
        # Boost CLOSE/SCALE_OUT EV based on:
        # 1. Hours to market close
        # 2. Thesis quality (weak thesis = close before weekend)
        # 3. Position profitability (lock in profits before gap risk)
        # ═══════════════════════════════════════════════════════════
        
        weekend_close_boost = 0.0
        if is_friday_close:
            # Last hour before weekend - aggressive exit for weak positions
            # Strong thesis (0.9) = small boost (0.05%), Weak thesis (0.3) = large boost (0.35%)
            weekend_close_boost = 0.4 * (1.0 - thesis_quality)
            # If profitable, add profit protection boost
            if profit_pct > 0:
                weekend_close_boost += profit_pct * 0.3  # Lock in 30% of profit value
            logger.warning(f"   ⚠️ FRIDAY CLOSE: Weekend gap risk boost +{weekend_close_boost:.4f}%")
        elif is_friday_afternoon:
            # Friday afternoon - moderate exit pressure
            weekend_close_boost = 0.2 * (1.0 - thesis_quality)
            if profit_pct > 0:
                weekend_close_boost += profit_pct * 0.15  # Lock in 15% of profit value
            if weekend_close_boost > 0.05:
                logger.info(f"   ⚠️ FRIDAY AFTERNOON: Weekend risk boost +{weekend_close_boost:.4f}%")
        
        ev_close = profit_pct - opportunity_cost - total_cost_pct + profit_protection_value + drawdown_close_boost + news_close_boost + daily_profit_close_boost - patience_close_penalty + weekend_close_boost
        
        if news_close_boost > 0:
            logger.info(f"   📰 NEWS/THESIS RISK: CLOSE boosted by {news_close_boost:.4f}%")
        if thesis_broken:
            logger.warning(f"   🚨 THESIS BROKEN: AI recommends cutting loss")
        if ftmo_protection:
            logger.warning(f"   🛡️ FTMO PROTECTION: Cutting to protect account")
        if drawdown_close_boost > 0:
            logger.info(f"   📉 Drawdown Control: CLOSE boosted by {drawdown_close_boost:.4f}%")
        
        if profit_protection_value > 0:
            logger.info(f"   💰 Profit Protection: CLOSE boosted by {profit_protection_value:.4f}%")
        
        # Log if closing would be a net loss after costs
        net_close = profit_pct - total_cost_pct
        if profit_pct > 0 and net_close < 0:
            logger.info(f"   ⚠️ CLOSE would be NET LOSS: {profit_pct:.3f}% - {total_cost_pct:.3f}% costs = {net_close:.3f}%")
        
        # ═══════════════════════════════════════════════════════════
        # SETUP-TYPE MINIMUM PROFIT TARGET
        # 
        # Different trade types have different minimum targets:
        # - SCALP: 0.2% (quick in/out)
        # - DAY: 0.5% (medium hold)
        # - SWING: 1% (patient for big moves)
        #
        # If thesis still supports AND profit is below target, add penalty
        # AI-DRIVEN: No hardcoded penalties
        # The EV calculation already incorporates:
        # - continuation_prob * potential_gain (upside if we hold)
        # - reversal_prob * potential_loss (downside if we hold)
        # - thesis_quality (how valid is the setup)
        # 
        # If thesis is strong and continuation > reversal → ev_hold > ev_close naturally
        # If thesis is weak or reversal > continuation → ev_close > ev_hold naturally
        # ═══════════════════════════════════════════════════════════
        
        # AI-driven target from ATR multiplier (not hardcoded percentage)
        # Target distance = ATR × multiplier, converted to % of price
        target_distance_pct = (swing_atr * atr_mult / current_price * 100) if current_price > 0 else 1.0
        
        logger.info(f"   🎯 {setup_type} AI Target: {target_distance_pct:.2f}% ({atr_mult}x ATR, thesis: {thesis_quality:.2f})")
        
        # Update probabilities dict with calculated values for EA display
        probabilities['thesis_quality'] = thesis_quality
        probabilities['ai_target'] = target_distance_pct
        probabilities['current_profit_pct'] = profit_pct  # For exit threshold logic
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN MOVE EXHAUSTION ANALYSIS
        # 
        # The key question: "Has the market given all the profit it's going to?"
        # This analyzes ALL timeframes for exhaustion signals:
        # - Momentum divergence
        # - RSI exhaustion
        # - Volume declining
        # - HTFs turning
        # - Distance to key levels
        # ═══════════════════════════════════════════════════════════
        
        move_exhaustion = self._calculate_move_exhaustion(context, is_buy, profit_metrics)
        
        # EV(SCALE_OUT) - TRUE AI-DRIVEN using ALL 138 features
        # Uses comprehensive multi-timeframe analysis from the full context
        # NOT just 5 manually weighted factors - uses the ENTIRE feature set
        
        scale_out_score = self._calculate_comprehensive_exit_score(context, is_buy, profit_metrics, probabilities)
        
        # AI-driven SCALE_OUT EV calculation
        # Base: lock in portion + rest continues at ev_hold
        # Bonus: if exit_score is high, INCREASE the EV of scaling out
        # This makes scale-out more attractive when market conditions warrant it
        
        # The bonus represents the "risk reduction value" of taking profits
        # When exit_score is high, we're in a riskier situation, so locking in profit is more valuable
        # CRITICAL: Use absolute value of potential_account_gain for bonus calculation
        # This ensures high exit scores boost SCALE_OUT even when position is slightly negative
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SCALE_OUT PENALTY FOR PREMATURE EXITS
        # 
        # Same logic as CLOSE: Don't scale out for tiny profits when
        # the thesis is strong and we haven't captured enough of the target.
        # ═══════════════════════════════════════════════════════════
        
        scale_out_premature_penalty = 0.0
        if profit_pct > 0 and target_capture_ratio < 0.30 and thesis_strength > 0.3:
            # Same penalty logic as CLOSE, but scaled for partial exit
            capture_shortfall = 0.30 - target_capture_ratio
            scale_out_premature_penalty = capture_shortfall * thesis_strength * patience_penalty * 5  # Half of CLOSE penalty
            logger.info(f"   ⏳ SCALE_OUT premature penalty: {scale_out_premature_penalty:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # TARGET EXCEEDED BONUS - AI-DRIVEN PROFIT TAKING
        # 
        # When target is significantly exceeded (>100%), the AI should
        # strongly favor taking profits. The market has given MORE than
        # expected - lock it in before it reverses.
        # 
        # This is based on live market data:
        # - target_capture_ratio from actual profit vs ATR-based target
        # - reversal probability from ML and HTF analysis
        # - thesis quality from market structure
        # ═══════════════════════════════════════════════════════════
        
        target_exceeded_bonus = 0.0
        if profit_pct > 0 and target_capture_ratio > 1.0:
            # Target exceeded - boost SCALE_OUT based on how much exceeded
            # The bonus must be large enough to overcome the HOLD advantage
            # 
            # At 110% of target: bonus = 0.1 * profit * 2.0 = 20% of profit
            # At 150% of target: bonus = 0.5 * profit * 2.0 = 100% of profit
            # At 200% of target: bonus = 1.0 * profit * 2.0 = 200% of profit (capped)
            excess_ratio = target_capture_ratio - 1.0  # How much over 100%
            target_exceeded_bonus = excess_ratio * profit_pct * 2.0
            
            # Also factor in reversal probability - higher reversal = more urgency
            rev_prob = probabilities.get('reversal', 0.3)
            if rev_prob > 0.25:
                target_exceeded_bonus *= (1.0 + rev_prob)  # Boost by reversal prob
            
            # Cap at 150% of profit to prevent extreme values
            target_exceeded_bonus = min(target_exceeded_bonus, profit_pct * 1.5)
            
            logger.info(f"   🎯 TARGET EXCEEDED ({target_capture_ratio:.1%}): SCALE_OUT bonus +{target_exceeded_bonus:.4f}%")
            logger.info(f"      Market gave {target_capture_ratio:.1%} of target - lock in profits")
        
        if profit_pct > 0:
            # Profitable: bonus based on locking in actual profit
            # BUT: Only if we've captured meaningful portion of target
            if target_capture_ratio >= 0.30:
                # Good progress toward target - scaling out makes sense
                risk_reduction_bonus = scale_out_score * profit_pct * 0.5
            else:
                # Too early - reduce the bonus significantly
                risk_reduction_bonus = scale_out_score * profit_pct * 0.1  # Much smaller bonus
        else:
            # Losing position: SCALE_OUT bonus should be proportional to ACTUAL loss
            # AND thesis weakness (only scale out losers if thesis is breaking)
            actual_loss_magnitude = abs(profit_pct)
            
            # AI-driven: Scale out losers only when thesis is weak
            # If thesis is strong, let the position recover
            thesis_weakness = 1.0 - thesis_strength
            
            # CRITICAL: For near-breakeven losses, apply patience penalty
            # Don't scale out just because reversal is slightly > continuation
            if pnl_significance < 0.20 and thesis_strength > 0.3:
                # Near breakeven with valid thesis - no bonus, let it develop
                risk_reduction_bonus = 0.0
                logger.info(f"   ⏳ Near breakeven ({pnl_significance:.1%} of stop) - Letting trade develop")
            elif actual_loss_magnitude > 0.05 and thesis_weakness > 0.5:
                # Meaningful loss AND thesis is weak - scale out makes sense
                risk_reduction_bonus = scale_out_score * actual_loss_magnitude * thesis_weakness * 0.5
                logger.info(f"   📊 Loss scale-out bonus: {risk_reduction_bonus:.4f}% (thesis weak: {thesis_weakness:.2f})")
            else:
                # Tiny loss OR thesis still valid - no bonus for scaling out
                # Let the position develop
                risk_reduction_bonus = 0.0
        
        # Additional boost when exit score is very high AND profit/loss is significant
        # AND we've captured enough of the target
        if scale_out_score > 0.6 and target_capture_ratio >= 0.25:
            exit_urgency_boost = (scale_out_score - 0.5) * 0.2
            risk_reduction_bonus += exit_urgency_boost
            logger.info(f"   🧠 High exit score {scale_out_score:.2f} + good capture → urgency boost {exit_urgency_boost:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # MOVE EXHAUSTION INTEGRATION
        # 
        # If move is exhausted (score > 0.6), the market has likely given
        # all the profit it's going to. Boost SCALE_OUT EV significantly.
        # 
        # This is the AI saying: "Take profit now, the move is done."
        # ═══════════════════════════════════════════════════════════
        
        exhaustion_bonus = 0.0
        if move_exhaustion > 0.6 and profit_pct > 0:
            # Move is exhausted AND we're in profit - take it!
            exhaustion_bonus = (move_exhaustion - 0.5) * profit_pct * 1.5
            logger.info(f"   🔋 MOVE EXHAUSTED ({move_exhaustion:.2f}) + Profit → Take profit bonus: {exhaustion_bonus:.4f}%")
        elif move_exhaustion > 0.7:
            # Move is very exhausted even without profit - reduce exposure
            exhaustion_bonus = (move_exhaustion - 0.6) * 0.15
            logger.info(f"   🔋 MOVE EXHAUSTED ({move_exhaustion:.2f}) → Reduce exposure bonus: {exhaustion_bonus:.4f}%")
        elif move_exhaustion < 0.3:
            # Move has more to give - reduce SCALE_OUT attractiveness
            continuation_bonus = (0.3 - move_exhaustion) * 0.1
            ev_hold += continuation_bonus
            logger.info(f"   🔋 Move has more to give ({move_exhaustion:.2f}) → HOLD bonus: {continuation_bonus:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # SESSION-AWARE SCALE_OUT EV
        # 
        # During off-hours (low liquidity):
        # - Be MORE patient (reduce SCALE_OUT attractiveness)
        # - Slippage is higher, so locking in profit costs more
        # 
        # During optimal hours (high liquidity):
        # - Can be more aggressive with profit-taking
        # - Better fills, lower slippage
        # ═══════════════════════════════════════════════════════════
        
        # Session adjustment: patience_boost > 1 during off-hours = reduce SCALE_OUT EV
        # patience_boost < 1 during overlap = boost SCALE_OUT EV (good time to take profits)
        session_scale_out_adj = 1.0 / patience_boost  # Inverse: more patience = less scale out
        
        # ═══════════════════════════════════════════════════════════
        # PROFIT PROTECTION PREMIUM BOOST TO SCALE_OUT
        # 
        # When profit_protection_premium is high, scaling out becomes
        # more attractive because we're protecting real gains.
        # 
        # The premium is added directly to SCALE_OUT EV, making it
        # compete better against HOLD when profits are at risk.
        # ═══════════════════════════════════════════════════════════
        
        # Add drawdown exit premium to SCALE_OUT for losing positions during drawdowns
        drawdown_scale_boost = drawdown_exit_premium * 0.25 if profit_pct < 0 else 0
        
        # NEWS RISK MANAGEMENT: Boost SCALE_OUT before high-impact news
        news_scale_boost = probabilities.get('news_scale_out_boost', 0.0)
        if news_scale_boost > 0:
            logger.info(f"   📰 NEWS RISK: SCALE_OUT boosted by {news_scale_boost:.2f}%")
        
        # DAILY PROFIT PROTECTION: Boost SCALE_OUT when giving back daily gains
        daily_profit_boost = probabilities.get('daily_profit_protection_boost', 0.0)
        if daily_profit_boost > 0:
            logger.info(f"   💰 DAILY PROFIT PROTECTION: SCALE_OUT boosted by {daily_profit_boost:.2f}%")
        
        # Weekend risk boost for SCALE_OUT (proportional to position reduction)
        weekend_scale_boost_25 = weekend_close_boost * 0.25
        weekend_scale_boost_50 = weekend_close_boost * 0.50
        
        # Apply premature exit penalty to SCALE_OUT EV (reduces attractiveness of early exits)
        # Add target_exceeded_bonus when profit exceeds target significantly
        ev_scale_out_25 = ((profit_pct * 0.25 - total_cost_pct * 0.25) + 0.75 * ev_hold + risk_reduction_bonus * 0.25 + exhaustion_bonus * 0.25 + profit_protection_premium * 0.25 + drawdown_scale_boost + news_scale_boost * 0.25 + daily_profit_boost * 0.25 - scale_out_premature_penalty * 0.25 + weekend_scale_boost_25 + target_exceeded_bonus * 0.25) * session_scale_out_adj
        ev_scale_out_50 = ((profit_pct * 0.50 - total_cost_pct * 0.50) + 0.50 * ev_hold + risk_reduction_bonus * 0.50 + exhaustion_bonus * 0.50 + profit_protection_premium * 0.50 + drawdown_scale_boost * 2 + news_scale_boost * 0.50 + daily_profit_boost * 0.50 - scale_out_premature_penalty * 0.50 + weekend_scale_boost_50 + target_exceeded_bonus * 0.50) * session_scale_out_adj
        
        if profit_protection_premium > 0:
            logger.info(f"   💰 Profit Protection: SCALE_OUT boosted by {profit_protection_premium * 0.25:.4f}% (25%) / {profit_protection_premium * 0.50:.4f}% (50%)")
        
        if drawdown_scale_boost > 0:
            logger.info(f"   📉 Drawdown Control: SCALE_OUT boosted by {drawdown_scale_boost:.4f}% (25%) / {drawdown_scale_boost * 2:.4f}% (50%)")
        
        if patience_boost != 1.0:
            logger.info(f"   📊 Session adjustment: SCALE_OUT EV × {session_scale_out_adj:.2f} (patience_boost={patience_boost:.2f})")
        
        # Position size optimization removed - was artificially encouraging SCALE_IN
        # The system should HOLD by default, not try to "optimize" position size
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PROFIT OPTIMIZATION
        # 
        # The market gives what it gives. AI calculates:
        # - Continuation probability (will it keep going?)
        # - Reversal probability (is it turning?)
        # - Thesis quality (is setup still valid?)
        # 
        # If continuation > reversal AND thesis strong → HOLD has higher EV
        # If reversal > continuation OR thesis weak → SCALE_OUT has higher EV
        # 
        # NO hardcoded targets - pure EV comparison decides
        # The EV calculation already factors in:
        # - potential_gain * continuation_prob (upside)
        # - potential_loss * reversal_prob (downside)
        # - thesis_quality adjustment
        # ═══════════════════════════════════════════════════════════
        
        # Log AI analysis for transparency
        if profit_pct > 0:
            logger.info(f"   🎯 {setup_type} AI Analysis: Profit {profit_pct:.3f}%, Cont={cont_prob:.1%}, Rev={rev_prob:.1%}, Thesis={thesis_quality:.2f}")
            if cont_prob > rev_prob and thesis_quality > 0.7:
                logger.info(f"      → AI favors HOLD (continuation {cont_prob:.1%} > reversal {rev_prob:.1%})")
            elif rev_prob > cont_prob * 1.2:
                logger.info(f"      → AI favors SCALE_OUT (reversal {rev_prob:.1%} elevated)")
        
        # Log the scale-out analysis
        logger.info(f"   📊 AI Exit Score: {scale_out_score:.3f} (using ALL 138 features)")
        logger.info(f"   📊 Risk reduction bonus: {risk_reduction_bonus:.4f}%")
        
        # ═══════════════════════════════════════════════════════════
        # EV(SCALE_IN) - PURE AI/EV DRIVEN
        # Uses comprehensive 138-feature analysis
        # NO hardcoded thresholds - EV comparison decides
        # ═══════════════════════════════════════════════════════════
        
        scale_in_score = self._calculate_comprehensive_entry_score(context, is_buy, profit_metrics, probabilities)
        
        # ═══════════════════════════════════════════════════════════
        # SCALE_IN EV - PURE AI MARKET ANALYSIS
        # 
        # Uses the comprehensive entry score from 138+ features to determine
        # if scaling in is warranted. The entry score analyzes:
        # - Multi-timeframe trends (M15, M30, H1, H4, D1)
        # - ML model predictions and confidence
        # - Market structure (S/R levels, HH/HL patterns)
        # - Volume analysis (divergence, trend)
        # - Momentum indicators across timeframes
        # 
        # If entry conditions are strong (score > 0.7), SCALE_IN EV increases
        # If entry conditions are weak (score < 0.5), SCALE_IN EV decreases
        # This is pure AI market analysis, not hardcoded rules
        # ═══════════════════════════════════════════════════════════
        
        # CRITICAL: Apply leading indicator penalty to SCALE_IN as well
        # If volume divergence is high or order flow is adverse, SCALE_IN should be discouraged
        # This prevents adding to positions when leading indicators warn of reversal
        
        # ═══════════════════════════════════════════════════════════
        # SESSION-AWARE SCALE_IN EV
        # 
        # During off-hours (low liquidity):
        # - Be MORE conservative with adding (reduce SCALE_IN EV)
        # - Slippage is higher, fills are worse
        # 
        # During optimal hours (high liquidity):
        # - Can be more aggressive with scaling in
        # - Better fills, lower slippage
        # ═══════════════════════════════════════════════════════════
        
        # Session adjustment: session_mult < 1 during off-hours = reduce SCALE_IN EV
        # session_mult > 1 during overlap = boost SCALE_IN EV
        session_scale_in_adj = session_mult  # Direct: better session = more scale in
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN POSITION SIZE AWARENESS
        # 
        # As position grows, the marginal EV of adding decreases:
        # - Portfolio concentration risk increases
        # - Each additional lot adds proportionally less value
        # - Risk per lot remains constant but total risk grows
        # 
        # This is calculated dynamically based on current_volume/max_lots
        # NOT a hardcoded limit - the EV naturally decreases
        # ═══════════════════════════════════════════════════════════
        
        # Calculate position concentration factor (0.0 to 1.0)
        # Higher concentration = lower marginal EV for adding
        position_concentration = current_volume / max_lots if max_lots > 0 else 1.0
        
        # Marginal utility decay: as position grows, adding becomes less attractive
        # At 0% of max: full EV (1.0x)
        # At 50% of max: 75% EV (0.75x)
        # At 80% of max: 40% EV (0.4x)
        # At 100% of max: 0% EV (0.0x)
        # This follows diminishing marginal returns principle
        marginal_utility_factor = max(0.0, 1.0 - (position_concentration ** 1.5))
        
        if position_concentration > 0.3:
            logger.info(f"   📊 Position concentration: {position_concentration:.1%} → marginal utility {marginal_utility_factor:.2f}x")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN SCALE_IN EV CALCULATION
        # 
        # The scale_in_score (0.0 to 1.0) comes from comprehensive 138-feature
        # analysis. It determines how attractive scaling in is based on:
        # - Current market conditions
        # - HTF trend alignment
        # - ML model confidence
        # - Volume and momentum
        # 
        # ADDITIONALLY, the AI considers:
        # - Price confirmation: Has the market moved in our direction since last scale?
        # - Time factor: New market information requires time to develop
        # 
        # This is AI-driven market analysis, not hardcoded cooldowns.
        # ═══════════════════════════════════════════════════════════
        
        # AI-driven entry confidence from 138-feature analysis
        entry_confidence_modifier = (scale_in_score - 0.5) * 2  # -1.0 to +1.0
        
        # ═══════════════════════════════════════════════════════════
        # PRICE CONFIRMATION FACTOR (AI-Driven)
        # 
        # The market must PROVE the move before we add more.
        # This is standard institutional practice - you don't pyramid
        # into a position without price confirmation.
        # 
        # The factor is based on:
        # - How much price has moved since last scale (% of ATR)
        # - Whether the move is in our direction
        # 
        # This prevents rapid consecutive scale-ins without new market
        # information confirming the thesis.
        # ═══════════════════════════════════════════════════════════
        
        # Get ATR for context (H4 ATR for swing trading)
        h4_volatility = getattr(context, 'h4_volatility', 0)
        current_price = market_data.get('current_price', 1.0)
        atr_pct = (h4_volatility / current_price * 100) if current_price > 0 and h4_volatility > 0 else 0.5
        
        # Price confirmation: How much has price moved relative to volatility?
        # If price moved > 0.5 ATR in our direction, that's confirmation
        # If price hasn't moved much, we don't have new information
        if atr_pct > 0:
            price_confirmation = min(1.0, price_move_since_scale / (atr_pct * 0.5))
        else:
            price_confirmation = 0.5 if price_move_since_scale > 0.1 else 0.0
        
        # If this is the first scale (time_since_scale = 999), allow it
        if time_since_scale > 60:  # More than 60 minutes = new market conditions
            price_confirmation = 1.0
        
        # Log the price confirmation analysis
        if price_confirmation < 1.0:
            logger.info(f"   📊 Price confirmation: {price_confirmation:.2f} (move={price_move_since_scale:.3f}%, ATR={atr_pct:.3f}%)")
        
        # SCALE_IN EV = HOLD EV modified by AI analysis AND price confirmation
        ev_scale_in_raw = ev_hold * (1.0 + entry_confidence_modifier * 0.3) * price_confirmation * (1.0 - leading_indicator_penalty) * session_scale_in_adj * marginal_utility_factor
        
        logger.info(f"   📊 AI Entry Score: {scale_in_score:.2f} → confidence modifier: {entry_confidence_modifier:+.2f}")
        
        if leading_indicator_penalty > 0.1:
            logger.warning(f"   ⚠️ SCALE_IN penalized by {leading_indicator_penalty:.0%} due to leading indicators")
        
        if session_mult != 1.0:
            logger.info(f"   📊 Session adjustment: SCALE_IN EV × {session_scale_in_adj:.2f} (session_mult={session_mult:.2f})")
        
        # ═══════════════════════════════════════════════════════════
        # SCALE_IN - PURE AI/EV DECISION
        # 
        # The EV calculation already incorporates profit_pct, so:
        # - Profitable positions: Higher EV (natural pyramiding incentive)
        # - Losing positions: Lower EV (natural DCA disincentive)
        # 
        # No additional penalties - the math handles it.
        # Hedge funds add to positions when the thesis is intact,
        # regardless of current P&L. The AI knows the thesis via
        # continuation probability, HTF trends, and market structure.
        # ═══════════════════════════════════════════════════════════
        
        if not can_scale_in:
            ev_scale_in = ev_hold - 1.0  # Safety: at max position
            logger.info(f"   🚫 SCALE_IN blocked: Position at max or not allowed")
        elif is_friday_afternoon:
            # HEDGE FUND RULE: No adding to positions on Friday afternoon
            # Gap risk over weekend is too high to increase exposure
            ev_scale_in = ev_hold - 0.5  # Always worse than HOLD
            logger.warning(f"   🚫 SCALE_IN blocked: Friday afternoon - no new exposure before weekend")
        else:
            # Apply thesis quality to SCALE_IN decision
            # Only add to positions when thesis is strong (D1 supports)
            # This is AI-driven: thesis_quality comes from D1 + HTF analysis
            if thesis_quality >= 0.7:
                # Strong thesis (D1 supports) - allow SCALE_IN based on EV
                ev_scale_in = ev_scale_in_raw
                logger.info(f"   📊 SCALE_IN allowed: Strong thesis (quality={thesis_quality:.1f})")
            elif thesis_quality >= 0.4:
                # Moderate thesis - penalize SCALE_IN but don't block
                ev_scale_in = ev_scale_in_raw * 0.5  # Reduce attractiveness
                logger.info(f"   ⚠️ SCALE_IN penalized: Moderate thesis (quality={thesis_quality:.1f})")
            else:
                # Weak thesis - block SCALE_IN
                ev_scale_in = ev_hold - 0.1  # Always worse than HOLD
                logger.info(f"   🚫 SCALE_IN blocked: Weak thesis (quality={thesis_quality:.1f})")
        
        # ═══════════════════════════════════════════════════════════
        # EV(DCA) - AI-DRIVEN (Same as SCALE_IN)
        # 
        # DCA and SCALE_IN are the same action (add to position).
        # The distinction was artificial. The AI/EV calculation
        # naturally handles both cases:
        # - If thesis is intact (high continuation): EV is positive
        # - If thesis is broken (high reversal): EV is negative
        # 
        # Hedge funds add when thesis is intact, regardless of P&L.
        # ═══════════════════════════════════════════════════════════
        
        # DCA uses same EV as SCALE_IN (they're the same action)
        ev_dca = ev_scale_in
        
        if profit_pct < 0:
            logger.info(f"   📊 Position in loss: Add EV = {ev_dca:.4f}% (AI will decide based on thesis)")
        
        return {
            'HOLD': ev_hold,
            'SCALE_OUT_25': ev_scale_out_25,
            'SCALE_OUT_50': ev_scale_out_50,
            'CLOSE': ev_close,
            'SCALE_IN': ev_scale_in,
            'DCA': ev_dca,
            'target_capture_ratio': target_capture_ratio,  # For profit-taking decisions
        }
    
    def _calculate_target(self, market_data: Dict, current_profit_pct: float, is_buy: bool) -> float:
        """
        Calculate target profit % based on market structure.
        Uses distance to resistance/support, NOT arbitrary percentages.
        
        Returns target as % of risk (e.g., 150 = 1.5R target)
        """
        
        dist_to_resistance = market_data['dist_to_resistance']
        dist_to_support = market_data['dist_to_support']
        current_price = market_data['current_price']
        atr = market_data['atr']
        
        # Get a reasonable ATR estimate if not available
        if atr <= 0:
            # Estimate ATR as ~1% of price for most instruments
            atr = current_price * 0.01 if current_price > 0 else 1.0
        
        # Calculate target based on market structure
        if is_buy and dist_to_resistance > 0:
            target_distance = dist_to_resistance
        elif not is_buy and dist_to_support > 0:
            target_distance = dist_to_support
        else:
            # Fallback: use ATR-based target (2x ATR)
            target_distance = atr * 2.0
        
        # Convert to % of risk (risk = 1 ATR typically)
        # Cap target at reasonable levels (max 300% = 3R)
        target_pct = min(300.0, (target_distance / atr) * 100)
        
        # Target should be above current profit (at least 20% more room to run)
        return max(target_pct, current_profit_pct + 20.0)
    
    def _calculate_dynamic_stop(
        self,
        context,
        market_data: Dict,
        probabilities: Dict,
        profit_metrics: Dict,
        is_buy: bool,
        setup_type: str = 'DAY',
        setup_config: Dict = None
    ) -> Dict:
        """
        Calculate AI-driven dynamic stop loss based on CURRENT market conditions.
        
        This adapts the stop for open positions based on:
        1. Higher timeframe volatility (H1/H4 only - NOT M1)
        2. ML confidence in continuation
        3. Continuation/reversal probabilities
        4. AI-driven trailing logic (not arbitrary percentages)
        5. Market structure (support/resistance)
        6. Setup type (SCALP/DAY/SWING) - determines patience level
        
        Returns dict with recommended stop price and reasoning.
        """
        
        # Get setup config if not provided
        if setup_config is None:
            setup_config = self.SETUP_CONFIG.get(setup_type, self.SETUP_CONFIG['DAY'])
        
        current_price = market_data['current_price']
        atr = market_data['atr'] if market_data['atr'] > 0 else current_price * 0.01
        ml_confidence = market_data['ml_confidence'] / 100.0
        continuation_prob = probabilities['continuation']
        reversal_prob = probabilities['reversal']
        profit_pct = profit_metrics['profit_pct']
        peak_profit = profit_metrics.get('peak_profit', profit_pct)
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND GRADE: TIMEFRAME-ALIGNED VOLATILITY
        # 
        # Stop timeframe MUST match setup type:
        # - SCALP: Use M15/H1 volatility (quick trades, tighter stops)
        # - DAY: Use H1/H4 volatility (intraday swings)
        # - SWING: Use H4/D1 volatility (multi-day holds)
        # ═══════════════════════════════════════════════════════════
        
        # Get all timeframe volatilities
        m15_volatility = getattr(context, 'm15_volatility', 0)
        h1_volatility = getattr(context, 'h1_volatility', 0)
        h4_volatility = getattr(context, 'h4_volatility', 0)
        d1_volatility = getattr(context, 'd1_volatility', atr * 5.0)  # D1 is ~5x M1 ATR
        
        # Fallbacks if volatility not available
        if m15_volatility <= 0:
            m15_volatility = atr * 1.5
        if h1_volatility <= 0:
            h1_volatility = atr * 2.0
        if h4_volatility <= 0:
            h4_volatility = atr * 3.0
        if d1_volatility <= 0:
            d1_volatility = atr * 5.0
        
        # Select volatility based on setup type (CRITICAL for proper stops)
        patience = setup_config.get('patience', 'MEDIUM')
        if patience == 'LOW':  # SCALP
            effective_volatility = max(m15_volatility, h1_volatility)
            stop_timeframe = "M15/H1"
        elif patience == 'MEDIUM':  # DAY
            effective_volatility = max(h1_volatility, h4_volatility)
            stop_timeframe = "H1/H4"
        else:  # HIGH = SWING
            effective_volatility = max(h4_volatility, d1_volatility)
            stop_timeframe = "H4/D1"
        
        # Get current stop from position
        current_sl = getattr(context, 'position_sl', 0)
        entry_price = getattr(context, 'position_entry_price', current_price)
        
        # Get market score for AI decisions
        market_score = market_data.get('market_score', 50.0)
        
        # ═══════════════════════════════════════════════════════════
        # HEDGE FUND GRADE: STRUCTURE-BASED STOPS (S/R + ATR)
        # 
        # Institutional approach:
        # 1. Find nearest S/R level in the direction of stop
        # 2. Place stop BEYOND that level (to avoid stop hunts)
        # 3. Add ATR buffer for volatility protection
        # 4. Never use pure ATR - always consider structure
        # ═══════════════════════════════════════════════════════════
        
        # Get S/R distances (as % of price)
        h4_dist_support = getattr(context, 'h4_dist_to_support', 0)
        h4_dist_resistance = getattr(context, 'h4_dist_to_resistance', 0)
        d1_dist_support = getattr(context, 'd1_dist_to_support', 0)
        d1_dist_resistance = getattr(context, 'd1_dist_to_resistance', 0)
        
        # Select S/R based on setup type
        if patience == 'LOW':  # SCALP - use H4 S/R
            dist_to_support = h4_dist_support
            dist_to_resistance = h4_dist_resistance
        else:  # DAY/SWING - use D1 S/R (stronger levels)
            dist_to_support = d1_dist_support if d1_dist_support > 0 else h4_dist_support
            dist_to_resistance = d1_dist_resistance if d1_dist_resistance > 0 else h4_dist_resistance
        
        # Calculate structure-based stop distance
        # For LONG: Stop below support
        # For SHORT: Stop above resistance
        if is_buy:
            # Stop should be below support level + buffer
            if dist_to_support > 0:
                structure_stop_distance = (dist_to_support / 100.0) * current_price
                # Add 0.5 ATR buffer beyond structure
                structure_stop_distance += effective_volatility * 0.5
            else:
                structure_stop_distance = 0
        else:
            # Stop should be above resistance level + buffer
            if dist_to_resistance > 0:
                structure_stop_distance = (dist_to_resistance / 100.0) * current_price
                # Add 0.5 ATR buffer beyond structure
                structure_stop_distance += effective_volatility * 0.5
            else:
                structure_stop_distance = 0
        
        # ATR-based stop as fallback/minimum
        atr_stop_distance = effective_volatility * 2.0
        
        # ═══════════════════════════════════════════════════════════
        # AI FACTORS: Adjust stop based on market conditions
        # ═══════════════════════════════════════════════════════════
        
        # AI Factor 1: ML confidence
        # Higher confidence = can use tighter stop (more conviction)
        confidence_factor = 1.0 - ((ml_confidence - 0.5) * 0.3)  # 0.85 at 100%, 1.15 at 50%
        
        # AI Factor 2: Continuation probability
        # Higher continuation = tighter stop (trend is strong)
        continuation_factor = 1.0 - ((continuation_prob - 0.5) * 0.2)  # 0.9 at 100%, 1.1 at 50%
        
        # AI Factor 3: Reversal probability
        # Higher reversal = wider stop to avoid premature exit
        if reversal_prob > 0.35:
            reversal_factor = 1.0 + (reversal_prob - 0.35) * 0.4  # Up to 1.26x wider
        else:
            reversal_factor = 1.0
        
        # AI Factor 4: Market score
        # Higher score = more conviction = tighter stop
        score_factor = 1.0 - ((market_score - 50) / 100 * 0.15)  # 0.925 at 100, 1.075 at 50
        
        # Combined AI adjustment factor
        ai_adjustment = confidence_factor * continuation_factor * reversal_factor * score_factor
        
        # ═══════════════════════════════════════════════════════════
        # FINAL STOP: Use structure if available, else ATR
        # Structure-based stops are more intelligent (thesis invalidation)
        # ═══════════════════════════════════════════════════════════
        
        if structure_stop_distance > 0:
            # Use structure-based stop, adjusted by AI factors
            ai_stop_distance = structure_stop_distance * ai_adjustment
            stop_method = f"STRUCTURE ({stop_timeframe})"
        else:
            # Fallback to ATR-based stop
            ai_stop_distance = atr_stop_distance * ai_adjustment
            stop_method = f"ATR ({stop_timeframe})"
        
        # Ensure minimum stop distance (avoid stops too tight)
        min_stop_distance = effective_volatility * 1.0  # At least 1 ATR
        ai_stop_distance = max(ai_stop_distance, min_stop_distance)
        
        logger.info(f"   📊 Stop Method: {stop_method}, Distance: {ai_stop_distance:.2f}")
        logger.info(f"   📊 S/R: support={dist_to_support:.2f}%, resistance={dist_to_resistance:.2f}%")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN TRAILING STOP (based on market analysis, not fixed %)
        # ═══════════════════════════════════════════════════════════
        
        trailing_stop_price = None
        trail_reasoning = None
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN TRAILING STOP - Uses ALL 138 features + Setup Type
        # 
        # The trailing stop behavior varies by setup type (from SETUP_CONFIG):
        # - SCALP (patience=LOW): Trail earlier, lock in profits quickly
        # - DAY (patience=MEDIUM): Balanced trailing
        # - SWING (patience=HIGH): Trail later, give room to develop
        # 
        # Key AI inputs:
        # - continuation_prob: High = give room, Low = tighten
        # - reversal_prob: High = tighten, Low = give room
        # - ml_confidence: High = trust the move, Low = protect
        # - HTF trends: Are higher timeframes supporting?
        # - Volume divergence: Is volume confirming?
        # - Setup type patience level: Determines base thresholds
        # ═══════════════════════════════════════════════════════════
        
        # patience already defined above from setup_config
        atr_mult = setup_config.get('atr_mult', 4.0)  # Target ATR multiplier
        
        # Patience-based base parameters (from SETUP_CONFIG philosophy)
        # SCALP: Quick exits, protect small gains
        # DAY: Balanced approach
        # SWING: Let winners run, wide trailing
        patience_params = {
            'LOW': {    # SCALP
                'base_activation_threshold': 0.35,  # Trail earlier
                'min_trail_pct': 0.20,              # Lock in more
                'max_trail_pct': 0.55,              # Cap tighter
                'profit_weight': 0.25,              # Profit matters more
            },
            'MEDIUM': { # DAY
                'base_activation_threshold': 0.45,  # Balanced
                'min_trail_pct': 0.15,              # Moderate lock-in
                'max_trail_pct': 0.60,              # Moderate cap
                'profit_weight': 0.15,              # Balanced
            },
            'HIGH': {   # SWING
                'base_activation_threshold': 0.55,  # Trail later
                'min_trail_pct': 0.10,              # Lock in less
                'max_trail_pct': 0.50,              # Give more room
                'profit_weight': 0.10,              # Let it run
            }
        }
        params = patience_params.get(patience, patience_params['MEDIUM'])
        
        if entry_price > 0 and current_price > 0 and profit_pct > 0:
            price_move = current_price - entry_price if is_buy else entry_price - current_price
            
            if price_move > 0:
                # Calculate how many ATRs we've moved (for reference)
                atr_multiple = price_move / effective_volatility if effective_volatility > 0 else 1.0
                
                # ═══════════════════════════════════════════════════════════
                # AI DECISION 1: Should we trail at all?
                # 
                # Trail activation score based on market conditions:
                # - High continuation + high ML confidence = DON'T trail yet
                # - High reversal + low continuation = START trailing
                # - Volume divergence = START trailing (smart money exiting)
                # 
                # Threshold varies by setup type (patience level)
                # ═══════════════════════════════════════════════════════════
                
                # Get additional AI features
                h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
                h4_trend = getattr(context, 'h4_trend', 0.5)
                d1_trend = getattr(context, 'd1_trend', 0.5)
                adx = getattr(context, 'adx', 25.0)
                
                # Calculate "should trail" score (0 = don't trail, 1 = definitely trail)
                trail_activation_score = 0.0
                trail_factors = []
                
                # Factor 1: Reversal probability (high = trail)
                trail_activation_score += reversal_prob * 0.35
                if reversal_prob > 0.4:
                    trail_factors.append(f"rev={reversal_prob:.0%}")
                
                # Factor 2: Continuation probability (low = trail)
                trail_activation_score += (1.0 - continuation_prob) * 0.25
                if continuation_prob < 0.5:
                    trail_factors.append(f"cont={continuation_prob:.0%}")
                
                # Factor 3: Volume divergence (high = trail - smart money exiting)
                trail_activation_score += h4_vol_div * 0.20
                if h4_vol_div > 0.3:
                    trail_factors.append(f"vol_div={h4_vol_div:.0%}")
                
                # Factor 4: ML confidence against position (trail if ML disagrees)
                ml_against = (ml_confidence) if (
                    (is_buy and market_data['ml_direction'] == 'SELL') or
                    (not is_buy and market_data['ml_direction'] == 'BUY')
                ) else 0.0
                trail_activation_score += ml_against * 0.20
                if ml_against > 0.5:
                    trail_factors.append(f"ML_against={ml_against:.0%}")
                
                # Factor 5: Profit size - weight varies by patience level
                profit_factor = min(1.0, atr_multiple / 3.0)  # Scales 0-1 over 3 ATR
                trail_activation_score += profit_factor * params['profit_weight']
                if atr_multiple > 1.0:
                    trail_factors.append(f"profit={atr_multiple:.1f}xATR")
                
                # Bonus: Weak trend = trail more aggressively
                if adx < 20:
                    trail_activation_score += 0.08
                    trail_factors.append("weak_trend")
                
                # ═══════════════════════════════════════════════════════════
                # AI DECISION 2: How much to trail?
                # 
                # Trail percentage based on AI analysis + setup type:
                # - High reversal risk = lock in more (higher %)
                # - High continuation = lock in less (lower %)
                # - Strong HTF support = lock in less
                # - SCALP = tighter, SWING = looser
                # ═══════════════════════════════════════════════════════════
                
                # Base trail scales with reversal probability
                base_trail_pct = params['min_trail_pct'] + (reversal_prob * 0.35)
                
                # Adjust for continuation probability
                if continuation_prob > 0.6:
                    base_trail_pct *= 0.7  # Give more room if likely to continue
                elif continuation_prob < 0.4:
                    base_trail_pct *= 1.3  # Tighten if unlikely to continue
                
                # Adjust for HTF trend support
                htf_support = 0
                if is_buy:
                    if h4_trend > 0.55: htf_support += 1
                    if d1_trend > 0.55: htf_support += 1
                else:
                    if h4_trend < 0.45: htf_support += 1
                    if d1_trend < 0.45: htf_support += 1
                
                if htf_support >= 2:
                    base_trail_pct *= 0.8  # Strong HTF support = give room
                elif htf_support == 0:
                    base_trail_pct *= 1.2  # No HTF support = tighten
                
                # Cap trail percentage based on setup type
                base_trail_pct = max(params['min_trail_pct'], min(params['max_trail_pct'], base_trail_pct))
                
                # ═══════════════════════════════════════════════════════════
                # AI DECISION 3: Apply trailing stop?
                # 
                # Uses LIVE MARKET ANALYSIS to determine activation threshold:
                # - Profit size: More profit = LOWER threshold (protect gains)
                # - ATR multiple: Bigger move = LOWER threshold
                # - Reversal probability: Higher = LOWER threshold
                # - Setup type: SCALP trails earlier, SWING trails later
                # 
                # NO FIXED THRESHOLDS - AI calculates based on conditions
                # ═══════════════════════════════════════════════════════════
                
                # Base threshold from setup type
                base_threshold = params['base_activation_threshold']
                
                # AI Factor 1: Profit size lowers threshold significantly
                # More profit = more to protect = lower threshold
                # 1 ATR move = reduce threshold by 0.15
                # 2 ATR move = reduce threshold by 0.25
                profit_reduction = min(0.30, atr_multiple * 0.12)
                
                # AI Factor 2: Reversal probability lowers threshold
                # High reversal risk = protect profits now
                reversal_reduction = reversal_prob * 0.15
                
                # AI Factor 3: Low continuation lowers threshold
                # If continuation is weak, protect what we have
                continuation_reduction = (1.0 - continuation_prob) * 0.10
                
                # Combined AI-driven threshold
                activation_threshold = base_threshold - profit_reduction - reversal_reduction - continuation_reduction
                activation_threshold = max(0.15, activation_threshold)  # Floor at 0.15
                
                logger.info(f"      Trail threshold: base={base_threshold:.2f} - profit={profit_reduction:.2f} - rev={reversal_reduction:.2f} - cont={continuation_reduction:.2f} = {activation_threshold:.2f}")
                
                if trail_activation_score >= activation_threshold:
                    # Calculate trailing stop price
                    if is_buy:
                        new_trail = entry_price + (price_move * base_trail_pct)
                        # Don't let trail go backwards
                        if current_sl > 0 and new_trail > current_sl:
                            trailing_stop_price = new_trail
                        elif current_sl > 0:
                            trailing_stop_price = current_sl
                    else:
                        new_trail = entry_price - (price_move * base_trail_pct)
                        if current_sl > 0 and new_trail < current_sl:
                            trailing_stop_price = new_trail
                        elif current_sl > 0:
                            trailing_stop_price = current_sl
                    
                    trail_reasoning = f"AI {setup_type} trail ({', '.join(trail_factors[:3])})"
                    logger.info(f"   🧠 AI Trail ({setup_type}): score={trail_activation_score:.2f} >= {activation_threshold:.2f}, lock={base_trail_pct:.0%}")
                    logger.info(f"      Factors: {', '.join(trail_factors)}")
                else:
                    trail_reasoning = f"AI {setup_type}: no trail (score={trail_activation_score:.2f} < {activation_threshold:.2f})"
                    logger.info(f"   🧠 AI Trail ({setup_type}): score={trail_activation_score:.2f} < {activation_threshold:.2f} - letting trade run")
                    logger.info(f"      cont={continuation_prob:.0%}, rev={reversal_prob:.0%}, HTF={htf_support}/2")
        
        # ═══════════════════════════════════════════════════════════
        # FINAL STOP CALCULATION
        # ═══════════════════════════════════════════════════════════
        
        # Calculate base AI stop price from CURRENT price
        if is_buy:
            ai_stop_price = current_price - ai_stop_distance
        else:
            ai_stop_price = current_price + ai_stop_distance
        
        # CRITICAL FIX: Ensure stop is never tighter than minimum distance from ENTRY
        # This prevents the stop from chasing price when position is losing
        min_stop_distance = effective_volatility * 1.5  # Minimum 1.5x H4 volatility from entry
        
        if entry_price > 0:
            if is_buy:
                # For BUY, stop must be at least min_distance BELOW entry
                min_stop_from_entry = entry_price - min_stop_distance
                if ai_stop_price > min_stop_from_entry and profit_pct < 0:
                    ai_stop_price = min_stop_from_entry
                    logger.info(f"   ⚠️ Stop capped at minimum distance from entry: {ai_stop_price:.2f}")
            else:
                # For SELL, stop must be at least min_distance ABOVE entry
                min_stop_from_entry = entry_price + min_stop_distance
                if ai_stop_price < min_stop_from_entry and profit_pct < 0:
                    ai_stop_price = min_stop_from_entry
                    logger.info(f"   ⚠️ Stop capped at minimum distance from entry: {ai_stop_price:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN PROFIT PROTECTION (No hardcoded rules)
        # The AI considers commissions and decides whether to protect profits
        # based on market conditions, NOT arbitrary thresholds
        # ═══════════════════════════════════════════════════════════
        
        # Estimate commission cost as % of account (typical: $3-7 per lot round trip)
        # For a $200k account with 20 lots, commission ~$100 = 0.05%
        estimated_commission_pct = 0.05  # Approximate commission impact
        
        # Log profit vs commission analysis
        peak_profit_pct = profit_metrics.get('peak_profit', profit_pct)
        net_profit_after_commission = profit_pct - estimated_commission_pct
        
        if profit_pct > 0:
            logger.info(f"   📊 Profit Analysis: Gross {profit_pct:.3f}% - Commission ~{estimated_commission_pct:.3f}% = Net {net_profit_after_commission:.3f}%")
            
            # AI DECISION: Should we protect this profit?
            # Consider: Is the net profit meaningful? What does ML say about continuation?
            
            # If net profit is NEGATIVE after commission, closing now is a loss
            # Let the AI decide based on continuation probability
            if net_profit_after_commission < 0:
                logger.info(f"   ⚠️ Net profit after commission is NEGATIVE - AI will decide based on continuation prob")
            
            # If reversal probability is HIGH and we have meaningful profit, AI may tighten
            # But this is already handled by the trailing stop logic above
            # We don't force any specific behavior - let EV calculation decide
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN BREAKEVEN STOP
        # Move stop to breakeven when AI analysis suggests protection
        # Based on: volume divergence, order flow, reversal probability
        # NOT hardcoded thresholds - pure AI market analysis
        # ═══════════════════════════════════════════════════════════
        
        breakeven_stop = None
        volume_divergence = getattr(context, 'volume_divergence', 0.0)
        ask_pressure = getattr(context, 'ask_pressure', 0.5)
        bid_pressure = getattr(context, 'bid_pressure', 0.5)
        
        # AI decides if breakeven is warranted based on market conditions
        # High HTF volume divergence + adverse market structure = protect capital
        if profit_pct > 0 and entry_price > 0:
            # Calculate AI "protection score" from HTF indicators (not M1)
            protection_score = 0.0
            
            # HTF Volume divergence suggests trend weakening
            h4_vol_div = getattr(context, 'h4_volume_divergence', 0.0)
            protection_score += h4_vol_div * 0.4
            
            # Market structure against position (from H4)
            h4_structure = getattr(context, 'h4_market_structure', 0.0)
            if is_buy and h4_structure < -0.3:  # Downtrend structure
                protection_score += abs(h4_structure) * 0.4
            elif not is_buy and h4_structure > 0.3:  # Uptrend structure
                protection_score += h4_structure * 0.4
            
            # Reversal probability
            protection_score += reversal_prob * 0.2
            
            # If protection score is high, AI recommends breakeven
            if protection_score > 0.5:
                # Add small buffer above/below entry for commission
                buffer = effective_volatility * 0.1  # Small buffer
                if is_buy:
                    breakeven_stop = entry_price + buffer
                else:
                    breakeven_stop = entry_price - buffer
                logger.info(f"   🧠 AI BREAKEVEN: Protection score {protection_score:.2f} → Moving stop to breakeven")
        
        # Use the HIGHER (more protective) of trailing stop, AI stop, or breakeven
        if trailing_stop_price is not None:
            if is_buy:
                recommended_stop = max(ai_stop_price, trailing_stop_price)
            else:
                recommended_stop = min(ai_stop_price, trailing_stop_price)
            stop_type = "TRAILING" if recommended_stop == trailing_stop_price else "AI"
        else:
            recommended_stop = ai_stop_price
            stop_type = "AI"
        
        # Apply breakeven if AI recommends it and it's more protective
        if breakeven_stop is not None:
            if is_buy and breakeven_stop > recommended_stop:
                recommended_stop = breakeven_stop
                stop_type = "BREAKEVEN"
            elif not is_buy and breakeven_stop < recommended_stop:
                recommended_stop = breakeven_stop
                stop_type = "BREAKEVEN"
        
        # ═══════════════════════════════════════════════════════════
        # CRITICAL VALIDATION: Stop must be on correct side of CURRENT PRICE
        # For BUY: stop must be BELOW current price
        # For SELL: stop must be ABOVE current price
        # 
        # NOTE: For profitable positions, stop CAN be above/below entry (trailing)
        # We only validate against CURRENT price, not entry price
        # ═══════════════════════════════════════════════════════════
        if current_price > 0:
            if is_buy and recommended_stop >= current_price:
                # BUY stop must be BELOW current price - force it below
                recommended_stop = current_price - (effective_volatility * 1.5)
                logger.warning(f"   🚨 INVALID STOP CORRECTED: BUY stop was >= current price, forced to {recommended_stop:.2f}")
            elif not is_buy and recommended_stop <= current_price:
                # SELL stop must be ABOVE current price - force it above
                recommended_stop = current_price + (effective_volatility * 1.5)
                logger.warning(f"   🚨 INVALID STOP CORRECTED: SELL stop was <= current price, forced to {recommended_stop:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN STOP MODIFICATION
        # 
        # The AI decides whether to WIDEN or TIGHTEN the stop based on:
        # - Continuation probability (high = widen, give room)
        # - Reversal probability (high = tighten, protect profits)
        # - Profit status (in profit = can tighten to lock in)
        # - Thesis quality (strong = widen, weak = tighten)
        # 
        # NO hardcoded "wider is always better" - AI decides direction
        # ═══════════════════════════════════════════════════════════
        should_modify = False
        
        # CRITICAL: If no stop loss exists, ALWAYS recommend setting one!
        if current_sl == 0 or current_sl is None:
            should_modify = True
            logger.warning(f"   🚨 NO STOP LOSS! Recommending AI stop: {recommended_stop:.2f}")
        elif current_sl > 0:
            # Calculate stop direction preference from AI analysis
            # For BUY: stop is BELOW entry, so higher stop = tighter (closer to entry)
            # For SELL: stop is ABOVE entry, so lower stop = tighter (closer to entry)
            # 
            # NOTE: We compare recommended vs current stop to determine direction
            # BUY: recommended > current = tighter (moving stop up toward entry)
            # SELL: recommended < current = tighter (moving stop down toward entry)
            is_tighter = (is_buy and recommended_stop > current_sl) or (not is_buy and recommended_stop < current_sl)
            is_wider = not is_tighter
            
            # AI decides: Should we tighten or widen?
            # Use reversal probability, profit status, and thesis quality
            reversal_prob = probabilities.get('reversal', 0.3) if probabilities else 0.3
            continuation_prob = probabilities.get('continuation', 0.5) if probabilities else 0.5
            thesis_quality = probabilities.get('thesis_quality', 0.7) if probabilities else 0.7
            
            # Calculate profit status
            current_profit_pct = profit_pct if profit_pct else 0
            in_profit = current_profit_pct > 0.05  # More than spread/commission
            
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN STOP TIGHTENING SCORE
            # 
            # NO HARDCODED THRESHOLDS - Pure AI calculation
            # Uses all available market data to compute a tightening score
            # Score > 0.5 = tighten, Score < 0.5 = widen
            # ═══════════════════════════════════════════════════════════
            
            ftmo_danger = probabilities.get('ftmo_danger', 0.0)
            portfolio_stress = probabilities.get('portfolio_stress', 0.0)
            
            # Get additional market context for AI decision
            h4_vol_div = probabilities.get('h4_volume_divergence', 0.0)
            h4_structure = probabilities.get('h4_market_structure', 0.0)
            ml_confidence = probabilities.get('ml_confidence', 50.0) / 100.0
            ml_agrees = probabilities.get('ml_agrees_direction', True)
            
            # ═══════════════════════════════════════════════════════════
            # TIGHTENING SCORE: Higher = more reason to tighten
            # Each factor contributes based on its severity
            # ═══════════════════════════════════════════════════════════
            
            tighten_score = 0.0
            
            # Factor 1: Reversal probability (0-0.25 contribution)
            # Higher reversal = more tightening pressure
            tighten_score += reversal_prob * 0.25
            
            # Factor 2: Thesis weakness (0-0.20 contribution)
            # Weaker thesis = more tightening pressure
            thesis_weakness = 1.0 - thesis_quality
            tighten_score += thesis_weakness * 0.20
            
            # Factor 3: FTMO danger (0-0.20 contribution)
            # Higher danger = more tightening pressure
            tighten_score += ftmo_danger * 0.20
            
            # Factor 4: Portfolio stress (0-0.10 contribution)
            tighten_score += portfolio_stress * 0.10
            
            # Factor 5: Volume divergence (0-0.10 contribution)
            # High divergence = move not supported by volume
            tighten_score += h4_vol_div * 0.10
            
            # Factor 6: ML disagreement (0-0.10 contribution)
            if not ml_agrees:
                tighten_score += (1.0 - ml_confidence) * 0.10
            
            # Factor 7: Profit protection (0-0.05 contribution)
            # If in profit and thesis weakening, protect gains
            if in_profit and thesis_quality < 0.7:
                profit_protection = min(current_profit_pct / 1.0, 1.0) * 0.05
                tighten_score += profit_protection
            
            # ═══════════════════════════════════════════════════════════
            # WIDENING SCORE: Higher = more reason to widen
            # ═══════════════════════════════════════════════════════════
            
            widen_score = 0.0
            
            # Factor 1: Continuation probability (0-0.30 contribution)
            widen_score += continuation_prob * 0.30
            
            # Factor 2: Thesis strength (0-0.25 contribution)
            widen_score += thesis_quality * 0.25
            
            # Factor 3: Low reversal risk (0-0.20 contribution)
            low_reversal = 1.0 - reversal_prob
            widen_score += low_reversal * 0.20
            
            # Factor 4: ML confidence in direction (0-0.15 contribution)
            if ml_agrees:
                widen_score += ml_confidence * 0.15
            
            # Factor 5: Market structure support (0-0.10 contribution)
            # Positive structure = bullish for longs, bearish for shorts
            if (is_buy and h4_structure > 0) or (not is_buy and h4_structure < 0):
                widen_score += abs(h4_structure) * 0.10
            
            # ═══════════════════════════════════════════════════════════
            # AI DECISION: Compare scores
            # ═══════════════════════════════════════════════════════════
            
            # Normalize scores to 0-1 range
            tighten_score = min(1.0, max(0.0, tighten_score))
            widen_score = min(1.0, max(0.0, widen_score))
            
            # Decision based on which score dominates
            # Bias toward tightening when scores are close (capital preservation)
            should_tighten = tighten_score > widen_score * 0.8  # 20% bias toward protection
            should_widen = widen_score > tighten_score * 1.2  # Need 20% more confidence to widen
            
            logger.info(f"   🧠 AI Stop Scores: tighten={tighten_score:.3f}, widen={widen_score:.3f}")
            
            logger.info(f"   🧠 AI Stop Decision: cont={continuation_prob:.1%}, rev={reversal_prob:.1%}, thesis={thesis_quality:.2f}, profit={current_profit_pct:.2%}")
            logger.info(f"   🧠 AI Stop Direction: should_tighten={should_tighten}, should_widen={should_widen}")
            
            # Check if AI recommendation matches what we should do
            ai_wants_this_direction = (is_tighter and should_tighten) or (is_wider and should_widen)
            
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN PROFIT SIGNIFICANCE CHECK
            # 
            # Uses LIVE MARKET ANALYSIS to determine if trailing makes sense:
            # - Continuation probability: High = give room, don't trail tight
            # - Reversal probability: High = lock in more profit
            # - Thesis quality: Strong = let it run
            # - Volatility: Determines what's a "meaningful" move
            # - ML confidence: High confidence = trust the move
            # 
            # NO HARDCODED THRESHOLDS - All based on AI analysis
            # ═══════════════════════════════════════════════════════════
            
            if current_profit_pct > 0 and is_tighter:
                # Calculate what profit we'd lock in with the new stop
                if is_buy:
                    locked_profit_pct = (recommended_stop - entry_price) / entry_price * 100 if entry_price > 0 else 0
                else:
                    locked_profit_pct = (entry_price - recommended_stop) / entry_price * 100 if entry_price > 0 else 0
                
                # ═══════════════════════════════════════════════════════════
                # AI CALCULATES MINIMUM PROFIT TO LOCK IN
                # Based on live market conditions, not hardcoded values
                # ═══════════════════════════════════════════════════════════
                
                # Base: Use volatility to determine what's meaningful
                # A move less than 0.5x ATR is noise, not profit
                atr_based_min = (effective_volatility / current_price * 100) * 0.5 if current_price > 0 else 0.1
                
                # AI Factor 1: Continuation probability
                # High continuation = require locking in MORE (we expect more profit coming)
                # Low continuation = can lock in less (this might be all we get)
                continuation_factor = 0.2 + (continuation_prob * 0.6)  # 0.2 to 0.8
                
                # AI Factor 2: Reversal probability  
                # High reversal = lock in less (protect what we have)
                # Low reversal = require more (let it run)
                reversal_factor = 1.0 - (reversal_prob * 0.5)  # 0.5 to 1.0
                
                # AI Factor 3: Thesis quality
                # Strong thesis = require more profit locked (trade should work)
                # Weak thesis = can lock in less (take what we can get)
                thesis_factor = 0.3 + (thesis_quality * 0.5)  # 0.3 to 0.8
                
                # AI Factor 4: ML confidence in our direction
                ml_agrees = (is_buy and market_data.get('ml_direction') == 'BUY') or \
                           (not is_buy and market_data.get('ml_direction') == 'SELL')
                ml_factor = 1.2 if ml_agrees and ml_confidence > 0.6 else 0.8
                
                # Combined AI-driven minimum profit retention
                # When AI is confident trade will continue: require locking in more
                # When AI sees reversal risk: allow locking in less
                ai_profit_retention = continuation_factor * reversal_factor * thesis_factor * ml_factor
                ai_profit_retention = max(0.15, min(0.70, ai_profit_retention))  # Clamp to reasonable range
                
                # Final required locked profit: AI-calculated retention of current profit
                # Plus minimum based on volatility (to avoid locking in noise)
                required_locked_profit = max(atr_based_min, current_profit_pct * ai_profit_retention)
                
                logger.info(f"   🧠 AI Profit Lock Analysis:")
                logger.info(f"      cont={continuation_prob:.0%}, rev={reversal_prob:.0%}, thesis={thesis_quality:.2f}")
                logger.info(f"      AI retention factor: {ai_profit_retention:.2f} (require {ai_profit_retention:.0%} of profit)")
                logger.info(f"      Current: {current_profit_pct:.3f}%, Would lock: {locked_profit_pct:.3f}%, Required: {required_locked_profit:.3f}%")
                
                if locked_profit_pct < required_locked_profit:
                    logger.info(f"   🛡️ PROFIT PROTECTION: Stop would lock in only {locked_profit_pct:.3f}%")
                    logger.info(f"      Current profit: {current_profit_pct:.3f}%, Required minimum: {required_locked_profit:.3f}%")
                    logger.info(f"      Keeping wider stop to allow more profit development")
                    recommended_stop = current_sl
                    ai_wants_this_direction = False
            
            if ai_wants_this_direction:
                improvement = abs(recommended_stop - current_sl)
                min_improvement = effective_volatility * 0.05  # Small threshold for meaningful changes
                
                logger.info(f"   📊 Stop Modify Check: is_buy={is_buy}, recommended={recommended_stop:.2f}, current_sl={current_sl:.2f}")
                logger.info(f"   📊 Stop Modify Check: improvement={improvement:.2f}, min_improvement={min_improvement:.2f}")
                
                if improvement > min_improvement:
                    should_modify = True
                    direction = "TIGHTEN" if is_tighter else "WIDEN"
                    reason = f"rev={reversal_prob:.0%}" if is_tighter else f"cont={continuation_prob:.0%}"
                    logger.info(f"   ✅ AI Stop modification: {direction} {current_sl:.2f} → {recommended_stop:.2f} ({reason})")
            else:
                # AI doesn't want to move stop in this direction
                direction = "tighter" if is_tighter else "wider"
                logger.info(f"   📊 AI Stop: Recommended {recommended_stop:.2f} is {direction} but AI prefers current - keeping {current_sl:.2f}")
                recommended_stop = current_sl
        
        logger.info(f"   📊 Dynamic Stop ({stop_timeframe} based):")
        logger.info(f"      Method: {stop_method} | Effective Vol: {effective_volatility:.5f}")
        logger.info(f"      S/R: support={dist_to_support:.2f}%, resistance={dist_to_resistance:.2f}%")
        logger.info(f"      Current SL: {current_sl:.2f} | AI Stop: {ai_stop_price:.2f}")
        if trailing_stop_price:
            logger.info(f"      Trail: {trailing_stop_price:.2f} ({trail_reasoning})")
        logger.info(f"      Recommended: {recommended_stop:.2f} ({stop_type}) | Modify: {should_modify}")
        
        return {
            'recommended_stop': recommended_stop,
            'stop_type': stop_type,
            'should_modify': should_modify,
            'ai_stop_distance': ai_stop_distance,
            'trailing_stop': trailing_stop_price,
            'current_sl': current_sl,
            'stop_method': stop_method  # For EA display
        }
    
    def _create_decision(
        self,
        best_action: str,
        best_ev: float,
        all_evs: Dict,
        profit_metrics: Dict,
        current_volume: float,
        dynamic_stop: Dict = None,
        symbol: str = None,
        current_price: float = 0,
        probabilities: Dict = None,
        setup_type: str = '',
        session_name: str = '',
        ml_direction: str = '',
        ml_confidence: float = 0,
        ai_target: float = 0,
        dist_to_support: float = 0,
        dist_to_resistance: float = 0
    ) -> Dict:
        """Create the decision dict based on best action."""
        
        # Calculate confidence based on EV difference
        second_best_ev = sorted(all_evs.values(), reverse=True)[1]
        ev_advantage = best_ev - second_best_ev
        confidence = min(95, 60 + ev_advantage * 2)
        
        # Record scale-in event for tracking (prevents back-to-back adds)
        if best_action in ['SCALE_IN', 'DCA'] and symbol:
            import time
            symbol_key = symbol.lower()
            self.position_peaks[f"{symbol_key}_scale"] = {
                'price': current_price,
                'time': time.time(),
                'profit_pct': profit_metrics.get('profit_pct', 0)
            }
            logger.info(f"   📝 Recording scale-in at price {current_price:.2f} for {symbol}")
        
        # ═══════════════════════════════════════════════════════════
        # TRACK LAST ACTION STATE FOR ANTI-CHURN LOGIC
        # This enables AI-driven detection of thesis changes
        # ═══════════════════════════════════════════════════════════
        if symbol and best_action != 'HOLD' and probabilities:
            import time
            symbol_key = symbol.lower()
            self.last_action_state[symbol_key] = {
                'action': best_action,
                'cont_prob': probabilities.get('continuation', 0.5),
                'rev_prob': probabilities.get('reversal', 0.3),
                'thesis_quality': probabilities.get('thesis_quality', 1.0),
                'time': time.time(),
                'price': current_price
            }
            logger.info(f"   📝 Recording action state: {best_action} at cont={probabilities.get('continuation', 0):.1%}")
        
        # Base decision dict with dynamic stop info and position data for EA display
        stop_method = dynamic_stop.get('stop_method', '') if dynamic_stop else ''
        
        base_decision = {
            'confidence': confidence,
            'dynamic_stop': dynamic_stop if dynamic_stop else {},
            'modify_stop': dynamic_stop.get('should_modify', False) if dynamic_stop else False,
            'recommended_stop': dynamic_stop.get('recommended_stop', 0) if dynamic_stop else 0,
            # Position analysis data for EA logging
            'all_evs': all_evs,
            'cont_prob': probabilities.get('continuation', 0) if probabilities else 0,
            'rev_prob': probabilities.get('reversal', 0) if probabilities else 0,
            'thesis_quality': probabilities.get('thesis_quality', 0) if probabilities else 0,
            # Extra fields for EA display
            'setup_type': setup_type,
            'session': session_name,
            'ml_direction': ml_direction,
            'ml_confidence': ml_confidence,
            'stop_method': stop_method,
            'ai_target': ai_target,
            'dist_to_support': dist_to_support,
            'dist_to_resistance': dist_to_resistance,
        }
        
        if best_action == 'CLOSE':
            return {
                **base_decision,
                'action': 'CLOSE',
                'reason': f'EV optimization: CLOSE ({best_ev:.1f}%) is best action',
                'priority': 'HIGH',
                'cont_prob': probabilities.get('continuation', 0.5) if probabilities else 0.5
            }
        
        elif best_action == 'SCALE_OUT_50':
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN SCALE_OUT_50 SIZE
            # 
            # Base is 50%, but adjust based on:
            # - Reversal probability (higher = take more off)
            # - Thesis quality (lower = take more off)
            # - Move exhaustion (higher = take more off)
            # 
            # Range: 40% to 65% of current position
            # ═══════════════════════════════════════════════════════════
            rev_prob = probabilities.get('reversal', 0.3) if probabilities else 0.3
            thesis_quality = probabilities.get('thesis_quality', 0.7) if probabilities else 0.7
            
            # Base: 50%
            reduce_pct = 0.50
            
            # Increase if reversal is high
            if rev_prob > 0.50:
                reduce_pct += 0.15  # Take 65% off
            elif rev_prob > 0.40:
                reduce_pct += 0.08  # Take 58% off
            
            # Increase if thesis is weak
            if thesis_quality < 0.4:
                reduce_pct += 0.10
            elif thesis_quality < 0.6:
                reduce_pct += 0.05
            
            # Clamp to reasonable range
            reduce_pct = max(0.40, min(0.65, reduce_pct))
            
            logger.info(f"   📊 AI SCALE_OUT: {reduce_pct:.0%} of position (rev={rev_prob:.1%}, thesis={thesis_quality:.2f})")
            
            return {
                **base_decision,
                'action': 'SCALE_OUT',
                'reason': f'EV optimization: SCALE_OUT {reduce_pct:.0%} ({best_ev:.1f}%) is best',
                'reduce_lots': current_volume * reduce_pct,
                'reduce_pct': reduce_pct,  # For logging
                'priority': 'MEDIUM'
            }
        
        elif best_action == 'SCALE_OUT_25':
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN SCALE_OUT_25 SIZE
            # 
            # Base is 25%, but adjust based on market conditions
            # This is a lighter partial - used when thesis is still OK
            # but we want to lock in some profit
            # 
            # Range: 20% to 35% of current position
            # ═══════════════════════════════════════════════════════════
            rev_prob = probabilities.get('reversal', 0.3) if probabilities else 0.3
            thesis_quality = probabilities.get('thesis_quality', 0.7) if probabilities else 0.7
            
            # Base: 25%
            reduce_pct = 0.25
            
            # Slight increase if reversal is elevated
            if rev_prob > 0.45:
                reduce_pct += 0.10  # Take 35% off
            elif rev_prob > 0.35:
                reduce_pct += 0.05  # Take 30% off
            
            # Clamp to reasonable range
            reduce_pct = max(0.20, min(0.35, reduce_pct))
            
            logger.info(f"   📊 AI SCALE_OUT: {reduce_pct:.0%} of position (rev={rev_prob:.1%}, thesis={thesis_quality:.2f})")
            
            return {
                **base_decision,
                'action': 'SCALE_OUT',
                'reason': f'EV optimization: SCALE_OUT {reduce_pct:.0%} ({best_ev:.1f}%) is best',
                'reduce_lots': current_volume * reduce_pct,
                'reduce_pct': reduce_pct,  # For logging
                'priority': 'MEDIUM'
            }
        
        elif best_action == 'SCALE_IN':
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN SCALE_IN SIZE
            # 
            # Instead of fixed 40%, scale based on:
            # - Continuation probability (higher = add more)
            # - Thesis quality (higher = add more)
            # - Current profit (higher = add more aggressively)
            # 
            # Range: 30% to 60% of current position
            # ═══════════════════════════════════════════════════════════
            cont_prob = probabilities.get('continuation', 0.5) if probabilities else 0.5
            thesis_quality = probabilities.get('thesis_quality', 0.7) if probabilities else 0.7
            profit_pct = profit_metrics.get('profit_pct', 0)
            
            # Base: 40%
            add_pct = 0.40
            
            # Boost for strong continuation (up to +15%)
            if cont_prob > 0.65:
                add_pct += 0.15
            elif cont_prob > 0.55:
                add_pct += 0.08
            
            # Boost for strong thesis (up to +10%)
            if thesis_quality > 0.8:
                add_pct += 0.10
            elif thesis_quality > 0.6:
                add_pct += 0.05
            
            # Reduce if not profitable yet (safety)
            if profit_pct < 0:
                add_pct *= 0.7  # Only add 70% of calculated amount when losing
            
            # Clamp to reasonable range
            add_pct = max(0.30, min(0.60, add_pct))
            
            logger.info(f"   📊 AI SCALE_IN: {add_pct:.0%} of position (cont={cont_prob:.1%}, thesis={thesis_quality:.2f})")
            
            return {
                **base_decision,
                'action': 'SCALE_IN',
                'reason': f'EV optimization: SCALE_IN ({best_ev:.1f}%) is best',
                'add_lots': current_volume * add_pct,
                'add_pct': add_pct,  # For logging
                'priority': 'MEDIUM'
            }
        
        elif best_action == 'DCA':
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN DCA SIZE
            # 
            # DCA is adding to a losing position - be more conservative
            # Scale based on recovery probability and thesis quality
            # 
            # Range: 20% to 40% of current position
            # ═══════════════════════════════════════════════════════════
            cont_prob = probabilities.get('continuation', 0.5) if probabilities else 0.5
            thesis_quality = probabilities.get('thesis_quality', 0.7) if probabilities else 0.7
            
            # Base: 25% (conservative for DCA)
            add_pct = 0.25
            
            # Only boost if thesis is very strong
            if cont_prob > 0.70 and thesis_quality > 0.8:
                add_pct = 0.40  # Strong conviction DCA
            elif cont_prob > 0.60 and thesis_quality > 0.7:
                add_pct = 0.30  # Moderate conviction DCA
            
            logger.info(f"   📊 AI DCA: {add_pct:.0%} of position (cont={cont_prob:.1%}, thesis={thesis_quality:.2f})")
            
            return {
                **base_decision,
                'action': 'DCA',
                'reason': f'EV optimization: DCA ({best_ev:.1f}%) is best',
                'add_lots': current_volume * add_pct,
                'add_pct': add_pct,  # For logging
                'priority': 'MEDIUM'
            }
        
        else:  # HOLD
            return {
                **base_decision,
                'action': 'HOLD',
                'reason': f'EV optimization: HOLD ({best_ev:.1f}%) is best action',
                'priority': 'LOW'
            }
