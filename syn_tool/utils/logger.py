"""Logging configuration."""

import sys
from pathlib import Path
from loguru import logger

def setup_logger():
    """Configure logger with file and console outputs."""
    logger.remove()
    
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level="INFO"
    )
    
    logger.add(
        logs_dir / "sync_{time}.log",
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
               "{name}:{function}:{line} - {message}",
        level="DEBUG"
    )
    
    return logger

def get_logger(name: str = None):
    """Get a logger instance."""
    return logger.bind(name=name)
