"""Credit synchronization service."""
# TODO:: Incomplete implementation
from typing import Dict, Optional
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_exponential
from ..clients import SAPClient, ShopifyClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

class CreditService:
    """Service for handling credit synchronization."""
    
    def __init__(self, sap_client: SAPClient, shopify_client: ShopifyClient):
        """Initialize credit service."""
        self.sap_client = sap_client
        self.shopify_client = shopify_client
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _sync_refund(self, refund: Dict) -> None:
        """Sync a single refund with retry logic."""
        try:
            sap_refund = self._transform_refund_to_sap_format(refund)
            self.sap_client.create_refund(sap_refund)
        except Exception as e:
            logger.error(f"Failed to sync refund {refund['id']}: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _sync_credit_memo(self, credit_memo: Dict) -> None:
        """Sync a single credit memo with retry logic."""
        try:
            sap_credit_memo = self._transform_credit_memo_to_sap_format(credit_memo)
            self.sap_client.create_credit_memo(sap_credit_memo)
        except Exception as e:
            logger.error(f"Failed to sync credit memo {credit_memo['id']}: {str(e)}")
            raise
    
    def sync_credits(self, credit_type: str, mode: str,
                    progress: Optional[Progress] = None) -> Dict:
        """Sync credits from Shopify to SAP.
        
        Args:
            credit_type: Type of credit to sync ('refund' or 'credit_memo')
            mode: Sync mode ('full' or 'incremental')
            progress: Optional progress bar
        """
        result = {
            'refunds': {'synced': 0, 'failed': 0},
            'credit_memos': {'synced': 0, 'failed': 0}
        }
        
        try:
            if credit_type in ['refund', 'both']:
                refunds = self.shopify_client.get_refunds()
                total = len(refunds)
                
                if progress:
                    progress.update(progress.task_ids[0], 
                                  total=total,
                                  description="Syncing refunds...")
                
                for i, refund in enumerate(refunds):
                    try:
                        self._sync_refund(refund)
                        result['refunds']['synced'] += 1
                    except Exception:
                        result['refunds']['failed'] += 1
                    
                    if progress:
                        progress.update(progress.task_ids[0], advance=1)
            
            if credit_type in ['credit_memo', 'both']:
                credit_memos = self.shopify_client.get_credit_memos()
                total = len(credit_memos)
                
                if progress:
                    progress.update(progress.task_ids[0], 
                                  total=total,
                                  description="Syncing credit memos...")
                
                for i, credit_memo in enumerate(credit_memos):
                    try:
                        self._sync_credit_memo(credit_memo)
                        result['credit_memos']['synced'] += 1
                    except Exception:
                        result['credit_memos']['failed'] += 1
                    
                    if progress:
                        progress.update(progress.task_ids[0], advance=1)
                    
        except Exception as e:
            logger.error(f"Credit sync failed: {str(e)}")
            raise
        
        return result
    
    def _transform_refund_to_sap_format(self, shopify_refund: Dict) -> Dict:
        """Transform Shopify refund to SAP format."""
        return {
            'DocEntry': shopify_refund.get('order_id'),
            'DocNum': shopify_refund.get('id'),
            'DocType': 'rCustomer',
            'DocDate': shopify_refund.get('created_at', '').split('T')[0],
            'CardCode': shopify_refund.get('customer', {}).get('id'),
            'DocCurrency': shopify_refund.get('currency', 'USD'),
            'CashSum': float(shopify_refund.get('amount', 0)),
            'Comments': shopify_refund.get('note', ''),
            'PaymentInvoices': [{
                'DocEntry': shopify_refund.get('order_id'),
                'SumApplied': float(shopify_refund.get('amount', 0)),
                'InvoiceType': 'it_Invoice'
            }]
        }
    
    def _transform_credit_memo_to_sap_format(self, shopify_credit_memo: Dict) -> Dict:
        """Transform Shopify credit memo to SAP format."""
        return {
            'CardCode': shopify_credit_memo.get('customer', {}).get('id'),
            'DocDate': shopify_credit_memo.get('created_at', '').split('T')[0],
            'DocDueDate': shopify_credit_memo.get('created_at', '').split('T')[0],
            'Comments': shopify_credit_memo.get('note', ''),
            'DocCurrency': shopify_credit_memo.get('currency', 'USD'),
            'DocumentLines': [
                {
                    'ItemCode': line.get('sku', ''),
                    'Quantity': line.get('quantity', 0),
                    'UnitPrice': float(line.get('price', 0)),
                    'WarehouseCode': line.get('warehouse_code', '')
                }
                for line in shopify_credit_memo.get('line_items', [])
            ]
        }
