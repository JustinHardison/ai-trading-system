"""
Persistent Trade Journal with AI Decision Context

Logs all trades with FULL AI context at entry and exit:
- Market conditions (trends, momentum, volatility)
- AI reasoning (thesis quality, ML confidence, probabilities)
- EV calculations (hold vs exit vs scale)
- Timeframe alignment (M15, M30, H1, H4, D1)

This allows post-analysis of what the AI was thinking
when it made entry/exit decisions.

Data is stored in:
- data/trade_journal.csv (summary of all trades)
- data/trade_journal_details.json (full AI context per trade)
- data/trade_entries.json (entry context by ticket)
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
ENTRY_CONTEXT_JSON = os.path.join(DATA_DIR, 'trade_entries.json')

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


# ═══════════════════════════════════════════════════════════════════
# ENTRY CONTEXT LOGGING
# Captures AI decision context at the moment of entry
# ═══════════════════════════════════════════════════════════════════

def log_entry_context(
    ticket: int,
    symbol: str,
    direction: str,
    lots: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    # AI Decision Context
    ml_confidence: float = 0,
    ml_direction: str = '',
    market_score: float = 0,
    setup_type: str = '',
    thesis_quality: float = 0,
    # Timeframe Trends
    m15_trend: float = 0.5,
    m30_trend: float = 0.5,
    h1_trend: float = 0.5,
    h4_trend: float = 0.5,
    d1_trend: float = 0.5,
    # Market Conditions
    regime: str = '',
    volatility: float = 0,
    atr: float = 0,
    session: str = '',
    # Entry Reasoning
    entry_reason: str = '',
    extra_context: Dict = None
):
    """
    Log AI decision context at the moment of entry.
    This is called when a trade is APPROVED, before it's sent to MT5.
    """
    with _file_lock:
        try:
            _ensure_data_dir()
            
            entry_data = {
                'ticket': ticket,
                'symbol': symbol,
                'direction': direction,
                'lots': lots,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'entry_time': datetime.now().isoformat(),
                # AI Decision
                'ml_confidence': ml_confidence,
                'ml_direction': ml_direction,
                'market_score': market_score,
                'setup_type': setup_type,
                'thesis_quality': thesis_quality,
                # Timeframes
                'trends': {
                    'm15': m15_trend,
                    'm30': m30_trend,
                    'h1': h1_trend,
                    'h4': h4_trend,
                    'd1': d1_trend
                },
                # Market
                'regime': regime,
                'volatility': volatility,
                'atr': atr,
                'session': session,
                'entry_reason': entry_reason,
                'extra': extra_context or {}
            }
            
            # Load existing entries
            entries = {}
            if os.path.exists(ENTRY_CONTEXT_JSON):
                try:
                    with open(ENTRY_CONTEXT_JSON, 'r') as f:
                        entries = json.load(f)
                except:
                    entries = {}
            
            # Add new entry
            entries[str(ticket)] = entry_data
            
            # Keep only last 500 entries
            if len(entries) > 500:
                sorted_tickets = sorted(entries.keys(), key=int, reverse=True)[:500]
                entries = {k: entries[k] for k in sorted_tickets}
            
            # Save
            with open(ENTRY_CONTEXT_JSON, 'w') as f:
                json.dump(entries, f, indent=2)
            
            logger.info(f"📓 ENTRY LOGGED: #{ticket} {symbol} {direction} {lots}L @ {entry_price}")
            logger.info(f"   ML: {ml_confidence:.1f}% {ml_direction} | Score: {market_score} | Setup: {setup_type}")
            logger.info(f"   Trends: M15={m15_trend:.2f} M30={m30_trend:.2f} H1={h1_trend:.2f} H4={h4_trend:.2f} D1={d1_trend:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log entry context: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════
# EXIT CONTEXT LOGGING  
# Captures AI decision context at the moment of exit
# ═══════════════════════════════════════════════════════════════════

def log_exit_context(
    ticket: int,
    symbol: str,
    action: str,  # CLOSE, SCALE_OUT, etc.
    exit_price: float,
    profit_dollars: float,
    profit_pct: float,
    # AI Decision Context
    ev_hold: float = 0,
    ev_close: float = 0,
    ev_scale_out: float = 0,
    continuation_prob: float = 0,
    reversal_prob: float = 0,
    thesis_quality: float = 0,
    # Timeframe Trends at Exit
    m15_trend: float = 0.5,
    m30_trend: float = 0.5,
    h1_trend: float = 0.5,
    h4_trend: float = 0.5,
    d1_trend: float = 0.5,
    # Market Conditions at Exit
    regime: str = '',
    volatility: float = 0,
    session: str = '',
    # Exit Reasoning
    exit_reason: str = '',
    extra_context: Dict = None
):
    """
    Log AI decision context at the moment of exit.
    This is called when AI decides to CLOSE or SCALE_OUT.
    """
    with _file_lock:
        try:
            _ensure_data_dir()
            
            # Load entry context if available
            entry_context = None
            if os.path.exists(ENTRY_CONTEXT_JSON):
                try:
                    with open(ENTRY_CONTEXT_JSON, 'r') as f:
                        entries = json.load(f)
                        entry_context = entries.get(str(ticket))
                except:
                    pass
            
            exit_data = {
                'ticket': ticket,
                'symbol': symbol,
                'action': action,
                'exit_price': exit_price,
                'exit_time': datetime.now().isoformat(),
                'profit_dollars': profit_dollars,
                'profit_pct': profit_pct,
                # AI Decision
                'ev_hold': ev_hold,
                'ev_close': ev_close,
                'ev_scale_out': ev_scale_out,
                'continuation_prob': continuation_prob,
                'reversal_prob': reversal_prob,
                'thesis_quality': thesis_quality,
                # Timeframes at Exit
                'trends_at_exit': {
                    'm15': m15_trend,
                    'm30': m30_trend,
                    'h1': h1_trend,
                    'h4': h4_trend,
                    'd1': d1_trend
                },
                # Market at Exit
                'regime': regime,
                'volatility': volatility,
                'session': session,
                'exit_reason': exit_reason,
                'extra': extra_context or {},
                # Entry context for comparison
                'entry_context': entry_context
            }
            
            # Save to detailed journal
            _save_trade_details(ticket, exit_data)
            
            logger.info(f"📓 EXIT LOGGED: #{ticket} {symbol} {action} @ {exit_price} → ${profit_dollars:.2f}")
            logger.info(f"   EV: Hold={ev_hold:.2f}% Close={ev_close:.2f}% | Cont={continuation_prob:.0f}% Rev={reversal_prob:.0f}%")
            logger.info(f"   Trends: M15={m15_trend:.2f} M30={m30_trend:.2f} H1={h1_trend:.2f} H4={h4_trend:.2f} D1={d1_trend:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log exit context: {e}")
            return False


def get_entry_context(ticket: int) -> Optional[Dict]:
    """Get the entry context for a specific trade"""
    if not os.path.exists(ENTRY_CONTEXT_JSON):
        return None
    try:
        with open(ENTRY_CONTEXT_JSON, 'r') as f:
            entries = json.load(f)
            return entries.get(str(ticket))
    except:
        return None


# Initialize on import
_load_logged_tickets()
