"""
Logging configuration
"""
import sys
from pathlib import Path
from loguru import logger

from ..config import get_settings


def setup_logger():
    """Configure logger with file and console output"""
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File handler if enabled
    if settings.log_to_file:
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(exist_ok=True, parents=True)

        logger.add(
            log_dir / "trading_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        )

        # Separate file for errors
        logger.add(
            log_dir / "errors_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )


def get_logger(name: str):
    """Get logger instance"""
    return logger.bind(name=name)


# Initialize logger on import
setup_logger()
