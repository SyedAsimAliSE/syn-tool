"""
Type definitions for syn-tool.
"""
from enum import Enum, auto

class Direction(str, Enum):
    """Sync direction."""
    SAP_TO_SHOPIFY = 'sap-to-shopify'
    SHOPIFY_TO_SAP = 'shopify-to-sap'
    BOTH = 'both'

class SyncMode(str, Enum):
    """Sync mode."""
    FULL = 'full'
    INCREMENTAL = 'incremental'

class EntityType(str, Enum):
    """Entity types."""
    GROUP = 'group'
    PRODUCT = 'product'
    ORDER = 'order'
    PAYMENT = 'payment'
    CREDIT = 'credit'
