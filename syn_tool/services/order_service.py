"""Order synchronization service."""

from typing import Dict, Optional, List
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_exponential
from ..clients import SAPClient, ShopifyClient
from ..utils.logger import get_logger
import json
import os
import time
from datetime import datetime

logger = get_logger(__name__)

class OrderService:
    """Service for handling order synchronization."""
    
    def __init__(self, sap_client: SAPClient, shopify_client: ShopifyClient):
        """Initialize order service."""
        self.sap_client = sap_client
        self.shopify_client = shopify_client
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _sync_order(self, order: Dict) -> None:
        """Sync a single order with retry logic."""
        try:
            sap_order = self._transform_to_sap_format(order, self._get_or_create_customer(order.get("customer", {})))
            self.sap_client.create_order(sap_order)
        except Exception as e:
            logger.error(f"Failed to sync order {order['id']}: {str(e)}")
            raise
    
    def sync_orders(self, mode: str, batch_size: int,
                   progress: Optional[Progress] = None) -> Dict:
        """Sync orders from Shopify to SAP."""
        result = {'synced': 0, 'failed': 0, 'skipped': 0}
        
        try:
            # Get orders from Shopify
            shopify_orders = self.shopify_client.get_orders()
            total = len(shopify_orders)
            
            if progress:
                progress.update(progress.task_ids[0], total=total)
            
            # Sync each order to SAP
            for i, order in enumerate(shopify_orders):
                try:
                    self._sync_order(order)
                    result['synced'] += 1
                except Exception:
                    result['failed'] += 1
                
                if progress:
                    progress.update(progress.task_ids[0], advance=1)
                    
        except Exception as e:
            logger.error(f"Order sync failed: {str(e)}")
            raise
        
        return result
    
    def sync_single_order(self, order_id: str, progress=None) -> Dict[str, int]:
        """Sync a single order from Shopify to SAP.
        
        Args:
            order_id: The Shopify order ID to sync
            progress: Optional progress bar
            
        Returns:
            Dict containing counts of synced, failed, and skipped orders
        """
        try:
            # Get order from Shopify
            order = self.shopify_client.get_order(order_id)
            if not order:
                logger.error(f"Order {order_id} not found in Shopify")
                return {"synced": 0, "failed": 1, "skipped": 0}
            
            # Log order data for debugging
            logger.info(f"Order data: {order}")
            
            # Ensure UDFs exist
            if not self.sap_client._ensure_udfs_exist():
                logger.error("Failed to ensure UDFs exist")
                return {"synced": 0, "failed": 1, "skipped": 0}
            
            # Check numbering series
            series = self.sap_client.get_numbering_series()
            if not series:
                logger.error("No numbering series found for business partners")
                return {"synced": 0, "failed": 1, "skipped": 0}
            
            # Process the order
            try:
                self._process_order(order)
                logger.info(f"Successfully synced order {order_id}")
                return {"synced": 1, "failed": 0, "skipped": 0}
            except Exception as e:
                logger.error(f"Failed to sync order {order_id}: {str(e)}")
                return {"synced": 0, "failed": 1, "skipped": 0}
                
        except Exception as e:
            logger.error(f"Error syncing order {order_id}: {str(e)}")
            return {"synced": 0, "failed": 1, "skipped": 0}
    
    def _transform_to_sap_format(self, order: Dict, card_code: str) -> Dict:
        """Transform Shopify order to SAP format.
        
        Args:
            order: Shopify order data
            card_code: SAP customer card code
            
        Returns:
            Dict: Order data in SAP format
        """
        try:
            # Get default tax code from env or use a default
            default_tax_code = os.getenv('SAP_DEFAULT_TAX_CODE', 'GST')
            
            # Get order series from env or use a default
            order_series = int(os.getenv('SAP_ORDER_SERIES', '1'))
            
            # Base order data
            sap_order = {
                "CardCode": card_code,
                "DocDate": order['created_at'][:10],  # YYYY-MM-DD
                "DocDueDate": order['created_at'][:10],
                "TaxDate": order['created_at'][:10],
                "Series": order_series,
                "U_ShopifyOrderId": str(order['id']),
                "DocCurrency": order.get('currency', 'AUD'),
                "Comments": f"Shopify Order #{order['order_number']}",
                "DocumentLines": []
            }
            
            # Add line items
            for i, item in enumerate(order['line_items']):
                quantity = float(item['quantity'])
                original_price = float(item.get("original_price", item["price"]))
                total_discount = float(item.get('total_discount', '0.00'))
                
                # Calculate discount percent
                line_total = quantity * original_price
                discount_percent = (total_discount / line_total * 100) if line_total > 0 else 0
                
                sap_line = {
                    "LineNum": i,
                    "ItemCode": self._get_sap_item_code(item.get("product_id"), item["sku"]),
                    "Quantity": quantity,
                    "UnitPrice": original_price,
                    "DiscountPercent": discount_percent,
                    "VatGroup": default_tax_code,
                    "WarehouseCode": self.sap_client.warehouse
                }
                
                sap_order['DocumentLines'].append(sap_line)
                
            return sap_order
            
        except Exception as e:
            logger.error(f"Error transforming order {order['id']} to SAP format: {str(e)}")
            raise

    def _get_sap_item_code(self, product_id: str, sku: str) -> str:
        """Get SAP item code for a Shopify product.
        
        Args:
            product_id: Shopify product ID
            sku: Product SKU
            
        Returns:
            str: SAP item code
            
        Raises:
            Exception if item not found
        """
        try:
            # First try to find by Shopify product ID
            if product_id:
                items = self.sap_client.query_items(
                    {"$filter": f"U_ShopifyProductId eq '{product_id}'"}
                )
                if items:
                    return items[0]['ItemCode']
            
            # Then try by SKU
            if sku:
                items = self.sap_client.query_items(
                    {"$filter": f"ItemCode eq '{sku}'"}
                )
                if items:
                    return items[0]['ItemCode']
                    
            # If neither found, raise exception
            raise Exception(f"Item not found for product_id: {product_id}, sku: {sku}")
            
        except Exception as e:
            logger.error(f"Error getting SAP item code for product {product_id}: {str(e)}")
            raise

    def _prepare_order_lines(self, order_lines: List[Dict], tax_code: str = None) -> List[Dict]:
        """Prepare order lines for SAP.
        
        Args:
            order_lines: List of order line items from Shopify
            tax_code: Optional tax code to use for all lines
            
        Returns:
            List of order lines formatted for SAP
        """
        sap_lines = []
        for i, item in enumerate(order_lines):
            # Calculate unit price and discount
            quantity = item["quantity"]
            price = float(item["price"])
            original_price = float(item.get("original_price", price))
            discount_percent = ((original_price - price) / original_price * 100) if original_price > price else 0
            
            # Get tax code
            if not tax_code:
                # Query available tax codes
                tax_codes = self.sap_client.query_vat_groups({"$select": "Code,Name,Inactive"})
                if tax_codes and len(tax_codes) > 0:
                    # Find first active tax code
                    active_codes = [tc for tc in tax_codes if tc.get("Inactive") != "tYES"]
                    if active_codes:
                        tax_code = active_codes[0].get("Code")
                    else:
                        tax_code = tax_codes[0].get("Code")
                else:
                    tax_code = "S1" # Default to S1 if no tax codes found
            
            sap_line = {
                "LineNum": i,
                "ItemCode": self._get_sap_item_code(item.get("product_id"), item["sku"]),
                "Quantity": quantity,
                "UnitPrice": original_price,
                "DiscountPercent": discount_percent,
                "Price": price,
                "WarehouseCode": self.sap_client.warehouse,
                "VatGroup": tax_code,  # Changed from TaxCode to VatGroup
                "AccountCode": self.sap_client.config.revenue_account,
                "U_ShopifyLineItemId": str(item["id"])
            }
            sap_lines.append(sap_line)
            
        return sap_lines

    def _create_order(self, order_data: Dict, customer_code: str) -> Optional[str]:
        """Create an order in SAP.
        
        Args:
            order_data: Order data from Shopify
            customer_code: SAP customer code
            
        Returns:
            str: SAP DocEntry if successful, None otherwise
        """
        try:
            # Get tax code from environment variable or use a default
            tax_code = os.getenv("SAP_DEFAULT_TAX_CODE", "X0")
            
            # Basic order data
            sap_order = {
                "CardCode": customer_code,
                "DocDate": order_data.get("created_at")[:10],  # YYYY-MM-DD
                "DocDueDate": order_data.get("created_at")[:10],  # YYYY-MM-DD
                "Comments": f"Shopify Order #{order_data.get('order_number')}",
                "U_ShopifyOrderId": str(order_data.get("id")),
                "DocumentLines": self._prepare_order_lines(order_data.get("line_items", []), tax_code)
            }
            
            # Create order in SAP
            logger.info(f"Creating order with data: {json.dumps(sap_order, indent=2)}")
            response = self.sap_client.create_order(sap_order)
            
            if response:
                return response.get("DocEntry")
            return None
            
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            raise

    def _get_or_create_customer(self, shopify_customer: dict) -> Optional[str]:
        """Get or create a customer in SAP based on Shopify customer data.
        
        Args:
            shopify_customer: Shopify customer data
            
        Returns:
            str: SAP CardCode if successful, None otherwise
        """
        try:
            logger.info(f"Processing customer with Shopify ID: {shopify_customer['id']}")
            
            # First try to find customer by Shopify ID
            query = f"U_ShopifyCustomerId eq '{shopify_customer['id']}'"
            existing_customers = self.sap_client.query_business_partners({"$filter": query})
            
            if existing_customers:
                card_code = existing_customers[0].get('CardCode')
                logger.info(f"Found existing customer with CardCode: {card_code}")
                
                # Get full customer details
                customer_details = self.sap_client.get(f'BusinessPartners(\'{card_code}\')')
                logger.info(f"Customer details: {json.dumps(customer_details, indent=2)}")
                
                # Check if customer is inactive and needs to be recreated
                if customer_details.get('Valid') == 'tNO' or customer_details.get('Frozen') == 'tYES':
                    logger.info(f"Customer {card_code} is inactive, attempting to recreate...")
                    
                    # Try updating the customer first
                    try:
                        update_data = {
                            'Valid': 'tYES',
                            'ValidFrom': datetime.now().strftime("%Y-%m-%d"),
                            'ValidTo': '2099-12-31',
                            'Frozen': 'tNO',
                            'Block': 'tNO',
                            'Inactive': 'tNO',
                            'Status': 1,
                            'PaymentBlock': 'tNO',
                            'BlockDunning': 'tNO'
                        }
                        logger.info(f"Attempting to update customer {card_code} with data: {json.dumps(update_data, indent=2)}")
                        
                        self.sap_client.patch(f'BusinessPartners(\'{card_code}\')', update_data)
                        logger.info(f"Successfully updated customer {card_code}")
                        
                        # Verify the update
                        updated_customer = self.sap_client.get(f'BusinessPartners(\'{card_code}\')')
                        logger.info(f"Updated customer details: {json.dumps(updated_customer, indent=2)}")
                        
                        if updated_customer.get('Valid') == 'tYES' and updated_customer.get('Frozen') == 'tNO':
                            logger.info(f"Customer {card_code} is now active")
                            return card_code
                            
                        logger.error(f"Customer {card_code} is still inactive after update")
                    except Exception as e:
                        logger.error(f"Failed to update customer {card_code}: {str(e)}")
                    
                    # If update fails, try recreating
                    try:
                        # Delete the customer
                        self.sap_client.delete(f'BusinessPartners(\'{card_code}\')')
                        logger.info(f"Successfully deleted inactive customer {card_code}")
                        
                        # Wait a moment for SAP to process the deletion
                        time.sleep(2)
                        
                        # Verify the customer is deleted
                        check_query = f"CardCode eq '{card_code}'"
                        existing = self.sap_client.query_business_partners({"$filter": check_query})
                        if existing:
                            logger.error(f"Failed to delete customer {card_code} - still exists in SAP")
                            logger.error(f"Existing customer data: {json.dumps(existing[0], indent=2)}")
                            return None
                            
                        # Create new customer data
                        customer_data = {
                            "CardCode": card_code,  # Use the same card code
                            "CardName": f"{shopify_customer.get('first_name', '')} {shopify_customer.get('last_name', '')}".strip(),
                            "CardType": "cCustomer",
                            "GroupCode": 100,
                            "Series": int(os.getenv('SAP_CUSTOMER_SERIES', '92')),
                            "EmailAddress": shopify_customer.get('email'),
                            "Phone1": shopify_customer.get('phone', ''),
                            "Valid": "tYES",
                            "ValidFrom": datetime.now().strftime("%Y-%m-%d"),
                            "ValidTo": "2099-12-31",
                            "U_ShopifyCustomerId": str(shopify_customer['id'])
                        }
                        
                        # Add billing address if available
                        default_address = self._get_customer_default_address(shopify_customer['id'])
                        if default_address:
                            customer_data.update({
                                'BillToState': default_address.get('province', ''),
                                'BillToCountry': default_address.get('country', ''),
                                'BillToCity': default_address.get('city', ''),
                                'BillToStreet': default_address.get('address1', ''),
                                'BillToZipCode': default_address.get('zip', ''),
                                'ShipToState': default_address.get('province', ''),
                                'ShipToCountry': default_address.get('country', ''),
                                'ShipToCity': default_address.get('city', ''),
                                'ShipToStreet': default_address.get('address1', ''),
                                'ShipToZipCode': default_address.get('zip', '')
                            })
                            
                        # Create the new customer
                        try:
                            logger.info(f"Creating new customer with data: {json.dumps(customer_data, indent=2)}")
                            response = self.sap_client.create_business_partner(customer_data)
                            if response:
                                logger.info(f"Successfully recreated customer {card_code}")
                                
                                # Verify the new customer is active
                                new_customer = self.sap_client.get(f'BusinessPartners(\'{card_code}\')')
                                logger.info(f"New customer data: {json.dumps(new_customer, indent=2)}")
                                
                                if new_customer.get('Valid') != 'tYES':
                                    logger.error(f"New customer {card_code} is still inactive")
                                    return None
                                
                                return card_code
                            else:
                                logger.error(f"Failed to recreate customer {card_code}")
                                return None
                        except Exception as e:
                            logger.error(f"Error recreating customer {card_code}: {str(e)}")
                            return None
                            
                    except Exception as e:
                        logger.error(f"Failed to delete inactive customer {card_code}: {str(e)}")
                        return None
                        
                return card_code
            
            # Generate a unique CardCode based on Shopify customer ID
            card_code = f"C{str(shopify_customer['id'])[-9:]}"  # Take last 9 digits
            
            # Prepare customer data for SAP
            customer_data = {
                "CardCode": card_code,
                "CardName": f"{shopify_customer.get('first_name', '')} {shopify_customer.get('last_name', '')}".strip(),
                "CardType": "cCustomer",
                "GroupCode": 100,
                "Series": int(os.getenv('SAP_CUSTOMER_SERIES', '92')),
                "EmailAddress": shopify_customer.get('email'),
                "Phone1": shopify_customer.get('phone', ''),
                "Valid": "tYES",
                "ValidFrom": datetime.now().strftime("%Y-%m-%d"),
                "ValidTo": "2099-12-31",
                "U_ShopifyCustomerId": str(shopify_customer['id'])
            }
            
            # Add billing address if available
            default_address = self._get_customer_default_address(shopify_customer['id'])
            if default_address:
                customer_data.update({
                    'BillToState': default_address.get('province', ''),
                    'BillToCountry': default_address.get('country', ''),
                    'BillToCity': default_address.get('city', ''),
                    'BillToStreet': default_address.get('address1', ''),
                    'BillToZipCode': default_address.get('zip', ''),
                    'ShipToState': default_address.get('province', ''),
                    'ShipToCountry': default_address.get('country', ''),
                    'ShipToCity': default_address.get('city', ''),
                    'ShipToStreet': default_address.get('address1', ''),
                    'ShipToZipCode': default_address.get('zip', '')
                })
            
            # Create customer in SAP
            response = self.sap_client.create_business_partner(customer_data)
            if not response:
                raise Exception(f"Failed to create customer {card_code} in SAP")
                
            # Get the actual CardCode assigned by SAP
            card_code = response.get('CardCode')
            logger.info(f"Created new customer with CardCode: {card_code}")
            return card_code
            
        except Exception as e:
            logger.error(f"Error handling customer {shopify_customer['id']}: {str(e)}")
            raise

    def _process_order(self, order: Dict) -> None:
        """Process a single order with proper error handling."""
        order_id = order.get('id')
        customer = order.get('customer', {})
        
        if not customer:
            raise ValueError(f"No customer data found for order {order_id}")
            
        # Get or create customer first
        card_code = self._get_or_create_customer(customer)
        if not card_code:
            raise ValueError(f"Failed to get or create customer for order {order_id}")
            
        # Verify customer status before processing
        if not self._verify_customer_status(card_code):
            logger.info(f"Customer {card_code} inactive, attempting activation")
            if not self._activate_customer(card_code):
                raise ValueError(f"Failed to activate customer {card_code}")
            
        # Transform and create order with verification
        try:
            sap_order = self._transform_to_sap_format(order, card_code)
            
            # Log order data for debugging
            logger.info(f"Creating SAP order with data: {json.dumps(sap_order, indent=2)}")
            
            order_num = self.sap_client.create_order(sap_order)
            
            # Verify order creation
            if not self.sap_client.get_order(order_num):
                raise ValueError(f"Order {order_num} not found after creation")
                
            logger.info(f"Successfully created and verified order {order_num}")
            
        except Exception as e:
            logger.error(f"Order processing failed for {order_id}: {str(e)}")
            raise

    def _verify_customer_status(self, card_code: str) -> bool:
        """Verify customer status in SAP.
        
        Args:
            card_code: SAP Business Partner card code
            
        Returns:
            bool: True if customer is active and can process orders
        """
        try:
            customer = self.sap_client.get(f'BusinessPartners(\'{card_code}\')')
            if not customer:
                logger.error(f"Customer {card_code} not found")
                return False
            
            is_valid = customer.get('Valid') == 'tYES'
            not_frozen = customer.get('Frozen') == 'tNO'
            not_blocked = customer.get('Block') == 'tNO'
            not_payment_blocked = customer.get('PaymentBlock') == 'tNO'
            valid_from = datetime.strptime(customer.get('ValidFrom', '2099-12-31'), '%Y-%m-%d').date()
            valid_to = datetime.strptime(customer.get('ValidTo', '2000-01-01'), '%Y-%m-%d').date()
            today = datetime.now().date()
            
            status_ok = (
                is_valid and 
                not_frozen and 
                not_blocked and 
                not_payment_blocked and
                valid_from <= today <= valid_to
            )
            
            logger.info(
                f"Customer {card_code} status - Valid: {is_valid}, Not Frozen: {not_frozen}, "
                f"Not Blocked: {not_blocked}, Not Payment Blocked: {not_payment_blocked}, "
                f"Valid Period: {valid_from} to {valid_to}"
            )
            return status_ok
            
        except Exception as e:
            logger.error(f"Error checking customer {card_code} status: {str(e)}")
            return False

    def _activate_customer(self, card_code: str) -> bool:
        """Activate customer and verify status.
        
        Args:
            card_code: SAP Business Partner card code
            
        Returns:
            bool: True if activation successful
        """
        try:
            # Set all activation fields to active
            activation_data = {
                'Valid': 'tYES',
                'Frozen': 'tNO',
                'Block': 'tNO',
                'PaymentBlock': 'tNO',
                'ValidFrom': datetime.now().strftime('%Y-%m-%d'),
                'ValidTo': '2099-12-31',
                'CardType': 'cCustomer',
                'FatherType': 'cPayments_sum',
                'Currency': 'AUD',
                'GroupCode': 100
            }
            
            # Log the activation attempt
            logger.info(f"Attempting to activate customer {card_code} with data: {activation_data}")
            
            # Update customer in SAP
            response = self.sap_client.patch(f'BusinessPartners(\'{card_code}\')', activation_data)
            
            # Verify the activation worked
            return self._verify_customer_status(card_code)
            
        except Exception as e:
            logger.error(f"Error activating customer {card_code}: {str(e)}")
            return False

    def _get_customer_default_address(self, customer_id: str) -> Dict:
        """Get customer's default address from Shopify.
        
        Args:
            customer_id: Shopify customer ID
            
        Returns:
            Dict containing address information or empty dict if not found
        """
        try:
            customer = self.shopify_client.get_customer(customer_id)
            if not customer:
                return {}
                
            # Get default address
            default_address = customer.get('default_address', {})
            if not default_address:
                return {}
                
            return default_address
            
        except Exception as e:
            logger.error(f"Error getting customer default address: {str(e)}")
            return {}
            
    def list_orders(self, status: Optional[str] = None, 
                   limit: int = 50) -> List[Dict]:
        """List orders from Shopify with optional filtering."""
        try:
            orders = self.shopify_client.get_orders(status=status, limit=limit)
            logger.info(f"Retrieved {len(orders)} orders from Shopify")
            return orders
        except Exception as e:
            logger.error(f"Failed to list orders: {str(e)}")
            return []

    def get_order_status(self, shopify_order_id: str) -> Dict:
        """Get sync status of a specific order."""
        try:
            # Get Shopify order
            shopify_order = self.shopify_client.get_order(shopify_order_id)
            if not shopify_order:
                return {"status": "not_found", "message": "Order not found in Shopify"}

            # Try to find corresponding SAP order
            # This needs to be enhanced with proper mapping logic
            sap_orders = self.sap_client.query_orders(
                f"U_ShopifyOrderId eq '{shopify_order_id}'")
            
            if not sap_orders:
                return {
                    "status": "pending_sync",
                    "shopify_status": shopify_order.get('financial_status', 'unknown'),
                    "sap_status": None
                }

            sap_order = sap_orders[0]
            return {
                "status": "synced",
                "shopify_status": shopify_order.get('financial_status', 'unknown'),
                "sap_status": sap_order.get('DocStatus', 'unknown'),
                "sap_doc_entry": sap_order.get('DocEntry')
            }

        except Exception as e:
            logger.error(f"Failed to get order status: {str(e)}")
            return {"status": "error", "message": str(e)}

    def describe_structure(self) -> Dict:
        """Describe the order structure in both systems."""
        try:
            with open("definitions/shopify/order_fields.json", "r") as f:
                shopify_fields = json.load(f)
            with open("definitions/sap/order_fields.json", "r") as f:
                sap_fields = json.load(f)
            
            return {
                "shopify": shopify_fields,
                "sap": sap_fields,
                "sync_direction": "shopify_to_sap"
            }
        except Exception as e:
            logger.error(f"Failed to load field definitions: {str(e)}")
            raise
