"""
Smart Position Sizer - AI-Driven Lot Size Calculation
Hedge fund grade position sizing using Expected Value and market context
"""
import logging
from typing import Dict
import numpy as np

logger = logging.getLogger(__name__)


class SmartPositionSizer:
    """
    AI-driven position sizing that considers:
    - Account balance and risk tolerance
    - Trade quality (score + ML confidence)
    - Market volatility and regime
    - Expected value of the trade
    - FTMO constraints
    - Symbol-specific characteristics
    """
    
    def __init__(self):
        # Symbol specifications (contract sizes and pip values)
        self.symbol_specs = {
            # Forex (standard lot = 100,000 units)
            'eurusd': {'contract_size': 100000, 'pip_value': 10.0, 'pip_size': 0.0001, 'min_lot': 0.01, 'lot_step': 0.01, 'type': 'forex'},
            'gbpusd': {'contract_size': 100000, 'pip_value': 10.0, 'pip_size': 0.0001, 'min_lot': 0.01, 'lot_step': 0.01, 'type': 'forex'},
            'usdjpy': {'contract_size': 100000, 'pip_value': 9.09, 'pip_size': 0.01, 'min_lot': 0.01, 'lot_step': 0.01, 'type': 'forex'},
            'audusd': {'contract_size': 100000, 'pip_value': 10.0, 'pip_size': 0.0001, 'min_lot': 0.01, 'lot_step': 0.01, 'type': 'forex'},
            
            # Indices (per point value)
            'us30': {'contract_size': 1, 'pip_value': 1.0, 'pip_size': 1.0, 'min_lot': 1.0, 'lot_step': 1.0, 'type': 'index'},
            'us100': {'contract_size': 1, 'pip_value': 1.0, 'pip_size': 1.0, 'min_lot': 1.0, 'lot_step': 1.0, 'type': 'index'},
            'us500': {'contract_size': 1, 'pip_value': 1.0, 'pip_size': 1.0, 'min_lot': 1.0, 'lot_step': 1.0, 'type': 'index'},
            
            # Commodities
            'xau': {'contract_size': 100, 'pip_value': 1.0, 'pip_size': 0.01, 'min_lot': 1.0, 'lot_step': 1.0, 'type': 'commodity'},  # Gold
            'xauusd': {'contract_size': 100, 'pip_value': 1.0, 'pip_size': 0.01, 'min_lot': 1.0, 'lot_step': 1.0, 'type': 'commodity'},
            'usoil': {'contract_size': 1000, 'pip_value': 10.0, 'pip_size': 0.01, 'min_lot': 1.0, 'lot_step': 1.0, 'type': 'commodity'},
        }
        
        # Base risk per trade (will be adjusted by AI)
        self.base_risk_pct = 0.01  # 1% base risk
        self.max_risk_pct = 0.03   # 3% maximum risk
    
    def calculate_lot_size(
        self,
        symbol: str,
        account_balance: float,
        account_equity: float,
        entry_price: float,
        stop_loss_price: float,
        trade_score: float,
        ml_confidence: float,
        market_volatility: float,
        regime: str,
        open_positions: int,
        daily_pnl: float = 0.0,
        ftmo_distance_to_daily: float = 10000.0,
        ftmo_distance_to_dd: float = 10000.0,
        expected_win_prob: float = 0.55
    ) -> Dict:
        """
        Calculate optimal lot size using AI-driven approach
        
        Returns:
            Dict with lot_size, risk_amount, risk_pct, reasoning
        """
        
        symbol_lower = symbol.lower()
        
        # Get symbol specifications
        specs = self.symbol_specs.get(symbol_lower)
        if not specs:
            logger.warning(f"⚠️ Unknown symbol {symbol}, using default specs")
            specs = {'contract_size': 100000, 'pip_value': 10.0, 'pip_size': 0.0001, 'min_lot': 0.01, 'lot_step': 0.01, 'type': 'forex'}
        
        logger.info(f"")
        logger.info(f"🎯 SMART POSITION SIZING - {symbol.upper()}")
        logger.info(f"   Balance: ${account_balance:,.2f} | Equity: ${account_equity:,.2f}")
        logger.info(f"   Entry: {entry_price:.5f} | Stop: {stop_loss_price:.5f}")
        logger.info(f"   Score: {trade_score:.0f}/100 | ML: {ml_confidence:.0f}%")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Calculate Stop Distance
        # ═══════════════════════════════════════════════════════════
        stop_distance = abs(entry_price - stop_loss_price)
        
        if stop_distance <= 0:
            logger.error(f"❌ Invalid stop distance: {stop_distance}")
            return {'lot_size': 0.0, 'risk_amount': 0.0, 'risk_pct': 0.0, 'reason': 'Invalid stop distance'}
        
        # Convert to pips/points
        pips_at_risk = stop_distance / specs['pip_size']
        
        logger.info(f"   Stop Distance: {stop_distance:.5f} ({pips_at_risk:.1f} pips)")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: AI Risk Adjustment (Pure EV-Based)
        # ═══════════════════════════════════════════════════════════
        
        # Start with base risk
        risk_pct = self.base_risk_pct
        adjustments = []
        
        # 2.1: Trade Quality Adjustment (0.5x to 1.5x)
        # Higher quality = more risk
        quality_factor = 0.5 + (trade_score / 100.0)  # 50-150%
        risk_pct *= quality_factor
        adjustments.append(f"Quality: {quality_factor:.2f}x")
        
        # 2.2: ML Confidence Adjustment (0.7x to 1.3x)
        # Higher confidence = more risk
        confidence_factor = 0.7 + (ml_confidence / 100.0 * 0.6)
        risk_pct *= confidence_factor
        adjustments.append(f"ML: {confidence_factor:.2f}x")
        
        # 2.3: Expected Value Adjustment (0.5x to 1.5x)
        # Based on win probability
        # EV = (win_prob * avg_win) - (loss_prob * avg_loss)
        # Assume R:R of 2:1
        avg_win = 2.0  # 2R
        avg_loss = 1.0  # 1R
        expected_value = (expected_win_prob * avg_win) - ((1 - expected_win_prob) * avg_loss)
        
        if expected_value > 0.5:
            ev_factor = 1.3  # High EV = increase risk
        elif expected_value > 0.2:
            ev_factor = 1.0  # Moderate EV = normal risk
        else:
            ev_factor = 0.7  # Low EV = reduce risk
        
        risk_pct *= ev_factor
        adjustments.append(f"EV: {ev_factor:.2f}x")
        
        # 2.4: Market Regime Adjustment
        if regime == "TRENDING":
            regime_factor = 1.2  # Trends are more predictable
        elif regime == "RANGING":
            regime_factor = 0.8  # Ranges are choppy
        elif regime == "VOLATILE":
            regime_factor = 0.7  # High vol = reduce risk
        else:
            regime_factor = 1.0
        
        risk_pct *= regime_factor
        adjustments.append(f"Regime: {regime_factor:.2f}x")
        
        # 2.5: Volatility Adjustment (0.6x to 1.2x)
        # Higher volatility = lower risk
        if market_volatility > 1.5:
            vol_factor = 0.6
        elif market_volatility > 1.0:
            vol_factor = 0.8
        elif market_volatility < 0.5:
            vol_factor = 1.2
        else:
            vol_factor = 1.0
        
        risk_pct *= vol_factor
        adjustments.append(f"Vol: {vol_factor:.2f}x")
        
        # 2.6: Portfolio Adjustment (multiple positions)
        if open_positions >= 3:
            portfolio_factor = 0.7
        elif open_positions >= 2:
            portfolio_factor = 0.85
        else:
            portfolio_factor = 1.0
        
        risk_pct *= portfolio_factor
        adjustments.append(f"Portfolio: {portfolio_factor:.2f}x")
        
        # 2.7: Account Health Adjustment
        floating_loss = account_balance - account_equity
        if floating_loss > 0:
            dd_pct = (floating_loss / account_balance) * 100
            if dd_pct > 5:
                health_factor = 0.5
            elif dd_pct > 3:
                health_factor = 0.75
            else:
                health_factor = 1.0
            
            risk_pct *= health_factor
            adjustments.append(f"Health: {health_factor:.2f}x")
        
        # 2.8: Daily P&L Adjustment
        # If winning today, can risk more. If losing, reduce risk.
        if daily_pnl > 500:
            daily_factor = 1.2  # Winning = increase
        elif daily_pnl < -500:
            daily_factor = 0.7  # Losing = reduce
        else:
            daily_factor = 1.0
        
        risk_pct *= daily_factor
        adjustments.append(f"Daily: {daily_factor:.2f}x")
        
        # 2.9: FTMO Protection
        ftmo_factor = 1.0
        if ftmo_distance_to_daily < 2000:
            ftmo_factor = min(ftmo_factor, ftmo_distance_to_daily / 2000)
            adjustments.append(f"FTMO Daily: {ftmo_factor:.2f}x")
        
        if ftmo_distance_to_dd < 4000:
            ftmo_factor = min(ftmo_factor, ftmo_distance_to_dd / 4000)
            adjustments.append(f"FTMO DD: {ftmo_factor:.2f}x")
        
        risk_pct *= ftmo_factor
        
        # Cap at maximum
        risk_pct = min(risk_pct, self.max_risk_pct)
        
        logger.info(f"   Risk Adjustments: {' | '.join(adjustments)}")
        logger.info(f"   Final Risk: {risk_pct*100:.2f}%")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Calculate Lot Size
        # ═══════════════════════════════════════════════════════════
        
        # Risk amount in dollars
        risk_amount = account_balance * risk_pct
        
        # Calculate risk per lot
        # For forex: risk_per_lot = pips * pip_value
        # For indices/commodities: risk_per_lot = points * point_value
        risk_per_lot = pips_at_risk * specs['pip_value']
        
        # Calculate lot size
        if risk_per_lot > 0:
            lot_size = risk_amount / risk_per_lot
        else:
            logger.error(f"❌ Invalid risk_per_lot: {risk_per_lot}")
            return {'lot_size': 0.0, 'risk_amount': 0.0, 'risk_pct': 0.0, 'reason': 'Invalid calculation'}
        
        logger.info(f"   Risk per Lot: ${risk_per_lot:.2f}")
        logger.info(f"   Risk Amount: ${risk_amount:.2f}")
        logger.info(f"   Calculated Lots: {lot_size:.2f}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Apply Constraints
        # ═══════════════════════════════════════════════════════════
        
        # Apply min/max
        lot_size = max(specs['min_lot'], lot_size)
        
        # Symbol-specific max lots
        max_lots_by_symbol = {
            'eurusd': 1.0, 'gbpusd': 1.0, 'usdjpy': 1.0, 'audusd': 1.0,
            'us30': 2.0, 'us100': 2.0, 'us500': 3.0,
            'xau': 5.0, 'xauusd': 5.0, 'usoil': 8.0
        }
        max_lots = max_lots_by_symbol.get(symbol_lower, 5.0)
        lot_size = min(lot_size, max_lots)
        
        # Round to lot step
        lot_size = round(lot_size / specs['lot_step']) * specs['lot_step']
        
        # Ensure minimum
        if lot_size < specs['min_lot']:
            lot_size = specs['min_lot']
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Calculate Actual Risk
        # ═══════════════════════════════════════════════════════════
        
        actual_risk = lot_size * risk_per_lot
        actual_risk_pct = (actual_risk / account_balance) * 100
        
        logger.info(f"")
        logger.info(f"   ✅ FINAL LOT SIZE: {lot_size:.2f}")
        logger.info(f"   💰 Actual Risk: ${actual_risk:.2f} ({actual_risk_pct:.2f}%)")
        logger.info(f"   📊 Risk/Reward: 1:{2.0:.1f} (assuming 2R target)")
        
        return {
            'lot_size': lot_size,
            'risk_amount': actual_risk,
            'risk_pct': actual_risk_pct,
            'reason': f'AI-optimized: {risk_pct*100:.2f}% risk',
            'adjustments': adjustments,
            'expected_value': expected_value
        }
    
    def calculate_scale_in_size(
        self,
        current_lots: float,
        current_profit_pct: float,
        market_score: float,
        symbol: str
    ) -> float:
        """
        Calculate lot size for scaling into winning position
        
        Scale in with smaller size (25-50% of original)
        """
        symbol_lower = symbol.lower()
        specs = self.symbol_specs.get(symbol_lower, {'min_lot': 0.01, 'lot_step': 0.01})
        
        # Scale in with 25-50% of current position
        if market_score > 75:
            scale_factor = 0.5  # Strong signal = 50%
        elif market_score > 60:
            scale_factor = 0.33  # Moderate signal = 33%
        else:
            scale_factor = 0.25  # Weak signal = 25%
        
        scale_lots = current_lots * scale_factor
        
        # Round and apply minimum
        scale_lots = round(scale_lots / specs['lot_step']) * specs['lot_step']
        scale_lots = max(specs['min_lot'], scale_lots)
        
        logger.info(f"   📈 Scale In: {scale_lots:.2f} lots ({scale_factor*100:.0f}% of current)")
        
        return scale_lots
    
    def calculate_scale_out_size(
        self,
        current_lots: float,
        reversal_probability: float,
        symbol: str
    ) -> float:
        """
        Calculate lot size for scaling out of winning position
        
        Scale out % = reversal probability
        """
        symbol_lower = symbol.lower()
        specs = self.symbol_specs.get(symbol_lower, {'min_lot': 0.01, 'lot_step': 0.01})
        
        # Exit percentage = reversal probability
        exit_pct = min(reversal_probability, 0.75)  # Cap at 75%
        
        scale_lots = current_lots * exit_pct
        
        # Round and apply minimum
        scale_lots = round(scale_lots / specs['lot_step']) * specs['lot_step']
        scale_lots = max(specs['min_lot'], scale_lots)
        scale_lots = min(scale_lots, current_lots)  # Can't exit more than we have
        
        logger.info(f"   📉 Scale Out: {scale_lots:.2f} lots ({exit_pct*100:.0f}% of position)")
        
        return scale_lots


# Global instance
_sizer = None

def get_smart_sizer() -> SmartPositionSizer:
    """Get global smart position sizer instance"""
    global _sizer
    if _sizer is None:
        _sizer = SmartPositionSizer()
    return _sizer
