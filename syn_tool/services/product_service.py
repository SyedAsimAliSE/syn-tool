"""Product synchronization service."""

from typing import Dict, Optional
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_exponential
from ..clients import SAPClient, ShopifyClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

class ProductService:
    """Service for handling product synchronization."""
    
    def __init__(self, sap_client: SAPClient, shopify_client: ShopifyClient):
        """Initialize product service."""
        self.sap_client = sap_client
        self.shopify_client = shopify_client
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _sync_product(self, product: Dict) -> None:
        """Sync a single product with retry logic."""
        try:
            shopify_product = self._transform_to_shopify_format(product)
            self.shopify_client.create_product(shopify_product)
        except Exception as e:
            logger.error(f"Failed to sync product {product.get('ItemCode')}: {str(e)}")
            raise
    
    def sync_products(self, direction: str, mode: str, batch_size: int,
                     progress: Optional[Progress] = None) -> Dict:
        """Sync products between SAP and Shopify."""
        result = {'synced': 0, 'failed': 0, 'skipped': 0}
        
        try:
            if direction in ['sap-to-shopify', 'both']:
                # Get products from SAP
                sap_products = self.sap_client.get_items()
                total = len(sap_products)
                
                if progress:
                    progress.update(progress.task_ids[0], total=total)
                
                # Sync each product to Shopify
                for i, product in enumerate(sap_products):
                    try:
                        self._sync_product(product)
                        result['synced'] += 1
                    except Exception:
                        result['failed'] += 1
                    
                    if progress:
                        progress.update(progress.task_ids[0], advance=1)
            
            if direction in ['shopify-to-sap', 'both']:
                # Implementation for Shopify to SAP sync
                pass
                
        except Exception as e:
            logger.error(f"Product sync failed: {str(e)}")
            raise
        
        return result
    
    def _transform_to_shopify_format(self, sap_product: Dict) -> Dict:
        """Transform SAP product to Shopify format."""
        return {
            'title': sap_product.get('ItemName', ''),
            'body_html': sap_product.get('Description', ''),
            'vendor': sap_product.get('Manufacturer', ''),
            'product_type': sap_product.get('ItemsGroupCode', ''),
            'variants': [{
                'price': str(sap_product.get('Price', 0)),
                'sku': sap_product.get('ItemCode', ''),
                'inventory_quantity': sap_product.get('QuantityOnStock', 0)
            }]
        }
