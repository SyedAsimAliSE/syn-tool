
import os
import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from ..core.config import SAPConfig
from ..utils.logging import get_logger
import loguru
import random
logger = get_logger(__name__)

class SAPClient:

    def __init__(self, config: SAPConfig):
        """Initialize SAP client."""
        self.config = config
        self.service_layer_url = self.config.service_layer_url or self.config.api_url
        self.session = None
        self.session_id = None
        self.warehouse = config.warehouse
        self._setup_session()
    
    def _setup_session(self) -> None:
        try:
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json'
            })
            
            if not self.config.verify_ssl:
                requests.packages.urllib3.disable_warnings(
                    requests.packages.urllib3.exceptions.InsecureRequestWarning
                )
                self.session.verify = False
            
            if not self._login():
                raise ConnectionError("Failed to log into SAP")
                
            logger.info("Successfully connected to SAP")
            
        except Exception as e:
            logger.error(f"Failed to set up SAP session: {str(e)}")
            raise
    
    def _login(self) -> bool:
        try:
            login_data = {
                'CompanyDB': self.config.company_db,
                'UserName': self.config.username,
                'Password': self.config.password
            }
            
            response = self.session.post(
                f"{self.config.api_url}/Login",
                json=login_data,
                verify=self.config.verify_ssl
            )
            
            if response.status_code == 200:
                self.session_id = response.cookies.get('B1SESSION')
                self.session.cookies.update(response.cookies)
                return True
            
            logger.error(f"Login failed with status code {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Send GET request to SAP API.
        
        Args:
            endpoint: API endpoint
            params: Optional query parameters
            
        Returns:
            Response data as dictionary
        """
        try:
            response = self.session.get(
                self._build_url(endpoint),
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GET request failed: {str(e)}")
            raise

    def post(self, endpoint: str, data: Dict) -> Dict:
        """Send POST request to SAP API.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            
        Returns:
            Response data as dictionary
        """
        try:
            url = self._build_url(endpoint)
            logger.info(f"Making POST request to URL: {url}")
            logger.info(f"Request data: {json.dumps(data, indent=2)}")
            
            response = self.session.post(
                url,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"POST request failed: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise

    def patch(self, endpoint: str, data: Dict) -> Dict:
        """Send PATCH request to SAP API.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            
        Returns:
            Response data as dictionary
        """
        try:
            url = self._build_url(endpoint)
            logger.info(f"Making PATCH request to URL: {url}")
            logger.info(f"Request data: {json.dumps(data, indent=2)}")
            
            response = self.session.patch(
                url,
                json=data
            )
            response.raise_for_status()
            
            if response.status_code == 204 or not response.text:
                return {}
            return response.json()
            
        except Exception as e:
            logger.error(f"PATCH request failed: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise

    def delete(self, endpoint: str) -> None:
        """Send DELETE request to SAP API.
        
        Args:
            endpoint: API endpoint
        """
        try:
            response = self.session.delete(
                self._build_url(endpoint)
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"DELETE request failed: {str(e)}")
            raise

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for SAP API endpoint."""
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
            
        url = f"{self.service_layer_url}{endpoint}"
        logger.debug(f"Built URL: {url}")
        return url

    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Optional[Dict]:
        """Make a request to the SAP API with retries."""
        if not self._is_session_valid():
            if not self._login():
                return None
                
        url = self._build_url(endpoint)
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                # Log request details
                logger.debug(f"Making {method} request to {url}")
                if data:
                    logger.debug(f"Request payload: {json.dumps(data, indent=2)}")
                if params:
                    logger.debug(f"Request params: {json.dumps(params, indent=2)}")
                
                if method == 'GET':
                    response = self.session.get(url, params=params, verify=self.config.verify_ssl)
                elif method == 'POST':
                    response = self.session.post(url, json=data, verify=self.config.verify_ssl)
                elif method == 'PATCH':
                    response = self.session.patch(url, json=data, verify=self.config.verify_ssl)
                elif method == 'DELETE':
                    response = self.session.delete(url, verify=self.config.verify_ssl)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                    
                if response.status_code in [200, 201, 204]:
                    if response.text:  # Only try to parse JSON if there's content
                        try:
                            return response.json()
                        except ValueError:
                            logger.error(f"Invalid JSON response: {response.text}")
                            return None
                    return {}
                    
                error_msg = "Unknown error"
                try:
                    error_data = response.json() if response.text else {}
                    if isinstance(error_data, dict):
                        error_msg = error_data.get('error', {}).get('message', response.text)
                except ValueError:
                    error_msg = response.text
                
                logger.error(f"Request failed: {response.status_code} {response.reason}")
                logger.error(f"Error details: {error_msg}")
                
                if response.status_code == 404:
                    return None
                    
                last_error = response
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(retry_count * 2)  # Exponential backoff
                continue
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Error response: {e.response.text}")
                last_error = e
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(retry_count * 2)
                continue
                
        if last_error is not None:
            if isinstance(last_error, requests.exceptions.RequestException):
                logger.error(f"All {max_retries} request attempts failed. Last error: {str(last_error)}")
            else:
                logger.error(f"All {max_retries} request attempts failed. Last status: {last_error.status_code}")
        return None

    def _is_session_valid(self) -> bool:
        """Check if the current session is still valid."""
        try:
            if not self.session or not self.session_id:
                return False
                
            response = self.session.get(
                self._build_url('/BusinessPartners?$top=1'),
                verify=self.config.verify_ssl
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error checking session validity: {str(e)}")
            return False

    def get_items(self) -> List[Dict]:
        """Get all items from SAP.
        
        Returns:
            List of all items in the system
        """
        try:
            endpoint = f"{self.config.service_layer_url}/Items"
            response = self.session.get(endpoint)
            if response.status_code != 200:
                logger.error(f"SAP API Error: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            items = response.json().get('value', [])
            logger.debug(f"Retrieved {len(items)} items from SAP")
            
            if items:
                logger.debug(f"Available fields in first item: {list(items[0].keys())}")
                logger.debug(f"Sample item: {items[0]}")
            
            price_list_endpoint = f"{self.config.service_layer_url}/PriceLists(1)"
            price_list_response = self.session.get(price_list_endpoint)
            if price_list_response.status_code == 200:
                logger.debug(f"Price list response: {price_list_response.json()}")
            else:
                logger.warning(f"Failed to get price list: {price_list_response.status_code} - {price_list_response.text}")
            
            return items
            
        except Exception as e:
            logger.error(f"Error getting SAP items: {str(e)}")
            raise

    def get_groups(self, group_id: Optional[str] = None, name: Optional[str] = None) -> List[Dict]:
        """Get item groups from SAP.
        
        Args:
            group_id: Optional group ID to filter by
            name: Optional group name to filter by
            
        Returns:
            List of groups matching the criteria
        """
        try:
            params = {}
            
            filters = []
            if group_id:
                try:
                    numeric_id = int(group_id)
                    filters.append(f"Number eq {numeric_id}")
                except ValueError:
                    logger.error(f"Invalid group ID format: {group_id}. Must be a number.")
                    raise ValueError(f"Group ID must be a number, got: {group_id}")
                    
            if name:
                filters.append(f"GroupName eq '{name}'")
            if filters:
                params['$filter'] = ' and '.join(filters)
                
            response = self._make_request('GET', 'ItemGroups', params=params)
            if response and 'value' in response:
                groups = response['value']
                logger.debug(f"Raw SAP groups response: {json.dumps(groups, indent=2)}")
                return groups
            return []
            
        except Exception as e:
            logger.error(f"Error getting SAP groups: {str(e)}")
            raise

    def get_group_items(self, group_id: Optional[str] = None, name: Optional[str] = None) -> List[Dict]:
        """Get items within a group from SAP.
        
        Args:
            group_id: Optional group ID to filter by
            name: Optional group name to filter by
            
        Returns:
            List of items in the group
        """
        try:
            if name and not group_id:
                groups = self.get_groups(name=name)
                if not groups:
                    raise ValueError(f"No group found with name: {name}")
                group_id = groups[0]['Number']
            
            if not group_id:
                raise ValueError("Either group_id or name must be provided")

            params = {
                '$select': 'ItemCode,ItemName,ItemsGroupCode,QuantityOnStock',
                '$filter': f"ItemsGroupCode eq {int(group_id)}"
            }
            
            response = self._make_request('GET', 'Items', params=params)
            
            if not response or 'value' not in response:
                logger.warning(f"No items found in group {group_id}")
                return []
            
            items = response['value']
            logger.debug(f"Found {len(items)} items in group {group_id}")
            
            formatted_items = []
            for item in items:
                try:
                    item_code = item.get('ItemCode', '')
                    
                    item_details = self._make_request('GET', f'Items(\'{item_code}\')')
                    if not item_details:
                        logger.warning(f"Could not get details for item {item_code}")
                        continue
                        
                    price_response = self._make_request('GET', f'Items(\'{item_code}\')/ItemPrices')
                    price = '0.00'
                    if price_response and 'value' in price_response:
                        for price_list in price_response['value']:
                            if price_list.get('PriceList') == 1:  # Assuming 1 is the default price list
                                price = str(price_list.get('Price', '0.00'))
                                break
                    
                    formatted_item = {
                        'ItemCode': item_code,
                        'ItemName': item.get('ItemName', ''),
                        'SKU': item_code,  # Using ItemCode as SKU
                        'Price': price,
                        'Quantity': item.get('QuantityOnStock', 0),
                        'Description': item_details.get('User_Text', '')  # Standard SAP field for description
                    }
                    
                    for key, value in item_details.items():
                        if key.startswith('U_'):
                            formatted_item[key] = value
                            
                    formatted_items.append(formatted_item)
                    
                except Exception as e:
                    logger.error(f"Error getting details for item {item.get('ItemCode')}: {str(e)}")
                    continue
                    
            return formatted_items
            
        except Exception as e:
            logger.error(f"Error getting SAP group items: {str(e)}")
            raise

    def _get_udf_info(self, table_name: str, field_name: str) -> dict:
        """Get information about a User-Defined Field (UDF).
        
        Args:
            table_name (str): The SAP table name (e.g., 'OCRD' for Business Partners)
            field_name (str): The UDF name (with or without 'U_' prefix)
            
        Returns:
            dict: UDF information if found, None otherwise
        """
        try:
            field_name = field_name.replace('U_', '')
            
            response = self.session.get(
                f"{self.service_layer_url}/UserFieldsMD?$filter=TableName eq '{table_name}' and Name eq '{field_name}'"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('value') and len(data['value']) > 0:
                    return data['value'][0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting UDF info: {str(e)}")
            return None

    def create_udf(self, table_name: str, field_name: str, field_type: str,
                 field_size: int = 50, field_description: str = None,
                 mandatory: bool = False) -> Optional[Dict]:
        """Create a User-Defined Field (UDF) in SAP."""
        try:
            field_name = field_name.replace('U_', '')
            
            sap_type_map = {
                'String': 'db_Alpha',
                'Alpha': 'db_Alpha',
                'Number': 'db_Numeric',
                'Numeric': 'db_Numeric',
                'Date': 'db_Date',
                'Boolean': 'db_Alpha',  # SAP uses 'tYES'/'tNO' for booleans
                'Memo': 'db_Memo'
            }
            sap_field_type = sap_type_map.get(field_type, 'db_Alpha')
            
            udf_data = {
                "Name": field_name,
                "Type": sap_field_type,
                "Size": min(254, field_size),  # Ensure size is within legal range
                "Description": field_description or field_name,
                "SubType": "st_None",  # Use proper SAP subtype
                "TableName": table_name,
                "Mandatory": "tYES" if mandatory else "tNO",  # Use SAP's boolean format
                "DefaultValue": ""
            }
            
            logger.info(f"Creating UDF with data: {udf_data}")
            response = self.session.post(
                f"{self.service_layer_url}/UserFieldsMD",
                json=udf_data
            )
            
            if response.status_code in [201, 200]:
                logger.info(f"Successfully created UDF: {field_name}")
                return response.json()
            else:
                logger.error(f"Failed to create UDF. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating UDF: {str(e)}")
            return None

    def delete_udf(self, table_name: str, field_name: str) -> bool:
        """Delete a User-Defined Field (UDF) from SAP.
        
        Args:
            table_name: Name of the table containing the UDF
            field_name: Name of the UDF to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not field_name.startswith('U_'):
                field_name = f'U_{field_name}'
                
            udf_info = self._get_udf_info(table_name, field_name)
            if not udf_info:
                logger.info(f"UDF {field_name} does not exist in table {table_name}")
                return True
                
            field_id = udf_info.get('FieldID')
            if not field_id:
                logger.error(f"Could not get FieldID for UDF {field_name}")
                return False
                
            response = self._make_request('DELETE', f'UserFieldsMD({field_id})')
            
            if response.status_code == 204:
                logger.info(f"Successfully deleted UDF {field_name} from table {table_name}")
                return True
            
            logger.error(f"Failed to delete UDF {field_name} from table {table_name}. Status code: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting UDF {field_name} from table {table_name}: {str(e)}")
            return False

    def upsert_group(self, group_data: Dict[str, Any]) -> Optional[Dict]:
        """Create or update an item group in SAP Business One.
        
        Args:
            group_data: Group data dictionary
            
        Returns:
            Optional[Dict[str, Any]]: Created/updated group data if successful, None otherwise
        """
        try:
            if not group_data.get('Number') or not group_data.get('GroupName'):
                logger.error("Group Number and GroupName are required")
                return None

            existing_groups = self.get_groups(group_id=group_data.get('Number'))
            
            group_payload = {
                "Number": group_data.get("Number"),
                "GroupName": group_data.get("GroupName"),
                "ProcurementMethod": "bom_Buy",
                "InventorySystem": "bis_MovingAverage",
                "PlanningSystem": "bop_None",
                "Alert": "tNO",
                "ItemClass": "itcMaterial",
                "RawMaterial": "tNO",
                "UoMGroupEntry": 1,  # Default UoM group
                "InventoryUoMEntry": 1,  # Default inventory UoM
                "DefaultSalesUoMEntry": 1,  # Default sales UoM
                "DefaultPurchasingUoMEntry": 1,  # Default purchasing UoM
                "ManageSerialNumbers": "tNO",
                "ManageBatchNumbers": "tNO",
                "Valid": "tYES",
                "ValidFrom": datetime.now().strftime("%Y-%m-%d"),
                "ValidTo": "2099-12-31",
                "PricingUnit": 1,
                "QuantityOnStock": 0,
                "WhsInfo": [
                    {
                        "WarehouseCode": self.warehouse
                    }
                ]
            }
            
            for key, value in group_data.items():
                if key.startswith('U_'):
                    group_payload[key] = value

            if existing_groups:
                # Update existing group
                group_id = existing_groups[0]['Number']
                return self._make_request('PATCH', f'ItemGroups({group_id})', data=group_payload)
            else:
                # Create new group
                return self._make_request('POST', 'ItemGroups', data=group_payload)
                
        except Exception as e:
            logger.error(f"Error upserting group: {str(e)}")
            return None

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an order in SAP.
        
        Args:
            order_data: Order data in SAP format
            
        Returns:
            Created order data from SAP
        """
        endpoint = 'Orders'
        try:
            response = self.post(endpoint, order_data)
            logger.info(f"Successfully created order in SAP: {response.get('DocEntry')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create order in SAP: {str(e)}")
            raise

    def get_order(self, doc_entry: int) -> Optional[Dict[str, Any]]:
        """Get an order from SAP by DocEntry.
        
        Args:
            doc_entry: The DocEntry of the order
            
        Returns:
            Order data if found, None otherwise
        """
        endpoint = f'/Orders({doc_entry})'
        try:
            return self._make_request('GET', endpoint)
        except Exception as e:
            logger.error(f"Failed to get order {doc_entry} from SAP: {str(e)}")
            return None

    def update_order(self, doc_entry: int, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an order in SAP.
        
        Args:
            doc_entry: The DocEntry of the order to update
            order_data: Updated order data
            
        Returns:
            Updated order data
        """
        endpoint = f'/Orders({doc_entry})'
        try:
            response = self._make_request('PATCH', endpoint, data=order_data)
            logger.info(f"Successfully updated order {doc_entry} in SAP")
            return response
        except Exception as e:
            logger.error(f"Failed to update order {doc_entry} in SAP: {str(e)}")
            raise

    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create payment in SAP."""
        try:
            return self._make_request('POST', 'IncomingPayments', data=payment_data)
        except Exception as e:
            logger.error(f"Failed to create payment: {str(e)}")
            raise
    
    def create_credit_memo(self, credit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create credit memo in SAP."""
        try:
            return self._make_request('POST', 'CreditNotes', data=credit_data)
        except Exception as e:
            logger.error(f"Failed to create credit memo: {str(e)}")
            raise
    
    def create_refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create refund in SAP."""
        try:
            return self._make_request('POST', 'VendorPayments', data=refund_data)
        except Exception as e:
            logger.error(f"Failed to create refund: {str(e)}")
            raise

    def query_orders(self, query: str) -> List[Dict[str, Any]]:
        """Query orders in SAP using OData filter.
        
        Args:
            query: OData filter query
            
        Returns:
            List of matching orders
        """
        try:
            params = {'$filter': query}
            response = self.get('Orders', params=params)
            return response.get('value', [])
        except Exception as e:
            logger.error(f"Failed to query orders: {str(e)}")
            return []

    def query_items(self, query_params: Dict) -> List[Dict]:
        """Query items from SAP.
        
        Args:
            query_params: OData query parameters
            
        Returns:
            List of items matching the query
        """
        endpoint = '/Items'
        try:
            response = self.get(endpoint, params=query_params)
            return response.get('value', [])
        except Exception as e:
            logger.error(f"Failed to query items from SAP: {str(e)}")
            return []
            
    def query_business_partners(self, query_params: Dict) -> List[Dict]:
        """Query business partners from SAP."""
        try:
            if '$filter' in query_params:
                filter_value = query_params['$filter'].replace("'", "")
                
                if 'U_ShopifyCustomerId eq' in filter_value:
                    value = filter_value.split('eq')[1].strip()
                    query_params['$filter'] = f"U_ShopifyCustomerId eq '{value}'"
                    
            logger.debug(f"Making request with params: {query_params}")
            response = self.get('/BusinessPartners', params=query_params)
            return response.get('value', []) if response else []
                
        except Exception as e:
            logger.error(f"Failed to query business partners from SAP: {str(e)}")
            return []

    def query_vat_groups(self, query_params: Dict) -> List[Dict]:
        """Query VAT groups (tax codes) from SAP.
        
        Args:
            query_params: OData query parameters
            
        Returns:
            List of VAT groups matching the query
        """
        try:
            response = self.get('VatGroups', params=query_params)
            if response and 'value' in response:
                return response['value']
            return []
        except Exception as e:
            logger.error(f"Failed to query VAT groups: {str(e)}")
            return []

    def create_business_partner(self, customer_data: dict) -> Optional[str]:
        """Create a business partner in SAP.
        
        Args:
            customer_data: Customer data dictionary
            
        Returns:
            str: CardCode if successful, None otherwise
        """
        try:
            customer_payload = {
                "CardCode": customer_data.get("CardCode"),
                "CardName": customer_data.get("CardName"),
                "CardType": "cCustomer",
                "GroupCode": 100,
                "Series": int(os.getenv('SAP_CUSTOMER_SERIES', '92')),
                "EmailAddress": customer_data.get("EmailAddress"),
                "Phone1": customer_data.get("Phone1", ""),
                "Valid": "tYES",
                "ValidFrom": datetime.now().strftime("%Y-%m-%d"),
                "ValidTo": "2099-12-31"
            }
            
            if customer_data.get("BillToAddress"):
                customer_payload["BillToAddress"] = customer_data["BillToAddress"]
                
            for key, value in customer_data.items():
                if key.startswith('U_'):
                    customer_payload[key] = value
            
            logger.info(f"Creating business partner with data: {json.dumps(customer_payload, indent=2)}")
            response = self._make_request('POST', 'BusinessPartners', data=customer_payload)
            
            if response:
                logger.info(f"Business partner creation response: {json.dumps(response, indent=2)}")
                return customer_payload.get('CardCode')
            logger.error("Business partner creation failed with no response")
            return None
            
        except Exception as e:
            logger.error(f"Failed to create business partner. Status: {str(e)}")
            return None

    def update_business_partner(self, card_code: str, update_data: Dict) -> Optional[Dict]:
        """Update a business partner in SAP."""
        try:
            logger.info(f"Updating business partner {card_code}")
            logger.debug(f"Update data: {json.dumps(update_data, indent=2)}")
            
            response = self.patch(f'BusinessPartners(\'{card_code}\')', update_data)
            if response:
                logger.info(f"Successfully updated business partner {card_code}")
                return response
                
            logger.error(f"Failed to update business partner {card_code}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to update business partner in SAP: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"SAP Error Response: {e.response.text}")
            return None

    def _ensure_udfs_exist(self) -> bool:
        """Ensure all required User-Defined Fields (UDFs) exist in SAP.
        
        Returns:
            bool: True if all UDFs exist or were created successfully, False otherwise
        """
        try:
            udf_info = self._get_udf_info('OCRD', 'U_ShopifyCustomerId')
            logger.info(f"ShopifyCustomerId UDF info: {udf_info}")
            
            if not udf_info:
                shopify_customer_udf = self.create_udf(
                    table_name='OCRD',  # Business Partners table
                    field_name='ShopifyCustomerId',
                    field_type='Alpha',  # Use Alpha type explicitly
                    field_size=100,  # Increase size to handle longer IDs
                    field_description='Shopify Customer ID',
                    mandatory=False
                )
                
                if not shopify_customer_udf:
                    logger.error("Failed to create ShopifyCustomerId UDF")
                    return False
                
                time.sleep(2)
                
                if not self._get_udf_info('OCRD', 'U_ShopifyCustomerId'):
                    logger.error("Failed to verify ShopifyCustomerId UDF creation")
                    return False

            udf_info = self._get_udf_info('OITM', 'U_ShopifyProductId')
            logger.info(f"ShopifyProductId UDF info: {udf_info}")
            
            if not udf_info:
                shopify_product_udf = self.create_udf(
                    table_name='OITM',  # Items table
                    field_name='ShopifyProductId',
                    field_type='Alpha',  # Use Alpha type explicitly
                    field_size=100,  # Increase size to handle longer IDs
                    field_description='Shopify Product ID',
                    mandatory=False
                )
                
                if not shopify_product_udf:
                    logger.error("Failed to create ShopifyProductId UDF")
                    return False
                
                # Wait for UDF to be fully created
                time.sleep(2)
                
                if not self._get_udf_info('OITM', 'U_ShopifyProductId'):
                    logger.error("Failed to verify ShopifyProductId UDF creation")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring UDFs exist: {str(e)}")
            return False

    def get_numbering_series(self) -> Optional[dict]:
        """Get the numbering series for business partners."""
        try:
            response = self.session.post(
                f"{self.service_layer_url}/SeriesService_GetDocumentSeries",
                json={
                    "DocumentTypeParams": {
                        "Document": "2",  # 2 is for Business Partners
                        "DocumentSubType": "C"  # C for Customer
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if 'value' not in data:
                logger.error(f"No series found for business partners. Response: {data}")
                return None
                
            active_series = [s for s in data['value'] if s.get('Locked') == 'tNO' and s.get('IsManual') == 'tNO']
            if not active_series:
                logger.error("No active non-manual series found for business partners")
                return None
                
            cust_series = next((s for s in active_series if s.get('Name') == 'Cust'), active_series[0])
            logger.info(f"Using numbering series: {cust_series}")
            return cust_series
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get numbering series. Status: {e.response.status_code}, Response: {e.response.text}")
            return None

    def create_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        """Create an item in SAP.
        
        Args:
            item_data: Item data dictionary
            
        Returns:
            str: ItemCode if successful, None otherwise
        """
        try:
            item_payload = {
                "ItemCode": item_data.get("ItemCode"),
                "ItemName": item_data.get("ItemName"),
                "ItemType": "itItems",
                "ItemsGroupCode": 100,
                "InventoryItem": "tYES",
                "SalesItem": "tYES",
                "PurchaseItem": "tYES",
                "Valid": "tYES",
                "ValidFrom": datetime.now().strftime("%Y-%m-%d"),
                "ValidTo": "2099-12-31",
                "QuantityOnStock": 0,
                "ItemWarehouseInfoCollection": [
                    {
                        "WarehouseCode": self.warehouse
                    }
                ]
            }
            
            logger.info(f"Creating item with data: {json.dumps(item_payload, indent=2)}")
            response = self._make_request('POST', 'Items', data=item_payload)
            
            if response:
                return item_payload.get('ItemCode')
            return None
            
        except Exception as e:
            logger.error(f"Failed to create item. Status: {str(e)}")
            return None

    def update_item(self, item_code: str, update_data: Dict[str, Any]) -> Optional[Dict]:
        """Update an item in SAP.
        
        Args:
            item_code: ItemCode of the item to update
            update_data: Updated item data
            
        Returns:
            Dict: Updated item data if successful, None otherwise
        """
        try:
            logger.info(f"Updating item {item_code}")
            logger.debug(f"Update data: {json.dumps(update_data, indent=2)}")
            
            response = self._make_request('PATCH', f'Items(\'{item_code}\')', data=update_data)
            if response:
                logger.info(f"Successfully updated item {item_code}")
                return response
                
            logger.error(f"Failed to update item {item_code}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to update item in SAP: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"SAP Error Response: {e.response.text}")
            return None
