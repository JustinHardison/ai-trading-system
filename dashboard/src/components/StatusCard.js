import React from 'react';

function StatusCard({ title, value, subtitle, status = 'info' }) {
  const statusColors = {
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6'
  };

  return (
    <div className="status-card" style={{ borderLeft: `4px solid ${statusColors[status]}` }}>
      <div className="card-header">
        <h3>{title}</h3>
      </div>
      <div className="card-body">
        <div className="card-value" style={{ color: statusColors[status] }}>
          {value}
        </div>
        {subtitle && <div className="card-subtitle">{subtitle}</div>}
      </div>
    </div>
  );
}

export default StatusCard;
