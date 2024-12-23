"""SAP-Shopify Synchronization Tool"""

__version__ = "0.1.0"

from syn_tool.utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
