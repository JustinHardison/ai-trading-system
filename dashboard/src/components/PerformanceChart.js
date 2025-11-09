import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

function PerformanceChart({ status }) {
  // Real-time data - shows current profit only (historical data would come from API)
  const currentProfit = status.current_profit_pct || 0;
  const data = [
    { time: 'Start', profit: 0 },
    { time: 'Current', profit: currentProfit },
  ];

  return (
    <div className="performance-chart">
      <h2>Performance Chart</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="time" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" />
          <Tooltip
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
            labelStyle={{ color: '#e5e7eb' }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="profit"
            stroke="#10b981"
            strokeWidth={2}
            name="Profit %"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PerformanceChart;
