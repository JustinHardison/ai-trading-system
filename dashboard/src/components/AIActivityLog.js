import React from 'react';
import './AIActivityLog.css';

function AIActivityLog({ activities }) {
  if (!activities || activities.length === 0) {
    return (
      <div className="ai-activity-log">
        <h3>🤖 AI Activity Log</h3>
        <p className="no-activities">Waiting for AI activity...</p>
      </div>
    );
  }

  // Get icon based on activity type
  const getActivityIcon = (activity) => {
    const text = activity.toLowerCase();
    if (text.includes('ml') || text.includes('machine learning')) return '🧠';
    if (text.includes('llm') || text.includes('groq') || text.includes('validating')) return '🤖';
    if (text.includes('scanning')) return '🔍';
    if (text.includes('executing') || text.includes('trade')) return '💰';
    if (text.includes('position sizing')) return '📊';
    if (text.includes('confidence')) return '📈';
    if (text.includes('waiting') || text.includes('no')) return '⏳';
    if (text.includes('error') || text.includes('failed')) return '❌';
    if (text.includes('success') || text.includes('completed')) return '✅';
    return '🔵';
  };

  // Get activity class based on type
  const getActivityClass = (activity) => {
    const text = activity.toLowerCase();
    if (text.includes('error') || text.includes('failed')) return 'activity-error';
    if (text.includes('ml') && text.includes('predictions')) return 'activity-ml';
    if (text.includes('llm') || text.includes('validating')) return 'activity-llm';
    if (text.includes('executing') || text.includes('trade')) return 'activity-trade';
    return 'activity-info';
  };

  return (
    <div className="ai-activity-log">
      <h3>🤖 AI Decision Log (Real-Time)</h3>
      <div className="activity-list">
        {activities.slice().reverse().map((activity, index) => (
          <div key={index} className={`activity-item ${getActivityClass(activity.message)}`}>
            <span className="activity-icon">{getActivityIcon(activity.message)}</span>
            <span className="activity-time">{new Date(activity.timestamp).toLocaleTimeString()}</span>
            <span className="activity-message">{activity.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AIActivityLog;
