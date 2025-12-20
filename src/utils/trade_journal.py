"""
Persistent Trade Journal

Logs all closed trades with full context for post-analysis.
This allows us to analyze what went wrong with losing trades
even after the API restarts or market closes.

Data is stored in:
- data/trade_journal.csv (all trades)
- data/trade_journal.json (detailed context per trade)
"""

import os
import json
import csv
import logging
from datetime import datetime
from typing import Dict, List, Optional
import threading

logger = logging.getLogger(__name__)

# File paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '../../data')
JOURNAL_CSV = os.path.join(DATA_DIR, 'trade_journal.csv')
JOURNAL_JSON = os.path.join(DATA_DIR, 'trade_journal_details.json')

# Thread lock for file operations
_file_lock = threading.Lock()

# Track which tickets we've already logged (to avoid duplicates)
_logged_tickets = set()


def _ensure_data_dir():
    """Ensure data directory exists"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_logged_tickets():
    """Load previously logged ticket numbers to avoid duplicates"""
    global _logged_tickets
    if os.path.exists(JOURNAL_CSV):
        try:
            with open(JOURNAL_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'ticket' in row:
                        _logged_tickets.add(int(row['ticket']))
        except Exception as e:
            logger.warning(f"Could not load logged tickets: {e}")


def _init_csv():
    """Initialize CSV file with headers if it doesn't exist"""
    _ensure_data_dir()
    if not os.path.exists(JOURNAL_CSV):
        headers = [
            'timestamp', 'ticket', 'symbol', 'direction', 'lots',
            'entry_price', 'exit_price', 'gross_pnl', 'net_pnl',
            'swap', 'commission', 'duration_minutes', 'setup_type',
            'entry_reason', 'exit_reason', 'thesis_quality', 'ml_confidence',
            'htf_alignment', 'session', 'is_friday', 'result'
        ]
        with open(JOURNAL_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        logger.info(f"📓 Created trade journal: {JOURNAL_CSV}")


def log_closed_trade(
    ticket: int,
    symbol: str,
    direction: str,  # 'BUY' or 'SELL'
    lots: float,
    entry_price: float,
    exit_price: float,
    gross_pnl: float,
    net_pnl: float,
    swap: float = 0,
    commission: float = 0,
    open_time: int = 0,
    close_time: int = 0,
    setup_type: str = 'UNKNOWN',
    entry_reason: str = '',
    exit_reason: str = '',
    thesis_quality: float = 0,
    ml_confidence: float = 0,
    htf_alignment: str = '',
    session: str = '',
    is_friday: bool = False,
    extra_context: Dict = None
):
    """
    Log a closed trade to the persistent journal.
    
    This should be called whenever we detect a trade has closed.
    """
    global _logged_tickets
    
    # Skip if already logged
    if ticket in _logged_tickets:
        return False
    
    with _file_lock:
        try:
            _init_csv()
            
            # Calculate duration
            duration_minutes = 0
            if open_time and close_time and close_time > open_time:
                duration_minutes = (close_time - open_time) / 60
            
            # Determine result
            result = 'WIN' if net_pnl > 0 else ('LOSS' if net_pnl < 0 else 'SCRATCH')
            
            # Current timestamp
            timestamp = datetime.now().isoformat()
            
            # Write to CSV
            row = [
                timestamp, ticket, symbol, direction, lots,
                entry_price, exit_price, gross_pnl, net_pnl,
                swap, commission, round(duration_minutes, 1), setup_type,
                entry_reason, exit_reason, round(thesis_quality, 2), round(ml_confidence, 2),
                htf_alignment, session, is_friday, result
            ]
            
            with open(JOURNAL_CSV, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            # Write detailed context to JSON
            if extra_context:
                _save_trade_details(ticket, {
                    'ticket': ticket,
                    'symbol': symbol,
                    'direction': direction,
                    'lots': lots,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'gross_pnl': gross_pnl,
                    'net_pnl': net_pnl,
                    'swap': swap,
                    'commission': commission,
                    'duration_minutes': duration_minutes,
                    'setup_type': setup_type,
                    'entry_reason': entry_reason,
                    'exit_reason': exit_reason,
                    'thesis_quality': thesis_quality,
                    'ml_confidence': ml_confidence,
                    'htf_alignment': htf_alignment,
                    'session': session,
                    'is_friday': is_friday,
                    'result': result,
                    'timestamp': timestamp,
                    'context': extra_context
                })
            
            _logged_tickets.add(ticket)
            
            # Log summary
            emoji = '✅' if result == 'WIN' else ('❌' if result == 'LOSS' else '⏸️')
            logger.info(f"📓 TRADE JOURNAL: {emoji} #{ticket} {symbol} {direction} {lots}L → ${net_pnl:.2f} ({result})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log trade to journal: {e}")
            return False


def _save_trade_details(ticket: int, details: Dict):
    """Save detailed trade context to JSON file"""
    try:
        _ensure_data_dir()
        
        # Load existing details
        all_details = {}
        if os.path.exists(JOURNAL_JSON):
            with open(JOURNAL_JSON, 'r') as f:
                all_details = json.load(f)
        
        # Add new trade
        all_details[str(ticket)] = details
        
        # Keep only last 500 trades to prevent file from growing too large
        if len(all_details) > 500:
            # Sort by ticket number and keep newest
            sorted_tickets = sorted(all_details.keys(), key=int, reverse=True)[:500]
            all_details = {k: all_details[k] for k in sorted_tickets}
        
        # Save
        with open(JOURNAL_JSON, 'w') as f:
            json.dump(all_details, f, indent=2)
            
    except Exception as e:
        logger.warning(f"Could not save trade details: {e}")


def get_recent_trades(days: int = 7, symbol: str = None) -> List[Dict]:
    """
    Get recent trades from the journal.
    
    Args:
        days: Number of days to look back
        symbol: Optional symbol filter
        
    Returns:
        List of trade dictionaries
    """
    trades = []
    
    if not os.path.exists(JOURNAL_CSV):
        return trades
    
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        with open(JOURNAL_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    trade_time = datetime.fromisoformat(row['timestamp'])
                    if trade_time >= cutoff:
                        if symbol is None or symbol.lower() in row['symbol'].lower():
                            trades.append(row)
                except:
                    continue
                    
    except Exception as e:
        logger.warning(f"Could not read trade journal: {e}")
    
    return trades


def get_trade_details(ticket: int) -> Optional[Dict]:
    """Get detailed context for a specific trade"""
    if not os.path.exists(JOURNAL_JSON):
        return None
    
    try:
        with open(JOURNAL_JSON, 'r') as f:
            all_details = json.load(f)
            return all_details.get(str(ticket))
    except:
        return None


def get_losing_trades(days: int = 7) -> List[Dict]:
    """Get all losing trades from the last N days"""
    trades = get_recent_trades(days)
    return [t for t in trades if t.get('result') == 'LOSS']


def get_trade_stats(days: int = 7) -> Dict:
    """Get summary statistics for recent trades"""
    trades = get_recent_trades(days)
    
    if not trades:
        return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'net_pnl': 0}
    
    wins = [t for t in trades if t.get('result') == 'WIN']
    losses = [t for t in trades if t.get('result') == 'LOSS']
    
    total_pnl = sum(float(t.get('net_pnl', 0)) for t in trades)
    
    return {
        'total': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'net_pnl': total_pnl,
        'avg_win': sum(float(t.get('net_pnl', 0)) for t in wins) / len(wins) if wins else 0,
        'avg_loss': sum(float(t.get('net_pnl', 0)) for t in losses) / len(losses) if losses else 0
    }


# Initialize on import
_load_logged_tickets()
