"""
FTMO Metrics Monitor
Analyzes FTMO account page and feeds data to LLM Risk Manager
Runs every hour at the top of the hour
"""
import requests
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup
import re
from loguru import logger
import schedule

# FTMO metrics URL - Update this when account changes
# Current account: 1600060464
FTMO_URL = "https://trader.ftmo.oanda.com/live-metrix/1600060464/share/019b37a3-394a-7088-9956-2af0345078cf?lang=en-US"
API_URL = "http://127.0.0.1:5007/api/risk/update"

logger.add("logs/ftmo_monitor_{time}.log", rotation="1 day")


def scrape_ftmo_metrics():
    """
    Scrape FTMO metrics page and extract key data
    
    Returns:
        dict: Account metrics including balance, equity, P&L, drawdown
    """
    try:
        logger.info("Fetching FTMO metrics page...")
        
        # Use session with headers to mimic browser
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = session.get(FTMO_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract metrics from page
        # Note: FTMO uses JavaScript to load data, so we may need to look for specific patterns
        metrics = {
            'balance': None,
            'equity': None,
            'daily_pnl': None,
            'total_pnl': None,
            'daily_pnl_pct': None,
            'total_pnl_pct': None,
            'drawdown': None,
            'drawdown_pct': None,
            'open_positions': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Try to extract from meta tags
        og_description = soup.find('meta', property='og:description')
        if og_description:
            desc = og_description.get('content', '')
            logger.info(f"OG Description: {desc}")
            
            # Extract profit from description
            # Example: "I made $336.10 while following FTMO rules"
            profit_match = re.search(r'\$([0-9,]+\.?\d*)', desc)
            if profit_match:
                profit_str = profit_match.group(1).replace(',', '')
                metrics['total_pnl'] = float(profit_str)
                logger.info(f"✓ Extracted profit: ${profit_str}")
        
        # Try to find data in script tags or JSON
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'balance' in script.string.lower():
                # Try to extract JSON data
                try:
                    # Look for patterns like: balance: 100000, equity: 100336
                    balance_match = re.search(r'balance["\']?\s*:\s*([0-9.]+)', script.string)
                    equity_match = re.search(r'equity["\']?\s*:\s*([0-9.]+)', script.string)
                    
                    if balance_match:
                        metrics['balance'] = float(balance_match.group(1))
                        logger.info(f"✓ Extracted balance: ${metrics['balance']}")
                    
                    if equity_match:
                        metrics['equity'] = float(equity_match.group(1))
                        logger.info(f"✓ Extracted equity: ${metrics['equity']}")
                except Exception as e:
                    logger.debug(f"Could not parse script: {e}")
        
        # If we couldn't get balance/equity, use defaults
        if metrics['balance'] is None:
            logger.warning("Could not extract balance from page, using default")
            metrics['balance'] = 100000  # Default FTMO account size
        
        if metrics['equity'] is None and metrics['total_pnl'] is not None:
            metrics['equity'] = metrics['balance'] + metrics['total_pnl']
            logger.info(f"✓ Calculated equity: ${metrics['equity']}")
        elif metrics['equity'] is None:
            metrics['equity'] = metrics['balance']
        
        # Calculate percentages
        if metrics['total_pnl'] is not None:
            metrics['total_pnl_pct'] = (metrics['total_pnl'] / metrics['balance']) * 100
        
        # Calculate drawdown
        if metrics['equity'] < metrics['balance']:
            metrics['drawdown'] = metrics['balance'] - metrics['equity']
            metrics['drawdown_pct'] = (metrics['drawdown'] / metrics['balance']) * 100
        else:
            metrics['drawdown'] = 0
            metrics['drawdown_pct'] = 0
        
        logger.info("="*60)
        logger.info("FTMO METRICS EXTRACTED:")
        logger.info(f"  Balance: ${metrics['balance']:,.2f}")
        logger.info(f"  Equity: ${metrics['equity']:,.2f}")
        logger.info(f"  Total P&L: ${metrics.get('total_pnl', 0):,.2f} ({metrics.get('total_pnl_pct', 0):.2f}%)")
        logger.info(f"  Drawdown: ${metrics['drawdown']:,.2f} ({metrics['drawdown_pct']:.2f}%)")
        logger.info("="*60)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error scraping FTMO metrics: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_ftmo_compliance(metrics):
    """
    Analyze FTMO metrics against rules
    
    Args:
        metrics (dict): Account metrics
        
    Returns:
        dict: Compliance analysis
    """
    if not metrics:
        return None
    
    analysis = {
        'compliant': True,
        'warnings': [],
        'violations': [],
        'risk_level': 'LOW'
    }
    
    # FTMO Rules
    DAILY_LOSS_LIMIT = 5.0  # 5%
    MAX_TOTAL_LOSS = 10.0   # 10%
    PROFIT_TARGET = 10.0    # 10%
    
    # Check daily loss (we don't have this from scraping, so estimate)
    daily_pnl_pct = metrics.get('daily_pnl_pct', 0)
    
    # Check total drawdown
    drawdown_pct = metrics.get('drawdown_pct', 0)
    total_pnl_pct = metrics.get('total_pnl_pct', 0)
    
    # Analyze drawdown
    if drawdown_pct >= MAX_TOTAL_LOSS:
        analysis['compliant'] = False
        analysis['violations'].append(f"VIOLATION: Total drawdown {drawdown_pct:.2f}% >= {MAX_TOTAL_LOSS}%")
        analysis['risk_level'] = 'CRITICAL'
    elif drawdown_pct >= 9.0:
        analysis['warnings'].append(f"WARNING: Approaching max loss limit ({drawdown_pct:.2f}%)")
        analysis['risk_level'] = 'HIGH'
    elif drawdown_pct >= 7.0:
        analysis['warnings'].append(f"CAUTION: Drawdown at {drawdown_pct:.2f}%")
        analysis['risk_level'] = 'MEDIUM'
    
    # Analyze profit
    if total_pnl_pct >= PROFIT_TARGET:
        analysis['warnings'].append(f"SUCCESS: Profit target reached ({total_pnl_pct:.2f}%)")
        analysis['risk_level'] = 'LOW'
    elif total_pnl_pct >= 7.0:
        analysis['warnings'].append(f"PROGRESS: Near profit target ({total_pnl_pct:.2f}%)")
    
    logger.info("COMPLIANCE ANALYSIS:")
    logger.info(f"  Status: {'COMPLIANT' if analysis['compliant'] else 'VIOLATION'}")
    logger.info(f"  Risk Level: {analysis['risk_level']}")
    if analysis['warnings']:
        for warning in analysis['warnings']:
            logger.info(f"  {warning}")
    if analysis['violations']:
        for violation in analysis['violations']:
            logger.error(f"  {violation}")
    
    return analysis


def send_to_llm_risk_manager(metrics, analysis):
    """
    Send FTMO metrics to LLM Risk Manager
    
    Args:
        metrics (dict): Account metrics
        analysis (dict): Compliance analysis
    """
    try:
        # Prepare data for LLM
        account_data = {
            'balance': metrics.get('balance', 100000),
            'equity': metrics.get('equity', 100000),
            'daily_pnl': metrics.get('daily_pnl', 0),
            'drawdown': metrics.get('drawdown_pct', 0),
            'starting_balance': metrics.get('balance', 100000)
        }
        
        market_data = {
            'regime': 'unknown',
            'volatility': 'normal',
            'session': 'unknown'
        }
        
        # Add FTMO compliance info
        request_data = {
            **account_data,
            'market_data': market_data,
            'ftmo_compliant': analysis.get('compliant', True) if analysis else True,
            'ftmo_risk_level': analysis.get('risk_level', 'LOW') if analysis else 'LOW',
            'ftmo_warnings': analysis.get('warnings', []) if analysis else [],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Sending to LLM Risk Manager: {API_URL}")
        response = requests.post(API_URL, json=request_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✓ LLM Risk Manager updated:")
            logger.info(f"  Mode: {result.get('scalping_mode', 'UNKNOWN')}")
            logger.info(f"  Risk Multiplier: {result.get('scalping_risk_multiplier', 1.0):.1f}x")
            logger.info(f"  Threshold Adj: {result.get('scalping_threshold_adjustment', 0):.0f}%")
            return result
        else:
            logger.error(f"Failed to update LLM: {response.status_code}")
            logger.error(response.text)
            return None
            
    except Exception as e:
        logger.error(f"Error sending to LLM: {e}")
        return None


def monitor_ftmo():
    """
    Main monitoring function - runs every hour
    """
    logger.info("="*60)
    logger.info(f"FTMO MONITORING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # 1. Scrape FTMO metrics
    metrics = scrape_ftmo_metrics()
    
    if not metrics:
        logger.error("Failed to scrape FTMO metrics")
        return
    
    # 2. Analyze compliance
    analysis = analyze_ftmo_compliance(metrics)
    
    # 3. Send to LLM Risk Manager
    llm_response = send_to_llm_risk_manager(metrics, analysis)
    
    # 4. Save to file for history
    try:
        with open('logs/ftmo_history.jsonl', 'a') as f:
            record = {
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'analysis': analysis,
                'llm_response': llm_response
            }
            f.write(json.dumps(record) + '\n')
    except Exception as e:
        logger.error(f"Error saving history: {e}")
    
    logger.info("✓ FTMO monitoring complete")
    logger.info("")


def run_scheduler():
    """
    Run monitoring on schedule (every hour at :00)
    """
    logger.info("="*60)
    logger.info("FTMO METRICS MONITOR STARTED")
    logger.info("Schedule: Every hour at :00")
    logger.info("="*60)
    
    # Run immediately on start
    monitor_ftmo()
    
    # Schedule for every hour at :00
    schedule.every().hour.at(":00").do(monitor_ftmo)
    
    logger.info("Scheduler running... Press Ctrl+C to stop")
    
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='FTMO Metrics Monitor')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--schedule', action='store_true', help='Run on schedule (every hour)')
    
    args = parser.parse_args()
    
    if args.once:
        # Run once
        monitor_ftmo()
    elif args.schedule:
        # Run on schedule
        run_scheduler()
    else:
        # Default: run once
        logger.info("Running once (use --schedule for continuous monitoring)")
        monitor_ftmo()
