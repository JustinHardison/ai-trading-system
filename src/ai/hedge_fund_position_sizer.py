"""
Hedge Fund Grade Position Sizer
Designed for micro contracts on large accounts
Uses AI to calculate optimal position sizes for real profits
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class HedgeFundPositionSizer:
    """
    Professional position sizing for micro contracts
    
    Philosophy:
    - $200k account should make $1k-$5k per trade
    - Micro contracts allow 20-100 lots safely
    - Risk 0.25-0.5% per trade ($500-$1,000)
    - AI adjusts based on trade quality
    """
    
    def __init__(self):
        # Target profit per trade (in dollars)
        self.target_profit_min = 500    # Minimum $500 profit target
        self.target_profit_ideal = 2000  # Ideal $2,000 profit target
        
        # Risk per trade (in percentage)
        self.base_risk_pct = 0.0025  # 0.25% base risk
        self.max_risk_pct = 0.005    # 0.5% maximum risk
    
    def calculate_position_size(
        self,
        account_balance: float,
        tick_value: float,
        stop_distance_ticks: float,
        trade_quality: float,  # 0.0-1.0 from AI
        ml_confidence: float,  # 0.0-1.0 from ML
        market_volatility: float = 0.5,  # 0.0-1.0
        symbol: str = "UNKNOWN",
        ftmo_distance_to_daily: float = 10000.0,  # FTMO daily limit distance
        ftmo_distance_to_dd: float = 20000.0,  # FTMO drawdown limit distance
        max_lot_broker: float = 100.0,  # Broker's maximum lot size
        contract_size: float = 100.0  # Contract size from broker
    ) -> Dict:
        """
        Calculate position size for micro contracts
        
        Args:
            account_balance: Account size in dollars
            tick_value: Dollar value per tick (from EA)
            stop_distance_ticks: Stop loss in ticks
            trade_quality: AI score 0.0-1.0
            ml_confidence: ML confidence 0.0-1.0
            market_volatility: Volatility 0.0-1.0
            symbol: Trading symbol
            
        Returns:
            Dict with lot_size, risk_dollars, profit_target, reasoning
        """
        
        logger.info(f"")
        logger.info(f"💰 HEDGE FUND POSITION SIZING - {symbol}")
        logger.info(f"   Account: ${account_balance:,.0f}")
        logger.info(f"   Tick Value: ${tick_value:.4f}")
        logger.info(f"   Stop Distance: {stop_distance_ticks:.1f} ticks")
        logger.info(f"   Trade Quality: {trade_quality:.2f} | ML: {ml_confidence:.2f}")
        logger.info(f"   FTMO Daily Limit: ${ftmo_distance_to_daily:,.0f} remaining")
        logger.info(f"   FTMO DD Limit: ${ftmo_distance_to_dd:,.0f} remaining")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Calculate AI-Adjusted Risk with FTMO Constraints
        # ═══════════════════════════════════════════════════════════
        
        # Base risk starts at 0.25%
        risk_pct = self.base_risk_pct
        
        # FTMO CONSTRAINT: Never risk more than 20% of daily limit
        max_risk_from_ftmo_daily = ftmo_distance_to_daily * 0.2
        max_risk_from_ftmo_dd = ftmo_distance_to_dd * 0.1
        ftmo_max_risk = min(max_risk_from_ftmo_daily, max_risk_from_ftmo_dd)
        
        logger.info(f"   FTMO Max Risk: ${ftmo_max_risk:,.0f}")
        
        # ═══════════════════════════════════════════════════════════
        # AI MULTIPLIER: Adjust risk based on setup quality
        # This replaces hardcoded thresholds with smooth scaling
        # ═══════════════════════════════════════════════════════════
        
        # Calculate base quality (0.0-1.0)
        quality_multiplier = (trade_quality + ml_confidence) / 2.0
        
        # AI Enhancement: Scale risk smoothly from 0.25% to 0.5%
        # Instead of: IF quality > 0.8 THEN 0.5%
        # We do: risk = 0.25% + (quality × 0.25%)
        # This means:
        #   quality=0.5 → 0.25% + 0.125% = 0.375% risk
        #   quality=0.7 → 0.25% + 0.175% = 0.425% risk
        #   quality=0.9 → 0.25% + 0.225% = 0.475% risk
        
        risk_pct = self.base_risk_pct + (quality_multiplier * (self.max_risk_pct - self.base_risk_pct))
        
        logger.info(f"   Quality Multiplier: {quality_multiplier:.2f}")
        logger.info(f"   AI-Scaled Risk: {risk_pct*100:.3f}% (from {self.base_risk_pct*100:.2f}% to {self.max_risk_pct*100:.2f}%)")
        
        # EV MULTIPLIER: Adjust based on Risk:Reward ratio
        # Better R:R = can risk more (better opportunity)
        if stop_distance_ticks > 0:
            # Use default 2:1 R:R for now (target is 2x stop distance)
            target_distance_ticks = stop_distance_ticks * 2.0
            
            risk_reward_ratio = target_distance_ticks / stop_distance_ticks
            ev_multiplier = min(risk_reward_ratio / 2.0, 1.5)  # Cap at 1.5×
            
            risk_pct *= ev_multiplier
            logger.info(f"   R:R Ratio: {risk_reward_ratio:.1f}:1 → EV Multiplier: {ev_multiplier:.2f}×")
            logger.info(f"   EV-Enhanced Risk: {risk_pct*100:.3f}%")
        
        # Reduce risk in high volatility (keep this safety check)
        if market_volatility > 0.7:
            risk_pct *= 0.7  # Reduce by 30%
            logger.info(f"   High volatility adjustment: {risk_pct*100:.3f}%")
        
        risk_dollars = account_balance * risk_pct
        
        # APPLY FTMO CONSTRAINT
        if risk_dollars > ftmo_max_risk:
            logger.info(f"   ⚠️ Risk ${risk_dollars:,.0f} exceeds FTMO limit ${ftmo_max_risk:,.0f}")
            risk_dollars = ftmo_max_risk
            risk_pct = (risk_dollars / account_balance) * 100
        
        logger.info(f"   Final Risk: {risk_pct*100:.3f}% = ${risk_dollars:,.0f}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: Calculate Position Size
        # ═══════════════════════════════════════════════════════════
        
        # Risk per lot = tick_value × stop_distance_ticks
        risk_per_lot = tick_value * stop_distance_ticks
        
        if risk_per_lot <= 0:
            logger.error(f"❌ Invalid risk per lot: {risk_per_lot}")
            return {
                'lot_size': 1.0,
                'risk_dollars': risk_dollars,
                'profit_target': 0,
                'reason': 'Invalid risk calculation - using minimum'
            }
        
        # Lots = Risk / Risk_per_lot
        calculated_lots = risk_dollars / risk_per_lot
        
        logger.info(f"   Risk per lot: ${risk_per_lot:.2f}")
        logger.info(f"   Calculated lots: {calculated_lots:.1f}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Apply Constraints
        # ═══════════════════════════════════════════════════════════
        
        # SMART MAX LOT BASED ON SYMBOL TYPE
        # Forex (EURUSD, GBPUSD, etc): Max 5 lots, min 0.01
        # Gold/Silver (XAU, XAG): Max 50 lots, min 1.0
        # Indices/Oil (US30, USOIL): Max 50 lots, min 1.0
        
        symbol_upper = symbol.upper()
        is_forex = any(pair in symbol_upper for pair in ['EUR', 'GBP', 'USD', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']) and 'XAU' not in symbol_upper and 'XAG' not in symbol_upper
        
        if is_forex:
            min_lot_size = 0.01
            smart_max = min(5.0, max_lot_broker)  # Cap forex at 5 lots ($500k exposure)
            logger.info(f"   📊 FOREX detected ({symbol}) - Smart max: {smart_max:.2f} lots")
        else:
            min_lot_size = 1.0
            smart_max = max_lot_broker
            logger.info(f"   📊 COMMODITY/INDEX detected ({symbol}) - Broker max: {smart_max:.0f} lots")
        
        lot_size = max(min_lot_size, calculated_lots)
        lot_size = min(smart_max, lot_size)
        
        if calculated_lots > smart_max:
            logger.info(f"   ⚠️ Capped at smart max: {calculated_lots:.1f} → {smart_max:.2f}")
        
        # Round appropriately: forex to 0.01, commodities to whole lots
        if is_forex:
            lot_size = round(lot_size, 2)  # Round to 0.01
        else:
            lot_size = round(lot_size)  # Round to whole lots
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Calculate Profit Target
        # ═══════════════════════════════════════════════════════════
        
        # Target 2:1 or 3:1 risk/reward
        rr_ratio = 2.5 if quality_multiplier > 0.7 else 2.0
        
        profit_target_dollars = risk_dollars * rr_ratio
        profit_target_ticks = profit_target_dollars / (tick_value * lot_size) if tick_value > 0 else 0
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Validation
        # ═══════════════════════════════════════════════════════════
        
        actual_risk = lot_size * risk_per_lot
        actual_profit_target = lot_size * tick_value * profit_target_ticks
        
        logger.info(f"")
        logger.info(f"   ✅ FINAL POSITION:")
        logger.info(f"   Lot Size: {lot_size:.0f} lots")
        logger.info(f"   Risk: ${actual_risk:,.0f} ({(actual_risk/account_balance)*100:.3f}%)")
        logger.info(f"   Profit Target: ${actual_profit_target:,.0f} ({profit_target_ticks:.0f} ticks)")
        logger.info(f"   Risk/Reward: 1:{rr_ratio:.1f}")
        
        return {
            'lot_size': lot_size,
            'risk_dollars': actual_risk,
            'risk_pct': (actual_risk / account_balance) * 100,
            'profit_target_dollars': actual_profit_target,
            'profit_target_ticks': profit_target_ticks,
            'risk_reward_ratio': rr_ratio,
            'reasoning': f"AI-optimized: {lot_size:.0f} lots for ${actual_profit_target:,.0f} target"
        }
    
    def calculate_scale_size(
        self,
        current_lots: float,
        current_profit_pct: float,
        market_score: float,  # 0-100
        account_balance: float
    ) -> float:
        """
        Calculate size for scaling into winning position
        
        Args:
            current_lots: Current position size
            current_profit_pct: Current profit percentage
            market_score: Market quality 0-100
            account_balance: Account size
            
        Returns:
            Additional lots to add
        """
        
        # Only scale if profit > 0.3% and market score > 70
        if current_profit_pct < 0.3 or market_score < 70:
            return 0.0
        
        # Add 25-50% of original position
        if market_score > 80 and current_profit_pct > 0.5:
            # Excellent conditions: add 50%
            add_lots = current_lots * 0.5
        else:
            # Good conditions: add 25%
            add_lots = current_lots * 0.25
        
        # Round and ensure minimum 1 lot
        add_lots = max(1.0, round(add_lots))
        
        logger.info(f"   📈 SCALE-IN: Adding {add_lots:.0f} lots to {current_lots:.0f} lot position")
        
        return add_lots
    
    def calculate_dca_size(
        self,
        current_lots: float,
        current_loss_pct: float,
        recovery_probability: float,  # 0.0-1.0
        account_balance: float
    ) -> float:
        """
        Calculate size for averaging down (DCA)
        
        Args:
            current_lots: Current position size
            current_loss_pct: Current loss percentage (negative)
            recovery_probability: AI recovery probability 0.0-1.0
            account_balance: Account size
            
        Returns:
            Additional lots to add
        """
        
        # Only DCA if:
        # 1. Loss is meaningful (> 0.5%)
        # 2. Recovery probability is high (> 0.7)
        if abs(current_loss_pct) < 0.5 or recovery_probability < 0.7:
            return 0.0
        
        # Add 50% of original position for strong recovery signals
        if recovery_probability > 0.8:
            add_lots = current_lots * 0.5
        else:
            add_lots = current_lots * 0.25
        
        # Round and ensure minimum 1 lot
        add_lots = max(1.0, round(add_lots))
        
        logger.info(f"   📉 DCA: Adding {add_lots:.0f} lots to {current_lots:.0f} lot position")
        logger.info(f"   Recovery Probability: {recovery_probability:.1%}")
        
        return add_lots
