import React, { useState, useEffect } from 'react';
import './App.css';
import StatusCard from './components/StatusCard';
import ControlPanel from './components/ControlPanel';
import PositionsList from './components/PositionsList';
import PerformanceChart from './components/PerformanceChart';
import Settings from './components/Settings';
import AIMarketAnalysis from './components/AIMarketAnalysis';
import SymbolAnalysis from './components/SymbolAnalysis';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

function App() {
  const [status, setStatus] = useState({
    enabled: false,
    mt5_connected: false,
    current_activity: 'Idle',
    balance: 0.0,
    equity: 0.0,
    current_profit_pct: 0.0,
    target_profit_pct: 10.0,
    open_positions: [],
    pacing_status: 'INITIALIZING',
    confidence_threshold: 75.0,
    daily_profit: 0.0,
    total_trades: 0,
    win_rate: 0.0,
    last_trade: null,
    news_filter_active: false,
    consistency_safe: true,
    circuit_breaker_ok: true,
    last_updated: new Date().toISOString()
  });

  const [aiAnalysis, setAiAnalysis] = useState(null);

  // Fetch AI analysis periodically
  useEffect(() => {
    const fetchAiAnalysis = async () => {
      try {
        const response = await fetch(`${API_URL}/api/analysis`);
        const data = await response.json();
        setAiAnalysis(data);
      } catch (error) {
        console.error('Error fetching AI analysis:', error);
      }
    };

    // Initial fetch
    fetchAiAnalysis();

    // Poll every 10 seconds
    const interval = setInterval(fetchAiAnalysis, 10000);

    return () => clearInterval(interval);
  }, []);

  const [settings, setSettings] = useState({
    phase: 1,
    starting_balance: 10000.0,
    scan_interval: 180,
    min_confidence: 75.0,
    auto_stop_at_target: true,
    max_profit_before_stop: 15.0
  });

  const [connected, setConnected] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // WebSocket connection
  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws`);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('WebSocket message:', data);

      if (data.type === 'initial_state') {
        setStatus(data.data.status);
        setSettings(data.data.settings);
      } else if (data.type === 'status_update') {
        setStatus(data.data);
      } else if (data.type === 'settings_updated') {
        setSettings(data.data);
      } else if (data.type === 'trader_started') {
        setStatus(prev => ({ ...prev, enabled: true }));
      } else if (data.type === 'trader_stopped') {
        setStatus(prev => ({ ...prev, enabled: false }));
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

  const handleStart = async () => {
    try {
      const response = await fetch(`${API_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start' })
      });

      if (response.ok) {
        console.log('Trader started');
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error starting trader:', error);
      alert('Failed to start trader. Is the API server running?');
    }
  };

  const handleStop = async () => {
    try {
      const response = await fetch(`${API_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'stop' })
      });

      if (response.ok) {
        console.log('Trader stopped');
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error stopping trader:', error);
      alert('Failed to stop trader');
    }
  };

  const handleSettingsUpdate = async (newSettings) => {
    try {
      const response = await fetch(`${API_URL}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings)
      });

      if (response.ok) {
        const data = await response.json();
        setSettings(data.settings);
        setShowSettings(false);
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error updating settings:', error);
      alert('Failed to update settings');
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-content">
          <h1>🤖 AI Trading System v2.0</h1>
          <div className="connection-status">
            <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></span>
            <span>{connected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </header>

      <div className="dashboard-container">
        {/* Control Panel */}
        <ControlPanel
          enabled={status.enabled}
          onStart={handleStart}
          onStop={handleStop}
          onSettings={() => setShowSettings(true)}
        />

        {/* AI Status Banner */}
        <div className="ai-status-banner">
          <div className="ai-status-icon">
            {status.enabled ? '🤖' : '⏸️'}
          </div>
          <div className="ai-status-content">
            <div className="ai-status-title">
              {status.enabled ? 'AI System Active' : 'AI System Paused'}
            </div>
            <div className="ai-status-message">
              {status.current_activity || 'Idle - Waiting to start'}
            </div>
          </div>
        </div>

        {/* Status Cards */}
        <div className="status-grid">
          <StatusCard
            title="MT5 Status"
            value={status.mt5_connected ? '✓ Connected' : '✗ Disconnected'}
            subtitle={status.current_activity || 'Idle'}
            status={status.mt5_connected ? 'success' : 'error'}
          />
          <StatusCard
            title="Account Balance"
            value={`$${(status.balance || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}
            subtitle={`Equity: $${(status.equity || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}
            status="info"
          />
          <StatusCard
            title="Current Profit"
            value={`${status.current_profit_pct.toFixed(2)}%`}
            subtitle={`Target: ${status.target_profit_pct}%`}
            status={status.current_profit_pct >= status.target_profit_pct ? 'success' : 'info'}
          />
          <StatusCard
            title="Pacing Status"
            value={status.pacing_status}
            subtitle={`Confidence: ${status.confidence_threshold}%`}
            status={status.pacing_status === 'NORMAL' ? 'success' :
                    status.pacing_status === 'AGGRESSIVE' ? 'warning' : 'info'}
          />
          <StatusCard
            title="Open Positions"
            value={status.open_positions.length}
            subtitle={`Total Trades: ${status.total_trades}`}
            status="info"
          />
          <StatusCard
            title="Win Rate"
            value={`${status.win_rate.toFixed(1)}%`}
            subtitle={`Daily P&L: ${status.daily_profit.toFixed(2)}%`}
            status={status.win_rate >= 75 ? 'success' : 'warning'}
          />
        </div>

        {/* Safety Status */}
        <div className="safety-status">
          <div className={`safety-item ${status.news_filter_active ? 'warning' : 'success'}`}>
            🚫 News Filter: {status.news_filter_active ? 'ACTIVE' : 'Clear'}
          </div>
          <div className={`safety-item ${status.consistency_safe ? 'success' : 'warning'}`}>
            📊 Consistency: {status.consistency_safe ? 'Safe' : 'At Risk'}
          </div>
          <div className={`safety-item ${status.circuit_breaker_ok ? 'success' : 'error'}`}>
            ⚡ Circuit Breaker: {status.circuit_breaker_ok ? 'OK' : 'TRIGGERED'}
          </div>
        </div>

        {/* AI Market Analysis */}
        <AIMarketAnalysis analysis={aiAnalysis} />

        {/* Symbol Analysis */}
        <SymbolAnalysis apiBaseUrl={API_URL} />

        {/* Performance Chart */}
        <PerformanceChart status={status} />

        {/* Open Positions */}
        <PositionsList positions={status.open_positions} />

        {/* Settings Modal */}
        {showSettings && (
          <Settings
            settings={settings}
            onUpdate={handleSettingsUpdate}
            onClose={() => setShowSettings(false)}
            disabled={status.enabled}
          />
        )}

        {/* Footer */}
        <footer className="dashboard-footer">
          <p>Last Updated: {new Date(status.last_updated).toLocaleString()}</p>
          <p>System running on VPS - Independent of local computer</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
