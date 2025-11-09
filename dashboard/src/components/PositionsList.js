import React from 'react';

function PositionsList({ positions }) {
  if (!positions || positions.length === 0) {
    return (
      <div className="positions-container">
        <h2>Open Positions</h2>
        <div className="empty-state">
          <p>No open positions</p>
        </div>
      </div>
    );
  }

  return (
    <div className="positions-container">
      <h2>Open Positions ({positions.length})</h2>
      <div className="positions-table">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Type</th>
              <th>Size</th>
              <th>Entry</th>
              <th>Current</th>
              <th>P&L</th>
              <th>P&L%</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position, index) => {
              const isProfit = position.profit >= 0;
              return (
                <tr key={index}>
                  <td className="symbol">{position.symbol}</td>
                  <td>
                    <span className={`badge ${position.type === 'BUY' ? 'badge-buy' : 'badge-sell'}`}>
                      {position.type}
                    </span>
                  </td>
                  <td>{position.volume}</td>
                  <td>{position.open_price}</td>
                  <td>{position.current_price}</td>
                  <td className={isProfit ? 'profit' : 'loss'}>
                    ${position.profit.toFixed(2)}
                  </td>
                  <td className={isProfit ? 'profit' : 'loss'}>
                    {position.profit_pct ? position.profit_pct.toFixed(2) : '0.00'}%
                  </td>
                  <td>{position.open_time ? new Date(position.open_time).toLocaleTimeString() : 'N/A'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PositionsList;
