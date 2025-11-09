import React from 'react';

function ControlPanel({ enabled, onStart, onStop, onSettings }) {
  return (
    <div className="control-panel">
      <div className="control-buttons">
        <button
          className="btn btn-start"
          onClick={onStart}
          disabled={enabled}
        >
          {enabled ? '✓ Trading Active' : '▶ Start Trading'}
        </button>

        <button
          className="btn btn-stop"
          onClick={onStop}
          disabled={!enabled}
        >
          ⏹ Stop Trading
        </button>

        <button
          className="btn btn-settings"
          onClick={onSettings}
          disabled={enabled}
        >
          ⚙ Settings
        </button>
      </div>

      <div className="control-status">
        <div className={`status-badge ${enabled ? 'active' : 'inactive'}`}>
          {enabled ? '🟢 ACTIVE' : '🔴 INACTIVE'}
        </div>
      </div>
    </div>
  );
}

export default ControlPanel;
