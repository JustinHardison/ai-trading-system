import React, { useState, useEffect } from 'react';
import './SymbolAnalysis.css';

const SymbolAnalysis = ({ apiBaseUrl }) => {
  const [symbolsData, setSymbolsData] = useState(null);
  const [filter, setFilter] = useState('all'); // all, opportunities, fast-track
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSymbolAnalysis = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/symbols/analysis`);
        const data = await response.json();

        if (data.error) {
          setError(data.error);
        } else {
          setSymbolsData(data);
          setError(null);
        }
      } catch (err) {
        setError(`Failed to fetch symbol analysis: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchSymbolAnalysis();

    // Poll every 5 seconds
    const interval = setInterval(fetchSymbolAnalysis, 5000);

    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  const getDecisionBadgeClass = (decision) => {
    switch (decision) {
      case 'FAST-TRACK':
        return 'badge-fast-track';
      case 'TRADE':
        return 'badge-trade';
      case 'MONITOR':
        return 'badge-monitor';
      case 'NO_SIGNAL':
        return 'badge-no-signal';
      default:
        return 'badge-error';
    }
  };

  const getTierBadgeClass = (tier) => {
    switch (tier) {
      case 'HIGH_PRIORITY':
        return 'tier-high';
      case 'MEDIUM_PRIORITY':
        return 'tier-medium';
      case 'LOW_PRIORITY':
        return 'tier-low';
      default:
        return 'tier-unknown';
    }
  };

  const getFilteredSymbols = () => {
    if (!symbolsData || !symbolsData.symbols) return [];

    switch (filter) {
      case 'opportunities':
        return symbolsData.symbols.filter(s => s.has_opportunity);
      case 'fast-track':
        return symbolsData.symbols.filter(s => s.fast_track_eligible);
      default:
        return symbolsData.symbols;
    }
  };

  if (loading) {
    return (
      <div className="symbol-analysis">
        <h3>Symbol Analysis</h3>
        <div className="loading">Loading symbol analysis...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="symbol-analysis">
        <h3>Symbol Analysis</h3>
        <div className="error">{error}</div>
      </div>
    );
  }

  const filteredSymbols = getFilteredSymbols();

  return (
    <div className="symbol-analysis">
      <div className="symbol-analysis-header">
        <h3>AI Symbol Analysis</h3>
        <div className="symbol-stats">
          <span className="stat">
            Total: <strong>{symbolsData?.total_symbols || 0}</strong>
          </span>
          <span className="stat stat-opportunities">
            Opportunities: <strong>{symbolsData?.with_opportunities || 0}</strong>
          </span>
          <span className="stat stat-fast-track">
            Fast-Track Ready: <strong>{symbolsData?.fast_track_ready || 0}</strong>
          </span>
        </div>
      </div>

      <div className="symbol-filters">
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All Symbols
        </button>
        <button
          className={`filter-btn ${filter === 'opportunities' ? 'active' : ''}`}
          onClick={() => setFilter('opportunities')}
        >
          With Opportunities
        </button>
        <button
          className={`filter-btn ${filter === 'fast-track' ? 'active' : ''}`}
          onClick={() => setFilter('fast-track')}
        >
          Fast-Track Only
        </button>
      </div>

      <div className="symbols-grid">
        {filteredSymbols.length === 0 ? (
          <div className="no-symbols">
            No symbols match the selected filter.
          </div>
        ) : (
          filteredSymbols.map((symbol) => (
            <div key={symbol.symbol} className="symbol-card">
              <div className="symbol-header">
                <span className="symbol-name">{symbol.symbol}</span>
                <span className={`tier-badge ${getTierBadgeClass(symbol.tier)}`}>
                  {symbol.tier.replace('_PRIORITY', '')}
                </span>
              </div>

              <div className="symbol-decision">
                <span className={`decision-badge ${getDecisionBadgeClass(symbol.decision)}`}>
                  {symbol.decision}
                </span>
                {symbol.fast_track_eligible && (
                  <span className="fast-track-icon" title="Fast-Track Eligible">
                    ⚡
                  </span>
                )}
              </div>

              <div className="symbol-details">
                <div className="detail-row">
                  <span className="detail-label">Scan Interval:</span>
                  <span className="detail-value">{symbol.scan_interval}s</span>
                </div>

                {symbol.has_opportunity && (
                  <>
                    <div className="detail-row">
                      <span className="detail-label">Confidence:</span>
                      <span className="detail-value confidence">
                        {symbol.confidence?.toFixed(1)}%
                      </span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Direction:</span>
                      <span className={`detail-value direction ${symbol.direction?.toLowerCase()}`}>
                        {symbol.direction}
                      </span>
                    </div>
                  </>
                )}

                <div className="decision-reason">
                  {symbol.decision_reason}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="symbol-analysis-footer">
        Last updated: {new Date(symbolsData?.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
};

export default SymbolAnalysis;
