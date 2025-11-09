"""
Net Currency Exposure Tracker
Prevents correlation bombs (e.g., long EURUSD + long GBPUSD = double short USD)
"""
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CurrencyExposure:
    """Currency exposure breakdown"""
    currency: str
    net_exposure_pct: float  # Net exposure as % of account
    long_exposure_pct: float
    short_exposure_pct: float
    positions: List[str]  # List of symbols contributing


@dataclass
class PortfolioExposure:
    """Full portfolio exposure analysis"""
    total_risk_pct: float  # Portfolio heat
    exposures: Dict[str, CurrencyExposure]
    max_exposure: Tuple[str, float]  # (currency, exposure_pct)
    warnings: List[str]
    is_safe: bool


class CurrencyExposureTracker:
    """
    Tracks net currency exposure across all positions
    """

    def __init__(self, max_currency_exposure_pct: float = 4.0):
        """
        Args:
            max_currency_exposure_pct: Maximum exposure to any single currency (% of account)
        """
        self.max_exposure = max_currency_exposure_pct

    def calculate_exposure(
        self,
        positions: List[Dict],
        account_balance: float
    ) -> PortfolioExposure:
        """
        Calculate net currency exposure from all positions

        Args:
            positions: List of open positions with {symbol, direction, lots, profit}
            account_balance: Current account balance

        Returns:
            PortfolioExposure with breakdown and warnings
        """
        if not positions:
            return PortfolioExposure(
                total_risk_pct=0.0,
                exposures={},
                max_exposure=('NONE', 0.0),
                warnings=[],
                is_safe=True
            )

        # Parse each position
        currency_exposures = {}
        total_risk = 0.0

        for pos in positions:
            symbol = pos['symbol']
            direction = pos['direction']  # 'BUY' or 'SELL'
            lots = pos['lots']
            risk_pct = pos.get('risk_pct', 1.0)  # Estimated risk

            # Parse currency pair (e.g., EURUSD → EUR, USD)
            base_currency, quote_currency = self._parse_symbol(symbol)

            # Calculate exposure
            if direction == 'BUY':
                # Long EURUSD = long EUR, short USD
                self._add_exposure(currency_exposures, base_currency, risk_pct, symbol, 'LONG')
                self._add_exposure(currency_exposures, quote_currency, -risk_pct, symbol, 'SHORT')
            else:
                # Short EURUSD = short EUR, long USD
                self._add_exposure(currency_exposures, base_currency, -risk_pct, symbol, 'SHORT')
                self._add_exposure(currency_exposures, quote_currency, risk_pct, symbol, 'LONG')

            total_risk += risk_pct

        # Convert to CurrencyExposure objects
        exposures = {}
        for currency, data in currency_exposures.items():
            exposures[currency] = CurrencyExposure(
                currency=currency,
                net_exposure_pct=data['net'],
                long_exposure_pct=data['long'],
                short_exposure_pct=data['short'],
                positions=data['positions']
            )

        # Find max exposure
        max_currency = max(exposures.items(), key=lambda x: abs(x[1].net_exposure_pct))
        max_exposure = (max_currency[0], abs(max_currency[1].net_exposure_pct))

        # Generate warnings
        warnings = self._generate_warnings(exposures, total_risk)

        is_safe = len(warnings) == 0

        logger.info(f"Portfolio exposure: {len(exposures)} currencies, max: {max_exposure[0]} "
                   f"({max_exposure[1]:.1f}%), total risk: {total_risk:.1f}%")

        return PortfolioExposure(
            total_risk_pct=total_risk,
            exposures=exposures,
            max_exposure=max_exposure,
            warnings=warnings,
            is_safe=is_safe
        )

    def check_new_trade(
        self,
        current_exposure: PortfolioExposure,
        new_symbol: str,
        new_direction: str,
        new_risk_pct: float
    ) -> Tuple[bool, str]:
        """
        Check if new trade would violate exposure limits

        Returns:
            (is_allowed, reason)
        """
        base, quote = self._parse_symbol(new_symbol)

        # Calculate what new exposure would be
        current_base = current_exposure.exposures.get(base)
        current_quote = current_exposure.exposures.get(quote)

        if new_direction == 'BUY':
            new_base_exposure = (current_base.net_exposure_pct if current_base else 0) + new_risk_pct
            new_quote_exposure = (current_quote.net_exposure_pct if current_quote else 0) - new_risk_pct
        else:
            new_base_exposure = (current_base.net_exposure_pct if current_base else 0) - new_risk_pct
            new_quote_exposure = (current_quote.net_exposure_pct if current_quote else 0) + new_risk_pct

        # Check limits
        if abs(new_base_exposure) > self.max_exposure:
            return False, f"Would exceed {base} exposure limit: {abs(new_base_exposure):.1f}% > {self.max_exposure}%"

        if abs(new_quote_exposure) > self.max_exposure:
            return False, f"Would exceed {quote} exposure limit: {abs(new_quote_exposure):.1f}% > {self.max_exposure}%"

        # Check total portfolio heat
        new_total_risk = current_exposure.total_risk_pct + new_risk_pct
        if new_total_risk > 8.0:  # Max 8% portfolio heat
            return False, f"Would exceed portfolio heat limit: {new_total_risk:.1f}% > 8.0%"

        return True, "Trade allowed"

    def _parse_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Parse forex symbol into base and quote currency
        Examples: EURUSD → (EUR, USD), GBPJPY → (GBP, JPY)
        """
        # Remove .sim suffix if present
        symbol = symbol.replace('.sim', '')

        # Handle standard 6-character forex pairs
        if len(symbol) == 6:
            return symbol[:3], symbol[3:6]

        # Handle 7+ character pairs (e.g., USDMXN)
        # Assume first 3 chars are base, rest is quote
        return symbol[:3], symbol[3:]

    def _add_exposure(
        self,
        exposures: Dict,
        currency: str,
        exposure_pct: float,
        symbol: str,
        direction: str
    ):
        """Add exposure to tracking dictionary"""
        if currency not in exposures:
            exposures[currency] = {
                'net': 0.0,
                'long': 0.0,
                'short': 0.0,
                'positions': []
            }

        exposures[currency]['net'] += exposure_pct

        if exposure_pct > 0:
            exposures[currency]['long'] += exposure_pct
        else:
            exposures[currency]['short'] += abs(exposure_pct)

        exposures[currency]['positions'].append(f"{symbol} ({direction})")

    def _generate_warnings(
        self,
        exposures: Dict[str, CurrencyExposure],
        total_risk: float
    ) -> List[str]:
        """Generate exposure warnings"""
        warnings = []

        # Check individual currency limits
        for currency, exposure in exposures.items():
            if abs(exposure.net_exposure_pct) > self.max_exposure:
                warnings.append(
                    f"CRITICAL: {currency} exposure {abs(exposure.net_exposure_pct):.1f}% "
                    f"exceeds limit {self.max_exposure}%. Positions: {', '.join(exposure.positions)}"
                )

        # Check total portfolio heat
        if total_risk > 8.0:
            warnings.append(f"CRITICAL: Total portfolio risk {total_risk:.1f}% exceeds 8% limit")

        # Check for high concentration
        for currency, exposure in exposures.items():
            if abs(exposure.net_exposure_pct) > self.max_exposure * 0.75:
                warnings.append(
                    f"WARNING: {currency} exposure {abs(exposure.net_exposure_pct):.1f}% "
                    f"near limit ({self.max_exposure * 0.75:.1f}%)"
                )

        return warnings

    def get_correlation_matrix(self, symbols: List[str]) -> np.ndarray:
        """
        Calculate currency correlation matrix
        Note: This is simplified. Real version would use historical price data.
        """
        # Hardcoded typical forex correlations
        correlation_map = {
            ('EUR', 'GBP'): 0.7,
            ('EUR', 'CHF'): 0.8,
            ('EUR', 'JPY'): -0.3,
            ('GBP', 'CHF'): 0.6,
            ('GBP', 'JPY'): -0.2,
            ('USD', 'JPY'): -0.5,
            ('AUD', 'NZD'): 0.85,
            ('EUR', 'AUD'): 0.4,
        }

        # Build matrix
        currencies = list(set([self._parse_symbol(s)[0] for s in symbols] +
                             [self._parse_symbol(s)[1] for s in symbols]))

        n = len(currencies)
        matrix = np.eye(n)  # Start with identity

        for i, curr1 in enumerate(currencies):
            for j, curr2 in enumerate(currencies):
                if i != j:
                    # Check both directions
                    corr = correlation_map.get((curr1, curr2)) or \
                          correlation_map.get((curr2, curr1)) or 0.0
                    matrix[i, j] = corr

        return matrix
