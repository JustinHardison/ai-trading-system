#!/usr/bin/env python3
"""
Hybrid Exit Manager - Combines RL Q-learning with Professional EV-based decisions

BEST OF BOTH WORLDS:
1. RL Agent: Learns from 2,197 backtest trades (data-driven patterns)
2. Professional Exit Manager: EV calculations and risk management (domain expertise)
3. Hybrid: Uses RL Q-values as learned EV estimates, applies professional rules

ARCHITECTURE:
- RL provides: Q(HOLD), Q(CLOSE), Q(SCALE_50), Q(SCALE_25) from learned experience
- Professional adds: Risk adjustment, profit protection, time decay, uncertainty
- Result: Data-driven decisions with professional safety guardrails

ADVANTAGES:
✅ RL learns patterns from actual trades (not hardcoded)
✅ Professional rules prevent catastrophic mistakes
✅ Risk-adjusted EV using both learned and calculated values
✅ Uncertainty quantification around RL predictions
✅ Profit protection overrides if needed
"""
import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class HybridExitDecision:
    """Exit decision combining RL and Professional insights"""
    action: str  # HOLD, CLOSE_ALL, SCALE_OUT_50, SCALE_OUT_25
    expected_value: float  # Expected P&L in points
    rl_q_value: float  # Q-value from RL agent
    professional_ev: float  # EV from professional rules
    combined_ev: float  # Weighted combination
    probability: float  # Confidence in this decision
    uncertainty: float  # Uncertainty estimate
    reason: str  # Human-readable explanation
    rl_contribution: float  # How much RL influenced decision (0-1)
    professional_override: bool  # Did professional rules override RL?


