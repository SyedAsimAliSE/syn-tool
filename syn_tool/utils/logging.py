"""Logging configuration for the syn-tool project."""

import logging
import os
from typing import Optional

def setup_logging(level: Optional[str] = None) -> None:
    """Configure logging for the entire project.
    
    Args:
        level: Optional logging level. If not provided, uses LOGLEVEL env var or defaults to INFO.
    """
    log_level = level or os.environ.get('LOGLEVEL', 'INFO')
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the project's standard configuration.
    
    Args:
        name: Name of the logger, typically __name__ of the module.
    
    Returns:
        Logger instance with standard configuration.
    """
    return logging.getLogger(name)
