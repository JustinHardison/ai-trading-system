"""
Adaptive AI Optimizer - Self-Learning Parameter Optimization
Automatically adjusts trading parameters based on performance
"""
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class AdaptiveOptimizer:
    """
    AI-driven parameter optimizer that learns from trading results
    Adjusts confidence thresholds, R:R requirements, and position sizing
    """
    
    def __init__(self, config_file='adaptive_config.json'):
        self.config_file = config_file
        
        # Initial parameters (starting point, not hardcoded limits)
        self.params = {
            'min_ml_confidence': 0.50,
            'min_rr_ratio': 1.0,  # Lowered to allow trading and data collection
            'min_quality_score': 0.9,
            'base_risk_pct': 0.012,
            'counter_trend_confidence': 0.60,
            'max_risk_pct': 0.025,
            'quality_scaling': True
        }
        
        # Performance tracking
        self.trade_history = []
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'avg_rr': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_dd': 0.0,
            'sharpe_ratio': 0.0
        }
        
        # Learning parameters
        self.learning_rate = 0.05  # How fast to adapt
        self.min_trades_for_adjustment = 10  # Minimum trades before adjusting
        self.adjustment_interval = 20  # Adjust every N trades
        
        # Load existing config if available
        self.load_config()
        
    def load_config(self):
        """Load saved configuration"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                self.params = data.get('params', self.params)
                self.trade_history = data.get('trade_history', [])
                self.performance_metrics = data.get('metrics', self.performance_metrics)
                logger.info(f"✅ Loaded adaptive config: {len(self.trade_history)} trades in history")
        except FileNotFoundError:
            logger.info("📝 No existing config, starting fresh")
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
    
    def save_config(self):
        """Save current configuration"""
        try:
            data = {
                'params': self.params,
                'trade_history': self.trade_history[-100:],  # Keep last 100 trades
                'metrics': self.performance_metrics,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("💾 Saved adaptive config")
        except Exception as e:
            logger.error(f"❌ Error saving config: {e}")
    
    def record_trade(self, trade_data: Dict):
        """
        Record trade result and trigger optimization if needed
        
        trade_data should include:
        - win: bool
        - pnl: float
        - risk_amount: float
        - ml_confidence: float
        - rr_ratio: float
        - quality_score: float
        - entry_reason: str
        """
        self.trade_history.append({
            **trade_data,
            'timestamp': datetime.now().isoformat()
        })
        
        # Update metrics
        self._update_metrics()
        
        # Check if we should optimize
        if len(self.trade_history) >= self.min_trades_for_adjustment:
            if len(self.trade_history) % self.adjustment_interval == 0:
                self.optimize_parameters()
        
        # Save after each trade
        self.save_config()
    
    def _update_metrics(self):
        """Update performance metrics from trade history"""
        if not self.trade_history:
            return
        
        recent_trades = self.trade_history[-50:]  # Last 50 trades
        
        wins = [t for t in recent_trades if t.get('win', False)]
        losses = [t for t in recent_trades if not t.get('win', False)]
        
        self.performance_metrics['total_trades'] = len(recent_trades)
        self.performance_metrics['winning_trades'] = len(wins)
        self.performance_metrics['losing_trades'] = len(losses)
        
        self.performance_metrics['win_rate'] = len(wins) / len(recent_trades) if recent_trades else 0
        
        if wins:
            self.performance_metrics['avg_win'] = np.mean([t['pnl'] for t in wins])
        if losses:
            self.performance_metrics['avg_loss'] = abs(np.mean([t['pnl'] for t in losses]))
        
        total_wins = sum([t['pnl'] for t in wins]) if wins else 0
        total_losses = abs(sum([t['pnl'] for t in losses])) if losses else 1
        self.performance_metrics['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0
        
        # Calculate Sharpe ratio (simplified)
        pnls = [t['pnl'] for t in recent_trades]
        if len(pnls) > 1:
            self.performance_metrics['sharpe_ratio'] = np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0
    
    def optimize_parameters(self):
        """
        AI-driven parameter optimization based on recent performance
        Uses reinforcement learning principles
        """
        logger.info("🤖 AI OPTIMIZER: Analyzing performance and adjusting parameters...")
        
        metrics = self.performance_metrics
        recent_trades = self.trade_history[-self.adjustment_interval:]
        
        # Calculate performance score (0-100)
        performance_score = self._calculate_performance_score(metrics)
        
        logger.info(f"📊 Performance Score: {performance_score:.1f}/100")
        logger.info(f"   Win Rate: {metrics['win_rate']*100:.1f}%")
        logger.info(f"   Profit Factor: {metrics['profit_factor']:.2f}")
        logger.info(f"   Sharpe: {metrics['sharpe_ratio']:.2f}")
        
        # Adjust based on performance
        if performance_score < 40:
            # Poor performance - be MORE selective
            self._increase_selectivity()
        elif performance_score > 70:
            # Good performance - can be LESS selective (more trades)
            self._decrease_selectivity()
        else:
            # Moderate performance - fine-tune
            self._fine_tune_parameters(recent_trades)
        
        # Adjust risk based on drawdown
        self._adjust_risk_based_on_dd()
        
        # Log new parameters
        logger.info("🎯 NEW PARAMETERS:")
        for key, value in self.params.items():
            logger.info(f"   {key}: {value}")
        
        self.save_config()
    
    def _calculate_performance_score(self, metrics: Dict) -> float:
        """Calculate overall performance score (0-100)"""
        score = 0.0
        
        # Win rate component (0-30 points)
        win_rate = metrics.get('win_rate', 0)
        if win_rate > 0.55:
            score += 30
        elif win_rate > 0.50:
            score += 25
        elif win_rate > 0.45:
            score += 20
        elif win_rate > 0.40:
            score += 10
        
        # Profit factor component (0-40 points)
        pf = metrics.get('profit_factor', 0)
        if pf > 2.0:
            score += 40
        elif pf > 1.5:
            score += 30
        elif pf > 1.2:
            score += 20
        elif pf > 1.0:
            score += 10
        
        # Sharpe ratio component (0-30 points)
        sharpe = metrics.get('sharpe_ratio', 0)
        if sharpe > 2.0:
            score += 30
        elif sharpe > 1.5:
            score += 25
        elif sharpe > 1.0:
            score += 20
        elif sharpe > 0.5:
            score += 10
        
        return score
    
    def _increase_selectivity(self):
        """Make system MORE selective (fewer, better trades)"""
        logger.info("⬆️  INCREASING SELECTIVITY (performance below target)")
        
        # Raise confidence threshold
        self.params['min_ml_confidence'] = min(0.65, self.params['min_ml_confidence'] + 0.03)
        
        # Raise R:R requirement
        self.params['min_rr_ratio'] = min(2.5, self.params['min_rr_ratio'] + 0.2)
        
        # Raise quality threshold
        self.params['min_quality_score'] = min(1.3, self.params['min_quality_score'] + 0.1)
        
        # Reduce risk
        self.params['base_risk_pct'] = max(0.008, self.params['base_risk_pct'] - 0.002)
    
    def _decrease_selectivity(self):
        """Make system LESS selective (more trades)"""
        logger.info("⬇️  DECREASING SELECTIVITY (performance above target)")
        
        # Lower confidence threshold (but not too much)
        self.params['min_ml_confidence'] = max(0.45, self.params['min_ml_confidence'] - 0.02)
        
        # Lower R:R requirement (but keep reasonable)
        self.params['min_rr_ratio'] = max(1.3, self.params['min_rr_ratio'] - 0.1)
        
        # Lower quality threshold
        self.params['min_quality_score'] = max(0.8, self.params['min_quality_score'] - 0.05)
        
        # Can increase risk slightly
        self.params['base_risk_pct'] = min(0.015, self.params['base_risk_pct'] + 0.001)
    
    def _fine_tune_parameters(self, recent_trades: List[Dict]):
        """Fine-tune based on specific patterns in recent trades"""
        
        # Analyze what's working
        high_conf_trades = [t for t in recent_trades if t.get('ml_confidence', 0) > 0.60]
        high_conf_win_rate = sum([1 for t in high_conf_trades if t.get('win', False)]) / len(high_conf_trades) if high_conf_trades else 0
        
        low_conf_trades = [t for t in recent_trades if t.get('ml_confidence', 0) < 0.55]
        low_conf_win_rate = sum([1 for t in low_conf_trades if t.get('win', False)]) / len(low_conf_trades) if low_conf_trades else 0
        
        # If high confidence trades doing much better, raise threshold
        if high_conf_win_rate > low_conf_win_rate + 0.15:
            self.params['min_ml_confidence'] = min(0.60, self.params['min_ml_confidence'] + 0.02)
            logger.info("   📈 High confidence trades performing better - raising threshold")
        
        # Analyze R:R effectiveness
        high_rr_trades = [t for t in recent_trades if t.get('rr_ratio', 0) > 2.0]
        if high_rr_trades:
            high_rr_win_rate = sum([1 for t in high_rr_trades if t.get('win', False)]) / len(high_rr_trades)
            if high_rr_win_rate > 0.45:
                self.params['min_rr_ratio'] = min(2.0, self.params['min_rr_ratio'] + 0.1)
                logger.info("   📈 High R:R trades profitable - raising requirement")
    
    def _adjust_risk_based_on_dd(self):
        """Adjust risk based on recent drawdown"""
        recent_pnls = [t['pnl'] for t in self.trade_history[-20:]]
        if recent_pnls:
            cumsum = np.cumsum(recent_pnls)
            running_max = np.maximum.accumulate(cumsum)
            drawdown = running_max - cumsum
            max_dd_pct = np.max(drawdown) / 100000 if len(drawdown) > 0 else 0  # Assuming 100k balance
            
            if max_dd_pct > 0.08:  # 8% DD
                # Reduce risk
                self.params['base_risk_pct'] = max(0.008, self.params['base_risk_pct'] * 0.9)
                logger.info(f"   ⚠️  High drawdown ({max_dd_pct*100:.1f}%) - reducing risk")
            elif max_dd_pct < 0.03:  # Low DD
                # Can increase risk slightly
                self.params['base_risk_pct'] = min(0.015, self.params['base_risk_pct'] * 1.05)
                logger.info(f"   ✅ Low drawdown ({max_dd_pct*100:.1f}%) - increasing risk")
    
    def get_current_parameters(self) -> Dict:
        """Get current optimized parameters"""
        return self.params.copy()
    
    def should_take_trade(self, ml_confidence: float, rr_ratio: float, quality_score: float, 
                         is_counter_trend: bool = False) -> Tuple[bool, str]:
        """
        AI decides if trade should be taken based on current optimized parameters
        
        Returns: (should_trade, reason)
        """
        
        # Check ML confidence
        min_conf = self.params['counter_trend_confidence'] if is_counter_trend else self.params['min_ml_confidence']
        if ml_confidence < min_conf:
            return False, f"ML confidence {ml_confidence:.1%} < {min_conf:.1%}"
        
        # Check R:R
        if rr_ratio < self.params['min_rr_ratio']:
            return False, f"R:R {rr_ratio:.2f} < {self.params['min_rr_ratio']:.2f}"
        
        # Check quality
        if quality_score < self.params['min_quality_score']:
            return False, f"Quality {quality_score:.2f} < {self.params['min_quality_score']:.2f}"
        
        return True, f"APPROVED: Conf={ml_confidence:.1%}, R:R={rr_ratio:.2f}, Q={quality_score:.2f}"
    
    def calculate_position_size(self, balance: float, quality_score: float, 
                               current_dd_pct: float = 0.0) -> float:
        """
        AI calculates optimal position size based on quality and current state
        
        Returns: risk amount in dollars
        """
        base_risk = balance * self.params['base_risk_pct']
        
        # Scale by quality if enabled
        if self.params['quality_scaling']:
            risk = base_risk * quality_score
        else:
            risk = base_risk
        
        # Reduce if in drawdown
        if current_dd_pct > 0.05:  # 5% DD
            risk *= 0.7
        elif current_dd_pct > 0.03:  # 3% DD
            risk *= 0.85
        
        # Cap at max risk
        max_risk = balance * self.params['max_risk_pct']
        risk = min(risk, max_risk)
        
        # Floor at 0.5% of balance
        min_risk = balance * 0.005
        risk = max(risk, min_risk)
        
        return risk
    
    def get_performance_summary(self) -> str:
        """Get human-readable performance summary"""
        m = self.performance_metrics
        return f"""
🤖 AI OPTIMIZER PERFORMANCE SUMMARY
{'='*50}
Total Trades: {m['total_trades']}
Win Rate: {m['win_rate']*100:.1f}%
Profit Factor: {m['profit_factor']:.2f}
Avg Win: ${m['avg_win']:.2f}
Avg Loss: ${m['avg_loss']:.2f}
Sharpe Ratio: {m['sharpe_ratio']:.2f}

CURRENT PARAMETERS:
Min ML Confidence: {self.params['min_ml_confidence']*100:.1f}%
Min R:R Ratio: {self.params['min_rr_ratio']:.2f}:1
Min Quality Score: {self.params['min_quality_score']:.2f}
Base Risk: {self.params['base_risk_pct']*100:.2f}%
{'='*50}
"""