class HybridExitManager:
    """
    Combines RL Agent and Professional Exit Manager

    Strategy:
    1. Get Q-values from RL agent (learned from 2,197 trades)
    2. Calculate EV from professional rules (domain expertise)
    3. Combine with adaptive weighting based on confidence
    4. Apply professional safety overrides
    """

    def __init__(
        self,
        rl_agent,
        professional_manager,
        rl_weight: float = 0.7,
        confidence_threshold: float = 0.3
    ):
        """
        Args:
            rl_agent: RLExitAgent instance (trained on backtest)
            professional_manager: ProfessionalExitManager instance
            rl_weight: Base weight for RL (0-1), 0.7 = 70% RL, 30% professional
            confidence_threshold: Min RL confidence to use RL heavily
        """
        self.rl_agent = rl_agent
        self.professional_manager = professional_manager
        self.rl_weight = rl_weight
        self.confidence_threshold = confidence_threshold

        # Professional override thresholds
        self.profit_protection_threshold = 0.7  # Protect 70% of max profit
        self.max_adverse_excursion = 0.3  # Close if retraced 30% from peak

    def decide_exit(
        self,
        features: Dict[str, float],
        current_profit_points: float,
        bars_held: int,
        max_profit_points: float,
        entry_confidence: float = 0.0,
        trade_type: str = "scalp"
    ) -> HybridExitDecision:
        """
        Make hybrid exit decision combining RL and professional insights

        Args:
            features: Market and position features
            current_profit_points: Current unrealized P&L
            bars_held: How long we've held position
            max_profit_points: Maximum profit achieved
            entry_confidence: Confidence from entry signal
            trade_type: 'scalp' or 'swing'

        Returns:
            HybridExitDecision with combined reasoning
        """

        # STEP 1: Get RL Agent's learned Q-values
        rl_decision = self.rl_agent.decide_exit(
            features=features,
            current_profit_points=current_profit_points,
            bars_held=bars_held,
            max_profit_points=max_profit_points,
            entry_confidence=entry_confidence,
            trade_type=trade_type
        )

        # Extract Q-values for all actions
        q_hold = rl_decision.q_values_all.get('HOLD', 0.0)
        q_close = rl_decision.q_values_all.get('CLOSE_ALL', 0.0)
        q_scale50 = rl_decision.q_values_all.get('SCALE_OUT_50', 0.0)
        q_scale25 = rl_decision.q_values_all.get('SCALE_OUT_25', 0.0)

        # STEP 2: Get Professional Exit Manager's EV calculations
        prof_decision = self.professional_manager.decide_exit(
            features=features,
            current_profit_points=current_profit_points,
            bars_held=bars_held,
            max_profit_points=max_profit_points,
            trade_type=trade_type
        )

        # STEP 3: Professional Safety Overrides (always respect these)

        # Override 1: Profit Protection
        if max_profit_points > 20:
            drawdown_from_peak = (max_profit_points - current_profit_points) / max_profit_points
            if drawdown_from_peak > self.max_adverse_excursion:
                return HybridExitDecision(
                    action="CLOSE_ALL",
                    expected_value=current_profit_points,
                    rl_q_value=q_close,
                    professional_ev=current_profit_points,
                    combined_ev=current_profit_points,
                    probability=1.0,
                    uncertainty=0.0,
                    reason=f"🛡️ PROFIT PROTECTION OVERRIDE: Retraced {drawdown_from_peak*100:.1f}% from {max_profit_points:.0f}pts peak",
                    rl_contribution=0.0,
                    professional_override=True
                )

        # Override 2: Time Decay for Scalps (learned + professional combined)
        if trade_type == "scalp" and bars_held > 30:
            if current_profit_points > 10:
                # RL might say HOLD, but professional says scalps overstay
                # Combine: If RL also suggests scaling/closing, do it
                if rl_decision.action in ["CLOSE_ALL", "SCALE_OUT_50", "SCALE_OUT_25"]:
                    return HybridExitDecision(
                        action=rl_decision.action,
                        expected_value=(q_close + current_profit_points) / 2,
                        rl_q_value=rl_decision.q_value,
                        professional_ev=current_profit_points,
                        combined_ev=(q_close + current_profit_points) / 2,
                        probability=0.85,
                        uncertainty=abs(q_close - current_profit_points) / 2,
                        reason=f"⏰ TIME DECAY + RL AGREEMENT: {bars_held} bars, RL={rl_decision.action}, secure {current_profit_points:.0f}pts",
                        rl_contribution=0.5,
                        professional_override=False
                    )

        # STEP 4: Adaptive Weighting based on RL Confidence
        # High confidence in RL → use more RL
        # Low confidence in RL → use more professional rules

        # Calculate RL confidence based on Q-value spread
        q_values = [q_hold, q_close, q_scale50, q_scale25]
        q_max = max(q_values)
        q_min = min(q_values)
        q_spread = abs(q_max - q_min)

        # High spread = confident decision, low spread = uncertain
        rl_confidence = min(1.0, q_spread / 50.0)  # Normalize to 0-1

        # Adaptive weight: More confident RL → higher RL weight
        if rl_confidence > self.confidence_threshold:
            adaptive_rl_weight = self.rl_weight + (1.0 - self.rl_weight) * (rl_confidence - self.confidence_threshold) / (1.0 - self.confidence_threshold)
        else:
            adaptive_rl_weight = self.rl_weight * (rl_confidence / self.confidence_threshold)

        adaptive_professional_weight = 1.0 - adaptive_rl_weight

        # STEP 5: Combine Q-values with Professional EV
        # Map professional action to EV
        prof_ev_map = {
            "HOLD": q_hold,  # Use RL's Q(HOLD) as learned EV
            "CLOSE_ALL": current_profit_points,  # Certain outcome
            "SCALE_OUT_50": (current_profit_points * 0.5 + q_hold * 0.5),
            "SCALE_OUT_25": (current_profit_points * 0.25 + q_hold * 0.75)
        }

        # Calculate combined EV for each action
        combined_ev = {}
        for action in ["HOLD", "CLOSE_ALL", "SCALE_OUT_50", "SCALE_OUT_25"]:
            if action == "HOLD":
                rl_ev = q_hold
            elif action == "CLOSE_ALL":
                rl_ev = q_close
            elif action == "SCALE_OUT_50":
                rl_ev = q_scale50
            else:  # SCALE_OUT_25
                rl_ev = q_scale25

            prof_ev = prof_ev_map.get(action, 0.0)

            # Weighted combination
            combined_ev[action] = (
                adaptive_rl_weight * rl_ev +
                adaptive_professional_weight * prof_ev
            )

        # STEP 6: Choose action with highest combined EV
        best_action = max(combined_ev, key=combined_ev.get)
        best_combined_ev = combined_ev[best_action]

        # Get individual components for chosen action
        if best_action == "HOLD":
            rl_q = q_hold
        elif best_action == "CLOSE_ALL":
            rl_q = q_close
        elif best_action == "SCALE_OUT_50":
            rl_q = q_scale50
        else:
            rl_q = q_scale25

        prof_ev = prof_ev_map.get(best_action, 0.0)

        # Calculate uncertainty (disagreement between RL and Professional)
        uncertainty = abs(rl_q - prof_ev)

        # Build reason
        reason_parts = []
        reason_parts.append(f"HYBRID: {best_action}")
        reason_parts.append(f"RL Q={rl_q:.1f}")
        reason_parts.append(f"Prof EV={prof_ev:.1f}")
        reason_parts.append(f"Combined={best_combined_ev:.1f}")
        reason_parts.append(f"(RL {adaptive_rl_weight*100:.0f}% / Prof {adaptive_professional_weight*100:.0f}%)")

        if rl_decision.action == prof_decision.action == best_action:
            reason_parts.append("✅ Full agreement")
        elif rl_decision.action == best_action:
            reason_parts.append("📊 RL-driven")
        elif prof_decision.action == best_action:
            reason_parts.append("🎓 Professional-driven")
        else:
            reason_parts.append("⚖️ Hybrid compromise")

        reason = " | ".join(reason_parts)

        # STEP 7: Return hybrid decision
        return HybridExitDecision(
            action=best_action,
            expected_value=best_combined_ev,
            rl_q_value=rl_q,
            professional_ev=prof_ev,
            combined_ev=best_combined_ev,
            probability=rl_confidence,
            uncertainty=uncertainty,
            reason=reason,
            rl_contribution=adaptive_rl_weight,
            professional_override=False
        )
