#!/usr/bin/env python3
"""
Professional Exit Manager - Expected Value Based Exit Decisions

PROBLEM WITH CLASSIFICATION APPROACH:
- Model outputs: HOLD, CLOSE, SCALE_OUT with confidence
- 40% confidence in CLOSE means 60% NOT confident
- Using confidence thresholds is a band-aid
- Doesn't quantify EXPECTED OUTCOMES

PROFESSIONAL TRADER APPROACH:
- Calculate Expected Value for each action
- Compare EV(hold) vs EV(close) vs EV(scale_out)
- Choose action with highest expected profit
- Quantify uncertainty and risk
- Incorporate market regime awareness

ARCHITECTURE:
1. Outcome Prediction Models (Regression, not Classification)
   - Predict expected P&L if we hold N more bars
   - Predict probability distribution of outcomes
   - Quantify uncertainty (prediction intervals)

2. Expected Value Calculator
   - EV(hold) = E[future_profit | hold] × P(profit | hold) - E[future_loss | hold] × P(loss | hold)
   - EV(scale_out_50) = current_profit × 0.5 + EV(hold_50%) × 0.5
   - EV(close) = current_profit (certain outcome)

3. Risk-Adjusted Decision
   - Incorporate risk aversion (Kelly Criterion style)
   - Market regime modifiers
   - Confidence intervals for uncertainty

4. Action Selection
   - Choose action with highest risk-adjusted EV
   - Minimum EV thresholds to prevent churn
   - Scaling logic based on EV gradients
"""
import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExitOutcome:
    """Predicted outcome for an exit decision"""
    action: str  # HOLD, CLOSE_ALL, SCALE_OUT_50, SCALE_OUT_25, SCALE_IN
    expected_value: float  # Expected P&L in points
    probability: float  # Probability this outcome materializes
    uncertainty: float  # Standard deviation of prediction
    confidence_interval: Tuple[float, float]  # (lower, upper) 95% CI
    reason: str  # Human-readable explanation


