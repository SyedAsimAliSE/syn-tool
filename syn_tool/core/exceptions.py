"""
Custom exceptions for syn-tool.
"""

class SyncError(Exception):
    """Base class for sync-related exceptions."""
    pass

class SyncValidationError(SyncError):
    """Raised when data validation fails during sync."""
    pass

class SyncTransformError(SyncError):
    """Raised when data transformation fails during sync."""
    pass

class SyncConnectionError(SyncError):
    """Raised when connection to SAP or Shopify fails."""
    pass

class SyncConfigError(SyncError):
    """Raised when there's an issue with configuration."""
    pass
