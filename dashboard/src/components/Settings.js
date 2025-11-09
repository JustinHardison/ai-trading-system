import React, { useState } from 'react';

function Settings({ settings, onUpdate, onClose, disabled }) {
  const [formData, setFormData] = useState(settings);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked :
              type === 'number' ? parseFloat(value) : value
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onUpdate(formData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="settings-form">
            <div className="form-group">
              <label>Phase</label>
              <select
                name="phase"
                value={formData.phase}
                onChange={handleChange}
                disabled={disabled}
              >
                <option value={1}>Phase 1 (10% target)</option>
                <option value={2}>Phase 2 (5% target)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Starting Balance ($)</label>
              <input
                type="number"
                name="starting_balance"
                value={formData.starting_balance}
                onChange={handleChange}
                disabled={disabled}
                step="100"
                min="1000"
              />
            </div>

            <div className="form-group">
              <label>Scan Interval (seconds)</label>
              <input
                type="number"
                name="scan_interval"
                value={formData.scan_interval}
                onChange={handleChange}
                disabled={disabled}
                step="30"
                min="60"
              />
              <small>Recommended: 180 seconds (3 minutes)</small>
            </div>

            <div className="form-group">
              <label>Minimum Confidence (%)</label>
              <input
                type="number"
                name="min_confidence"
                value={formData.min_confidence}
                onChange={handleChange}
                disabled={disabled}
                step="5"
                min="60"
                max="95"
              />
              <small>Higher = fewer but more accurate trades</small>
            </div>

            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="auto_stop_at_target"
                  checked={formData.auto_stop_at_target}
                  onChange={handleChange}
                  disabled={disabled}
                />
                Auto-stop when target reached
              </label>
            </div>

            <div className="form-group">
              <label>Max Profit Before Stop (%)</label>
              <input
                type="number"
                name="max_profit_before_stop"
                value={formData.max_profit_before_stop}
                onChange={handleChange}
                disabled={disabled}
                step="1"
                min="10"
                max="25"
              />
              <small>System stops trading when profit exceeds this</small>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={disabled}
            >
              {disabled ? 'Stop trading to change settings' : 'Save Settings'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default Settings;
