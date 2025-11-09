"""
AI Risk Manager - Intelligent Position Sizing

Not a formula. An AI that thinks about risk.
"""

import logging
from typing import Dict
import numpy as np

logger = logging.getLogger(__name__)


class AIRiskManager:
    """AI-driven position sizing based on context"""
    
    def __init__(self):
        self.max_daily_loss = 5000
        self.max_total_dd = 10000
        
        # Symbol behavior profiles
        self.profiles = {
            'us30': {'volatility': 'medium', 'base_risk': 0.008, 'max_lots': 2.0},
            'us100': {'volatility': 'high', 'base_risk': 0.007, 'max_lots': 2.0},
            'us500': {'volatility': 'medium', 'base_risk': 0.008, 'max_lots': 3.0},
            'xau': {'volatility': 'medium', 'base_risk': 0.010, 'max_lots': 5.0},
            'usoil': {'volatility': 'high', 'base_risk': 0.006, 'max_lots': 8.0},
            'eurusd': {'volatility': 'low', 'base_risk': 0.008, 'max_lots': 1.0},
            'gbpusd': {'volatility': 'medium', 'base_risk': 0.007, 'max_lots': 1.0},
            'usdjpy': {'volatility': 'low', 'base_risk': 0.008, 'max_lots': 1.0}
        }
    
    def calculate_position_size(
        self,
        symbol: str,
        account_balance: float,
        account_equity: float,
        stop_distance: float,
        quality_score: float,
        ml_confidence: float,
        open_positions: list,
        tick_value: float,
        tick_size: float,
        daily_pnl: float = 0.0,
        contract_size: float = 100000.0  # From EA/broker
    ) -> Dict:
        """
        AI determines lot size based on ALL context.
        
        EA provides: symbol, balance, stop distance, contract specs
        AI considers: account health, trade quality, symbol behavior, exposure
        Returns: lot size with reasoning
        """
        
        try:
            # 1. Account health (including floating drawdown)
            floating_pnl = account_equity - account_balance
            dd_pct = ((account_balance - account_equity) / account_balance) * 100 if account_balance > 0 else 0
            
            logger.info(f"💰 ACCOUNT HEALTH:")
            logger.info(f"   Balance: ${account_balance:,.2f}")
            logger.info(f"   Equity: ${account_equity:,.2f}")
            logger.info(f"   Floating P&L: ${floating_pnl:,.2f}")
            logger.info(f"   Floating DD: {dd_pct:.2f}%")
            
            # 2. Symbol profile
            profile = self.profiles.get(symbol, {
                'volatility': 'medium',
                'base_risk': 0.008,
                'max_lots': 5.0
            })
            
            # 3. Base risk (from symbol profile)
            base_risk_pct = profile['base_risk']
            
            # 3.5. DAILY TARGET ADJUSTMENT
            # Adjust risk based on daily P&L progress toward 1% target
            daily_target_info = self.calculate_daily_target_risk(
                account_balance=account_balance,
                daily_pnl=daily_pnl
            )
            daily_mult = daily_target_info['risk_multiplier']
            
            # 4. AI ADJUSTMENTS
            
            # Account health adjustment
            if dd_pct > 5:
                health_mult = 0.5
                logger.info(f"⚠️ High DD {dd_pct:.1f}% - cutting risk 50%")
            elif dd_pct > 3:
                health_mult = 0.75
                logger.info(f"⚠️ Moderate DD {dd_pct:.1f}% - cutting risk 25%")
            else:
                health_mult = 1.0
            
            # Quality adjustment (0.7x to 1.3x)
            quality_mult = 0.7 + (quality_score * 0.6)
            
            # Confidence adjustment (0.8x to 1.2x)
            conf_mult = 0.8 + (ml_confidence / 100 * 0.4)
            
            # Position count adjustment
            pos_count = len(open_positions)
            if pos_count >= 3:
                pos_mult = 0.7
            elif pos_count >= 2:
                pos_mult = 0.85
            else:
                pos_mult = 1.0
            
            # 5. Calculate risk amount (including daily target multiplier)
            final_risk_pct = base_risk_pct * health_mult * quality_mult * conf_mult * pos_mult * daily_mult
            risk_amount = account_balance * final_risk_pct
            
            # 6. Calculate lot size using PROPER formula
            # risk_per_lot = (stop_distance / tick_size) * tick_value
            # lot_size = risk_amount / risk_per_lot
            
            if stop_distance > 0 and tick_size > 0 and tick_value > 0:
                # Proper calculation using broker-provided values
                ticks_at_risk = stop_distance / tick_size  # Number of ticks in stop distance
                risk_per_lot = ticks_at_risk * tick_value  # Dollar risk per 1 lot
                lot_size = risk_amount / risk_per_lot if risk_per_lot > 0 else 1.0
                
                logger.info(f"🔧 Calculation:")
                logger.info(f"   Stop distance: {stop_distance:.5f}")
                logger.info(f"   Tick size: {tick_size:.5f}")
                logger.info(f"   Tick value: ${tick_value:.2f}")
                logger.info(f"   Ticks at risk: {ticks_at_risk:.0f}")
                logger.info(f"   Risk per lot: ${risk_per_lot:.2f}")
                logger.info(f"   Risk amount: ${risk_amount:.2f}")
                logger.info(f"   Calculated lots: {lot_size:.2f}")
                
                # Clamp to reasonable range
                if lot_size < 0.01:
                    lot_size = 0.01 if symbol in ['eurusd', 'gbpusd', 'usdjpy'] else 1.0
                elif lot_size > 100:
                    lot_size = profile['max_lots']
            else:
                # Fallback if tick values missing
                logger.warning(f"⚠️ Missing tick data, using fallback calculation")
                lot_size = 1.0
            
            # 7. Apply max lots cap
            max_lots = profile['max_lots']
            if lot_size > max_lots:
                logger.info(f"⚠️ Capping {symbol} from {lot_size:.2f} to {max_lots:.2f} lots")
                lot_size = max_lots
            
            # 8. Round to valid increment
            lot_size = self._round_lots(lot_size, symbol)
            
            # 9. Final validation
            # Calculate actual risk based on lot size and stop distance
            risk_per_lot = stop_distance * 10  # Approximate risk per lot
            actual_risk = lot_size * risk_per_lot
            actual_risk_pct = (actual_risk / account_balance) * 100
            
            logger.info(f"💰 AI RISK for {symbol.upper()}:")
            logger.info(f"   Base: {base_risk_pct*100:.2f}% | Health: {health_mult:.2f}x | Quality: {quality_mult:.2f}x")
            logger.info(f"   Confidence: {conf_mult:.2f}x | Positions: {pos_mult:.2f}x | Daily Target: {daily_mult:.2f}x")
            logger.info(f"   Final Risk: {actual_risk_pct:.2f}% (${actual_risk:.2f})")
            logger.info(f"   Lot Size: {lot_size:.2f}")
            
            return {
                'lot_size': lot_size,
                'risk_amount': actual_risk,
                'risk_pct': actual_risk_pct
            }
            
        except Exception as e:
            logger.error(f"❌ AI Risk Manager error: {e}")
            return {'lot_size': 0.0, 'risk_amount': 0.0, 'risk_pct': 0.0}
    
    def _round_lots(self, lot_size: float, symbol: str) -> float:
        """
        Round to valid lot size based on asset class:
        - Forex: 0.01 increments (0.01, 0.02, 0.03, etc.)
        - Indices: Whole numbers only (1, 2, 3, etc.)
        - Commodities: Whole numbers only (1, 2, 3, etc.)
        """
        symbol = symbol.lower()
        
        # Forex pairs: 0.01 increments
        if symbol in ['eurusd', 'gbpusd', 'usdjpy', 'eurjpy', 'gbpjpy', 'audusd', 'nzdusd', 'usdcad', 'usdchf']:
            if lot_size < 0.01:
                return 0.01  # Minimum forex lot
            return round(lot_size, 2)
        
        # Indices and Commodities: Whole numbers only (1, 2, 3, etc.)
        # US30, US100, US500, XAU (gold), USOIL, etc.
        else:
            if lot_size < 1.0:
                return 1.0  # Minimum 1 lot for indices/commodities
            return round(lot_size, 0)
    
    def should_scale_in(
        self,
        position: Dict,
        current_price: float,
        entry_price: float,
        current_profit_pct: float
    ) -> Dict:
        """
        AI decides: Should we add to winner?
        
        Scale in when:
        - Position profitable
        - Moving in our favor
        - Not overextended
        """
        
        is_buy = (position.get('type') == 0)
        current_volume = float(position.get('volume', 0))
        symbol = position.get('symbol', '').lower()
        is_forex = symbol in ['eurusd', 'gbpusd', 'usdjpy', 'eurjpy', 'gbpjpy', 'audusd', 'nzdusd', 'usdcad', 'usdchf']
        
        # AI-DRIVEN: Dynamic profit threshold for scaling in
        # Forex: Lower threshold (0.2%), Indices/Commodities: Higher threshold (0.3%)
        dynamic_scale_in_threshold = 0.2 if is_forex else 0.3
        
        # Need decent profit to scale in
        if current_profit_pct < dynamic_scale_in_threshold:
            return {'should_scale': False, 'reason': f'Profit too small {current_profit_pct:.2f}% (need {dynamic_scale_in_threshold}%)', 'add_lots': 0.0}
        
        # Calculate how much to add (30% of current size)
        # Forex: minimum 0.01 lots, Indices/Commodities: minimum 1 lot
        symbol = position.get('symbol', '').lower()
        is_forex = symbol in ['eurusd', 'gbpusd', 'usdjpy', 'eurjpy', 'gbpjpy', 'audusd', 'nzdusd', 'usdcad', 'usdchf']
        
        add_lots = current_volume * 0.3
        if is_forex:
            add_lots = max(0.01, add_lots)
        else:
            add_lots = max(1.0, round(add_lots, 0))  # Whole numbers for indices/commodities
        
        logger.info(f"✅ SCALE IN: Add {add_lots:.2f} lots to winning position ({current_profit_pct:.2f}% profit)")
        
        return {
            'should_scale': True,
            'reason': f'Scaling into winner at {current_profit_pct:.2f}% profit',
            'add_lots': add_lots
        }
    
    def should_scale_out(
        self,
        position: Dict,
        current_price: float,
        entry_price: float,
        current_profit_pct: float,
        h1_resistance: float = None,
        h1_support: float = None
    ) -> Dict:
        """
        AI decides: Should we take partial profits?
        
        Scale out when:
        - Hit intermediate resistance/support
        - Strong profit but not at final target
        - Protect gains while staying in trade
        """
        
        is_buy = (position.get('type') == 0)
        current_volume = float(position.get('volume', 0))
        symbol = position.get('symbol', '').lower()
        is_forex = symbol in ['eurusd', 'gbpusd', 'usdjpy', 'eurjpy', 'gbpjpy', 'audusd', 'nzdusd', 'usdcad', 'usdchf']
        
        # Minimum position size to scale out:
        # Forex: 0.02 lots (can reduce by 0.01), Indices/Commodities: 2 lots (can reduce by 1)
        min_size = 0.02 if is_forex else 2.0
        if current_volume < min_size:
            return {'should_scale': False, 'reason': 'Position too small to scale', 'reduce_lots': 0.0}
        
        # 🤖 TRUE AI-DRIVEN: Calculate dynamic thresholds from ACTUAL MARKET DATA
        # Use H1 ATR (Average True Range) to determine volatility
        # This adapts in REAL-TIME to current market conditions
        
        # Get H1 data for volatility calculation
        if h1_resistance is not None and h1_support is not None:
            # Calculate ATR-based threshold from actual price movement
            h1_range = abs(h1_resistance - h1_support)
            current_price_val = current_price
            
            # Dynamic threshold = % of H1 range relative to current price
            # This automatically adapts to each symbol's volatility
            dynamic_profit_threshold = (h1_range / current_price_val) * 0.5  # 50% of typical H1 range
            
            # Clamp to reasonable bounds (0.2% - 1.5%)
            dynamic_profit_threshold = max(0.2, min(1.5, dynamic_profit_threshold))
            
            logger.info(f"🤖 AI-DRIVEN threshold: {dynamic_profit_threshold:.2f}% (from H1 range: ${h1_range:.2f})")
        else:
            # Fallback if no H1 data (shouldn't happen)
            dynamic_profit_threshold = 0.5
            logger.warning(f"⚠️ No H1 data, using fallback threshold: {dynamic_profit_threshold}%")
        
        should_scale = False
        reason = ""
        
        # 1. At intermediate resistance/support (AI-driven threshold)
        if current_profit_pct > dynamic_profit_threshold:
            if is_buy and h1_resistance:
                if current_price >= h1_resistance * 0.995:  # Within 0.5% of resistance
                    should_scale = True
                    reason = f"At H1 resistance + {current_profit_pct:.2f}% profit (threshold: {dynamic_profit_threshold}%)"
            elif not is_buy and h1_support:
                if current_price <= h1_support * 1.005:
                    should_scale = True
                    reason = f"At H1 support + {current_profit_pct:.2f}% profit (threshold: {dynamic_profit_threshold}%)"
        
        # 2. AI-DRIVEN: Strong profit based on symbol volatility
        strong_profit_threshold = dynamic_profit_threshold * 2  # 2x the base threshold
        if current_profit_pct > strong_profit_threshold:
            should_scale = True
            reason = f"Strong profit {current_profit_pct:.2f}% (AI threshold: {strong_profit_threshold:.1f}%) - securing 50%"
        
        if should_scale:
            # Take off 50% of position
            reduce_lots = current_volume * 0.5
            
            # Forex: minimum 0.01 lots, leave at least 0.01
            if is_forex:
                reduce_lots = max(0.01, reduce_lots)
                reduce_lots = min(reduce_lots, current_volume - 0.01)
            # Indices/Commodities: minimum 1 lot, leave at least 1
            else:
                reduce_lots = max(1.0, round(reduce_lots, 0))
                reduce_lots = min(reduce_lots, current_volume - 1.0)
            
            logger.info(f"💰 SCALE OUT: Reduce by {reduce_lots:.2f} lots ({reason})")
            
            return {
                'should_scale': True,
                'reason': reason,
                'reduce_lots': reduce_lots
            }
        
        return {'should_scale': False, 'reason': 'Holding full position', 'reduce_lots': 0.0}
    
    def should_dca(
        self,
        position: Dict,
        current_price: float,
        entry_price: float,
        current_profit_pct: float,
        h1_support: float = None,
        h1_resistance: float = None,
        ml_confidence: float = 0.0,
        account_balance: float = 100000
    ) -> Dict:
        """
        AI-Driven Smart Dollar Cost Averaging
        
        NOT risky averaging into losers!
        
        Only DCA when:
        1. Position is slightly negative (not deep loss)
        2. Price pulled back to STRONG H1 support/resistance
        3. ML still confirms direction
        4. Not overexposed
        5. Account can handle it
        
        This is STRATEGIC averaging, not desperate averaging.
        """
        
        is_buy = (position.get('type') == 0)
        current_volume = float(position.get('volume', 0))
        
        # CRITICAL: Check if volume has grown (indicates we already DCA'd)
        # If volume > 1.0, we've already added to this position - DON'T DCA AGAIN!
        if current_volume > 1.0:
            return {'should_dca': False, 'reason': f'Already DCA\'d - volume is {current_volume:.1f} lots', 'add_lots': 0.0}
        
        # Rule 1: Don't DCA if already large
        if current_volume >= 10.0:
            return {'should_dca': False, 'reason': 'Position already too large', 'add_lots': 0.0}
        
        # Rule 2: Only DCA on SMALL losses (not deep drawdown)
        if current_profit_pct < -0.5:
            return {'should_dca': False, 'reason': f'Loss too deep {current_profit_pct:.2f}% - no DCA', 'add_lots': 0.0}
        
        if current_profit_pct > 0:
            return {'should_dca': False, 'reason': 'Position profitable - use scale in instead', 'add_lots': 0.0}
        
        # Rule 3: Only DCA at STRONG H1 support/resistance
        # This is the KEY - we're not averaging randomly, we're buying at a better level
        at_strong_level = False
        
        if is_buy and h1_support:
            # For BUY: price should be AT or BELOW strong H1 support
            if current_price <= h1_support * 1.002:  # Within 0.2% of support
                at_strong_level = True
                level_type = "H1 support"
        elif not is_buy and h1_resistance:
            # For SELL: price should be AT or ABOVE strong H1 resistance
            if current_price >= h1_resistance * 0.998:
                at_strong_level = True
                level_type = "H1 resistance"
        
        if not at_strong_level:
            return {'should_dca': False, 'reason': 'Not at strong H1 level - no DCA', 'add_lots': 0.0}
        
        # Rule 4: ML must STILL confirm direction
        # If ML changed its mind, don't DCA!
        # SMART: Lower threshold at key levels (better R:R), higher elsewhere
        try:
            # Try to get optimizer threshold
            import sys
            api_module = sys.modules.get('api')
            if api_module and hasattr(api_module, 'adaptive_optimizer') and api_module.adaptive_optimizer:
                optimizer_threshold = api_module.adaptive_optimizer.get_current_parameters()['min_ml_confidence'] * 100
            else:
                optimizer_threshold = 50.0
        except:
            optimizer_threshold = 50.0
        
        # At key levels: LOWER threshold (better entry = less risk)
        # Not at key levels: HIGHER threshold (random entry = more risk)
        if at_strong_level:
            min_ml_confidence = optimizer_threshold * 0.9  # 10% easier at support/resistance
            logger.info(f"   🎯 At {level_type}: Using reduced threshold {min_ml_confidence:.1f}%")
        else:
            min_ml_confidence = optimizer_threshold * 1.1  # 10% harder elsewhere
        
        if ml_confidence < min_ml_confidence:
            return {'should_dca': False, 'reason': f'ML confidence {ml_confidence:.1f}% < {min_ml_confidence:.1f}% - no DCA', 'add_lots': 0.0}
        
        # Rule 5: Account health check
        # Don't DCA if account is stressed
        max_risk_for_dca = account_balance * 0.01  # Max 1% more risk
        
        # Calculate DCA size (smaller than original)
        # Add 30-50% of original size (not doubling down!)
        dca_lots = current_volume * 0.4
        
        # Validate total position won't be too large
        total_after_dca = current_volume + dca_lots
        if total_after_dca > 10.0:
            dca_lots = 10.0 - current_volume
        
        if dca_lots < 0.1:
            return {'should_dca': False, 'reason': 'DCA size too small', 'add_lots': 0.0}
        
        logger.info(f"✅ SMART DCA: Add {dca_lots:.2f} lots at {level_type}")
        logger.info(f"   Current: {current_volume:.2f} lots @ ${entry_price:.2f}")
        logger.info(f"   Adding: {dca_lots:.2f} lots @ ${current_price:.2f}")
        logger.info(f"   New Avg: ${((entry_price * current_volume) + (current_price * dca_lots)) / (current_volume + dca_lots):.2f}")
        logger.info(f"   ML Confidence: {ml_confidence:.1f}%")
        
        return {
            'should_dca': True,
            'reason': f'Smart DCA at {level_type} with ML {ml_confidence:.1f}% confidence',
            'add_lots': dca_lots,
            'new_average': ((entry_price * current_volume) + (current_price * dca_lots)) / (current_volume + dca_lots)
        }
    
    def calculate_daily_target_risk(
        self,
        account_balance: float,
        daily_pnl: float,
        daily_target_pct: float = 0.01,  # 1% daily target
        max_daily_loss: float = 5000
    ) -> Dict:
        """
        Calculate how aggressive we should be to hit daily 1% target.
        
        Works with optimizer to adjust risk based on:
        - How much profit made today
        - How much time left in day
        - FTMO limits
        
        Returns: risk_multiplier and reasoning
        """
        
        daily_target_dollars = account_balance * daily_target_pct
        remaining_target = daily_target_dollars - daily_pnl
        
        # Calculate how far we are from target
        progress_pct = (daily_pnl / daily_target_dollars) * 100 if daily_target_dollars > 0 else 0
        
        # Adjust risk based on progress
        if daily_pnl >= daily_target_dollars:
            # Hit target! Reduce risk, protect gains
            risk_mult = 0.5
            reason = f"Daily target hit (${daily_pnl:.2f}/${daily_target_dollars:.2f}) - reducing risk"
        
        elif daily_pnl > daily_target_dollars * 0.7:
            # Close to target (70%+) - maintain current risk
            risk_mult = 1.0
            reason = f"Near target ({progress_pct:.0f}%) - maintaining risk"
        
        elif daily_pnl > 0:
            # Profitable but below target - slightly increase risk
            risk_mult = 1.2
            reason = f"Profitable ({progress_pct:.0f}% of target) - slightly increasing risk"
        
        elif daily_pnl > -max_daily_loss * 0.3:
            # Small loss - maintain risk, can recover
            risk_mult = 1.0
            reason = f"Small loss (${daily_pnl:.2f}) - maintaining risk to recover"
        
        elif daily_pnl > -max_daily_loss * 0.6:
            # Moderate loss - reduce risk
            risk_mult = 0.7
            reason = f"Moderate loss (${daily_pnl:.2f}) - reducing risk"
        
        else:
            # Large loss - significantly reduce risk
            risk_mult = 0.5
            reason = f"Large loss (${daily_pnl:.2f}) - protecting capital"
        
        logger.info(f"📊 DAILY TARGET ANALYSIS:")
        logger.info(f"   Target: ${daily_target_dollars:.2f} (1%)")
        logger.info(f"   Current P&L: ${daily_pnl:.2f}")
        logger.info(f"   Progress: {progress_pct:.0f}%")
        logger.info(f"   Remaining: ${remaining_target:.2f}")
        logger.info(f"   Risk Multiplier: {risk_mult:.2f}x")
        logger.info(f"   Reason: {reason}")
        
        return {
            'risk_multiplier': risk_mult,
            'daily_target': daily_target_dollars,
            'current_pnl': daily_pnl,
            'remaining': remaining_target,
            'progress_pct': progress_pct,
            'reason': reason
        }
