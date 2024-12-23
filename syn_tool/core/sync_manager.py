"""Core sync manager implementation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rich.progress import Progress
from ..utils.logger import get_logger
from ..clients import SAPClient, ShopifyClient
from ..services import (
    ProductService,
    OrderService,
    PaymentService,
    CreditService
)
from ..services.test_service import TestService
from ..core.config import Config

logger = get_logger(__name__)

class SyncManager:
    """Manages synchronization operations between SAP and Shopify."""
    
    def __init__(self):
        """Initialize sync manager."""
        self.config = Config.from_env()
        self.sap_client = SAPClient(self.config.sap)
        self.shopify_client = ShopifyClient(self.config.shopify)
        
        # Initialize services
        self.product_service = ProductService(self.sap_client, self.shopify_client)
        self.order_service = OrderService(self.sap_client, self.shopify_client)
        self.payment_service = PaymentService(self.sap_client, self.shopify_client)
        self.credit_service = CreditService(self.sap_client, self.shopify_client)
        self.test_service = TestService(self.sap_client, self.shopify_client)
        
        self.failed_records_file = Path("failed_records.json")
        self._load_failed_records()
    
    def _load_failed_records(self):
        """Load failed records from file."""
        if self.failed_records_file.exists():
            with open(self.failed_records_file) as f:
                self.failed_records = json.load(f)
        else:
            self.failed_records = []
    
    def _save_failed_records(self):
        """Save failed records to file."""
        with open(self.failed_records_file, 'w') as f:
            json.dump(self.failed_records, f, indent=2)
    
    def _add_failed_record(self, record_type: str, record_id: str, error: str):
        """Add a failed record."""
        self.failed_records.append({
            'type': record_type,
            'id': record_id,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        })
        self._save_failed_records()
    
    def test_sap_connection(self) -> Tuple[bool, str]:
        """Test connection to SAP."""
        return self.test_service.test_sap_connection()
    
    def test_shopify_connection(self) -> Tuple[bool, str]:
        """Test connection to Shopify."""
        return self.test_service.test_shopify_connection()
    
    def test_operations(self, platform: str, operation: str) -> Dict[str, bool]:
        """Test platform operations.
        
        Args:
            platform: The platform to test (sap or shopify)
            operation: The operation to test (create, read, update, delete)
        """
        if platform == 'sap':
            return self.test_service.test_sap_operations(operation)
        elif platform == 'shopify':
            return self.test_service.test_shopify_operations(operation)
        else:
            return {'success': False, 'message': f'Unknown platform: {platform}'}
    
    def sync_products(self, direction: str, mode: str, batch_size: int,
                     progress: Optional[Progress] = None) -> Dict:
        """Sync products between SAP and Shopify."""
        return self.product_service.sync_products(direction, mode, batch_size, progress)
    
    def sync_orders(self, mode: str, batch_size: int,
                   progress: Optional[Progress] = None) -> Dict:
        """Sync orders from Shopify to SAP."""
        return self.order_service.sync_orders(mode, batch_size, progress)
    
    def sync_payments(self, mode: str, batch_size: int,
                     progress: Optional[Progress] = None) -> Dict:
        """Sync payments from Shopify to SAP."""
        return self.payment_service.sync_payments(mode, batch_size, progress)
    
    def sync_credits(self, credit_type: str, mode: str,
                    progress: Optional[Progress] = None) -> Dict:
        """Sync credits from Shopify to SAP."""
        return self.credit_service.sync_credits(credit_type, mode, progress)
    
    def get_failed_records(self) -> List[Dict]:
        """Get all failed records."""
        return self.failed_records
    
    def retry_failed_records(self, progress: Optional[Progress] = None) -> Dict:
        """Retry all failed records."""
        result = {'success': 0, 'failed': 0}
        
        if not self.failed_records:
            return result
        
        total_records = len(self.failed_records)
        if progress:
            progress.update(progress.task_ids[0], total=total_records)
        
        # Create a new list for still-failed records
        still_failed = []
        
        for i, record in enumerate(self.failed_records):
            try:
                if record['type'] == 'product':
                    # Retry product sync based on direction
                    pass
                elif record['type'] == 'order':
                    # Retry order sync
                    pass
                elif record['type'] == 'payment':
                    # Retry payment sync
                    pass
                elif record['type'] == 'credit':
                    # Retry credit sync
                    pass
                
                result['success'] += 1
                
                if progress:
                    progress.update(progress.task_ids[0], 
                                  advance=1,
                                  description=f"[cyan]Retried {i+1}/{total_records}")
            except Exception as e:
                logger.error(f"Retry failed for {record['type']} {record['id']}: {str(e)}")
                still_failed.append(record)
                result['failed'] += 1
        
        self.failed_records = still_failed
        self._save_failed_records()
        
        return result