class ProfessionalExitManager:
    """
    Expected Value based exit decision system

    Instead of classifying actions with confidence, this system:
    1. Predicts expected outcomes for each action
    2. Calculates EV for each action
    3. Chooses action with highest risk-adjusted EV
    """

    def __init__(self, outcome_model=None, risk_aversion: float = 1.0):
        """
        Args:
            outcome_model: Regression model predicting future P&L
            risk_aversion: Risk aversion parameter (0-2)
                          0 = risk neutral (maximize EV)
                          1 = standard risk aversion
                          2 = very conservative
        """
        self.outcome_model = outcome_model
        self.risk_aversion = risk_aversion

        # Minimum EV improvement needed to take action (prevent churn)
        self.min_ev_improvement = 5.0  # 5 points minimum

        # Professional trader parameters
        self.profit_protection_threshold = 0.7  # Start protecting at 70% of max profit
        self.max_adverse_excursion = 0.3  # Close if retraced 30% from peak

    def decide_exit(
        self,
        features: Dict[str, float],
        current_profit_points: float,
        bars_held: int,
        max_profit_points: float,
        trade_type: str = "scalp"
    ) -> ExitOutcome:
        """
        Make professional exit decision based on Expected Value

        Args:
            features: Market and position features
            current_profit_points: Current unrealized P&L in points
            bars_held: How long we've held the position
            max_profit_points: Maximum profit achieved since entry
            trade_type: 'scalp' or 'swing'

        Returns:
            ExitOutcome with action and rationale
        """

        # Calculate EV for each possible action
        ev_hold = self._calculate_ev_hold(features, current_profit_points, bars_held, trade_type)
        ev_close = self._calculate_ev_close(current_profit_points)
        ev_scale_out_50 = self._calculate_ev_scale_out(
            current_profit_points, ev_hold, scale_pct=0.5
        )
        ev_scale_out_25 = self._calculate_ev_scale_out(
            current_profit_points, ev_hold, scale_pct=0.25
        )

        # Risk-adjusted EV (penalize uncertainty)
        risk_adjusted_ev_hold = self._risk_adjust(ev_hold, self.risk_aversion)
        risk_adjusted_ev_close = self._risk_adjust(ev_close, 0)  # Closing is certain
        risk_adjusted_ev_scale_50 = self._risk_adjust(ev_scale_out_50, self.risk_aversion * 0.5)
        risk_adjusted_ev_scale_25 = self._risk_adjust(ev_scale_out_25, self.risk_aversion * 0.75)

        # Professional trader rules overlay
        # Rule 1: Protect profits - if we've given back too much from peak, exit
        if max_profit_points > 20:  # Only applies if we had real profit
            drawdown_from_peak = (max_profit_points - current_profit_points) / max_profit_points
            if drawdown_from_peak > self.max_adverse_excursion:
                return ExitOutcome(
                    action="CLOSE_ALL",
                    expected_value=current_profit_points,
                    probability=1.0,
                    uncertainty=0.0,
                    confidence_interval=(current_profit_points, current_profit_points),
                    reason=f"PROFIT PROTECTION: Retraced {drawdown_from_peak*100:.1f}% from peak ({max_profit_points:.0f}pts)"
                )

        # Rule 2: Time-based exits for scalps
        if trade_type == "scalp" and bars_held > 30:  # M1 bars = 30 minutes
            if current_profit_points > 10:  # Profitable
                # Scale out if holding too long with profit
                return ExitOutcome(
                    action="SCALE_OUT_50",
                    expected_value=ev_scale_out_50['ev'],
                    probability=0.8,
                    uncertainty=ev_scale_out_50['uncertainty'],
                    confidence_interval=ev_scale_out_50['ci'],
                    reason=f"TIME DECAY: {bars_held} bars held, scalp overstayed, secure {current_profit_points:.0f}pts"
                )

        # Rule 3: Choose action with highest risk-adjusted EV
        actions_ev = {
            "HOLD": risk_adjusted_ev_hold,
            "CLOSE_ALL": risk_adjusted_ev_close,
            "SCALE_OUT_50": risk_adjusted_ev_scale_50,
            "SCALE_OUT_25": risk_adjusted_ev_scale_25
        }

        best_action = max(actions_ev, key=lambda k: actions_ev[k]['ev'])
        best_ev = actions_ev[best_action]

        # Rule 4: Minimum EV improvement to act (prevent churn)
        if best_action != "HOLD":
            ev_improvement = best_ev['ev'] - risk_adjusted_ev_hold['ev']
            if ev_improvement < self.min_ev_improvement:
                # Not enough EV improvement to justify action
                return ExitOutcome(
                    action="HOLD",
                    expected_value=ev_hold['ev'],
                    probability=ev_hold['probability'],
                    uncertainty=ev_hold['uncertainty'],
                    confidence_interval=ev_hold['ci'],
                    reason=f"INSUFFICIENT EV: {best_action} only +{ev_improvement:.1f}pts vs HOLD (need +{self.min_ev_improvement:.0f})"
                )

        # Execute best action
        if best_action == "HOLD":
            return ExitOutcome(
                action="HOLD",
                expected_value=ev_hold['ev'],
                probability=ev_hold['probability'],
                uncertainty=ev_hold['uncertainty'],
                confidence_interval=ev_hold['ci'],
                reason=f"OPTIMAL: EV(hold)={ev_hold['ev']:.1f}pts @ {bars_held} bars"
            )

        elif best_action == "CLOSE_ALL":
            return ExitOutcome(
                action="CLOSE_ALL",
                expected_value=current_profit_points,
                probability=1.0,
                uncertainty=0.0,
                confidence_interval=(current_profit_points, current_profit_points),
                reason=f"OPTIMAL: EV(close)={current_profit_points:.1f}pts > EV(hold)={ev_hold['ev']:.1f}pts"
            )

        elif best_action == "SCALE_OUT_50":
            return ExitOutcome(
                action="SCALE_OUT_50",
                expected_value=ev_scale_out_50['ev'],
                probability=0.8,
                uncertainty=ev_scale_out_50['uncertainty'],
                confidence_interval=ev_scale_out_50['ci'],
                reason=f"OPTIMAL: EV(scale50)={ev_scale_out_50['ev']:.1f}pts - partial profit taking"
            )

        else:  # SCALE_OUT_25
            return ExitOutcome(
                action="SCALE_OUT_25",
                expected_value=ev_scale_out_25['ev'],
                probability=0.8,
                uncertainty=ev_scale_out_25['uncertainty'],
                confidence_interval=ev_scale_out_25['ci'],
                reason=f"OPTIMAL: EV(scale25)={ev_scale_out_25['ev']:.1f}pts - conservative scaling"
            )

    def _calculate_ev_hold(
        self,
        features: Dict[str, float],
        current_profit: float,
        bars_held: int,
        trade_type: str
    ) -> Dict[str, float]:
        """
        Calculate Expected Value of holding position

        EV(hold) = E[profit_N_bars_ahead] × P(profit) - E[loss_N_bars_ahead] × P(loss)
        """
        if self.outcome_model is None:
            # Fallback: Simple heuristic
            # Assume mean reversion: profit decays, loss grows
            time_decay = 1.0 - (bars_held / 100.0)  # Decay over time

            if current_profit > 0:
                # Profitable - assume mean reversion pulls it down
                expected_future_profit = current_profit * 0.9 * time_decay
                prob_profit = 0.6
                expected_future_loss = current_profit * 0.3
                prob_loss = 0.4
            else:
                # Losing - assume continues losing
                expected_future_profit = abs(current_profit) * 0.2
                prob_profit = 0.3
                expected_future_loss = abs(current_profit) * 1.2
                prob_loss = 0.7

            ev = expected_future_profit * prob_profit - expected_future_loss * prob_loss
            uncertainty = abs(current_profit) * 0.5  # High uncertainty

            return {
                'ev': ev,
                'probability': prob_profit,
                'uncertainty': uncertainty,
                'ci': (ev - uncertainty * 1.96, ev + uncertainty * 1.96)
            }

        # TODO: Use outcome_model to predict future P&L distribution
        # model.predict_distribution(features) -> (mean, std, quantiles)
        pass

    def _calculate_ev_close(self, current_profit: float) -> Dict[str, float]:
        """
        Calculate EV of closing now (certain outcome)
        """
        return {
            'ev': current_profit,
            'probability': 1.0,
            'uncertainty': 0.0,
            'ci': (current_profit, current_profit)
        }

    def _calculate_ev_scale_out(
        self,
        current_profit: float,
        ev_hold: Dict[str, float],
        scale_pct: float
    ) -> Dict[str, float]:
        """
        Calculate EV of scaling out (partial exit)

        EV(scale_out) = current_profit × scale_pct + EV(hold) × (1 - scale_pct)
        """
        certain_profit = current_profit * scale_pct
        remaining_ev = ev_hold['ev'] * (1 - scale_pct)

        total_ev = certain_profit + remaining_ev

        # Uncertainty is reduced by taking partial profit
        uncertainty = ev_hold['uncertainty'] * (1 - scale_pct)

        return {
            'ev': total_ev,
            'probability': 0.8,  # High probability since partially protected
            'uncertainty': uncertainty,
            'ci': (total_ev - uncertainty * 1.96, total_ev + uncertainty * 1.96)
        }

    def _risk_adjust(self, outcome: Dict[str, float], risk_aversion: float) -> Dict[str, float]:
        """
        Apply risk aversion to Expected Value

        Risk-adjusted EV = EV - risk_aversion × uncertainty²

        This penalizes high-uncertainty outcomes, similar to utility theory
        """
        ev = outcome['ev']
        uncertainty = outcome['uncertainty']

        # Penalize uncertainty quadratically (professional traders hate uncertainty)
        risk_penalty = risk_aversion * (uncertainty ** 2) / 100.0

        risk_adjusted_ev = ev - risk_penalty

        return {
            'ev': risk_adjusted_ev,
            'probability': outcome['probability'],
            'uncertainty': uncertainty,
            'ci': outcome['ci']
        }
