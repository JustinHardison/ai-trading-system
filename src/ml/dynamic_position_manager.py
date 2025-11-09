"""
Dynamic Position Manager - Professional Scalping
Scale in/out, dynamic stops, breakeven, trailing
Analyzes every tick for optimal entry/exit
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DynamicPositionManager:
    """
    Professional scalping position management
    
    Features:
    - Scale in: Add to winning positions
    - Scale out: Take profits at key levels
    - Breakeven: Move stop to entry after profit
    - Trailing stop: Follow price dynamically
    - Momentum-based exits: Exit when momentum fades
    - No fixed TP/SL: All decisions based on market analysis
    """
    
    def __init__(self):
        self.positions = {}  # Track all open positions
        
        # Scaling parameters
        self.max_scale_ins = 2  # Max 2 additional entries
        self.scale_in_threshold = 20  # Scale in after 20 points profit
        self.scale_out_levels = [30, 50, 70]  # Take partial profits
        
        # Dynamic stop parameters
        self.breakeven_trigger = 25  # Move to BE after 25 points
        self.trailing_start = 40  # Start trailing after 40 points
        self.trailing_distance = 15  # Trail 15 points behind
        
        logger.info("Dynamic Position Manager initialized")
        logger.info(f"  Scale in: Max {self.max_scale_ins} additions")
        logger.info(f"  Scale out: At {self.scale_out_levels} points")
        logger.info(f"  Breakeven: After {self.breakeven_trigger} points")
        logger.info(f"  Trailing: Start {self.trailing_start}, distance {self.trailing_distance}")
    
    def analyze_entry_scaling(
        self,
        position: Dict,
        current_price: float,
        momentum: float,
        confidence: float,
        market_structure: Dict
    ) -> Dict:
        """
        Analyze if we should scale into position
        
        Returns:
            {
                'should_scale_in': bool,
                'scale_size': float,
                'reason': str
            }
        """
        if not position:
            return {'should_scale_in': False, 'reason': 'No position'}
        
        entry_price = position['entry_price']
        direction = position['direction']
        scale_count = position.get('scale_count', 0)
        
        # Check if already scaled in max times
        if scale_count >= self.max_scale_ins:
            return {'should_scale_in': False, 'reason': 'Max scale-ins reached'}
        
        # Calculate current profit
        if direction == 'BUY':
            profit_points = current_price - entry_price
        else:  # SELL
            profit_points = entry_price - current_price
        
        # SCALE IN CONDITIONS:
        # 1. Position is profitable
        # 2. Momentum is strong in our direction
        # 3. Confidence is high
        # 4. Market structure supports continuation
        
        should_scale = False
        reason = ""
        
        # Condition 1: Profitable enough
        if profit_points < self.scale_in_threshold:
            return {'should_scale_in': False, 'reason': f'Profit {profit_points:.1f} < threshold {self.scale_in_threshold}'}
        
        # Condition 2: Strong momentum
        momentum_aligned = (
            (direction == 'BUY' and momentum > 0.5) or
            (direction == 'SELL' and momentum < -0.5)
        )
        if not momentum_aligned:
            return {'should_scale_in': False, 'reason': 'Momentum not aligned'}
        
        # Condition 3: High confidence
        if confidence < 75:
            return {'should_scale_in': False, 'reason': f'Confidence {confidence:.1f}% < 75%'}
        
        # Condition 4: Market structure (no resistance ahead for BUY, no support for SELL)
        if direction == 'BUY':
            resistance_near = market_structure.get('resistance_distance', 999)
            if resistance_near < 30:  # Resistance within 30 points
                return {'should_scale_in': False, 'reason': f'Resistance {resistance_near:.1f} points ahead'}
        else:  # SELL
            support_near = market_structure.get('support_distance', 999)
            if support_near < 30:
                return {'should_scale_in': False, 'reason': f'Support {support_near:.1f} points ahead'}
        
        # All conditions met - SCALE IN!
        # Scale size decreases with each addition (pyramid down)
        base_size = position['size']
        scale_size = base_size * (0.5 ** (scale_count + 1))  # 50%, 25%, etc.
        
        return {
            'should_scale_in': True,
            'scale_size': scale_size,
            'reason': f'Profit {profit_points:.1f}pts, momentum {momentum:.2f}, conf {confidence:.1f}%'
        }
    
    def analyze_exit_scaling(
        self,
        position: Dict,
        current_price: float,
        momentum: float,
        confidence: float,
        market_structure: Dict
    ) -> Dict:
        """
        Analyze if we should scale out (take partial profits)
        
        Returns:
            {
                'should_scale_out': bool,
                'scale_out_pct': float (0.0 - 1.0),
                'reason': str
            }
        """
        if not position:
            return {'should_scale_out': False, 'reason': 'No position'}
        
        entry_price = position['entry_price']
        direction = position['direction']
        remaining_size = position.get('remaining_size', position['size'])
        
        # Calculate current profit
        if direction == 'BUY':
            profit_points = current_price - entry_price
        else:
            profit_points = entry_price - current_price
        
        # SCALE OUT LOGIC:
        # Take partial profits at key levels
        # Keep runner for bigger moves
        
        scale_out_pct = 0.0
        reason = ""
        
        # Level 1: 30 points - take 33%
        if profit_points >= self.scale_out_levels[0] and not position.get('scaled_out_1', False):
            scale_out_pct = 0.33
            reason = f"Level 1: {profit_points:.1f} points profit"
            position['scaled_out_1'] = True
        
        # Level 2: 50 points - take another 33% (of remaining)
        elif profit_points >= self.scale_out_levels[1] and not position.get('scaled_out_2', False):
            scale_out_pct = 0.33
            reason = f"Level 2: {profit_points:.1f} points profit"
            position['scaled_out_2'] = True
        
        # Level 3: 70 points - take another 50% (of remaining)
        elif profit_points >= self.scale_out_levels[2] and not position.get('scaled_out_3', False):
            scale_out_pct = 0.50
            reason = f"Level 3: {profit_points:.1f} points profit"
            position['scaled_out_3'] = True
        
        # MOMENTUM-BASED EXIT: If momentum fades, exit remaining
        elif profit_points > 20:  # Only if profitable
            momentum_fading = (
                (direction == 'BUY' and momentum < 0.2) or
                (direction == 'SELL' and momentum > -0.2)
            )
            if momentum_fading:
                scale_out_pct = 1.0  # Exit all remaining
                reason = f"Momentum fading: {momentum:.2f}"
        
        # STRUCTURE-BASED EXIT: Near key levels
        if direction == 'BUY':
            resistance_near = market_structure.get('resistance_distance', 999)
            if resistance_near < 10 and profit_points > 15:
                scale_out_pct = max(scale_out_pct, 0.5)  # At least 50%
                reason = f"Resistance {resistance_near:.1f} points ahead"
        else:
            support_near = market_structure.get('support_distance', 999)
            if support_near < 10 and profit_points > 15:
                scale_out_pct = max(scale_out_pct, 0.5)
                reason = f"Support {support_near:.1f} points ahead"
        
        return {
            'should_scale_out': scale_out_pct > 0,
            'scale_out_pct': scale_out_pct,
            'reason': reason
        }
    
    def calculate_dynamic_stop(
        self,
        position: Dict,
        current_price: float,
        atr: float,
        market_structure: Dict
    ) -> Dict:
        """
        Calculate dynamic stop loss (breakeven, trailing, structure-based)
        
        Returns:
            {
                'stop_price': float,
                'stop_type': str,
                'reason': str
            }
        """
        if not position:
            return {'stop_price': 0, 'stop_type': 'none', 'reason': 'No position'}
        
        entry_price = position['entry_price']
        direction = position['direction']
        current_stop = position.get('stop_price', 0)
        
        # Calculate current profit
        if direction == 'BUY':
            profit_points = current_price - entry_price
        else:
            profit_points = entry_price - current_price
        
        new_stop = current_stop
        stop_type = position.get('stop_type', 'initial')
        reason = ""
        
        # BREAKEVEN: Move stop to entry after threshold
        if profit_points >= self.breakeven_trigger and stop_type == 'initial':
            new_stop = entry_price
            stop_type = 'breakeven'
            reason = f"Moved to breakeven after {profit_points:.1f} points profit"
        
        # TRAILING STOP: Trail price after threshold
        elif profit_points >= self.trailing_start:
            if direction == 'BUY':
                trailing_stop = current_price - self.trailing_distance
                if trailing_stop > new_stop:  # Only move up
                    new_stop = trailing_stop
                    stop_type = 'trailing'
                    reason = f"Trailing {self.trailing_distance} points behind price"
            else:  # SELL
                trailing_stop = current_price + self.trailing_distance
                if trailing_stop < new_stop or new_stop == 0:  # Only move down
                    new_stop = trailing_stop
                    stop_type = 'trailing'
                    reason = f"Trailing {self.trailing_distance} points behind price"
        
        # STRUCTURE-BASED STOP: Use recent swing points
        if stop_type in ['breakeven', 'trailing']:
            if direction == 'BUY':
                recent_low = market_structure.get('recent_swing_low', 0)
                if recent_low > new_stop:  # Better stop
                    new_stop = recent_low - 5  # 5 points below swing
                    stop_type = 'structure'
                    reason = "Using recent swing low"
            else:  # SELL
                recent_high = market_structure.get('recent_swing_high', 999999)
                if recent_high < new_stop or new_stop == 0:
                    new_stop = recent_high + 5  # 5 points above swing
                    stop_type = 'structure'
                    reason = "Using recent swing high"
        
        return {
            'stop_price': new_stop,
            'stop_type': stop_type,
            'reason': reason
        }
    
    def should_exit_full_position(
        self,
        position: Dict,
        current_price: float,
        momentum: float,
        confidence: float,
        market_structure: Dict
    ) -> Dict:
        """
        Determine if we should exit the entire position
        
        Returns:
            {
                'should_exit': bool,
                'reason': str,
                'exit_type': str
            }
        """
        if not position:
            return {'should_exit': False, 'reason': 'No position'}
        
        entry_price = position['entry_price']
        direction = position['direction']
        stop_price = position.get('stop_price', 0)
        
        # Calculate profit
        if direction == 'BUY':
            profit_points = current_price - entry_price
            stop_hit = current_price <= stop_price if stop_price > 0 else False
        else:
            profit_points = entry_price - current_price
            stop_hit = current_price >= stop_price if stop_price > 0 else False
        
        # EXIT CONDITIONS:
        
        # 1. STOP LOSS HIT
        if stop_hit:
            return {
                'should_exit': True,
                'reason': f'Stop loss hit at {stop_price:.2f}',
                'exit_type': 'stop_loss'
            }
        
        # 2. MOMENTUM REVERSAL (strong)
        momentum_reversed = (
            (direction == 'BUY' and momentum < -0.7) or
            (direction == 'SELL' and momentum > 0.7)
        )
        if momentum_reversed:
            return {
                'should_exit': True,
                'reason': f'Strong momentum reversal: {momentum:.2f}',
                'exit_type': 'momentum_reversal'
            }
        
        # 3. CONFIDENCE DROP (market changed)
        if confidence < 40:  # Was confident, now not
            return {
                'should_exit': True,
                'reason': f'Confidence dropped to {confidence:.1f}%',
                'exit_type': 'confidence_drop'
            }
        
        # 4. TIME-BASED (scalping - don't hold too long)
        time_in_trade = (datetime.now() - position.get('entry_time', datetime.now())).total_seconds() / 60
        if time_in_trade > 30:  # 30 minutes max for scalp
            return {
                'should_exit': True,
                'reason': f'Time limit: {time_in_trade:.1f} minutes',
                'exit_type': 'time_limit'
            }
        
        # 5. STRUCTURE BREAK (support/resistance broken)
        if direction == 'BUY':
            support_broken = market_structure.get('support_broken', False)
            if support_broken:
                return {
                    'should_exit': True,
                    'reason': 'Support level broken',
                    'exit_type': 'structure_break'
                }
        else:
            resistance_broken = market_structure.get('resistance_broken', False)
            if resistance_broken:
                return {
                    'should_exit': True,
                    'reason': 'Resistance level broken',
                    'exit_type': 'structure_break'
                }
        
        # No exit conditions met
        return {'should_exit': False, 'reason': 'Position still valid'}
    
    def get_position_management_decision(
        self,
        position: Dict,
        current_price: float,
        momentum: float,
        confidence: float,
        atr: float,
        market_structure: Dict
    ) -> Dict:
        """
        Main function: Analyze position and return management decision
        
        Returns complete decision for tick-by-tick management
        """
        if not position:
            return {'action': 'none', 'reason': 'No position'}
        
        # 1. Check for full exit first
        exit_decision = self.should_exit_full_position(
            position, current_price, momentum, confidence, market_structure
        )
        if exit_decision['should_exit']:
            return {
                'action': 'exit_full',
                'reason': exit_decision['reason'],
                'exit_type': exit_decision['exit_type']
            }
        
        # 2. Check for scale out
        scale_out = self.analyze_exit_scaling(
            position, current_price, momentum, confidence, market_structure
        )
        if scale_out['should_scale_out']:
            return {
                'action': 'scale_out',
                'scale_out_pct': scale_out['scale_out_pct'],
                'reason': scale_out['reason']
            }
        
        # 3. Check for scale in
        scale_in = self.analyze_entry_scaling(
            position, current_price, momentum, confidence, market_structure
        )
        if scale_in['should_scale_in']:
            return {
                'action': 'scale_in',
                'scale_size': scale_in['scale_size'],
                'reason': scale_in['reason']
            }
        
        # 4. Update dynamic stop
        stop_update = self.calculate_dynamic_stop(
            position, current_price, atr, market_structure
        )
        if stop_update['stop_price'] != position.get('stop_price', 0):
            return {
                'action': 'update_stop',
                'stop_price': stop_update['stop_price'],
                'stop_type': stop_update['stop_type'],
                'reason': stop_update['reason']
            }
        
        # 5. Hold position
        return {
            'action': 'hold',
            'reason': 'Position managed, no changes needed'
        }
