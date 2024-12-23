"""Payment synchronization service."""
# TODO:: Incomplete implementation
from typing import Dict, Optional
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_exponential
from ..clients import SAPClient, ShopifyClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

class PaymentService:
    """Service for handling payment synchronization."""
    
    def __init__(self, sap_client: SAPClient, shopify_client: ShopifyClient):
        """Initialize payment service."""
        self.sap_client = sap_client
        self.shopify_client = shopify_client
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _sync_payment(self, payment: Dict) -> None:
        """Sync a single payment with retry logic."""
        try:
            sap_payment = self._transform_to_sap_format(payment)
            self.sap_client.create_payment(sap_payment)
        except Exception as e:
            logger.error(f"Failed to sync payment {payment['id']}: {str(e)}")
            raise
    
    def sync_payments(self, mode: str, batch_size: int,
                     progress: Optional[Progress] = None) -> Dict:
        """Sync payments from Shopify to SAP."""
        result = {'synced': 0, 'failed': 0, 'skipped': 0}
        
        try:
            shopify_payments = self.shopify_client.get_payments()
            total = len(shopify_payments)
            
            if progress:
                progress.update(progress.task_ids[0], total=total)
            
            for i, payment in enumerate(shopify_payments):
                try:
                    self._sync_payment(payment)
                    result['synced'] += 1
                except Exception:
                    result['failed'] += 1
                
                if progress:
                    progress.update(progress.task_ids[0], advance=1)
                    
        except Exception as e:
            logger.error(f"Payment sync failed: {str(e)}")
            raise
        
        return result
    
    def _transform_to_sap_format(self, shopify_payment: Dict) -> Dict:
        """Transform Shopify payment to SAP format."""
        return {
            'DocEntry': shopify_payment.get('order_id'),
            'DocNum': shopify_payment.get('id'),
            'DocType': 'rCustomer',
            'DocDate': shopify_payment.get('created_at', '').split('T')[0],
            'CardCode': shopify_payment.get('customer', {}).get('id'),
            'DocCurrency': shopify_payment.get('currency', 'USD'),
            'CashSum': float(shopify_payment.get('amount', 0)),
            'TransferSum': 0,
            'CheckSum': 0,
            'CreditSum': 0,
            'PaymentInvoices': [{
                'DocEntry': shopify_payment.get('order_id'),
                'SumApplied': float(shopify_payment.get('amount', 0)),
                'InvoiceType': 'it_Invoice'
            }]
        }
