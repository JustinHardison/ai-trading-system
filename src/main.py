"""
Main entry point for the AI Trading Bot
"""
import asyncio
import sys
from .trading_bot import AITradingBot
from .utils.logger import get_logger


logger = get_logger(__name__)


def main():
    """Main entry point"""
    logger.info("Starting AI Trading System...")

    # Create and start trading bot
    bot = AITradingBot()

    # Run the bot
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
