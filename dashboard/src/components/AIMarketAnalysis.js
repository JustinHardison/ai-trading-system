import React from 'react';
import './AIMarketAnalysis.css';

const AIMarketAnalysis = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="ai-analysis-card">
        <div className="card-header">
          <h3>AI Market Analysis</h3>
          <span className="analysis-badge waiting">Awaiting Data</span>
        </div>
        <div className="analysis-empty">
          <p>No analysis available yet. Start the trading system to see AI insights.</p>
        </div>
      </div>
    );
  }

  const getConfidenceBadge = (confidence) => {
    if (confidence >= 90) return 'very-high';
    if (confidence >= 80) return 'high';
    if (confidence >= 70) return 'medium';
    return 'low';
  };

  const getSentimentIcon = (sentiment) => {
    if (sentiment === 'BULLISH') return '📈';
    if (sentiment === 'BEARISH') return '📉';
    return '➡️';
  };

  return (
    <div className="ai-analysis-card">
      <div className="card-header">
        <h3>AI Market Analysis</h3>
        <span className={`analysis-badge ${analysis.status || 'active'}`}>
          {analysis.status === 'scanning' ? '🔍 Scanning' : '✓ Active'}
        </span>
      </div>

      <div className="analysis-content">
        {/* Market Regime */}
        {analysis.market_regime && (
          <div className="analysis-section">
            <div className="section-header">
              <span className="section-icon">🌍</span>
              <h4>Market Regime</h4>
            </div>
            <div className="regime-info">
              <div className="regime-main">
                <span className={`regime-badge ${analysis.market_regime.type?.toLowerCase()}`}>
                  {analysis.market_regime.type || 'Unknown'}
                </span>
                <span className="regime-strength">
                  Confidence: {analysis.market_regime.confidence?.toFixed(0) || 0}%
                </span>
              </div>
              {analysis.market_regime.description && (
                <p className="regime-description">{analysis.market_regime.description}</p>
              )}
            </div>
          </div>
        )}

        {/* Current Signals */}
        {analysis.signals && analysis.signals.length > 0 && (
          <div className="analysis-section">
            <div className="section-header">
              <span className="section-icon">⚡</span>
              <h4>Active Signals ({analysis.signals.length})</h4>
            </div>
            <div className="signals-list">
              {analysis.signals.slice(0, 5).map((signal, idx) => (
                <div key={idx} className="signal-item">
                  <div className="signal-header">
                    <span className="signal-symbol">{signal.symbol}</span>
                    <span className={`signal-direction ${signal.direction?.toLowerCase()}`}>
                      {signal.direction === 'BUY' ? '↑' : '↓'} {signal.direction}
                    </span>
                    <span className={`confidence-badge ${getConfidenceBadge(signal.confidence)}`}>
                      {signal.confidence?.toFixed(0)}%
                    </span>
                  </div>
                  {signal.reason && (
                    <p className="signal-reason">{signal.reason}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ML Model Insights */}
        {analysis.ml_insights && (
          <div className="analysis-section">
            <div className="section-header">
              <span className="section-icon">🤖</span>
              <h4>ML Model Insights</h4>
            </div>
            <div className="insights-grid">
              {analysis.ml_insights.model_accuracy && (
                <div className="insight-item">
                  <span className="insight-label">Model Accuracy</span>
                  <span className="insight-value">{analysis.ml_insights.model_accuracy}%</span>
                </div>
              )}
              {analysis.ml_insights.symbols_scanned && (
                <div className="insight-item">
                  <span className="insight-label">Symbols Scanned</span>
                  <span className="insight-value">{analysis.ml_insights.symbols_scanned}</span>
                </div>
              )}
              {analysis.ml_insights.scan_duration && (
                <div className="insight-item">
                  <span className="insight-label">Scan Duration</span>
                  <span className="insight-value">{analysis.ml_insights.scan_duration}s</span>
                </div>
              )}
              {analysis.ml_insights.next_scan && (
                <div className="insight-item">
                  <span className="insight-label">Next Scan</span>
                  <span className="insight-value">{analysis.ml_insights.next_scan}s</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Market Sentiment */}
        {analysis.sentiment && (
          <div className="analysis-section">
            <div className="section-header">
              <span className="section-icon">{getSentimentIcon(analysis.sentiment.overall)}</span>
              <h4>Market Sentiment</h4>
            </div>
            <div className="sentiment-info">
              <div className="sentiment-overall">
                <span className={`sentiment-badge ${analysis.sentiment.overall?.toLowerCase()}`}>
                  {analysis.sentiment.overall}
                </span>
                {analysis.sentiment.score !== undefined && (
                  <span className="sentiment-score">
                    Score: {analysis.sentiment.score > 0 ? '+' : ''}{analysis.sentiment.score.toFixed(1)}
                  </span>
                )}
              </div>
              {analysis.sentiment.summary && (
                <p className="sentiment-summary">{analysis.sentiment.summary}</p>
              )}
            </div>
          </div>
        )}

        {/* Risk Assessment */}
        {analysis.risk_assessment && (
          <div className="analysis-section">
            <div className="section-header">
              <span className="section-icon">⚠️</span>
              <h4>Risk Assessment</h4>
            </div>
            <div className="risk-info">
              <div className="risk-level">
                <span className={`risk-badge ${analysis.risk_assessment.level?.toLowerCase()}`}>
                  {analysis.risk_assessment.level || 'Unknown'}
                </span>
              </div>
              {analysis.risk_assessment.factors && analysis.risk_assessment.factors.length > 0 && (
                <ul className="risk-factors">
                  {analysis.risk_assessment.factors.map((factor, idx) => (
                    <li key={idx}>{factor}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* AI Reasoning */}
        {analysis.ai_reasoning && (
          <div className="analysis-section">
            <div className="section-header">
              <span className="section-icon">💭</span>
              <h4>AI Reasoning</h4>
            </div>
            <div className="reasoning-text">
              <p>{analysis.ai_reasoning}</p>
            </div>
          </div>
        )}

        {/* Last Updated */}
        <div className="analysis-footer">
          <span className="last-updated">
            Last updated: {analysis.last_updated ? new Date(analysis.last_updated).toLocaleTimeString() : 'Never'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default AIMarketAnalysis;
