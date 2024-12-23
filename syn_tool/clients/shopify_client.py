"""Shopify API client."""

import os
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..core.config import ShopifyConfig
from syn_tool.utils.logging import get_logger

logger = get_logger(__name__)

class ShopifyClient:
    """Client for Shopify API communication."""
    
    def __init__(self, config: ShopifyConfig):
        """Initialize Shopify client."""
        self.config = config
        self.shop_url = config.shop_url  # Add this line to store shop_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.config.access_token,
            'Accept': 'application/json'  # Explicitly request JSON response
        })
        self._setup_session()
    
    def _setup_session(self) -> None:
        """Set up the Shopify API session."""
        try:
            # Test the connection
            response = self.get('shop.json')
            logger.info(f"Successfully connected to Shopify with response: {response}")
        except Exception as e:
            logger.error(f"Failed to connect to Shopify: {str(e)}")
            raise

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for Shopify API endpoint."""
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        url = f"https://{self.config.shop_url}/admin/api/2024-01/{endpoint}"
        logger.debug(f"Built URL: {url}")
        return url

    def _handle_response(self, response: requests.Response) -> Dict:
        """Handle API response and extract data.
        
        Args:
            response: Response from Shopify API
            
        Returns:
            Response data as dictionary
            
        Raises:
            Exception if response is invalid
        """
        try:
            response.raise_for_status()
            
            if not response.text:
                logger.error("Empty response from Shopify")
                return {}
            
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                logger.error(f"Unexpected content type: {content_type}")
                logger.error(f"Response text: {response.text[:500]}")  # Log first 500 chars
                raise Exception("Invalid response format")
            
            self._last_response = response
            
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {str(e)}")
            logger.error(f"Response status: {response.status_code}")
            logger.error(f"Response headers: {response.headers}")
            logger.error(f"Response text: {response.text[:500]}")  # Log first 500 chars
            raise
        except Exception as e:
            logger.error(f"Failed to handle response: {str(e)}")
            raise

    def get_next_page_info(self) -> Optional[str]:
        """Get the next page info from the Link header of the last response.
        
        Returns:
            Next page info token or None if no next page
        """
        if not hasattr(self, '_last_response'):
            return None
            
        link_header = self._last_response.headers.get('Link')
        if not link_header:
            return None
            
        links = link_header.split(',')
        for link in links:
            if 'rel="next"' in link:
                import re
                match = re.search(r'page_info=([^&>]+)', link)
                if match:
                    return match.group(1)
        return None

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Send GET request to Shopify API.
        
        Args:
            endpoint: API endpoint
            params: Optional query parameters
            
        Returns:
            Response data as dictionary
        """
        try:
            url = self._build_url(endpoint)
            response = self.session.get(url, params=params)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"GET request failed: {str(e)}")
            raise

    def post(self, endpoint: str, data: Dict) -> Dict:
        """Send POST request to Shopify API.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            
        Returns:
            Response data as dictionary
        """
        try:
            url = self._build_url(endpoint)
            response = self.session.post(url, json=data)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"POST request failed: {str(e)}")
            raise

    def put(self, endpoint: str, data: Dict) -> Dict:
        """Send PUT request to Shopify API.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            
        Returns:
            Response data as dictionary
        """
        try:
            url = self._build_url(endpoint)
            response = self.session.put(url, json=data)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"PUT request failed: {str(e)}")
            raise

    def delete(self, endpoint: str) -> None:
        """Send DELETE request to Shopify API.
        
        Args:
            endpoint: API endpoint
        """
        try:
            url = self._build_url(endpoint)
            response = self.session.delete(url)
            self._handle_response(response)
        except Exception as e:
            logger.error(f"DELETE request failed: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """Test the connection to Shopify."""
        try:
            response = self.get('shop.json')
            logger.info(f"Successfully connected to Shopify shop: {response['shop']['name']}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Shopify: {str(e)}")
            return False

    def get_products(self) -> List[Dict]:
        """Get all products from Shopify.
        
        Returns:
            List of products
        """
        try:
            params = {'limit': 250}  # Maximum allowed by Shopify
            response = self.get('products.json', params=params)
            products = response.get('products', [])
            logger.debug(f"Retrieved {len(products)} products from Shopify")
            
            return products
            
        except Exception as e:
            logger.error(f"Failed to get products: {str(e)}")
            raise

    def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create product in Shopify."""
        try:
            response = self.post('products.json', {'product': product_data})
            return response['product']
        except Exception as e:
            logger.error(f"Failed to create product: {str(e)}")
            raise

    def update_product(self, product_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update product in Shopify."""
        try:
            response = self.put(f'products/{product_id}.json', {'product': product_data})
            return response['product']
        except Exception as e:
            logger.error(f"Failed to update product: {str(e)}")
            raise

    def get_orders(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get orders from Shopify.
        
        Args:
            status: Filter by order financial status (paid, unpaid, pending)
            limit: Maximum number of orders to retrieve
            
        Returns:
            List of orders
        """
        params = {'limit': limit}
        if status:
            params['financial_status'] = status
            
        response = self.get('orders.json', params=params)
        return response.get('orders', [])

    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get a specific order from Shopify.
        
        Args:
            order_id: The order ID
            
        Returns:
            Order data if found, None otherwise
        """
        try:
            response = self.get(f'orders/{order_id}.json')
            return response.get('order')
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {str(e)}")
            return None

    def get_transactions(self, order_id: str) -> List[Dict[str, Any]]:
        """Get transactions for an order."""
        try:
            response = self.get(f'orders/{order_id}/transactions.json')
            return response['transactions']
        except Exception as e:
            logger.error(f"Failed to get transactions for order {order_id}: {str(e)}")
            raise

    def get_refunds(self, last_modified: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get refunds from Shopify."""
        try:
            refunds = []
            orders = self.get_orders(last_modified)
            
            for order in orders:
                order_id = order['id']
                order_refunds = self.get(f'orders/{order_id}/refunds.json')
                if order_refunds['refunds']:
                    refunds.extend([
                        {**refund, 'order_id': order_id}
                        for refund in order_refunds['refunds']
                    ])
            
            return refunds
        except Exception as e:
            logger.error(f"Failed to get refunds: {str(e)}")
            raise

    def get_collections(self, collection_id: Optional[str] = None, title: Optional[str] = None) -> List[Dict]:
        """Get collections from Shopify.
        
        Args:
            collection_id: Optional collection ID to filter by
            title: Optional collection title to filter by
            
        Returns:
            List of collections
        """
        try:
            if collection_id:
                response = self.get(f'custom_collections/{collection_id}.json')
                return [response['custom_collection']] if response else []
                
            endpoint = 'custom_collections.json'
            params = {}
            
            if title:
                params['title'] = title
                
            response = self.get(endpoint, params=params)
            return response.get('custom_collections', [])
            
        except Exception as e:
            logger.error(f"Error getting Shopify collections: {str(e)}")
            raise

    def get_collection_products(self, collection_id: Optional[str] = None, title: Optional[str] = None) -> List[Dict]:
        """Get products within a collection from Shopify.
        
        Args:
            collection_id: Optional collection ID to filter by
            title: Optional collection title to filter by
            
        Returns:
            List of products in the collection
        """
        try:
            if title and not collection_id:
                collections = self.get_collections(title=title)
                if not collections:
                    raise ValueError(f"No collection found with title: {title}")
                collection_id = collections[0]['id']
            
            if not collection_id:
                raise ValueError("Either collection_id or title must be provided")
                
            endpoint = f'collections/{collection_id}/products.json'
            response = self.get(endpoint)
            
            return response.get('products', [])
            
        except Exception as e:
            logger.error(f"Error getting Shopify collection products: {str(e)}")
            raise

    def get_product_collections(self, product_id: str) -> List[Dict]:
        """Get collections that contain a specific product.
        
        Args:
            product_id: Product ID to find collections for
            
        Returns:
            List of collections containing the product
        """
        try:
            endpoint = 'collects.json'
            params = {'product_id': product_id}
            response = self.get(endpoint, params=params)
            collects = response.get('collects', [])
            
            collections = []
            for collect in collects:
                collection_id = collect['collection_id']
                try:
                    collection_response = self.get(f'custom_collections/{collection_id}.json')
                    if 'custom_collection' in collection_response:
                        collections.append(collection_response['custom_collection'])
                        continue
                except Exception:
                    pass
                    
                try:
                    smart_collection_response = self.get(f'smart_collections/{collection_id}.json')
                    if 'smart_collection' in smart_collection_response:
                        collections.append(smart_collection_response['smart_collection'])
                except Exception:
                    pass
            
            return collections
            
        except Exception as e:
            logger.error(f"Error getting collections for product {product_id}: {str(e)}")
            return []

    def upsert_collection(self, collection_data: Dict) -> str:
        """Create or update a collection in Shopify.
        
        Args:
            collection_data: Collection data to create/update
            
        Returns:
            Collection ID
        """
        try:
            collection_id = collection_data.get('id')
            
            if collection_id:
                response = self.put(
                    f'custom_collections/{collection_id}.json',
                    {'custom_collection': collection_data}
                )
                return str(response['custom_collection']['id'])
            else:
                response = self.post(
                    'custom_collections.json',
                    {'custom_collection': collection_data}
                )
                return str(response['custom_collection']['id'])
            
        except Exception as e:
            logger.error(f"Error upserting Shopify collection: {str(e)}")
            raise

    def upsert_product(self, product_data: Dict, collection_id: Optional[str] = None) -> str:
        """Create or update a product in Shopify.
        
        Args:
            product_data: Product data to create/update
            collection_id: Optional collection ID to add the product to
            
        Returns:
            Product ID
        """
        try:
            product_id = product_data.get('id')
            
            if product_id:
                response = self.put(
                    f'products/{product_id}.json',
                    {'product': product_data}
                )
            else:
                response = self.post(
                    'products.json',
                    {'product': product_data}
                )
                
            product_id = str(response['product']['id'])
            
            if collection_id:
                self.post(
                    'collect.json',
                    {
                        'collect': {
                            'product_id': product_id,
                            'collection_id': collection_id
                        }
                    }
                )
                
            return product_id
            
        except Exception as e:
            logger.error(f"Error upserting Shopify product: {str(e)}")
            raise

    def get_customer(self, customer_id: str) -> Optional[Dict]:
        """Get a customer by ID from Shopify.
        
        Args:
            customer_id: The Shopify customer ID
            
        Returns:
            Dict containing customer data or None if not found
        """
        try:
            response = self.get(f'customers/{customer_id}.json')
            if not response:
                return None
                
            return response.get('customer', {})
            
        except Exception as e:
            logger.error(f"Error getting customer {customer_id}: {str(e)}")
            return None
