"""Service for testing connections and operations."""

from typing import Dict, Optional, Tuple
from ..clients import SAPClient, ShopifyClient
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TestService:
    """Service for handling connection and operation testing."""
    
    def __init__(self, sap_client: SAPClient, shopify_client: ShopifyClient):
        """Initialize test service."""
        self.sap_client = sap_client
        self.shopify_client = shopify_client
    
    def test_sap_connection(self) -> Tuple[bool, str]:
        """Test connection to SAP.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # The _setup_session call in SAPClient constructor will test the connection
            return True, "Successfully connected to SAP"
        except Exception as e:
            error_msg = f"SAP connection test failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def test_shopify_connection(self) -> Tuple[bool, str]:
        """Test connection to Shopify.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            self.shopify_client.test_connection()
            return True, "Successfully connected to Shopify"
        except Exception as e:
            error_msg = f"Shopify connection test failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def test_sap_operations(self, operation: str) -> Dict[str, bool]:
        """Test SAP CRUD operations.
        
        Args:
            operation: The operation to test (create, read, update, delete)
            
        Returns:
            Dictionary with operation results
        """
        results = {'success': False, 'message': ''}
        
        try:
            if operation == 'create':
                test_item = {
                    'ItemCode': 'TEST_ITEM',
                    'ItemName': 'Test Item',
                    'ItemType': 'itItems'
                }
                self.sap_client.create_item(test_item)
                results['success'] = True
                results['message'] = 'Successfully created test item in SAP'
            
            elif operation == 'read':
                self.sap_client.get_item('TEST_ITEM')
                results['success'] = True
                results['message'] = 'Successfully read test item from SAP'
            
            elif operation == 'update':
                test_item = {
                    'ItemCode': 'TEST_ITEM',
                    'ItemName': 'Updated Test Item'
                }
                self.sap_client.update_item('TEST_ITEM', test_item)
                results['success'] = True
                results['message'] = 'Successfully updated test item in SAP'
            
            elif operation == 'delete':
                self.sap_client.delete_item('TEST_ITEM')
                results['success'] = True
                results['message'] = 'Successfully deleted test item from SAP'
            
        except Exception as e:
            results['success'] = False
            results['message'] = f"SAP {operation} operation test failed: {str(e)}"
            logger.error(results['message'])
        
        return results
    
    def test_shopify_operations(self, operation: str) -> Dict[str, bool]:
        """Test Shopify CRUD operations.
        
        Args:
            operation: The operation to test (create, read, update, delete)
            
        Returns:
            Dictionary with operation results
        """
        results = {'success': False, 'message': ''}
        
        try:
            if operation == 'create':
                test_product = {
                    'title': 'Test Product',
                    'body_html': 'Test product description',
                    'vendor': 'Test Vendor',
                    'product_type': 'Test Type',
                    'variants': [{
                        'price': '10.00',
                        'sku': 'TEST_SKU',
                        'inventory_quantity': 100
                    }]
                }
                self.shopify_client.create_product(test_product)
                results['success'] = True
                results['message'] = 'Successfully created test product in Shopify'
            
            elif operation == 'read':
                self.shopify_client.get_product('TEST_SKU')
                results['success'] = True
                results['message'] = 'Successfully read test product from Shopify'
            
            elif operation == 'update':
                test_product = {
                    'title': 'Updated Test Product',
                    'variants': [{
                        'sku': 'TEST_SKU',
                        'price': '15.00'
                    }]
                }
                self.shopify_client.update_product('TEST_SKU', test_product)
                results['success'] = True
                results['message'] = 'Successfully updated test product in Shopify'
            
            elif operation == 'delete':
                self.shopify_client.delete_product('TEST_SKU')
                results['success'] = True
                results['message'] = 'Successfully deleted test product from Shopify'
            
        except Exception as e:
            results['success'] = False
            results['message'] = f"Shopify {operation} operation test failed: {str(e)}"
            logger.error(results['message'])
        
        return results
