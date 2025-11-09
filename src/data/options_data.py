"""
OPTIONS DATA INTEGRATION - DIA (DOW JONES ETF)
Direct US30 options exposure via DIA
Gamma exposure and delta levels for US30 trading
"""
import requests
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta

from ..utils.logger import get_logger

logger = get_logger(__name__)


class OptionsDataProvider:
    """
    Fetches DIA (Dow Jones ETF) options data
    DIRECT correlation to US30 forex
    Uses Yahoo Finance (free, no API key)
    """

    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com"
        self.symbol = "DIA"  # Dow Jones ETF - DIRECT US30 proxy

    def get_dia_gamma_exposure(self) -> Dict[str, float]:
        """
        Calculate DIA gamma exposure levels
        High gamma = market maker hedging = lower volatility
        Low/negative gamma = higher volatility

        Returns features for ML model
        """
        try:
            # Get DIA options chain
            options_data = self._fetch_dia_options()

            if not options_data:
                return self._default_features()

            # Calculate gamma exposure
            gamma_features = self._calculate_gamma_features(options_data)

            # Calculate delta features
            delta_features = self._calculate_delta_features(options_data)

            # Combine all features
            features = {**gamma_features, **delta_features}

            logger.info(f"Options data features: {len(features)} metrics extracted")
            return features

        except Exception as e:
            logger.warning(f"Options data error: {e}")
            return self._default_features()

    def _fetch_dia_options(self) -> Dict:
        """Fetch DIA options chain from Yahoo Finance"""
        try:
            # Get current DIA price (Dow Jones ETF)
            dia_url = f"{self.base_url}/v8/finance/chart/DIA?interval=1d&range=1d"
            dia_response = requests.get(dia_url, timeout=5)

            if dia_response.status_code != 200:
                return None

            dia_data = dia_response.json()
            dia_price = dia_data['chart']['result'][0]['meta']['regularMarketPrice']

            # Get options chain for nearest expiration
            options_url = f"{self.base_url}/v7/finance/options/DIA"
            options_response = requests.get(options_url, timeout=5)

            if options_response.status_code != 200:
                return None

            options_data = options_response.json()

            result = options_data.get('optionChain', {}).get('result', [])
            if not result:
                return None

            options = result[0].get('options', [])
            if not options:
                return None

            calls = options[0].get('calls', [])
            puts = options[0].get('puts', [])

            return {
                'spot_price': dia_price,
                'calls': calls,
                'puts': puts
            }

        except Exception as e:
            logger.warning(f"Failed to fetch DIA options: {e}")
            return None

    def _calculate_gamma_features(self, options_data: Dict) -> Dict[str, float]:
        """Calculate gamma exposure metrics"""
        features = {}

        spot = options_data['spot_price']
        calls = options_data['calls']
        puts = options_data['puts']

        # Calculate total gamma exposure
        # Simplified gamma calculation (real gamma requires Black-Scholes)
        # Using open interest as proxy for exposure

        call_gamma_proxy = 0
        put_gamma_proxy = 0

        for call in calls:
            strike = call.get('strike', 0)
            oi = call.get('openInterest', 0)

            if strike > 0:
                # Gamma peaks at-the-money
                moneyness = abs(spot - strike) / spot
                gamma_factor = max(0, 1 - moneyness * 10)  # Simplified
                call_gamma_proxy += oi * gamma_factor

        for put in puts:
            strike = put.get('strike', 0)
            oi = put.get('openInterest', 0)

            if strike > 0:
                moneyness = abs(spot - strike) / spot
                gamma_factor = max(0, 1 - moneyness * 10)
                put_gamma_proxy += oi * gamma_factor

        # Net gamma (calls are positive, puts are negative for dealers)
        net_gamma = call_gamma_proxy - put_gamma_proxy

        features['dia_net_gamma'] = net_gamma
        features['dia_call_gamma'] = call_gamma_proxy
        features['dia_put_gamma'] = put_gamma_proxy
        features['dia_gamma_ratio'] = call_gamma_proxy / (put_gamma_proxy + 1e-10)

        # Normalize to -1 to +1
        max_gamma = max(abs(net_gamma), 1e6)
        features['dia_gamma_normalized'] = net_gamma / max_gamma

        # High positive gamma = market makers sell volatility = bullish calm
        # Negative gamma = dealers buy volatility = bearish/choppy
        features['dia_gamma_bullish'] = 1 if net_gamma > 0 else 0

        return features

    def _calculate_delta_features(self, options_data: Dict) -> Dict[str, float]:
        """Calculate delta exposure metrics"""
        features = {}

        spot = options_data['spot_price']
        calls = options_data['calls']
        puts = options_data['puts']

        # Calculate put/call ratio (sentiment indicator)
        total_call_oi = sum(c.get('openInterest', 0) for c in calls)
        total_put_oi = sum(p.get('openInterest', 0) for p in puts)

        put_call_ratio = total_put_oi / (total_call_oi + 1e-10)

        features['dia_put_call_ratio'] = put_call_ratio
        features['dia_put_call_bearish'] = 1 if put_call_ratio > 1.0 else 0

        # High put/call ratio (>1.0) = bearish
        # Low put/call ratio (<0.7) = bullish
        if put_call_ratio > 1.2:
            features['dia_pc_sentiment'] = -1.0  # Very bearish
        elif put_call_ratio > 1.0:
            features['dia_pc_sentiment'] = -0.5  # Bearish
        elif put_call_ratio > 0.7:
            features['dia_pc_sentiment'] = 0.0  # Neutral
        else:
            features['dia_pc_sentiment'] = 0.5  # Bullish

        # Calculate implied volatility skew
        # OTM puts should have higher IV than OTM calls in normal markets
        call_ivs = [c.get('impliedVolatility', 0) for c in calls if c.get('impliedVolatility')]
        put_ivs = [p.get('impliedVolatility', 0) for p in puts if p.get('impliedVolatility')]

        if call_ivs and put_ivs:
            avg_call_iv = np.mean(call_ivs)
            avg_put_iv = np.mean(put_ivs)

            iv_skew = avg_put_iv - avg_call_iv
            features['dia_iv_skew'] = iv_skew

            # Positive skew (puts > calls) = normal/bearish
            # Negative skew (calls > puts) = euphoria/warning
            features['dia_skew_warning'] = 1 if iv_skew < 0 else 0
        else:
            features['dia_iv_skew'] = 0
            features['dia_skew_warning'] = 0

        # Max pain calculation (simplified)
        # Strike where most options expire worthless
        strikes_with_oi = {}

        for call in calls:
            strike = call.get('strike', 0)
            oi = call.get('openInterest', 0)
            if strike not in strikes_with_oi:
                strikes_with_oi[strike] = 0
            strikes_with_oi[strike] += oi

        for put in puts:
            strike = put.get('strike', 0)
            oi = put.get('openInterest', 0)
            if strike not in strikes_with_oi:
                strikes_with_oi[strike] = 0
            strikes_with_oi[strike] += oi

        if strikes_with_oi:
            max_pain_strike = max(strikes_with_oi, key=strikes_with_oi.get)
            features['dia_max_pain'] = max_pain_strike
            features['dia_vs_max_pain'] = (spot - max_pain_strike) / spot

            # If price far from max pain, market may gravitate toward it
            features['dia_max_pain_pull'] = abs(features['dia_vs_max_pain'])
        else:
            features['dia_max_pain'] = spot
            features['dia_vs_max_pain'] = 0
            features['dia_max_pain_pull'] = 0

        return features

    def _default_features(self) -> Dict[str, float]:
        """Return default neutral features if data unavailable"""
        return {
            'dia_net_gamma': 0,
            'dia_call_gamma': 0,
            'dia_put_gamma': 0,
            'dia_gamma_ratio': 1.0,
            'dia_gamma_normalized': 0,
            'dia_gamma_bullish': 0,
            'dia_put_call_ratio': 1.0,
            'dia_put_call_bearish': 0,
            'dia_pc_sentiment': 0,
            'dia_iv_skew': 0,
            'dia_skew_warning': 0,
            'dia_max_pain': 0,
            'dia_vs_max_pain': 0,
            'dia_max_pain_pull': 0
        }

    def get_options_summary(self) -> str:
        """Get human-readable options summary"""
        features = self.get_dia_gamma_exposure()

        summary = "DIA OPTIONS ANALYSIS\n"
        summary += "=" * 50 + "\n"

        if features['dia_gamma_bullish']:
            summary += "Gamma: POSITIVE (Dealers selling vol = Bullish calm)\n"
        else:
            summary += "Gamma: NEGATIVE (Dealers buying vol = Choppy)\n"

        if features['dia_put_call_bearish']:
            summary += f"Put/Call: {features['dia_put_call_ratio']:.2f} (BEARISH)\n"
        else:
            summary += f"Put/Call: {features['dia_put_call_ratio']:.2f} (Bullish)\n"

        if features['dia_skew_warning']:
            summary += "IV Skew: WARNING (Calls > Puts = Euphoria)\n"
        else:
            summary += "IV Skew: Normal\n"

        summary += "=" * 50

        return summary
