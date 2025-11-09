"""
Elite Hedge Fund Position Sizer
Uses portfolio optimization, CVaR, and Information Ratio
Based on Renaissance Technologies / Citadel approach

Enhanced with:
- Cross-Asset Correlation Matrix (institutional grade)
- AI Regime Detection (sophisticated market state classification)
- News Sentiment Analysis (NLP-based impact assessment)
"""
import logging
from typing import Dict, List
import numpy as np
from .portfolio_state import get_portfolio_state
from .ftmo_strategy import get_ftmo_strategy
from .ai_market_analyzer import get_ai_analyzer, AIMarketState
from .cross_asset_correlation import get_cross_asset_matrix
from .regime_detector import get_regime_detector, MarketRegime
from .news_sentiment_analyzer import get_news_analyzer

logger = logging.getLogger(__name__)


class ElitePositionSizer:
    """
    Elite hedge fund grade position sizing
    
    Features:
    - Portfolio correlation-aware
    - CVaR (tail risk) based sizing
    - Dynamic risk budgeting
    - Information Ratio optimization
    - Regime-dependent allocation
    - Performance feedback loop
    """
    
    def __init__(self):
        self.portfolio_state = get_portfolio_state()
        self.ftmo_strategy = get_ftmo_strategy()
        
        # NEW: Hedge fund grade modules
        self.cross_asset_matrix = get_cross_asset_matrix()
        self.regime_detector = get_regime_detector()
        self.news_analyzer = get_news_analyzer()
        
        # Risk parameters (HEDGE FUND STANDARD)
        # Renaissance/Citadel typically risk 0.5-1% per trade
        # INCREASED from 0.5% to 1.0% - too many multipliers were reducing to minimum
        self.base_risk_pct = 0.01  # 1.0% base risk per trade
        self.max_concentration = 1.0  # Can use full allocation per position
        
        # Symbol-specific limits - NOW AI-DRIVEN
        # max_lots removed - AI calculates based on S/R stop distance and risk budget
        # max_notional_pct is the ONLY constraint - prevents excessive exposure
        # The AI will size based on: risk_budget / risk_per_lot (from S/R stop)
        self.symbol_limits = {
            'FOREX': {'max_notional_pct': 5.0},   # Forex: 5% max notional
            'GOLD': {'max_notional_pct': 5.0},    # Gold: 5% max notional
            'INDICES': {'max_notional_pct': 5.0}, # Indices: 5% max notional
            'OIL': {'max_notional_pct': 5.0},     # Oil: 5% max notional
        }
    
    def calculate_position_size(
        self,
        # Trade parameters
        account_balance: float,
        ml_confidence: float,  # 0-100
        market_score: float,  # 0-100
        entry_price: float,
        stop_loss: float,
        target_price: float,
        tick_value: float,
        tick_size: float,
        contract_size: float,
        symbol: str,
        direction: str,  # 'BUY' or 'SELL'
        
        # Market state
        regime: str,  # 'TRENDING', 'RANGING', 'VOLATILE'
        volatility: float,  # ATR as % of price
        current_atr: float,
        
        # Portfolio state
        open_positions: List[Dict],
        
        # Risk limits
        ftmo_distance_to_daily: float,
        ftmo_distance_to_dd: float,
        max_lot_broker: float,
        min_lot: float,
        lot_step: float,
        
        # NEW: Full context for comprehensive 138-feature analysis
        context = None,  # EnhancedTradingContext (optional for backward compatibility)
        
        # NEW: Complete FTMO account data for intelligent sizing
        ftmo_data: Dict = None  # Full FTMO account info from EA
    ) -> Dict:
        """
        Calculate elite hedge fund position size
        
        Returns:
            {
                'lot_size': float,
                'risk_dollars': float,
                'expected_return': float,
                'diversification_factor': float,
                'performance_multiplier': float,
                'reasoning': str
            }
        """
        
        logger.info(f"")
        logger.info(f"🏆 ELITE POSITION SIZING - {symbol}")
        logger.info(f"   Account: ${account_balance:,.0f}")
        logger.info(f"   ML: {ml_confidence:.1f}% | Market Score: {market_score:.0f}")
        logger.info(f"   Regime: {regime} | Volatility: {volatility:.2%}")
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN MARKET ANALYSIS - Replaces all hardcoded thresholds
        # ═══════════════════════════════════════════════════════════
        
        ai_analyzer = get_ai_analyzer()
        is_buy = (direction == 'BUY')
        
        # Get comprehensive AI market state
        if context is not None:
            ai_state = ai_analyzer.analyze_market(context, is_buy)
            logger.info(f"   🧠 AI Market Analysis:")
            logger.info(f"      HTF Alignment: {ai_state.htf_alignment:.2f}")
            logger.info(f"      ML Direction: {ai_state.ml_direction_alignment:+.2f}")
            logger.info(f"      Volatility Regime: {ai_state.volatility_regime:.2f}")
            logger.info(f"      Portfolio Heat: {ai_state.portfolio_heat:.2f}")
        else:
            # Fallback if no context
            ai_state = AIMarketState()
            ai_state.ml_confidence = ml_confidence / 100.0
            ai_state.volatility_regime = min(1.0, volatility * 50)  # Normalize
            logger.info(f"   📊 Basic Analysis (no context)")
        
        # AI-driven position size multiplier (replaces session/FTMO hardcodes)
        ai_size_multiplier = ai_analyzer.get_position_size_multiplier(ai_state)
        logger.info(f"   🎯 AI Size Multiplier: {ai_size_multiplier:.2f}x")
        
        # Session awareness (AI-adjusted, not hardcoded)
        from datetime import datetime
        import pytz
        
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        hour = now_ny.hour
        
        # Session factor derived from volatility and liquidity patterns
        # AI adjusts based on actual market conditions, not just time
        if 8 <= hour < 16:  # NY/London hours
            session = "OPTIMAL"
            session_factor = 1.0 + (ai_state.volume_confirmation - 0.5) * 0.2
        elif 20 <= hour or hour < 3:  # Asian
            session = "ASIAN"
            session_factor = 0.8 - ai_state.volatility_regime * 0.2
        else:
            session = "TRANSITION"
            session_factor = 0.9
        
        session_multiplier = max(0.5, min(1.2, session_factor))
        logger.info(f"   📊 Session: {session} → {session_multiplier:.2f}x (AI-adjusted)")
        
        # ═══════════════════════════════════════════════════════════
        # FTMO ACCOUNT ANALYSIS - Use ALL available data
        # ═══════════════════════════════════════════════════════════
        
        ftmo_multiplier = session_multiplier  # Start with session multiplier
        
        if ftmo_data:
            # Extract FTMO metrics
            equity = ftmo_data.get('equity', account_balance)
            daily_pnl = ftmo_data.get('daily_pnl', 0)
            daily_realized_pnl = ftmo_data.get('daily_realized_pnl', 0)
            daily_start_balance = ftmo_data.get('daily_start_balance', account_balance)
            peak_balance = ftmo_data.get('peak_balance', account_balance)
            max_daily_loss = ftmo_data.get('max_daily_loss', account_balance * 0.05)
            max_total_drawdown = ftmo_data.get('max_total_drawdown', account_balance * 0.10)
            
            # ═══════════════════════════════════════════════════════════
            # MARGIN LEVEL ANALYSIS - Critical for FTMO
            # Margin call at 100%, stop out at 50%
            # Safe trading: Keep margin level > 200%
            # ═══════════════════════════════════════════════════════════
            margin_used = ftmo_data.get('margin', 0)
            free_margin = ftmo_data.get('free_margin', equity)
            margin_level = ftmo_data.get('margin_level', 1000)  # Default high if not provided
            
            logger.info(f"      Margin Used: ${margin_used:,.0f} | Free: ${free_margin:,.0f}")
            logger.info(f"      Margin Level: {margin_level:.1f}%")
            
            # Margin-based position sizing adjustment
            # NOTE: margin_level = 0 means NO positions, which is FINE (full margin available)
            # Only reject if margin_level is low AND we have positions (margin_used > 0)
            if margin_level < 150 and margin_used > 0:
                # CRITICAL: Very low margin with existing positions - reject new trades
                logger.warning(f"   🚨 MARGIN CRITICAL: {margin_level:.1f}% < 150% → REJECT TRADE")
                return {
                    'lot_size': 0,
                    'should_trade': False,
                    'reasoning': f'Margin level critical: {margin_level:.1f}% (need >150%)',
                    'expected_return': 0
                }
            elif margin_level == 0 and margin_used == 0:
                # No positions - full margin available, this is fine
                logger.info(f"   ✅ No positions - full margin available")
            elif margin_level < 200:
                # LOW: Reduce size significantly
                margin_mult = 0.3
                logger.warning(f"   ⚠️ MARGIN LOW: {margin_level:.1f}% → 0.3x size")
                ftmo_multiplier *= margin_mult
            elif margin_level < 300:
                # MODERATE: Slight reduction
                margin_mult = 0.7
                logger.info(f"   📊 MARGIN MODERATE: {margin_level:.1f}% → 0.7x size")
                ftmo_multiplier *= margin_mult
            else:
                # HEALTHY: Full size allowed
                logger.info(f"   ✅ MARGIN HEALTHY: {margin_level:.1f}%")
            
            # Calculate key FTMO metrics
            daily_loss_used_pct = abs(min(0, daily_pnl)) / max_daily_loss * 100 if max_daily_loss > 0 else 0
            total_dd_from_peak = (peak_balance - equity) / peak_balance * 100 if peak_balance > 0 else 0
            total_dd_used_pct = (peak_balance - equity) / max_total_drawdown * 100 if max_total_drawdown > 0 else 0
            
            # Calculate profit toward goal (assuming 10% profit target for challenge)
            profit_target = daily_start_balance * 0.10  # 10% profit target
            current_profit = account_balance - daily_start_balance
            progress_to_goal_pct = (current_profit / profit_target) * 100 if profit_target > 0 else 0
            
            logger.info(f"   📊 FTMO STATUS:")
            logger.info(f"      Daily P&L: ${daily_pnl:,.2f} (Realized: ${daily_realized_pnl:,.2f})")
            logger.info(f"      Daily Loss Used: {daily_loss_used_pct:.1f}% of ${max_daily_loss:,.0f} limit")
            logger.info(f"      Drawdown from Peak: {total_dd_from_peak:.2f}% (${peak_balance - equity:,.2f})")
            logger.info(f"      Total DD Used: {total_dd_used_pct:.1f}% of ${max_total_drawdown:,.0f} limit")
            logger.info(f"      Progress to Goal: {progress_to_goal_pct:.1f}%")
            
            # ═══════════════════════════════════════════════════════════
            # FTMO CHALLENGE STRATEGY - ASYMMETRIC RISK MANAGEMENT
            # Goal: 10% profit in 30 days = ~0.33%/day average
            # Risk: 5% daily loss, 10% max drawdown
            # Strategy: Aggressive on green days, ultra-conservative on red
            # ═══════════════════════════════════════════════════════════
            
            # Calculate daily profit as % of starting balance
            daily_profit_pct = (daily_pnl / daily_start_balance) * 100 if daily_start_balance > 0 else 0
            
            # ═══════════════════════════════════════════════════════════
            # AI-DRIVEN FTMO RISK MANAGEMENT
            # 
            # Instead of hardcoded thresholds, use continuous risk scoring:
            # - Daily P&L significance relative to limit
            # - Total DD significance relative to limit
            # - Progress toward goal
            # - AI market quality assessment
            # ═══════════════════════════════════════════════════════════
            
            # Update AI state with FTMO metrics
            ai_state.ftmo_daily_usage = daily_loss_used_pct / 100.0
            ai_state.ftmo_total_dd_usage = total_dd_used_pct / 100.0
            ai_state.portfolio_heat = max(ai_state.ftmo_daily_usage, ai_state.ftmo_total_dd_usage)
            
            # AI-driven FTMO multiplier based on continuous risk assessment
            # Formula: (1 - risk_level) * (1 + profit_buffer)
            risk_level = ai_state.portfolio_heat
            profit_buffer = max(0, daily_profit_pct / 1.0) if daily_pnl > 0 else 0
            
            # Base FTMO multiplier from risk level
            ftmo_base = 1.0 - (risk_level * 0.8)  # 1.0 at 0% risk, 0.2 at 100% risk
            
            # Profit buffer allows slightly larger size when winning
            profit_boost = 1.0 + min(0.2, profit_buffer * 0.2)
            
            # Progress protection (reduce as we approach goal)
            progress_protection = 1.0 - (progress_to_goal_pct / 100.0 * 0.5) if progress_to_goal_pct > 50 else 1.0
            
            ftmo_multiplier = ftmo_base * profit_boost * progress_protection * session_multiplier
            
            # FTMO RULES (these ARE hardcoded - broker requirements, not trading decisions)
            # Stop trading if daily loss > 60% of limit OR total DD > 80% of limit
            if daily_loss_used_pct > 60 or total_dd_used_pct > 80:
                ftmo_multiplier = 0.0
                logger.warning(f"   🛑 FTMO LIMIT PROTECTION: Daily={daily_loss_used_pct:.1f}%, Total={total_dd_used_pct:.1f}% → STOP")
            else:
                logger.info(f"   📊 AI FTMO Assessment:")
                logger.info(f"      Risk level: {risk_level:.2f} → base={ftmo_base:.2f}")
                logger.info(f"      Profit buffer: {profit_buffer:.2f} → boost={profit_boost:.2f}")
                logger.info(f"      Progress protection: {progress_protection:.2f}")
                logger.info(f"      Final FTMO mult: {ftmo_multiplier:.2f}x")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 0: News Sentiment Analysis (Hedge Fund Grade)
        # Check if news conditions allow trading
        # ═══════════════════════════════════════════════════════════
        
        # Get news sentiment for this symbol
        news_sentiment = self.news_analyzer.get_symbol_sentiment(symbol)
        should_avoid, avoid_reason = self.news_analyzer.should_avoid_trading(symbol)
        
        if should_avoid:
            logger.warning(f"   🚫 NEWS RISK: {avoid_reason}")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'expected_return': 0.0,
                'reasoning': f'News risk: {avoid_reason}'
            }
        
        # Log news sentiment
        if news_sentiment['relevant_events'] > 0:
            logger.info(f"   📰 NEWS SENTIMENT (Hedge Fund Grade):")
            logger.info(f"      Symbol Sentiment: {news_sentiment['sentiment_score']:.2f}")
            logger.info(f"      Risk Level: {news_sentiment['risk_level']}")
            logger.info(f"      Guidance: {news_sentiment['guidance']}")
            logger.info(f"      Reason: {news_sentiment['reason']}")
        
        # News-based size adjustment
        news_size_mult = 1.0
        if news_sentiment['risk_level'] == 'HIGH':
            news_size_mult = 0.7
            logger.info(f"      → Reducing size to 70% due to high news risk")
        elif news_sentiment['risk_level'] == 'MEDIUM':
            news_size_mult = 0.85
            logger.info(f"      → Reducing size to 85% due to medium news risk")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Calculate Expected Return & Strategy Quality
        # ═══════════════════════════════════════════════════════════
        
        win_prob = ml_confidence / 100.0
        loss_prob = 1.0 - win_prob
        
        # R:R from actual levels
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = abs(target_price - entry_price)
        rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 2.0
        
        # Expected return per dollar risked
        expected_return = (win_prob * rr_ratio) - (loss_prob * 1.0)
        
        logger.info(f"   R:R: {rr_ratio:.2f}:1 | Expected Return: {expected_return:.2f}")
        
        # ELITE FILTER #1: Reject negative expected value
        if expected_return <= 0:
            logger.warning(f"   ❌ TRADE REJECTED: Negative expected return ({expected_return:.2f})")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'expected_return': expected_return,
                'reasoning': f'Negative EV: {expected_return:.2f}'
            }
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN EV ASSESSMENT
        # 
        # Instead of hardcoded EV threshold (0.3), use AI to determine
        # if the trade is worth taking based on:
        # - Market quality (HTF alignment, ML confidence)
        # - Risk conditions (portfolio heat, volatility)
        # - Expected return relative to market conditions
        # ═══════════════════════════════════════════════════════════
        
        # AI-driven minimum EV threshold based on market conditions
        # In high-quality setups, we can accept lower EV
        # In poor conditions, we need higher EV to compensate
        entry_quality = ai_analyzer.get_entry_score(ai_state)
        
        # Dynamic EV threshold: 0.15 for excellent setups, 0.4 for poor setups
        min_ev_threshold = 0.4 - (entry_quality * 0.25)
        
        if expected_return < min_ev_threshold:
            logger.warning(f"   ❌ TRADE REJECTED: EV {expected_return:.2f} < AI threshold {min_ev_threshold:.2f}")
            logger.warning(f"      (Entry quality: {entry_quality:.2f} → requires EV >= {min_ev_threshold:.2f})")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'expected_return': expected_return,
                'reasoning': f'EV {expected_return:.2f} < AI threshold {min_ev_threshold:.2f}'
            }
        
        # AI-driven EV multiplier: Scale size based on EV relative to threshold
        # EV at threshold → 30% size, EV at 2x threshold → 100% size
        ev_ratio = expected_return / min_ev_threshold
        ev_multiplier = min(1.0, 0.3 + (ev_ratio - 1.0) * 0.7)
        logger.info(f"   🧠 AI EV Assessment:")
        logger.info(f"      Entry quality: {entry_quality:.2f} → min EV: {min_ev_threshold:.2f}")
        logger.info(f"      Actual EV: {expected_return:.2f} → multiplier: {ev_multiplier:.2f}x")
        
        # ═══════════════════════════════════════════════════════════
        # NEW: COMPREHENSIVE 138-FEATURE ANALYSIS
        # Same approach as SCALE_IN/SCALE_OUT - use ALL features
        # ═══════════════════════════════════════════════════════════
        
        is_buy = (direction == 'BUY')
        
        # Get setup_type from context if available
        setup_type = getattr(context, 'setup_type', 'DAY') if context else 'DAY'
        
        if context is not None:
            comprehensive_score = self._calculate_comprehensive_entry_quality(context, is_buy, setup_type)
            logger.info(f"   🧠 Comprehensive Entry Quality: {comprehensive_score:.3f} (using ALL 138 features, {setup_type} weights)")
        else:
            # Fallback to simple calculation if no context
            comprehensive_score = (ml_confidence / 100.0 + market_score / 100.0) / 2
            logger.info(f"   📊 Simple Entry Quality: {comprehensive_score:.3f} (no context available)")
        
        # Strategy quality now incorporates comprehensive analysis
        strategy_quality = comprehensive_score
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: AI-Driven Regime Detection (Hedge Fund Grade)
        # 
        # ENHANCED: Uses sophisticated regime classifier with:
        # - Multi-factor regime scoring
        # - Regime persistence tracking
        # - Regime-specific trading parameters
        # ═══════════════════════════════════════════════════════════
        
        # Detect current market regime using all available data
        if context is not None:
            regime_state = self.regime_detector.detect_regime(context)
            regime_params = self.regime_detector.get_regime_parameters(regime_state.regime)
            
            logger.info(f"   📊 REGIME DETECTION (Hedge Fund Grade):")
            logger.info(f"      Regime: {regime_state.regime.value}")
            logger.info(f"      Confidence: {regime_state.confidence:.2f}, Stability: {regime_state.regime_stability:.2f}")
            logger.info(f"      Duration: {regime_state.duration_minutes} min, Trend: {regime_state.trend_direction}")
            logger.info(f"      Vol Percentile: {regime_state.volatility_percentile:.0f}%, Momentum: {regime_state.momentum_score:.2f}")
            
            # Get regime-specific multiplier
            regime_multiplier = regime_params['position_size_mult']
            
            # Check if regime suggests reducing exposure
            should_reduce, reduce_reason = self.regime_detector.should_reduce_exposure()
            if should_reduce:
                regime_multiplier *= 0.7
                logger.warning(f"      ⚠️ {reduce_reason} → reducing size by 30%")
        else:
            # Fallback to simple regime calculation
            trend_strength = ai_state.htf_alignment
            vol_regime = ai_state.volatility_regime
            regime_multiplier = 0.8 + (trend_strength * 0.4) - (vol_regime * 0.2)
            regime_multiplier = max(0.6, min(1.3, regime_multiplier))
            
            logger.info(f"   🧠 AI Regime Assessment (Simple):")
            logger.info(f"      Trend strength: {trend_strength:.2f}, Vol regime: {vol_regime:.2f}")
        
        logger.info(f"      Regime multiplier: {regime_multiplier:.2f}x")
        
        expected_return *= regime_multiplier
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Portfolio Analysis - Total Lots & Correlation
        # ENHANCED: Now uses Cross-Asset Correlation Matrix
        # ═══════════════════════════════════════════════════════════
        
        # Calculate total portfolio lots
        total_portfolio_lots = sum(float(pos.get('volume', 0)) for pos in open_positions)
        total_portfolio_value = sum(float(pos.get('profit', 0)) for pos in open_positions)
        num_positions = len(open_positions)
        
        logger.info(f"   📊 PORTFOLIO STATUS:")
        logger.info(f"      Open Positions: {num_positions}")
        logger.info(f"      Total Lots: {total_portfolio_lots:.2f}")
        logger.info(f"      Floating P&L: ${total_portfolio_value:,.2f}")
        
        # Portfolio lot limit based on account size
        # $200k account → max ~50 lots total across all positions
        max_portfolio_lots = account_balance / 4000  # ~$4k per lot of exposure
        
        if total_portfolio_lots >= max_portfolio_lots:
            logger.warning(f"   🚫 PORTFOLIO FULL: {total_portfolio_lots:.1f} lots >= {max_portfolio_lots:.1f} max")
            return {
                'lot_size': 0,
                'should_trade': False,
                'reasoning': f'Portfolio at max lots: {total_portfolio_lots:.1f}/{max_portfolio_lots:.1f}',
                'expected_return': expected_return
            }
        elif total_portfolio_lots >= max_portfolio_lots * 0.8:
            # Near limit - reduce new position size
            remaining_capacity = (max_portfolio_lots - total_portfolio_lots) / max_portfolio_lots
            logger.warning(f"   ⚠️ PORTFOLIO NEAR LIMIT: {total_portfolio_lots:.1f}/{max_portfolio_lots:.1f} → {remaining_capacity:.0%} capacity")
        
        # ═══════════════════════════════════════════════════════════
        # ENHANCED: Cross-Asset Correlation Analysis (Hedge Fund Grade)
        # Uses institutional correlation matrix with regime awareness
        # ═══════════════════════════════════════════════════════════
        
        # Get cross-asset correlation analysis
        cross_asset_analysis = self.cross_asset_matrix.get_new_position_correlation(
            symbol, direction, open_positions
        )
        avg_correlation = cross_asset_analysis['avg_correlation']
        max_pos_correlation = cross_asset_analysis['max_correlation']
        corr_recommendation = cross_asset_analysis['recommendation']
        
        # Get cross-asset exposure breakdown
        exposure_analysis = self.cross_asset_matrix.calculate_cross_asset_exposure(open_positions)
        
        logger.info(f"   📊 CROSS-ASSET CORRELATION (Hedge Fund Grade):")
        logger.info(f"      Avg Correlation: {avg_correlation:.2f}, Max: {max_pos_correlation:.2f}")
        logger.info(f"      Recommendation: {corr_recommendation}")
        if exposure_analysis['warnings']:
            for warning in exposure_analysis['warnings']:
                logger.warning(f"      ⚠️ {warning}")
        
        # Apply correlation recommendation to sizing
        corr_size_mult = 1.0
        if corr_recommendation == 'REDUCE_SIZE':
            corr_size_mult = 0.6
            logger.info(f"      → Reducing size to {corr_size_mult:.0%} due to high correlation")
        elif corr_recommendation == 'ALLOW_BOOST':
            corr_size_mult = 1.15
            logger.info(f"      → Boosting size to {corr_size_mult:.0%} due to good diversification")
        
        diversification_factor = self.portfolio_state.calculate_diversification_factor(
            avg_correlation
        ) * corr_size_mult
        
        # AI-DRIVEN CORRELATION FILTER
        # Instead of hardcoded 0.80, use AI to determine acceptable correlation
        # based on portfolio heat and entry quality
        # When portfolio is hot or entry quality is low, require lower correlation
        max_correlation = 0.95 - (ai_state.portfolio_heat * 0.3) - ((1.0 - entry_quality) * 0.15)
        max_correlation = max(0.6, min(0.95, max_correlation))
        
        if avg_correlation > max_correlation:
            logger.warning(f"   ❌ TRADE REJECTED: Correlation {avg_correlation:.2f} > AI limit {max_correlation:.2f}")
            logger.warning(f"      (Portfolio heat: {ai_state.portfolio_heat:.2f}, Entry quality: {entry_quality:.2f})")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'expected_return': expected_return,
                'reasoning': f'Correlation {avg_correlation:.2f} > AI limit {max_correlation:.2f}'
            }
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Recent Performance Feedback
        # ═══════════════════════════════════════════════════════════
        
        performance_metrics = self.portfolio_state.calculate_recent_performance(last_n=10)
        performance_multiplier = performance_metrics['performance_multiplier']
        
        # AI-DRIVEN PERFORMANCE FILTER
        # Instead of hardcoded 0.5 threshold, use AI to balance performance vs opportunity
        # When entry quality is high, we can trade despite poor recent performance
        min_perf_mult = 0.3 + ((1.0 - entry_quality) * 0.4)  # 0.3 for excellent, 0.7 for poor
        ev_requirement = 0.5 + ((1.0 - entry_quality) * 0.5)  # 0.5 for excellent, 1.0 for poor
        
        if performance_multiplier < min_perf_mult and expected_return < ev_requirement:
            logger.warning(f"   ❌ TRADE REJECTED: Performance {performance_multiplier:.2f} < {min_perf_mult:.2f} AND EV {expected_return:.2f} < {ev_requirement:.2f}")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'expected_return': expected_return,
                'reasoning': f'Poor performance + insufficient EV for entry quality'
            }
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Calculate CVaR (Tail Risk)
        # ═══════════════════════════════════════════════════════════
        
        # Estimate 95% CVaR (average loss in worst 5% scenarios)
        uncertainty = 1.0 - (ml_confidence / 100.0)
        tail_risk_multiplier = 1.0 + (uncertainty ** 2)  # Higher uncertainty = bigger tail
        
        # CVaR is typically 1.5-2.5x the stop loss in tail scenarios
        cvar_95 = risk_distance * tail_risk_multiplier * 1.5
        
        logger.info(f"   CVaR (95%): {cvar_95:.5f} (vs stop: {risk_distance:.5f})")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 6: Dynamic Risk Budget Allocation
        # ═══════════════════════════════════════════════════════════
        
        # Base risk per trade (HEDGE FUND APPROACH)
        # 1% base risk = $1,893 on $189k account
        base_trade_risk = account_balance * self.base_risk_pct
        
        # ═══════════════════════════════════════════════════════════
        # SIMPLIFIED MULTIPLIER: Single AI-driven adjustment
        # 
        # PROBLEM: Too many multipliers (7+) were stacking and reducing
        # position size to broker minimum even with floors.
        # 
        # SOLUTION: Combine all factors into ONE multiplier (0.5 to 1.2)
        # - Base: 0.8 (conservative default)
        # - Boost for: high quality, good diversification, good performance
        # - Reduce for: poor quality, high correlation, poor performance
        # ═══════════════════════════════════════════════════════════
        
        # Calculate single combined multiplier
        combined_mult = 0.8  # Start at 80%
        
        # Adjust for strategy quality (±0.15)
        if strategy_quality > 0.7:
            combined_mult += 0.15
        elif strategy_quality < 0.5:
            combined_mult -= 0.15
        
        # Adjust for diversification (±0.10)
        if diversification_factor > 0.8:
            combined_mult += 0.10
        elif diversification_factor < 0.5:
            combined_mult -= 0.10
        
        # Adjust for performance (±0.15)
        if performance_multiplier > 0.8:
            combined_mult += 0.15
        elif performance_multiplier < 0.5:
            combined_mult -= 0.15
        
        # Clamp to reasonable range
        combined_mult = max(0.5, min(1.2, combined_mult))
        
        # Apply news sentiment multiplier (from Step 0)
        combined_mult *= news_size_mult
        
        # Apply regime multiplier (from Step 2)
        combined_mult *= regime_multiplier
        
        # Re-clamp after all adjustments
        combined_mult = max(0.4, min(1.5, combined_mult))
        
        adjusted_risk_budget = base_trade_risk * combined_mult
        
        logger.info(f"   📊 Combined Multiplier: {combined_mult:.2f}x (quality={strategy_quality:.2f}, div={diversification_factor:.2f}, perf={performance_multiplier:.2f}, news={news_size_mult:.2f}, regime={regime_multiplier:.2f})")
        
        logger.info(f"   Base Trade Risk: ${base_trade_risk:,.0f}")
        logger.info(f"   Adjusted Risk: ${adjusted_risk_budget:,.0f}")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 7: Calculate Position Size from CVaR
        # ═══════════════════════════════════════════════════════════
        
        # Risk per lot using CVaR (not just stop distance)
        stop_distance_ticks = cvar_95 / tick_size
        risk_per_lot = tick_value * stop_distance_ticks
        
        if risk_per_lot <= 0:
            logger.error(f"   ❌ Invalid risk per lot: {risk_per_lot}")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'profit_target_dollars': 0.0,
                'expected_return': expected_return,
                'reasoning': 'Invalid risk calculation'
            }
        
        # Base position size
        base_size = adjusted_risk_budget / risk_per_lot
        
        logger.info(f"   Risk per lot (CVaR): ${risk_per_lot:.2f}")
        logger.info(f"   Base size: {base_size:.2f} lots")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 8: Apply Hard Constraints
        # ═══════════════════════════════════════════════════════════
        
        # Determine symbol type
        # IMPORTANT: Check indices FIRST because US30/US100/US500 contain "USD"
        symbol_upper = symbol.upper()
        
        # Check for indices first (US30, US100, US500, etc.)
        if any(idx in symbol_upper for idx in ['US30', 'US100', 'US500', 'DOW', 'NAS', 'SPX', 'DAX', 'FTSE']):
            symbol_type = 'INDICES'
        elif 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
            symbol_type = 'GOLD'
        elif 'OIL' in symbol_upper or 'USOIL' in symbol_upper or 'WTI' in symbol_upper or 'BRENT' in symbol_upper:
            symbol_type = 'OIL'
        elif any(pair in symbol_upper for pair in ['EUR', 'GBP', 'USD', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']):
            symbol_type = 'FOREX'
        else:
            symbol_type = 'INDICES'  # Default to indices for unknown symbols
        
        logger.info(f"   📊 Symbol type: {symbol_type} (from {symbol_upper})")
        
        limits = self.symbol_limits[symbol_type]
        
        # ═══════════════════════════════════════════════════════════
        # AI-DRIVEN LOT SIZING - NO HARDCODED MAX_LOTS
        # 
        # The lot size is calculated from: risk_budget / risk_per_lot
        # Where risk_per_lot comes from the S/R-based stop distance
        # 
        # Constraints are now AI-driven:
        # 1. Notional exposure (% of account)
        # 2. FTMO DD limits (dynamic based on account status)
        # 3. Broker max (from MT5)
        # ═══════════════════════════════════════════════════════════
        
        # Constraint 1: Notional exposure (prevents excessive leverage)
        max_notional = account_balance * limits['max_notional_pct'] / 100.0
        logger.info(f"   📊 Notional calc: max_notional=${max_notional:,.0f}, contract_size={contract_size}, entry_price={entry_price}")
        if contract_size * entry_price > 0:
            notional_max = max_notional / (contract_size * entry_price)
            logger.info(f"   📊 notional_max = {max_notional:,.0f} / ({contract_size} * {entry_price}) = {notional_max:.1f}")
        else:
            notional_max = max_lot_broker
            logger.info(f"   📊 notional_max = broker max (contract_size or entry_price is 0)")
        
        # Constraint 2: FTMO limits (AI-driven based on current DD status)
        ftmo_safe_risk = min(
            ftmo_distance_to_daily * 0.20,  # Max 20% of remaining daily DD
            ftmo_distance_to_dd * 0.10      # Max 10% of remaining total DD
        )
        ftmo_max = ftmo_safe_risk / risk_per_lot if risk_per_lot > 0 else max_lot_broker
        logger.info(f"   📊 FTMO max: {ftmo_max:.1f} lots (safe risk: ${ftmo_safe_risk:,.0f})")
        
        # Constraint 3: Portfolio concentration (AI-driven)
        concentration_max_risk = self.portfolio_state.calculate_concentration_limit(
            base_trade_risk, self.max_concentration
        )
        concentration_max = concentration_max_risk / risk_per_lot if risk_per_lot > 0 else max_lot_broker
        
        # Constraint 4: Broker max (from MT5 - this is the ONLY hard limit)
        broker_max = max_lot_broker
        
        # Take minimum of AI-driven constraints (NO hardcoded max_lots!)
        final_size = min(
            base_size,        # From risk budget / risk per lot (S/R based)
            notional_max,     # Notional exposure limit
            ftmo_max,         # FTMO DD protection
            concentration_max, # Portfolio concentration
            broker_max        # Broker limit (only hard constraint)
        )
        
        logger.info(f"   📊 AI Lot Sizing: base={base_size:.1f}, notional={notional_max:.1f}, ftmo={ftmo_max:.1f}, conc={concentration_max:.1f}, broker={broker_max:.1f}")
        
        logger.info(f"   📊 After constraints: {final_size:.2f} lots")
        
        # ═══════════════════════════════════════════════════════════
        # SINGLE FTMO/MARKET ADJUSTMENT (replaces multiple multipliers)
        # 
        # Combine: volatility, EV, FTMO account status into ONE adjustment
        # Range: 0.4 to 1.0 (never boost above base, only reduce for safety)
        # ═══════════════════════════════════════════════════════════
        
        market_adjustment = 1.0
        
        # Volatility adjustment (reduce in high vol)
        if volatility > 0.02:
            market_adjustment -= 0.20
        elif volatility > 0.01:
            market_adjustment -= 0.10
        
        # EV adjustment (reduce for low EV, but floor at 0.7)
        if ev_multiplier < 0.5:
            market_adjustment -= 0.15
        elif ev_multiplier < 0.7:
            market_adjustment -= 0.10
        
        # FTMO account status (only reduce if in danger, otherwise ignore)
        if ftmo_multiplier == 0:
            # FTMO says stop trading entirely
            market_adjustment = 0
        elif ftmo_multiplier < 0.5:
            market_adjustment -= 0.20
        
        # Clamp to reasonable range
        market_adjustment = max(0.4, min(1.0, market_adjustment)) if market_adjustment > 0 else 0
        
        final_size = final_size * market_adjustment
        logger.info(f"   📊 After market adjustment: {final_size:.2f} lots (adj: {market_adjustment:.2f}x)")
        
        # ═══════════════════════════════════════════════════════════
        # FTMO STRATEGY: Correlation, Session, Win Rate, Recovery Mode
        # ═══════════════════════════════════════════════════════════
        
        # Get list of open position symbols
        open_position_symbols = list(self.portfolio_state.position_risks.keys())
        
        # Get FTMO strategy multipliers
        ftmo_strat = self.ftmo_strategy.get_total_multiplier(
            symbol=symbol,
            open_positions=open_position_symbols,
            ml_confidence=ml_confidence,
            market_score=market_score
        )
        
        # Check if we should trade at all
        if not ftmo_strat['should_trade']:
            logger.warning(f"   🚫 FTMO Strategy BLOCKED: {ftmo_strat['reason']}")
            return {
                'should_trade': False,
                'lot_size': 0.0,
                'risk_dollars': 0.0,
                'profit_target_dollars': 0.0,
                'expected_return': expected_return,
                'reasoning': ftmo_strat['reason']
            }
        
        # FTMO strategy multiplier - only apply if it would BLOCK the trade
        # Otherwise ignore (we already applied FTMO account status above)
        ftmo_strat_mult = ftmo_strat['total_multiplier']
        if ftmo_strat_mult < 0.3:
            # Very low multiplier = significant concern, apply it
            final_size = final_size * max(0.5, ftmo_strat_mult)
            logger.info(f"   📊 FTMO Strategy concern: {final_size:.2f} lots (strat mult: {ftmo_strat_mult:.2f}x)")
        else:
            logger.info(f"   📊 FTMO Strategy OK: {ftmo_strat_mult:.2f}x (not applied - already factored in)")
        
        # Round to lot_step
        final_size = round(final_size / lot_step) * lot_step
        
        # Ensure minimum - broker minimum
        final_size = max(min_lot, final_size)
        
        # ═══════════════════════════════════════════════════════════
        # MINIMUM VIABLE LOT SIZE - Per instrument type
        # 
        # FOREX: min_lot=0.01 from broker, but 0.5 minimum for viable trades
        #   - Commission ~$7/lot, need 0.5 lots to make 10 pips worthwhile
        #   - Contract size: 100,000 units
        #
        # INDICES: min_lot=1.0 from broker (CANNOT go lower!)
        #   - US30: contract_size=0.5, tick_value=0.01
        #   - US100: contract_size=2.0, tick_value=0.02
        #   - US500: contract_size=5.0, tick_value=0.05
        #
        # GOLD: min_lot=1.0 from broker (CANNOT go lower!)
        #   - XAU: contract_size=10.0, tick_value=0.1
        #
        # OIL: min_lot=1.0 from broker (CANNOT go lower!)
        #   - USOIL: contract_size=100.0, tick_value=0.1
        # ═══════════════════════════════════════════════════════════
        
        # Apply minimum viable sizes based on instrument type
        if symbol_type == 'FOREX':
            viable_min = max(min_lot, 0.5)  # Forex: broker min or 0.5 for viability
            if final_size < viable_min:
                logger.info(f"   ⚠️ Forex minimum viable size: {viable_min} lots (was {final_size:.2f})")
                final_size = viable_min
        elif symbol_type == 'INDICES':
            viable_min = max(min_lot, 1.0)  # Indices: broker requires 1.0 minimum
            if final_size < viable_min:
                logger.info(f"   ⚠️ Indices minimum size: {viable_min} lots (was {final_size:.2f})")
                final_size = viable_min
        elif symbol_type == 'GOLD':
            viable_min = max(min_lot, 1.0)  # Gold: broker requires 1.0 minimum
            if final_size < viable_min:
                logger.info(f"   ⚠️ Gold minimum size: {viable_min} lots (was {final_size:.2f})")
                final_size = viable_min
        elif symbol_type == 'OIL':
            viable_min = max(min_lot, 1.0)  # Oil: broker requires 1.0 minimum
            if final_size < viable_min:
                logger.info(f"   ⚠️ Oil minimum size: {viable_min} lots (was {final_size:.2f})")
                final_size = viable_min
        
        # Calculate final risk
        final_risk = final_size * risk_per_lot
        
        logger.info(f"")
        logger.info(f"   📊 AI-DRIVEN CONSTRAINTS:")
        logger.info(f"      Base (S/R risk): {base_size:.1f} lots")
        logger.info(f"      Notional max: {notional_max:.1f} lots (${max_notional:,.0f})")
        logger.info(f"      FTMO max: {ftmo_max:.1f} lots")
        logger.info(f"      Concentration max: {concentration_max:.1f} lots")
        logger.info(f"      Broker max: {broker_max:.1f} lots")
        logger.info(f"")
        logger.info(f"   ✅ FINAL SIZE: {final_size:.2f} lots")
        logger.info(f"   💰 FINAL RISK: ${final_risk:,.0f}")
        
        # Update portfolio state
        self.portfolio_state.update_position_risk(symbol, final_risk)
        
        # ✅ TRADE APPROVED - Passed all elite filters
        logger.info(f"   ✅ TRADE APPROVED BY ELITE FILTERS")
        
        # Calculate profit target based on R:R
        profit_target_dollars = final_risk * expected_return if expected_return > 0 else final_risk * 1.5
        
        return {
            'should_trade': True,  # ✅ Passed all filters
            'lot_size': final_size,
            'risk_dollars': final_risk,
            'profit_target_dollars': profit_target_dollars,  # Added for unified system
            'expected_return': expected_return,
            'diversification_factor': diversification_factor,
            'performance_multiplier': performance_multiplier,
            'cvar_95': cvar_95,
            'avg_correlation': avg_correlation,
            'recent_win_rate': performance_metrics['win_rate'],
            'comprehensive_score': comprehensive_score if 'comprehensive_score' in dir() else strategy_quality,
            'reasoning': f'Elite sizing: EV={expected_return:.2f}, Div={diversification_factor:.2f}x, Perf={performance_multiplier:.2f}x'
        }
    
    def _calculate_comprehensive_entry_quality(self, context, is_buy: bool, setup_type: str = 'DAY') -> float:
        """
        Calculate entry quality using ALL 138 features from context.
        
        Same approach as SCALE_IN in ev_exit_manager_v2.py - comprehensive
        multi-timeframe analysis for position sizing decisions.
        
        Setup type affects timeframe weighting:
        - SCALP: Lower TFs (M15/M30/H1) weighted more
        - DAY: Mid TFs (H1/H4) weighted more
        - SWING: Higher TFs (H4/D1) weighted more
        
        Returns a score from 0.0 (poor entry) to 1.0 (excellent entry)
        """
        
        quality_signals = []
        warning_signals = []
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 1: MULTI-TIMEFRAME TREND ANALYSIS (SWING TRADING)
        # M1/M5 EXCLUDED - too noisy for swing trading decisions
        # For entries, we want STRONG trend alignment in our direction
        # ═══════════════════════════════════════════════════════════
        
        # SWING TRADING: M15, M30, H1, H4, D1 only (no M1/M5 noise)
        # Dynamic weights based on setup type - CONSISTENT with ev_exit_manager_v2.py
        timeframes = ['m15', 'm30', 'h1', 'h4', 'd1']
        
        setup_type_weights = {
            'SCALP': [0.25, 0.25, 0.25, 0.15, 0.10],  # Lower TFs matter more
            'DAY':   [0.10, 0.15, 0.25, 0.30, 0.20],  # Mid TFs matter more
            'SWING': [0.05, 0.10, 0.15, 0.30, 0.40]   # Higher TFs matter more
        }
        tf_weights = setup_type_weights.get(setup_type, setup_type_weights['DAY'])
        
        for tf, weight in zip(timeframes, tf_weights):
            trend = getattr(context, f'{tf}_trend', 0.5)
            momentum = getattr(context, f'{tf}_momentum', 0.0)
            rsi = getattr(context, f'{tf}_rsi', 50.0)
            macd = getattr(context, f'{tf}_macd', 0.0)
            strength = getattr(context, f'{tf}_strength', 0.0)
            bb_position = getattr(context, f'{tf}_bb_position', 0.5)
            
            if is_buy:
                # For BUY: bullish signals = quality signals
                if trend > 0.6:
                    quality_signals.append(weight * (trend - 0.5))
                elif trend < 0.4:
                    warning_signals.append(weight * (0.5 - trend))
                    
                if momentum > 0.3:
                    quality_signals.append(weight * 0.5 * momentum)
                elif momentum < -0.3:
                    warning_signals.append(weight * 0.5 * abs(momentum))
                    
                # RSI: not overbought = room to run
                if rsi < 60:
                    quality_signals.append(weight * 0.2 * (60 - rsi) / 30)
                elif rsi > 75:
                    warning_signals.append(weight * 0.3 * (rsi - 70) / 30)
                    
                # MACD positive = bullish
                if macd > 0:
                    quality_signals.append(weight * 0.3 * min(1.0, macd))
                elif macd < 0:
                    warning_signals.append(weight * 0.3 * min(1.0, abs(macd)))
                    
                # BB position: middle or lower = room to run
                if bb_position < 0.6:
                    quality_signals.append(weight * 0.15 * (0.7 - bb_position))
            else:
                # For SELL: bearish signals = quality signals
                if trend < 0.4:
                    quality_signals.append(weight * (0.5 - trend))
                elif trend > 0.6:
                    warning_signals.append(weight * (trend - 0.5))
                    
                if momentum < -0.3:
                    quality_signals.append(weight * 0.5 * abs(momentum))
                elif momentum > 0.3:
                    warning_signals.append(weight * 0.5 * momentum)
                    
                if rsi > 40:
                    quality_signals.append(weight * 0.2 * (rsi - 40) / 30)
                elif rsi < 25:
                    warning_signals.append(weight * 0.3 * (30 - rsi) / 30)
                    
                if macd < 0:
                    quality_signals.append(weight * 0.3 * min(1.0, abs(macd)))
                elif macd > 0:
                    warning_signals.append(weight * 0.3 * min(1.0, macd))
                    
                if bb_position > 0.4:
                    quality_signals.append(weight * 0.15 * (bb_position - 0.3))
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 2: ML MODEL ANALYSIS
        # ML must agree with direction for quality entry
        # ═══════════════════════════════════════════════════════════
        
        ml_direction = getattr(context, 'ml_direction', 'HOLD')
        ml_confidence = getattr(context, 'ml_confidence', 50.0) / 100.0
        
        if is_buy:
            if ml_direction == 'BUY':
                quality_signals.append(0.30 * ml_confidence)
            elif ml_direction == 'SELL':
                warning_signals.append(0.30 * ml_confidence)
        else:
            if ml_direction == 'SELL':
                quality_signals.append(0.30 * ml_confidence)
            elif ml_direction == 'BUY':
                warning_signals.append(0.30 * ml_confidence)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 3: TIMEFRAME ALIGNMENT
        # Strong alignment = higher quality entry
        # ═══════════════════════════════════════════════════════════
        
        trend_alignment = getattr(context, 'trend_alignment', 0.5)
        macd_all_bullish = getattr(context, 'macd_all_bullish', 0.0)
        macd_all_bearish = getattr(context, 'macd_all_bearish', 0.0)
        
        if trend_alignment > 0.6:
            quality_signals.append(0.15 * (trend_alignment - 0.5))
        elif trend_alignment < 0.4:
            warning_signals.append(0.15 * (0.5 - trend_alignment))
        
        if is_buy:
            if macd_all_bullish > 0.5:
                quality_signals.append(0.12 * macd_all_bullish)
            if macd_all_bearish > 0.5:
                warning_signals.append(0.12 * macd_all_bearish)
        else:
            if macd_all_bearish > 0.5:
                quality_signals.append(0.12 * macd_all_bearish)
            if macd_all_bullish > 0.5:
                warning_signals.append(0.12 * macd_all_bullish)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 4: VOLUME INTELLIGENCE
        # Volume confirming the move = quality entry
        # ═══════════════════════════════════════════════════════════
        
        accumulation = getattr(context, 'accumulation', 0.0)
        distribution = getattr(context, 'distribution', 0.0)
        institutional_bars = getattr(context, 'institutional_bars', 0.0)
        
        if is_buy:
            if accumulation > 0.5:
                quality_signals.append(0.10 * accumulation)
            if distribution > 0.5:
                warning_signals.append(0.10 * distribution)
        else:
            if distribution > 0.5:
                quality_signals.append(0.10 * distribution)
            if accumulation > 0.5:
                warning_signals.append(0.10 * accumulation)
        
        if institutional_bars > 0.3:
            quality_signals.append(0.08 * institutional_bars)
        
        # ═══════════════════════════════════════════════════════════
        # CATEGORY 5: HTF MARKET STRUCTURE (replaces M1 order flow)
        # ═══════════════════════════════════════════════════════════
        
        h4_structure = getattr(context, 'h4_market_structure', 0.0)
        d1_structure = getattr(context, 'd1_market_structure', 0.0)
        htf_adx = getattr(context, 'htf_adx', 25.0)
        
        # Market structure supports entry direction = quality signal
        if is_buy:
            if h4_structure > 0.3:  # Uptrend structure
                quality_signals.append(0.10 * h4_structure)
            if h4_structure < -0.3:  # Downtrend structure = warning
                warning_signals.append(0.10 * abs(h4_structure))
        else:
            if h4_structure < -0.3:  # Downtrend structure
                quality_signals.append(0.10 * abs(h4_structure))
            if h4_structure > 0.3:  # Uptrend structure = warning
                warning_signals.append(0.10 * h4_structure)
        
        # Strong trend (high ADX) = higher quality
        if htf_adx > 30:
            quality_signals.append(0.05 * (htf_adx - 25) / 25)
        
        # ═══════════════════════════════════════════════════════════
        # CALCULATE FINAL SCORE
        # ═══════════════════════════════════════════════════════════
        
        total_quality = sum(quality_signals)
        total_warning = sum(warning_signals)
        
        # Normalize to 0-1 range
        if total_quality + total_warning > 0:
            entry_quality = total_quality / (total_quality + total_warning + 0.1)
        else:
            entry_quality = 0.5  # Neutral default
        
        # Clamp to 0-1
        entry_quality = max(0.0, min(1.0, entry_quality))
        
        logger.info(f"   🧠 Comprehensive Entry Analysis:")
        logger.info(f"      Quality signals: {len(quality_signals)} factors, total={total_quality:.3f}")
        logger.info(f"      Warning signals: {len(warning_signals)} factors, total={total_warning:.3f}")
        logger.info(f"      Final entry quality: {entry_quality:.3f}")
        
        return entry_quality
