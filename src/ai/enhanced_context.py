"""
Enhanced Trading Context
========================
Unified data structure that passes ALL 100 features to every AI component.

Instead of each component only seeing fragments, they all see the complete picture:
- Multi-timeframe data (M1, H1, H4)
- MT5 indicators
- Timeframe alignment
- Volume intelligence
- Order book pressure
- Market regime

This ensures Position Manager, Trade Manager, Risk Manager, and Exit Logic
all make decisions based on the SAME comprehensive data.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class EnhancedTradingContext:
    """
    Complete market context with all 100 features.
    Every AI component receives this - no more fragmented data.
    """
    
    # ═══════════════════════════════════════════════════════════
    # CORE PRICE DATA
    # ═══════════════════════════════════════════════════════════
    symbol: str
    current_price: float
    account_balance: float
    contract_size: float  # From broker via EA
    
    # ═══════════════════════════════════════════════════════════
    # MULTI-TIMEFRAME FEATURES (105 features - ALL 7 TIMEFRAMES!)
    # ═══════════════════════════════════════════════════════════
    # M1 (15 features)
    m1_returns: float = 0.0
    m1_volatility: float = 0.0
    m1_rsi: float = 50.0
    m1_macd: float = 0.0
    m1_trend: float = 0.0  # 1.0 = bullish, 0.0 = bearish
    m1_momentum: float = 0.0
    m1_volume_ratio: float = 1.0
    m1_bb_position: float = 0.5
    m1_price_to_sma: float = 1.0
    m1_hl_ratio: float = 0.0
    m1_range: float = 0.0
    m1_close_pos: float = 0.5
    m1_strength: float = 0.0
    m1_sma_20: float = 0.0
    m1_sma_50: float = 0.0
    
    # M5 (15 features)
    m5_returns: float = 0.0
    m5_volatility: float = 0.0
    m5_rsi: float = 50.0
    m5_macd: float = 0.0
    m5_trend: float = 0.0
    m5_momentum: float = 0.0
    m5_bb_position: float = 0.5
    m5_price_to_sma: float = 1.0
    m5_hl_ratio: float = 0.0
    m5_range: float = 0.0
    m5_close_pos: float = 0.5
    m5_strength: float = 0.0
    m5_sma_20: float = 0.0
    m5_sma_50: float = 0.0
    m5_macd_signal: float = 0.0
    
    # M15 (15 features) ⭐ THE SWING TIMEFRAME
    m15_returns: float = 0.0
    m15_volatility: float = 0.0
    m15_rsi: float = 50.0
    m15_macd: float = 0.0
    m15_trend: float = 0.0
    m15_momentum: float = 0.0
    m15_bb_position: float = 0.5
    m15_price_to_sma: float = 1.0
    m15_hl_ratio: float = 0.0
    m15_range: float = 0.0
    m15_close_pos: float = 0.5
    m15_strength: float = 0.0
    m15_sma_20: float = 0.0
    m15_sma_50: float = 0.0
    m15_macd_signal: float = 0.0
    
    # M30 (15 features)
    m30_returns: float = 0.0
    m30_volatility: float = 0.0
    m30_rsi: float = 50.0
    m30_macd: float = 0.0
    m30_trend: float = 0.0
    m30_momentum: float = 0.0
    m30_bb_position: float = 0.5
    m30_price_to_sma: float = 1.0
    m30_hl_ratio: float = 0.0
    m30_range: float = 0.0
    m30_close_pos: float = 0.5
    m30_strength: float = 0.0
    m30_sma_20: float = 0.0
    m30_sma_50: float = 0.0
    m30_macd_signal: float = 0.0
    
    # H1 (15 features)
    h1_returns: float = 0.0
    h1_volatility: float = 0.0
    h1_rsi: float = 50.0
    h1_macd: float = 0.0
    h1_trend: float = 0.0
    h1_momentum: float = 0.0
    h1_volume_ratio: float = 1.0
    h1_bb_position: float = 0.5
    h1_price_to_sma: float = 1.0
    h1_hl_ratio: float = 0.0
    h1_range: float = 0.0
    h1_close_pos: float = 0.5
    h1_strength: float = 0.0
    h1_sma_20: float = 0.0
    h1_sma_50: float = 0.0
    
    # H4 (15 features)
    h4_returns: float = 0.0
    h4_volatility: float = 0.0
    h4_rsi: float = 50.0
    h4_macd: float = 0.0
    h4_trend: float = 0.0
    h4_momentum: float = 0.0
    h4_volume_ratio: float = 1.0
    h4_bb_position: float = 0.5
    h4_price_to_sma: float = 1.0
    h4_hl_ratio: float = 0.0
    h4_range: float = 0.0
    h4_close_pos: float = 0.5
    h4_strength: float = 0.0
    h4_sma_20: float = 0.0
    h4_sma_50: float = 0.0
    
    # D1 (15 features)
    d1_returns: float = 0.0
    d1_volatility: float = 0.0
    d1_rsi: float = 50.0
    d1_macd: float = 0.0
    d1_trend: float = 0.0
    d1_momentum: float = 0.0
    d1_bb_position: float = 0.5
    d1_price_to_sma: float = 1.0
    d1_hl_ratio: float = 0.0
    d1_range: float = 0.0
    d1_close_pos: float = 0.5
    d1_strength: float = 0.0
    d1_sma_20: float = 0.0
    d1_sma_50: float = 0.0
    d1_macd_signal: float = 0.0
    
    # W1 - Weekly (for hierarchical bias)
    w1_trend: float = 0.5
    w1_momentum: float = 0.0
    
    # Hierarchical Timeframe Features
    htf_bias: float = 0.5  # Weighted: W1 40%, D1 30%, H4 20%, H1 10%
    htf_cascade: float = 0.5  # Multiplicative confirmation
    htf_confirmation: float = 0.0  # How many lower TFs confirm higher TF
    
    # ═══════════════════════════════════════════════════════════
    # MT5 INDICATORS (13 features)
    # ═══════════════════════════════════════════════════════════
    mt5_atr_14: float = 0.0
    mt5_atr_20: float = 0.0
    mt5_atr_50: float = 0.0
    mt5_rsi: float = 50.0
    mt5_macd: float = 0.0
    mt5_macd_signal: float = 0.0
    mt5_macd_diff: float = 0.0
    mt5_bb_upper: float = 0.0
    mt5_bb_middle: float = 0.0
    mt5_bb_lower: float = 0.0
    mt5_bb_width: float = 0.0
    mt5_bb_position: float = 0.5
    mt5_sma_20: float = 0.0
    
    # ═══════════════════════════════════════════════════════════
    # TIMEFRAME ALIGNMENT (15 features)
    # ═══════════════════════════════════════════════════════════
    rsi_m1_h1_diff: float = 0.0
    rsi_h1_h4_diff: float = 0.0
    rsi_all_oversold: float = 0.0  # 1.0 if all timeframes oversold
    rsi_all_overbought: float = 0.0
    macd_m1_h1_agree: float = 0.0  # 1.0 if both agree
    macd_h1_h4_agree: float = 0.0
    macd_all_bullish: float = 0.0
    macd_all_bearish: float = 0.0
    trend_m1_bullish: float = 0.0
    trend_h1_bullish: float = 0.0
    trend_h4_bullish: float = 0.0
    trend_alignment: float = 0.0  # 0.0-1.0 score
    vol_m1: float = 0.0
    vol_h1: float = 0.0
    vol_expanding: float = 0.0
    
    # ═══════════════════════════════════════════════════════════
    # VOLUME INTELLIGENCE (10 features)
    # ═══════════════════════════════════════════════════════════
    volume_spike_m1: float = 1.0
    volume_trend: float = 0.0
    volume_increasing: float = 0.0
    volume_divergence: float = 0.0  # 1.0 if price/volume diverging
    institutional_bars: float = 0.0  # % of recent bars with 2x volume
    volume_momentum: float = 1.0
    volume_std: float = 0.0
    accumulation: float = 0.0  # 1.0 if accumulating
    distribution: float = 0.0  # 1.0 if distributing
    volume_ratio: float = 1.0
    
    # ═══════════════════════════════════════════════════════════
    # ORDER BOOK (5 features)
    # ═══════════════════════════════════════════════════════════
    bid_ask_imbalance: float = 0.0  # -1.0 to 1.0
    bid_pressure: float = 0.5  # 0.0 to 1.0
    ask_pressure: float = 0.5
    orderbook_depth: float = 0.0
    large_orders: float = 0.0
    
    # ═══════════════════════════════════════════════════════════
    # POSITION DATA (if exists)
    # ═══════════════════════════════════════════════════════════
    has_position: bool = False
    position_type: int = -1  # 0=BUY, 1=SELL
    position_type_str: str = "NONE"  # "BUY", "SELL", or "NONE"
    position_volume: float = 0.0
    position_entry_price: float = 0.0
    position_current_profit: float = 0.0
    position_swap: float = 0.0  # Swap cost from broker
    position_sl: float = 0.0  # Current stop loss
    position_tp: float = 0.0  # Current take profit
    position_ticket: int = 0  # MT5 ticket number
    position_age_minutes: float = 0.0
    position_dca_count: int = 0
    
    # ═══════════════════════════════════════════════════════════
    # ML PREDICTIONS
    # ═══════════════════════════════════════════════════════════
    ml_direction: str = "HOLD"
    ml_confidence: float = 50.0
    
    # ═══════════════════════════════════════════════════════════
    # RAW REQUEST DATA (for legacy code compatibility)
    # ═══════════════════════════════════════════════════════════
    request: Optional[Dict] = None
    
    # ═══════════════════════════════════════════════════════════
    # FTMO RISK TRACKING - CRITICAL RULES
    # 
    # FTMO RULES (from ftmo.com):
    # - Max Daily Loss: 5% of INITIAL BALANCE (not current balance)
    # - Max Total Loss: 10% of INITIAL BALANCE (equity cannot drop below 90% of initial)
    # - Daily loss resets at midnight CE(S)T
    # - Includes floating P&L, commissions, and swaps
    # ═══════════════════════════════════════════════════════════
    
    # INITIAL BALANCE - The balance when challenge/account started
    # This is the CRITICAL value for FTMO calculations
    # It NEVER changes during the challenge
    initial_balance: float = 200000.0  # Set at account creation
    
    account_equity: float = 200000.0
    daily_start_balance: float = 200000.0  # Balance at midnight CE(S)T
    peak_balance: float = 200000.0  # Highest balance ever reached
    daily_pnl: float = 0.0  # Today's P&L (resets at midnight)
    total_drawdown: float = 0.0  # Current drawdown from peak
    daily_loss: float = 0.0  # Today's loss (positive number)
    
    # FTMO LIMITS - Calculated from INITIAL BALANCE
    # max_daily_loss = initial_balance * 0.05 (5%)
    # max_total_drawdown = initial_balance * 0.10 (10%)
    max_daily_loss: float = 10000.0  # 5% of $200K initial
    max_total_drawdown: float = 20000.0  # 10% of $200K initial
    
    distance_to_daily_limit: float = 10000.0
    distance_to_dd_limit: float = 20000.0
    ftmo_phase: str = "funded"  # "challenge_1", "challenge_2", "funded"
    ftmo_violated: bool = False
    can_trade: bool = True
    profit_target: float = 0.0  # Funded has no target
    progress_to_target: float = 0.0
    
    # ═══════════════════════════════════════════════════════════
    # MARKET STRUCTURE (for position management targets)
    # ═══════════════════════════════════════════════════════════
    dist_to_resistance: float = 0.0  # Distance to nearest resistance
    dist_to_support: float = 0.0     # Distance to nearest support
    above_pivot: float = 0.0         # 1.0 if above pivot point
    dist_to_pivot: float = 0.0       # Distance to pivot point
    atr: float = 0.0                 # ATR for dynamic stops/targets
    
    # ═══════════════════════════════════════════════════════════
    # NEW SWING TRADING INDICATORS (HTF-based, stable)
    # ═══════════════════════════════════════════════════════════
    
    # ADX - Trend Strength (0-100, >25 = trending, <20 = ranging)
    h1_adx: float = 25.0
    h4_adx: float = 25.0
    d1_adx: float = 25.0
    htf_adx: float = 25.0  # Average of H1/H4/D1
    
    # HTF Volume Trend (-1 to 1, positive = volume increasing)
    h1_volume_trend: float = 0.0
    h4_volume_trend: float = 0.0
    d1_volume_trend: float = 0.0
    
    # HTF Volume Divergence (0 to 1, higher = more divergence = warning)
    h4_volume_divergence: float = 0.0
    d1_volume_divergence: float = 0.0
    
    # Market Structure (-1 to 1, positive = uptrend, negative = downtrend)
    h4_market_structure: float = 0.0
    d1_market_structure: float = 0.0
    
    # HTF Support/Resistance Distance (%)
    h4_dist_to_support: float = 0.0
    h4_dist_to_resistance: float = 0.0
    d1_dist_to_support: float = 0.0
    d1_dist_to_resistance: float = 0.0
    
    # ═══════════════════════════════════════════════════════════
    # CROSS-ASSET CORRELATION (Institutional Edge)
    # 
    # DXY (Dollar Index): Inverse to EUR, GBP, Gold
    # VIX: Risk-off indicator (high = avoid risk)
    # US Indices: Risk sentiment
    # ═══════════════════════════════════════════════════════════
    
    # Dollar Index context (affects forex and gold)
    dxy_trend: float = 0.5  # 0=bearish, 0.5=neutral, 1=bullish
    dxy_momentum: float = 0.0  # -1 to 1
    dxy_strength: float = 0.0  # How strong is dollar move
    
    # Risk sentiment from indices
    risk_on_off: float = 0.5  # 0=risk-off, 0.5=neutral, 1=risk-on
    indices_aligned: float = 0.5  # Are US30/US100/US500 aligned?
    indices_momentum: float = 0.0  # Combined index momentum
    
    # Cross-asset signals
    gold_dollar_divergence: float = 0.0  # Gold and DXY moving same way = unusual
    forex_index_correlation: float = 0.0  # How correlated is this forex pair to indices
    
    # ═══════════════════════════════════════════════════════════
    # NEWS RISK MANAGEMENT (Hedge Fund Level)
    # ═══════════════════════════════════════════════════════════
    news_imminent: bool = False  # High-impact news within 30 minutes
    news_minutes_until: float = 999.0  # Minutes until next high-impact event
    news_event_name: str = ""  # Name of upcoming event (NFP, FOMC, CPI, PPI, etc.)
    news_currency: str = ""  # Currency affected by the news
    
    # ═══════════════════════════════════════════════════════════
    # DAILY PROFIT PROTECTION (Hedge Fund Level)
    # ═══════════════════════════════════════════════════════════
    peak_daily_pnl: float = 0.0  # Highest daily P&L reached today (for trailing protection)
    
    # ═══════════════════════════════════════════════════════════
    # PEAK TRACKING (for partial profit taking)
    # ═══════════════════════════════════════════════════════════
    position_peak_profit: float = 0.0
    position_peak_profit_pct: float = 0.0
    position_decline_from_peak: float = 0.0
    position_decline_from_peak_pct: float = 0.0
    
    def update_peak_tracking(self):
        """Update peak profit tracking and calculate decline"""
        if self.position_current_profit > self.position_peak_profit:
            self.position_peak_profit = self.position_current_profit
            self.position_peak_profit_pct = (self.position_current_profit / self.account_balance * 100) if self.account_balance > 0 else 0.0
            self.position_decline_from_peak = 0.0
            self.position_decline_from_peak_pct = 0.0
        elif self.position_peak_profit > 0:
            self.position_decline_from_peak = self.position_peak_profit - self.position_current_profit
            self.position_decline_from_peak_pct = (self.position_decline_from_peak / self.position_peak_profit * 100)
    
    @classmethod
    def from_features_and_request(cls, features: Dict[str, float], request: Dict, ml_direction: str, ml_confidence: float):
        """
        Create EnhancedTradingContext from feature dict and raw request.
        This is the bridge between feature engineering and AI components.
        """
        
        # Extract position info if exists
        positions = request.get('positions', [])
        symbol = request.get('symbol_info', {}).get('symbol', 'UNKNOWN')
        has_position = False
        position_info = {}
        
        if positions:
            for pos in positions:
                if pos.get('symbol') == symbol:
                    has_position = True
                    position_info = {
                        'position_type': pos.get('type'),
                        'position_volume': float(pos.get('volume', 0)),
                        'position_entry_price': float(pos.get('price_open', 0)),
                        'position_current_profit': float(pos.get('profit', 0)),
                        'position_age_minutes': float(pos.get('age_minutes', 0)),
                        'position_dca_count': pos.get('dca_count', 0)
                    }
                    break
        
        # Extract FTMO data from account
        account_data = request.get('account', {})
        account_balance = float(account_data.get('balance', 100000))
        account_equity = float(account_data.get('equity', account_balance))
        
        # Extract contract size from broker (via EA)
        symbol_info = request.get('symbol_info', {})
        contract_size = float(symbol_info.get('contract_size', symbol_info.get('trade_contract_size', 100000)))
        logger.info(f"   📊 Symbol info contract_size: {symbol_info.get('contract_size', 'NOT FOUND')}, using: {contract_size}")
        
        # ═══════════════════════════════════════════════════════════
        # FTMO RULES - CRITICAL CALCULATIONS
        # 
        # From FTMO Academy (ftmo.com):
        # - Max Daily Loss: 5% of INITIAL BALANCE (not current balance)
        # - Max Total Loss: 10% of INITIAL BALANCE (equity cannot drop below 90% of initial)
        # - Daily loss = (daily_start_balance + daily_realized_pnl) - current_equity
        # - Total loss = initial_balance - current_equity (must stay above 90%)
        # - Resets at midnight CE(S)T
        # - Includes floating P&L, commissions, and swaps
        # ═══════════════════════════════════════════════════════════
        
        # INITIAL BALANCE - The balance when the challenge/account started
        # This is the CRITICAL value - it NEVER changes during the challenge
        # EA should send this, otherwise use a reasonable default
        initial_balance = float(account_data.get('initial_balance', 200000.0))
        
        # Get other FTMO data from EA
        daily_pnl = float(account_data.get('daily_pnl', 0.0))
        daily_start_balance = float(account_data.get('daily_start_balance', account_balance))
        daily_realized_pnl = float(account_data.get('daily_realized_pnl', 0.0))
        peak_balance = float(account_data.get('peak_balance', initial_balance))
        
        # ═══════════════════════════════════════════════════════════
        # FTMO RULES - EXACT FORMULAS FROM FTMO.COM
        # ═══════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════
        # RULE 1: MAXIMUM DAILY LOSS (5% Rule)
        # 
        # Formula: Daily Loss Limit = Balance at midnight CE(S)T - (5% of initial balance)
        # 
        # Example for $200K account, if balance at midnight was $205K:
        #   Daily Loss Limit = $205,000 - $10,000 = $195,000
        #   Equity cannot drop below $195,000 today
        # 
        # This means if you made profits, you have MORE room before violation
        # The 5% is ALWAYS based on initial balance, not current
        # ═══════════════════════════════════════════════════════════
        
        five_percent_of_initial = initial_balance * 0.05  # Always $10K for $200K account
        
        # The minimum equity allowed TODAY = balance at midnight - 5% of initial
        min_equity_today = daily_start_balance - five_percent_of_initial
        
        # Daily loss = how much we've dropped from midnight balance
        # Includes closed positions + floating P&L + commissions + swaps
        daily_loss = max(0.0, daily_start_balance - account_equity)
        
        # Max daily loss is 5% of initial (the amount we can lose from midnight balance)
        max_daily_loss = five_percent_of_initial
        
        # ═══════════════════════════════════════════════════════════
        # RULE 2: MAXIMUM LOSS (10% Rule)
        # 
        # Formula: Equity cannot drop below 90% of INITIAL balance
        # 
        # Example for $200K account:
        #   Min Equity Allowed = $200,000 * 0.90 = $180,000
        #   If equity drops to $179,999, you're violated
        # 
        # This is ABSOLUTE - doesn't matter if you made profits before
        # Includes closed positions + floating P&L + commissions + swaps
        # ═══════════════════════════════════════════════════════════
        
        min_equity_allowed = initial_balance * 0.90  # $180K for $200K account
        max_total_drawdown = initial_balance * 0.10  # $20K for $200K account
        
        # Total drawdown = how far equity has dropped below initial
        total_drawdown = max(0.0, initial_balance - account_equity)
        
        # Calculate distances to limits
        distance_to_daily_limit = max(0.0, max_daily_loss - daily_loss)
        distance_to_dd_limit = max(0.0, max_total_drawdown - total_drawdown)
        
        # FTMO phase and targets (% based on initial balance)
        ftmo_phase = request.get('ftmo_phase', 'funded')
        if ftmo_phase == 'challenge_1':
            profit_target = initial_balance * 0.10  # 10% of initial
        elif ftmo_phase == 'challenge_2':
            profit_target = initial_balance * 0.05  # 5% of initial
        else:
            profit_target = 0.0  # Funded has no target
        
        # Calculate progress toward profit target
        current_profit = account_balance - initial_balance
        daily_target = initial_balance * 0.01  # 1% daily target
        progress_to_target = (daily_pnl / daily_target) if daily_target > 0 else 0.0
        
        # Check violations
        ftmo_violated = (daily_loss >= max_daily_loss or total_drawdown >= max_total_drawdown)
        can_trade = not ftmo_violated
        
        return cls(
            # Core
            symbol=symbol,
            current_price=float(request.get('current_price', {}).get('bid', 0)),
            account_balance=account_balance,
            contract_size=contract_size,  # From broker via EA
            
            # Store raw request for legacy code
            request=request,
            
            # M1 features
            m1_returns=features.get('returns', 0.0),
            m1_volatility=features.get('volatility_20', 0.0),
            m1_rsi=features.get('rsi', 50.0),
            m1_macd=features.get('macd', 0.0),
            m1_trend=1.0 if features.get('price_to_sma_20', 1.0) > 1.0 else 0.0,
            m1_momentum=features.get('momentum_10', 0.0),
            m1_volume_ratio=features.get('volume_ratio', 1.0),
            m1_bb_position=features.get('bb_position', 0.5),
            m1_price_to_sma=features.get('price_to_sma_20', 1.0),
            m1_hl_ratio=features.get('high_low_ratio', 0.0),
            m1_range=features.get('volatility_10', 0.0),
            m1_close_pos=features.get('close_position', 0.5),
            m1_strength=abs(features.get('momentum_20', 0.0)),
            m1_sma_20=features.get('sma_20', 0.0),
            m1_sma_50=features.get('sma_50', 0.0),
            
            # M5 features
            m5_returns=features.get('m5_returns', 0.0),
            m5_volatility=features.get('m5_volatility', 0.0),
            m5_rsi=features.get('m5_rsi', 50.0),
            m5_macd=features.get('m5_macd', 0.0),
            m5_trend=features.get('m5_trend', 0.0),
            m5_momentum=features.get('m5_momentum', 0.0),
            m5_bb_position=features.get('m5_bb_position', 0.5),
            m5_price_to_sma=features.get('m5_price_to_sma', 1.0),
            m5_hl_ratio=features.get('m5_hl_ratio', 0.0),
            m5_range=features.get('m5_range', 0.0),
            m5_close_pos=features.get('m5_close_pos', 0.5),
            m5_strength=features.get('m5_strength', 0.0),
            m5_sma_20=features.get('m5_sma_20', 0.0),
            m5_sma_50=features.get('m5_sma_50', 0.0),
            m5_macd_signal=features.get('m5_macd_signal', 0.0),
            
            # M15 features ⭐ THE SWING TIMEFRAME
            m15_returns=features.get('m15_returns', 0.0),
            m15_volatility=features.get('m15_volatility', 0.0),
            m15_rsi=features.get('m15_rsi', 50.0),
            m15_macd=features.get('m15_macd', 0.0),
            m15_trend=features.get('m15_trend', 0.0),
            m15_momentum=features.get('m15_momentum', 0.0),
            m15_bb_position=features.get('m15_bb_position', 0.5),
            m15_price_to_sma=features.get('m15_price_to_sma', 1.0),
            m15_hl_ratio=features.get('m15_hl_ratio', 0.0),
            m15_range=features.get('m15_range', 0.0),
            m15_close_pos=features.get('m15_close_pos', 0.5),
            m15_strength=features.get('m15_strength', 0.0),
            m15_sma_20=features.get('m15_sma_20', 0.0),
            m15_sma_50=features.get('m15_sma_50', 0.0),
            m15_macd_signal=features.get('m15_macd_signal', 0.0),
            
            # M30 features
            m30_returns=features.get('m30_returns', 0.0),
            m30_volatility=features.get('m30_volatility', 0.0),
            m30_rsi=features.get('m30_rsi', 50.0),
            m30_macd=features.get('m30_macd', 0.0),
            m30_trend=features.get('m30_trend', 0.0),
            m30_momentum=features.get('m30_momentum', 0.0),
            m30_bb_position=features.get('m30_bb_position', 0.5),
            m30_price_to_sma=features.get('m30_price_to_sma', 1.0),
            m30_hl_ratio=features.get('m30_hl_ratio', 0.0),
            m30_range=features.get('m30_range', 0.0),
            m30_close_pos=features.get('m30_close_pos', 0.5),
            m30_strength=features.get('m30_strength', 0.0),
            m30_sma_20=features.get('m30_sma_20', 0.0),
            m30_sma_50=features.get('m30_sma_50', 0.0),
            m30_macd_signal=features.get('m30_macd_signal', 0.0),
            
            # H1 features
            h1_returns=features.get('h1_returns', 0.0),
            h1_volatility=features.get('h1_volatility', 0.0),
            h1_rsi=features.get('h1_rsi', 50.0),
            h1_macd=features.get('h1_macd', 0.0),
            h1_trend=features.get('h1_trend', 0.0),
            h1_momentum=features.get('h1_momentum', 0.0),
            h1_volume_ratio=features.get('h1_f11', 1.0),  # Fallback to generic
            h1_bb_position=features.get('h1_bb_position', 0.5),
            h1_price_to_sma=features.get('h1_price_to_sma', 1.0),
            h1_hl_ratio=features.get('h1_hl_ratio', 0.0),
            h1_range=features.get('h1_range', 0.0),
            h1_close_pos=features.get('h1_close_pos', 0.5),
            h1_strength=features.get('h1_strength', 0.0),
            h1_sma_20=features.get('h1_sma_20', 0.0),
            h1_sma_50=features.get('h1_sma_50', 0.0),
            
            # H4 features
            h4_returns=features.get('h4_returns', 0.0),
            h4_volatility=features.get('h4_volatility', 0.0),
            h4_rsi=features.get('h4_rsi', 50.0),
            h4_macd=features.get('h4_macd', 0.0),
            h4_trend=features.get('h4_trend', 0.0),
            h4_momentum=features.get('h4_momentum', 0.0),
            h4_volume_ratio=features.get('h4_f11', 1.0),
            h4_bb_position=features.get('h4_bb_position', 0.5),
            h4_price_to_sma=features.get('h4_price_to_sma', 1.0),
            h4_hl_ratio=features.get('h4_hl_ratio', 0.0),
            h4_range=features.get('h4_range', 0.0),
            h4_close_pos=features.get('h4_close_pos', 0.5),
            h4_strength=features.get('h4_strength', 0.0),
            h4_sma_20=features.get('h4_sma_20', 0.0),
            h4_sma_50=features.get('h4_sma_50', 0.0),
            
            # D1 features
            d1_returns=features.get('d1_returns', 0.0),
            d1_volatility=features.get('d1_volatility', 0.0),
            d1_rsi=features.get('d1_rsi', 50.0),
            d1_macd=features.get('d1_macd', 0.0),
            d1_trend=features.get('d1_trend', 0.0),
            d1_momentum=features.get('d1_momentum', 0.0),
            d1_bb_position=features.get('d1_bb_position', 0.5),
            d1_price_to_sma=features.get('d1_price_to_sma', 1.0),
            d1_hl_ratio=features.get('d1_hl_ratio', 0.0),
            d1_range=features.get('d1_range', 0.0),
            d1_close_pos=features.get('d1_close_pos', 0.5),
            d1_strength=features.get('d1_strength', 0.0),
            d1_sma_20=features.get('d1_sma_20', 0.0),
            d1_sma_50=features.get('d1_sma_50', 0.0),
            d1_macd_signal=features.get('d1_macd_signal', 0.0),
            
            # W1 (Weekly) features
            w1_trend=features.get('w1_trend', 0.5),
            w1_momentum=features.get('w1_momentum', 0.0),
            
            # Hierarchical Timeframe Features
            htf_bias=features.get('htf_bias', 0.5),
            htf_cascade=features.get('htf_cascade', 0.5),
            htf_confirmation=features.get('htf_confirmation', 0.0),
            
            # MT5 indicators
            mt5_atr_14=features.get('mt5_atr_14', 0.0),
            mt5_atr_20=features.get('mt5_atr_20', 0.0),
            mt5_atr_50=features.get('mt5_atr_50', 0.0),
            mt5_rsi=features.get('mt5_rsi', 50.0),
            mt5_macd=features.get('mt5_macd', 0.0),
            mt5_macd_signal=features.get('mt5_macd_signal', 0.0),
            mt5_macd_diff=features.get('mt5_macd_diff', 0.0),
            mt5_bb_upper=features.get('mt5_bb_upper', 0.0),
            mt5_bb_middle=features.get('mt5_bb_middle', 0.0),
            mt5_bb_lower=features.get('mt5_bb_lower', 0.0),
            mt5_bb_width=features.get('mt5_bb_width', 0.0),
            mt5_bb_position=features.get('mt5_bb_position', 0.5),
            mt5_sma_20=features.get('mt5_sma_20', 0.0),
            
            # Timeframe alignment
            rsi_m1_h1_diff=features.get('rsi_m1_h1_diff', 0.0),
            rsi_h1_h4_diff=features.get('rsi_h1_h4_diff', 0.0),
            rsi_all_oversold=features.get('rsi_all_oversold', 0.0),
            rsi_all_overbought=features.get('rsi_all_overbought', 0.0),
            macd_m1_h1_agree=features.get('macd_m1_h1_agree', 0.0),
            macd_h1_h4_agree=features.get('macd_h1_h4_agree', 0.0),
            macd_all_bullish=features.get('macd_all_bullish', 0.0),
            macd_all_bearish=features.get('macd_all_bearish', 0.0),
            trend_m1_bullish=features.get('trend_m1_bullish', 0.0),
            trend_h1_bullish=features.get('trend_h1_bullish', 0.0),
            trend_h4_bullish=features.get('trend_h4_bullish', 0.0),
            trend_alignment=features.get('trend_alignment', 0.0),
            vol_m1=features.get('vol_m1', 0.0),
            vol_h1=features.get('vol_h1', 0.0),
            vol_expanding=features.get('vol_expanding', 0.0),
            
            # Volume intelligence
            volume_spike_m1=features.get('volume_spike_m1', 1.0),
            volume_trend=features.get('volume_trend', 0.0),
            volume_increasing=features.get('volume_increasing', 0.0),
            volume_divergence=features.get('volume_divergence', 0.0),
            institutional_bars=features.get('institutional_bars', 0.0),
            volume_momentum=features.get('volume_momentum', 1.0),
            volume_std=features.get('volume_std', 0.0),
            accumulation=features.get('accumulation', 0.0),
            distribution=features.get('distribution', 0.0),
            volume_ratio=features.get('volume_ratio', 1.0),
            
            # Order book
            bid_ask_imbalance=features.get('bid_ask_imbalance', 0.0),
            bid_pressure=features.get('bid_pressure', 0.5),
            ask_pressure=features.get('ask_pressure', 0.5),
            orderbook_depth=features.get('orderbook_depth', 0.0),
            large_orders=features.get('large_orders', 0.0),
            
            # Position info
            has_position=has_position,
            **position_info,
            
            # ML
            ml_direction=ml_direction,
            ml_confidence=ml_confidence,
            
            # FTMO Risk Tracking - All calculations based on INITIAL BALANCE
            initial_balance=initial_balance,  # CRITICAL: Never changes during challenge
            account_equity=account_equity,
            daily_start_balance=daily_start_balance,
            peak_balance=peak_balance,
            daily_pnl=daily_pnl,
            total_drawdown=total_drawdown,
            daily_loss=daily_loss,
            max_daily_loss=max_daily_loss,  # 5% of initial_balance
            max_total_drawdown=max_total_drawdown,  # 10% of initial_balance
            distance_to_daily_limit=distance_to_daily_limit,
            distance_to_dd_limit=distance_to_dd_limit,
            ftmo_phase=ftmo_phase,
            ftmo_violated=ftmo_violated,
            can_trade=can_trade,
            profit_target=profit_target,
            progress_to_target=progress_to_target,
            
            # Market Structure (for position management)
            dist_to_resistance=features.get('dist_to_resistance', 0.0),
            dist_to_support=features.get('dist_to_support', 0.0),
            above_pivot=features.get('above_pivot', 0.0),
            dist_to_pivot=features.get('dist_to_pivot', 0.0),
            atr=features.get('atr_20', features.get('atr_14', features.get('volatility_20', 0.0) * float(request.get('current_price', {}).get('bid', 1.0)))),
            
            # NEW SWING TRADING INDICATORS (HTF-based, stable)
            h1_adx=features.get('h1_adx', 25.0),
            h4_adx=features.get('h4_adx', 25.0),
            d1_adx=features.get('d1_adx', 25.0),
            htf_adx=features.get('htf_adx', 25.0),
            h1_volume_trend=features.get('h1_volume_trend', 0.0),
            h4_volume_trend=features.get('h4_volume_trend', 0.0),
            d1_volume_trend=features.get('d1_volume_trend', 0.0),
            h4_volume_divergence=features.get('h4_volume_divergence', 0.0),
            d1_volume_divergence=features.get('d1_volume_divergence', 0.0),
            h4_market_structure=features.get('h4_market_structure', 0.0),
            d1_market_structure=features.get('d1_market_structure', 0.0),
            h4_dist_to_support=features.get('h4_dist_to_support', 0.0),
            h4_dist_to_resistance=features.get('h4_dist_to_resistance', 0.0),
            d1_dist_to_support=features.get('d1_dist_to_support', 0.0),
            d1_dist_to_resistance=features.get('d1_dist_to_resistance', 0.0),
        )
    
    def is_multi_timeframe_bullish(self) -> bool:
        """All timeframes agree on bullish trend."""
        return self.trend_alignment > 0.66  # 2/3 timeframes bullish
    
    def is_multi_timeframe_bearish(self) -> bool:
        """All timeframes agree on bearish trend."""
        return self.trend_alignment < 0.33  # 2/3 timeframes bearish
    
    def has_strong_confluence(self) -> bool:
        """Multiple indicators across timeframes agree."""
        rsi_aligned = abs(self.rsi_m1_h1_diff) < 10 and abs(self.rsi_h1_h4_diff) < 10
        macd_aligned = self.macd_m1_h1_agree > 0.5 and self.macd_h1_h4_agree > 0.5
        trend_aligned = self.trend_alignment > 0.66 or self.trend_alignment < 0.33
        
        return sum([rsi_aligned, macd_aligned, trend_aligned]) >= 2
    
    def is_institutional_activity(self) -> bool:
        """Detect institutional buying/selling."""
        return (self.institutional_bars > 0.3 or 
                self.volume_spike_m1 > 2.0 or
                abs(self.bid_ask_imbalance) > 0.3)
    
    def get_market_regime(self) -> str:
        """Identify current market regime."""
        if self.vol_expanding > 0.5 and self.h1_volatility > 0.01:
            return "VOLATILE"
        elif self.trend_alignment > 0.66:
            return "TRENDING_UP"
        elif self.trend_alignment < 0.33:
            return "TRENDING_DOWN"
        elif self.h1_range < 0.01:
            return "RANGING"
        else:
            return "MIXED"
    
    def get_volume_regime(self) -> str:
        """Identify volume pattern."""
        if self.accumulation > 0.5:
            return "ACCUMULATION"
        elif self.distribution > 0.5:
            return "DISTRIBUTION"
        elif self.volume_divergence > 0.5:
            return "DIVERGENCE"
        elif self.institutional_bars > 0.3:
            return "INSTITUTIONAL"
        else:
            return "NORMAL"
    
    def get_ftmo_status(self) -> str:
        """Get FTMO risk status."""
        if self.ftmo_violated:
            return "VIOLATED"
        elif self.distance_to_daily_limit < 1000 or self.distance_to_dd_limit < 2000:
            return "DANGER"
        elif self.distance_to_daily_limit < 2000 or self.distance_to_dd_limit < 4000:
            return "WARNING"
        else:
            return "SAFE"
    
    def is_near_ftmo_limit(self) -> bool:
        """Check if near any FTMO limit."""
        return (self.distance_to_daily_limit < 2000 or 
                self.distance_to_dd_limit < 4000)
    
    def should_trade_conservatively(self) -> bool:
        """Should we trade more conservatively due to FTMO status?"""
        return self.get_ftmo_status() in ["WARNING", "DANGER"]
    
    def get_max_risk_per_trade(self) -> float:
        """Get maximum $ risk per trade based on FTMO limits."""
        # Conservative: max 20% of remaining daily limit per trade
        max_from_daily = self.distance_to_daily_limit * 0.2
        max_from_dd = self.distance_to_dd_limit * 0.1
        return min(max_from_daily, max_from_dd, 1000.0)  # Cap at $1K per trade
    
    def get_market_score(self) -> float:
        """
        Calculate comprehensive market score using ALL 138 features.
        
        Returns a score from 0-100 representing overall market quality for trading.
        This is used by the position sizer and entry logic.
        """
        score = 50.0  # Start neutral
        
        # 1. TREND ALIGNMENT (25 points max)
        # Strong trend alignment = higher score
        if self.trend_alignment > 0.66:
            score += 25 * (self.trend_alignment - 0.5) * 2  # Up to +25
        elif self.trend_alignment < 0.33:
            score += 25 * (0.5 - self.trend_alignment) * 2  # Up to +25 for bearish
        
        # 2. ML CONFIDENCE (20 points max)
        # Higher ML confidence = higher score
        ml_conf_normalized = (self.ml_confidence - 50) / 50  # -1 to +1
        score += 20 * max(0, ml_conf_normalized)  # Only add for confidence > 50%
        
        # 3. MOMENTUM ALIGNMENT (15 points max)
        # H1 and H4 momentum in same direction
        h1_mom = self.h1_momentum if hasattr(self, 'h1_momentum') else 0
        h4_mom = self.h4_momentum if hasattr(self, 'h4_momentum') else 0
        if (h1_mom > 0 and h4_mom > 0) or (h1_mom < 0 and h4_mom < 0):
            score += 15 * min(1.0, (abs(h1_mom) + abs(h4_mom)) / 2)
        
        # 4. VOLUME CONFIRMATION (10 points max)
        if self.volume_increasing > 0.5:
            score += 5
        if self.institutional_bars > 0.3:
            score += 5
        
        # 5. RSI NOT EXTREME (10 points max)
        # Penalize overbought/oversold conditions
        h1_rsi = self.h1_rsi if hasattr(self, 'h1_rsi') else 50
        if 30 < h1_rsi < 70:
            score += 10  # Room to move
        elif 20 < h1_rsi < 80:
            score += 5   # Some room
        # Else: extreme RSI, no bonus
        
        # 6. MACD ALIGNMENT (10 points max)
        if self.macd_all_bullish > 0.5 or self.macd_all_bearish > 0.5:
            score += 10
        elif self.macd_h1_h4_agree > 0.5:
            score += 5
        
        # 7. VOLATILITY CHECK (10 points max)
        # Not too volatile, not too quiet
        regime = self.get_market_regime()
        if regime in ['TRENDING_UP', 'TRENDING_DOWN']:
            score += 10
        elif regime == 'RANGING':
            score -= 5  # Penalize ranging markets
        elif regime == 'VOLATILE':
            score -= 10  # Penalize high volatility
        
        # Clamp to 0-100
        return max(0.0, min(100.0, score))
