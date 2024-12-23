"""
Service for handling synchronization of SAP Item Groups and Shopify Collections.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
from bs4 import BeautifulSoup
import random

from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_exponential
import os
import re

from ..core.exceptions import SyncValidationError, SyncTransformError
from ..core.types import Direction, SyncMode

logger = logging.getLogger(__name__)
console = Console()

class GroupService:
    """Service for handling SAP Item Groups and Shopify Collections synchronization."""

    def __init__(self, sap_client, shopify_client):
        """Initialize the group service.
        
        Args:
            sap_client: SAP B1 client instance
            shopify_client: Shopify client instance
        """
        self.sap_client = sap_client
        self.shopify_client = shopify_client
        self._load_definitions()

    def _load_definitions(self) -> None:
        """Load field definitions and mappings from JSON files."""
        definitions_dir = Path(__file__).parent.parent.parent / "definitions"
        
        with open(definitions_dir / "sap" / "group_fields.json") as f:
            self.sap_fields = json.load(f)
        
        with open(definitions_dir / "shopify" / "collection_fields.json") as f:
            self.shopify_fields = json.load(f)
        
        with open(definitions_dir / "mappings" / "group_mappings.json") as f:
            self.field_mappings = json.load(f)

    def describe_structure(self, source: str) -> None:
        """Display entity structure for SAP groups or Shopify collections.
        
        Args:
            source: Either 'sap' or 'shopify'
        """
        fields = self.sap_fields if source == 'sap' else self.shopify_fields
        
        table = Table(
            title=f"{'SAP Group' if source == 'sap' else 'Shopify Collection'} Structure"
        )
        table.add_column("Field", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Mandatory", style="red")
        table.add_column("Description", style="green")
        
        for field in fields.get('fields', []):
            table.add_row(
                field['name'],
                field['type'],
                '✓' if field.get('mandatory', False) else '',
                field.get('description', '')
            )
        
        console.print(table)

    def list_items(self, source: str, item_id: Optional[str] = None) -> None:
        """List groups/collections or show details of a specific item.
        
        Args:
            source: Either 'sap' or 'shopify'
            item_id: Optional ID to show specific item details
        """
        if source == 'sap':
            self._list_sap_groups(item_id)
        else:
            self._list_shopify_collections(item_id)

    def get_sap_groups(self) -> List[Dict]:
        """Get item groups from SAP with parent group information."""
        try:
            response = self.sap_client._make_request('GET', 'ItemGroups')
            if not response:
                return []
            
            groups = response.get('value', [])
            # Add parent group info
            for group in groups:
                if group.get('GroupName'):
                    parent_num = group.get('GroupNum')
                    if parent_num:
                        parent = next((g for g in groups if g.get('Number') == parent_num), None)
                        group['ParentGroup'] = parent.get('GroupName') if parent else None
            
            return groups
            
        except Exception as e:
            logger.error(f"Failed to get item groups: {str(e)}")
            raise

    def _list_sap_groups(self, group_id: Optional[str] = None) -> None:
        """List SAP groups or show specific group details."""
        try:
            if group_id:
                groups = self.get_sap_groups()
                group = next((g for g in groups if str(g.get('Number')) == group_id), None)
                if group:
                    self._display_sap_group_details(group)
                else:
                    console.print("[red]Group not found[/red]")
            else:
                groups = self.get_sap_groups()
                if not groups:
                    console.print("[yellow]No SAP item groups found[/yellow]")
                else:
                    self._display_sap_groups_list(groups)
        except Exception as e:
            logger.error(f"Error fetching SAP groups: {str(e)}")
            console.print(f"[red]Error fetching SAP groups: {str(e)}[/red]")

    def _list_shopify_collections(self, collection_id: Optional[str] = None) -> None:
        """List Shopify collections or show specific collection details."""
        try:
            if collection_id:
                collection = self._get_shopify_collection(collection_id)
                if collection:
                    self._display_shopify_collection_details(collection)
                else:
                    console.print("[red]Collection not found[/red]")
            else:
                custom_collections = self.shopify_client.get("/custom_collections")
                smart_collections = self.shopify_client.get("/smart_collections")
                
                custom = custom_collections.get('custom_collections', [])
                smart = smart_collections.get('smart_collections', [])
                
                if not custom and not smart:
                    console.print("[yellow]No Shopify collections found[/yellow]")
                else:
                    self._display_shopify_collections_list(custom, smart)
        except Exception as e:
            logger.error(f"Error fetching Shopify collections: {str(e)}")
            console.print(f"[red]Error fetching Shopify collections: {str(e)}[/red]")

    def _get_shopify_collection(self, collection_id: str) -> Optional[Dict]:
        """Get a specific Shopify collection, checking both custom and smart collections."""
        try:
            response = self.shopify_client.get(f"/custom_collections/{collection_id}")
            if response and 'custom_collection' in response:
                return response['custom_collection']
            
            response = self.shopify_client.get(f"/smart_collections/{collection_id}")
            if response and 'smart_collection' in response:
                return response['smart_collection']
            
            return None
        except Exception:
            return None

    def _display_sap_group_details(self, group: Dict) -> None:
        """Display detailed information about a specific SAP group."""
        table = Table(title="SAP Group Details")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        for field in self.sap_fields.get('fields', []):
            field_name = field['name']
            value = str(group.get(field_name, ''))
            table.add_row(field_name, value)
        
        console.print(table)

    def _display_shopify_collection_details(self, collection: Dict) -> None:
        """Display detailed information about a specific Shopify collection."""
        table = Table(title="Shopify Collection Details")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        for field in self.shopify_fields.get('fields', []):
            field_name = field['name']
            value = str(collection.get(field_name, ''))
            table.add_row(field_name, value)
        
        console.print(table)

    def _display_sap_groups_list(self, groups: List[Dict]) -> None:
        """Display list of SAP groups in a table."""
        table = Table(title="SAP Item Groups")
        table.add_column("Code", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Parent Group", style="yellow")
        
        for group in groups:
            table.add_row(
                str(group.get('Number', '')),
                str(group.get('GroupName', '')),
                str(group.get('ParentGroup', ''))
            )
        
        console.print(table)

    def _display_shopify_collections_list(self, custom: List[Dict], smart: List[Dict]) -> None:
        """Display list of Shopify collections in a table."""
        table = Table(title="Shopify Collections")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Published", style="magenta")
        
        for collection in custom:
            table.add_row(
                str(collection.get('id', '')),
                str(collection.get('title', '')),
                'Custom',
                '✓' if collection.get('published', False) else ''
            )
        
        for collection in smart:
            table.add_row(
                str(collection.get('id', '')),
                str(collection.get('title', '')),
                'Smart',
                '✓' if collection.get('published', False) else ''
            )
        
        console.print(table)

    def show_mappings(self) -> None:
        """Display field mappings between SAP groups and Shopify collections."""
        table = Table(title="Field Mappings")
        table.add_column("SAP Field", style="cyan")
        table.add_column("Shopify Field", style="magenta")
        table.add_column("Direction", style="yellow")
        table.add_column("Transform", style="green")
        
        for mapping in self.field_mappings.get('field_mappings', []):
            table.add_row(
                mapping['sap_field'],
                mapping['shopify_field'],
                mapping['direction'],
                mapping.get('transform', {}).get('type', 'direct')
            )
        
        console.print(table)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def validate(self, data: Dict, source: str) -> Tuple[bool, List[str]]:
        """Validate entity data against schema.
        
        Args:
            data: The data to validate
            source: Either 'sap' or 'shopify'
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        fields = self.sap_fields if source == 'sap' else self.shopify_fields
        errors = []
        
        for field in fields.get('fields', []):
            if field.get('mandatory', False):
                if field['name'] not in data:
                    errors.append(f"Missing required field: {field['name']}")
                    
        return len(errors) == 0, errors

    def transform(self, data: Dict, direction: str) -> Dict:
        """Transform entity data between systems.
        
        Args:
            data: The data to transform
            direction: Either 'sap-to-shopify' or 'shopify-to-sap'
            
        Returns:
            Transformed data
        """
        result = {}
        
        for mapping in self.field_mappings.get('field_mappings', []):
            if direction == 'sap-to-shopify':
                if mapping['direction'] in ['both', 'sap-to-shopify']:
                    source_field = mapping['sap_field']
                    target_field = mapping['shopify_field']
            else:
                if mapping['direction'] in ['both', 'shopify-to-sap']:
                    source_field = mapping['shopify_field']
                    target_field = mapping['sap_field']
                    
            if source_field in data:
                transform = mapping.get('transform', {})
                if transform.get('type') == 'custom':
                    # TODO: Implement custom transformations
                    pass
                else:
                    result[target_field] = data[source_field]
                    
        return result

    def sync(self, direction: str, mode: str = 'incremental') -> Dict:
        """Sync groups between SAP and Shopify.
        
        Args:
            direction: Either 'sap-to-shopify' or 'shopify-to-sap'
            mode: Either 'full' or 'incremental'
            
        Returns:
            Dict with sync results
        """
        try:
            if direction == 'sap-to-shopify':
                return self._sync_sap_to_shopify(mode)
            else:
                return self._sync_shopify_to_sap(mode)
        except Exception as e:
            logger.error(f"Error during sync: {str(e)}")
            raise

    def _sync_sap_to_shopify(self, mode: str) -> Dict:
        """Sync SAP groups to Shopify collections."""
        results = {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            # Get SAP groups
            sap_groups = self.get_sap_groups()
            
            # Process each group
            for group in sap_groups:
                try:
                    # Transform SAP group to Shopify collection
                    collection_data = self.transform(group, 'sap-to-shopify')
                    
                    # Validate transformed data
                    is_valid, errors = self.validate(collection_data, 'shopify')
                    if not is_valid:
                        results['failed'] += 1
                        results['errors'].append({
                            'group': group['Number'],
                            'errors': errors
                        })
                        continue
                    
                    # Check if collection exists
                    existing_collection = self._find_shopify_collection_by_handle(
                        collection_data['handle']
                    )
                    
                    if existing_collection:
                        # Update existing collection
                        self.shopify_client.put(
                            f"/custom_collections/{existing_collection['id']}",
                            {'custom_collection': collection_data}
                        )
                        results['updated'] += 1
                    else:
                        # Create new collection
                        self.shopify_client.post(
                            "/custom_collections",
                            {'custom_collection': collection_data}
                        )
                        results['created'] += 1
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'group': group['Number'],
                        'error': str(e)
                    })
                    
        except Exception as e:
            logger.error(f"Error syncing SAP to Shopify: {str(e)}")
            raise
            
        return results

    def _sync_shopify_to_sap(self, mode: str) -> Dict:
        """Sync Shopify collections to SAP groups."""
        results = {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            logger.info(f"Starting Shopify to SAP sync in {mode} mode")
            console.print(f"\n[bold blue]Starting Shopify to SAP sync (Mode: {mode})[/bold blue]\n")
            
            # Get both custom and smart collections
            logger.info("Fetching Shopify collections...")
            custom_collections = self.shopify_client.get("/custom_collections")
            smart_collections = self.shopify_client.get("/smart_collections")
            
            logger.debug(f"Raw custom collections response: {json.dumps(custom_collections, indent=2)}")
            logger.debug(f"Raw smart collections response: {json.dumps(smart_collections, indent=2)}")
            
            all_collections = []
            if custom_collections and 'custom_collections' in custom_collections:
                all_collections.extend(custom_collections['custom_collections'])
            if smart_collections and 'smart_collections' in smart_collections:
                all_collections.extend(smart_collections['smart_collections'])
            
            logger.info(f"Found {len(all_collections)} collections to process")
            console.print(f"Found {len(all_collections)} collections to process\n")
            
            # Get existing SAP groups for comparison
            logger.info("Fetching existing SAP groups...")
            existing_groups = {str(g.get('Number')): g for g in self.get_sap_groups()}
            logger.debug(f"Existing SAP groups: {json.dumps(existing_groups, indent=2)}")
            
            # Process all collections
            with Progress() as progress:
                task = progress.add_task("[cyan]Syncing collections...", total=len(all_collections))
                
                for collection in all_collections:
                    try:
                        collection_id = str(collection.get('id'))
                        logger.info(f"Processing collection {collection_id}: {collection.get('title')}")
                        logger.debug(f"Raw collection data: {json.dumps(collection, indent=2)}")
                        
                        # Skip if in incremental mode and group exists and hasn't changed
                        if mode == 'incremental' and collection_id in existing_groups:
                            existing_group = existing_groups[collection_id]
                            logger.debug(f"Found existing group: {json.dumps(existing_group, indent=2)}")
                            
                            if (existing_group.get('GroupName') == collection.get('title') and
                                existing_group.get('Active') == ('tYES' if collection.get('published') else 'tNO')):
                                logger.info(f"Skipping unchanged collection {collection_id}")
                                results['skipped'] += 1
                                self._display_sync_progress(collection, 'skipped')
                                progress.advance(task)
                                continue
                            else:
                                logger.info("Collection has changed, proceeding with update")
                                logger.debug(f"Changes detected - Title: {collection.get('title')} != {existing_group.get('GroupName')} or "
                                          f"Active: {'tYES' if collection.get('published') else 'tNO'} != {existing_group.get('Active')}")
                        
                        # Transform Shopify collection to SAP group
                        logger.info(f"Transforming collection {collection_id} to SAP format")
                        group_data = self._transform_shopify_to_sap(collection)
                        logger.debug(f"Transformed group data: {json.dumps(group_data, indent=2)}")
                        
                        # Validate transformed data
                        logger.info(f"Validating transformed data for collection {collection_id}")
                        is_valid, errors = self.validate(group_data, 'sap')
                        if not is_valid:
                            logger.error(f"Validation failed for collection {collection_id}: {errors}")
                            results['failed'] += 1
                            results['errors'].append({
                                'collection_id': collection_id,
                                'title': collection.get('title'),
                                'errors': errors
                            })
                            self._display_sync_progress(collection, 'failed', str(errors))
                            progress.advance(task)
                            continue
                        
                        # Update or create group in SAP
                        try:
                            if collection_id in existing_groups:
                                logger.info(f"Updating existing SAP group for collection {collection_id}")
                                endpoint = f"ItemGroups('{collection_id}')"
                                logger.debug(f"PATCH request to {endpoint} with data: {json.dumps(group_data, indent=2)}")
                                self.sap_client.patch(endpoint, group_data)
                                results['updated'] += 1
                                self._display_sync_progress(collection, 'success')
                                logger.info(f"Successfully updated SAP group for collection {collection.get('title')}")
                            else:
                                logger.info(f"Creating new SAP group for collection {collection_id}")
                                endpoint = "ItemGroups"
                                logger.debug(f"POST request to {endpoint} with data: {json.dumps(group_data, indent=2)}")
                                self.sap_client.post(endpoint, group_data)
                                results['created'] += 1
                                self._display_sync_progress(collection, 'success')
                                logger.info(f"Successfully created SAP group for collection {collection.get('title')}")
                                
                        except Exception as e:
                            logger.error(f"SAP API error for collection {collection_id}: {str(e)}", exc_info=True)
                            results['failed'] += 1
                            results['errors'].append({
                                'collection_id': collection_id,
                                'title': collection.get('title'),
                                'error': f"SAP API Error: {str(e)}"
                            })
                            self._display_sync_progress(collection, 'failed', str(e))
                            
                    except Exception as e:
                        logger.error(f"Error processing collection {collection.get('id')}: {str(e)}", exc_info=True)
                        results['failed'] += 1
                        results['errors'].append({
                            'collection_id': collection.get('id'),
                            'title': collection.get('title'),
                            'error': str(e)
                        })
                        self._display_sync_progress(collection, 'failed', str(e))
                    
                    progress.advance(task)
            
            # Display final summary
            logger.info("Sync complete")
            logger.info(f"Results: {json.dumps(results, indent=2)}")
            console.print("\n[bold blue]Sync Complete[/bold blue]")
            self._display_sync_summary(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in Shopify to SAP sync: {str(e)}", exc_info=True)
            console.print(f"\n[bold red]Sync Failed: {str(e)}[/bold red]")
            raise

    def _transform_shopify_to_sap(self, collection: Dict) -> Dict:
        """Transform Shopify collection to SAP group format."""
        try:
            # Initialize SAP group data with defaults
            group_data = {
                'Number': str(collection.get('id', '')),
                'GroupName': collection.get('title', ''),
                'Code': collection.get('handle', ''),
                'U_Description': collection.get('body_html', ''),
                'U_CollectionType': 'SMART' if 'rules' in collection else 'CUSTOM'
            }

            # Handle smart collection rules
            if 'rules' in collection:
                rules_json = json.dumps(collection.get('rules', []))
                group_data['U_Rules'] = rules_json[:254] if rules_json else ''  # Truncate if too long
            
            # Additional mappings based on collection type
            if collection.get('published_at'):
                group_data['Frozen'] = False  # If published_at exists, not frozen
            
            # Validate required fields
            if not group_data['GroupName']:
                raise ValueError("GroupName is required")
            if not group_data['Code']:
                raise ValueError("Code is required")
                
            return group_data
            
        except Exception as e:
            logger.error(f"Error transforming Shopify collection to SAP: {str(e)}")
            raise

    def list_group_items(self, source: str, group_id: str = None, name: str = None, 
                        status: str = 'all', search: str = None, output_format: str = 'table') -> None:
        """List all items in a group/collection with filtering options.
        
        Args:
            source: Source system ('sap' or 'shopify')
            group_id: ID of the group/collection
            name: Name of the group/collection (alternative to ID)
            status: Filter by status ('active', 'inactive', 'all')
            search: Search term for name or SKU
            output_format: Output format ('table' or 'json')
        """
        try:
            # Get items based on source
            if source == 'sap':
                if name and not group_id:
                    group_id = self._get_sap_group_id_by_name(name)
                items = self.sap_client.get_group_items(group_id)
            else:  # shopify
                if name and not group_id:
                    group_id = self._get_shopify_collection_id_by_name(name)
                items = self.shopify_client.get_collection_products(group_id)

            # Apply filters
            filtered_items = []
            for item in items:
                # Status filter
                item_status = item.get('Status', 'active') if source == 'sap' else item.get('status', 'active')
                if status != 'all' and item_status.lower() != status:
                    continue

                # Search filter
                if search:
                    search_lower = search.lower()
                    item_name = str(item.get('ItemName' if source == 'sap' else 'title', '')).lower()
                    item_sku = str(item.get('ItemCode' if source == 'sap' else 'sku', '')).lower()
                    if search_lower not in item_name and search_lower not in item_sku:
                        continue

                filtered_items.append(item)

            # Output results
            if output_format == 'json':
                console.print(json.dumps(filtered_items, indent=2))
            else:  # table format
                table = Table(show_header=True, header_style="bold magenta")
                
                # Add columns based on source
                if source == 'sap':
                    table.add_column("Item Code (SKU)")
                    table.add_column("Name")
                    table.add_column("Status")
                    table.add_column("Price")
                    
                    for item in filtered_items:
                        table.add_row(
                            str(item.get('ItemCode', '')),
                            str(item.get('ItemName', '')),
                            str(item.get('Status', '')),
                            str(item.get('Price', ''))
                        )
                else:  # shopify
                    table.add_column("ID")
                    table.add_column("Title")
                    table.add_column("SKU")
                    table.add_column("Status")
                    table.add_column("Price")
                    
                    for item in filtered_items:
                        # Get SKU and price from first variant
                        variant = item.get('variants', [{}])[0]
                        table.add_row(
                            str(item.get('id', '')),
                            str(item.get('title', '')),
                            str(variant.get('sku', '')),
                            str(item.get('status', '')),
                            str(variant.get('price', ''))
                        )

                console.print(table)

        except Exception as e:
            logger.error(f"Error listing items: {str(e)}")
            console.print(f"[red]Error listing items: {str(e)}[/red]")

    def _get_sap_group_id_by_name(self, name: str) -> str:
        """Get SAP group ID by name."""
        groups = self.sap_client.get_item_groups()
        for group in groups:
            if group.get('GroupName') == name:
                return group.get('GroupCode')
        raise ValueError(f"Group with name '{name}' not found in SAP")

    def _get_shopify_collection_id_by_name(self, name: str) -> str:
        """Get Shopify collection ID by name."""
        collections = self.shopify_client.get_collections()
        for collection in collections:
            if collection.get('title') == name:
                return collection.get('id')
        raise ValueError(f"Collection with name '{name}' not found in Shopify")

    def sync_groups(self, direction: str, mode: str, group_id: Optional[str] = None,
                   name: Optional[str] = None, with_items: bool = False) -> None:
        """Sync groups/collections between systems with enhanced options.
        
        Args:
            direction: Sync direction ('sap-to-shopify', 'shopify-to-sap', 'both')
            mode: Sync mode ('full' or 'incremental')
            group_id: Optional specific group ID to sync
            name: Optional specific group name to sync
            with_items: Whether to also sync items within groups
        """
        try:
            # Print configuration info
            logger.info("SHOPIFY_SHOP_URL: %s", self.shopify_client.shop_url)
            logger.info("SAP_API_URL: %s", self.sap_client.config.api_url)
            logger.info("SAP_COMPANY_DB: %s", self.sap_client.config.company_db)
            logger.info("SAP_USERNAME: %s", self.sap_client.config.username)
            logger.info("SAP_VERIFY_SSL: %s", str(self.sap_client.config.verify_ssl))
            logger.info("SAP_WAREHOUSE: %s", self.sap_client.config.warehouse)

            logger.info("Setting up sync environment...")
            
            if direction in ['sap-to-shopify', 'both']:
                # Get SAP groups
                groups = self.sap_client.get_groups(group_id=group_id, name=name)
                if not groups:
                    logger.warning("No SAP groups found matching ID: %s or name: %s", group_id, name)
                    return

                logger.info("Test Environment Setup:")
                logger.info("SAP Groups: %d", len(groups))
                
                # Process each group
                for group in groups:
                    try:
                        group_name = group.get('GroupName', '')
                        group_number = group.get('Number', '')
                        logger.info("Processing SAP group %s (ID: %s)", group_name, group_number)
                        
                        # Transform SAP group to Shopify collection
                        collection_data = self._transform_sap_to_shopify(group)
                        if not collection_data:
                            logger.error("Failed to transform SAP group %s", group_name)
                            continue
                            
                        logger.info("Transformed to Shopify collection with handle: %s", collection_data['handle'])
                        
                        # Check if collection exists
                        existing_collection = None
                        collection_id = None
                        
                        # Check custom collections first
                        custom_collections = self.shopify_client.get('custom_collections.json', {'handle': collection_data['handle']})
                        if custom_collections and 'custom_collections' in custom_collections:
                            existing_collection = custom_collections['custom_collections'][0]
                            collection_id = existing_collection['id']
                            logger.info("Found existing custom collection with ID: %s", collection_id)
                            
                            # Update existing collection
                            self.shopify_client.put(
                                f"custom_collections/{collection_id}.json",
                                {'custom_collection': collection_data}
                            )
                            logger.info("Updated Shopify collection %s", collection_data['handle'])
                        else:
                            # Create new collection
                            response = self.shopify_client.post(
                                "custom_collections.json",
                                {'custom_collection': collection_data}
                            )
                            if response and 'custom_collection' in response:
                                collection_id = response['custom_collection']['id']
                                logger.info("Created Shopify collection %s with ID: %s", collection_data['handle'], collection_id)
                            else:
                                logger.error("Failed to create Shopify collection for %s", group_name)
                                continue
                            
                        # Sync items if requested and we have a valid collection
                        if with_items and collection_id:
                            logger.info("Syncing items for group %s", group_name)
                            items = self.sap_client.get_group_items(group_number)
                            
                            if not items:
                                logger.warning("No items found in SAP group %s", group_name)
                                continue
                                
                            logger.info("Found %d items in group", len(items))
                            
                            for item in items:
                                try:
                                    item_code = item.get('ItemCode', '')
                                    # Check if product already exists
                                    existing_products = self.shopify_client.get('products.json', {'sku': item_code})
                                    product_id = None
                                    
                                    if existing_products and existing_products.get('products'):
                                        # Update existing product
                                        existing_product = existing_products['products'][0]
                                        product_id = existing_product['id']
                                        product_data = {'product': self._transform_sap_item_to_shopify(item)}
                                        response = self.shopify_client.put(f'products/{product_id}.json', product_data)
                                        logger.info("Updated existing product %s", item_code)
                                    else:
                                        # Create new product
                                        product_data = {'product': self._transform_sap_item_to_shopify(item)}
                                        response = self.shopify_client.post('products.json', product_data)
                                        
                                    if response and 'product' in response:
                                        product_id = response['product']['id']
                                        # Check if product is already in collection
                                        collects = self.shopify_client.get('collects.json', {
                                            'collection_id': collection_id,
                                            'product_id': product_id
                                        })
                                        
                                        if not collects or not collects.get('collects'):
                                            # Add to collection only if not already present
                                            collect_data = {
                                                'collect': {
                                                    'collection_id': collection_id,
                                                    'product_id': product_id
                                                }
                                            }
                                            self.shopify_client.post('collects.json', collect_data)
                                            logger.info("Added product %s to collection", item_code)
                                        else:
                                            logger.info("Product %s already in collection", item_code)
                                    else:
                                        logger.warning("Failed to create/update product %s", item_code)
                                except Exception as e:
                                    logger.error("Error syncing item %s: %s", item.get('ItemCode', ''), str(e))
                                    continue
                        
                    except Exception as e:
                        logger.error("Error syncing group %s: %s", group.get('GroupName', ''), str(e))
                        continue

            if direction in ['shopify-to-sap', 'both']:
                # Get Shopify collections
                collections = []
                
                # Get custom collections
                custom_collections = self.shopify_client.get('custom_collections.json')
                if custom_collections and 'custom_collections' in custom_collections:
                    collections.extend(custom_collections['custom_collections'])
                
                # Get smart collections
                smart_collections = self.shopify_client.get('smart_collections.json')
                if smart_collections and 'smart_collections' in smart_collections:
                    collections.extend(smart_collections['smart_collections'])
                
                if not collections:
                    logger.warning("No Shopify collections found")
                    return
                    
                logger.info("Shopify Collections: %d", len(collections))
                
                # Filter by ID or name if provided
                if group_id:
                    collections = [c for c in collections if str(c.get('id')) == str(group_id)]
                if name:
                    collections = [c for c in collections if c.get('title') == name]
                
                if not collections:
                    logger.warning("No Shopify collections found matching ID: %s or name: %s", group_id, name)
                    return
                
                # Process each collection
                for collection in collections:
                    try:
                        collection_title = collection.get('title', '')
                        collection_id = collection.get('id', '')
                        logger.info("Processing Shopify collection %s (ID: %s)", collection_title, collection_id)
                        
                        # Sync collection to SAP
                        self._sync_shopify_to_sap(collection, with_items)
                        logger.info("Synced Shopify collection %s to SAP", collection_title)
                        
                    except Exception as e:
                        logger.error("Error syncing collection %s: %s", collection_title, str(e))
                        continue

            logger.info("Sync completed successfully")

        except Exception as e:
            logger.error("Error during sync: %s", str(e))

    def _sync_sap_to_shopify(self, group: Dict, with_items: bool) -> None:
        """Sync a single SAP group to Shopify."""
        # Transform SAP group to Shopify collection format
        collection_data = self._transform_sap_to_shopify(group)
        
        # Create/update collection in Shopify
        collection_id = self.shopify_client.upsert_collection(collection_data)
        
        if with_items:
            # Get items from SAP group
            items = self.sap_client.get_group_items(group['Code'])
            
            # Transform and sync each item
            for item in items:
                product_data = self._transform_sap_item_to_shopify(item)
                self.shopify_client.upsert_product(product_data, collection_id)

    def _sync_shopify_to_sap(self, collection: Dict, with_items: bool) -> None:
        """Sync a single Shopify collection to SAP."""
        # Transform Shopify collection to SAP group format
        group_data = self._transform_shopify_to_sap(collection)
        
        # Create/update group in SAP
        group_code = self.sap_client.upsert_group(group_data)
        
        if with_items:
            # Get products from Shopify collection
            products = self.shopify_client.get_collection_products(collection['id'])
            
            # Transform and sync each product
            for product in products:
                item_data = self._transform_shopify_product_to_sap(product)
                self.sap_client.upsert_item(item_data, group_code)

    def _transform_sap_to_shopify(self, group: Dict) -> Dict:
        """Transform SAP group to Shopify collection format.
        
        Args:
            group: SAP group data
            
        Returns:
            Shopify collection data
        """
        handle = f"{str(group['Number']).lower()}-{str(group['GroupName']).lower().replace(' ', '-')}"
        collection_data = {
            'handle': handle,
            'title': group['GroupName'],
            'body_html': group.get('U_Description', ''),
            'published': True,
            'sort_order': 'alpha-asc',
            'template_suffix': '',
            'published_scope': 'web'
        }
        
        return collection_data

    def _transform_shopify_to_sap(self, collection: Dict) -> Dict:
        """Transform Shopify collection to SAP group format.
        
        Args:
            collection: Shopify collection data
            
        Returns:
            SAP group data
        """
        try:
            # Initialize SAP group data with defaults
            group_data = {
                'Number': str(collection.get('id', '')),
                'GroupName': collection.get('title', ''),
                'Code': collection.get('handle', ''),
                'U_Description': collection.get('body_html', ''),
                'U_CollectionType': 'SMART' if 'rules' in collection else 'CUSTOM'
            }

            # Handle smart collection rules
            if 'rules' in collection:
                rules_json = json.dumps(collection.get('rules', []))
                group_data['U_Rules'] = rules_json[:254] if rules_json else ''  # Truncate if too long
            
            # Additional mappings based on collection type
            if collection.get('published_at'):
                group_data['Frozen'] = False  # If published_at exists, not frozen
            
            # Validate required fields
            if not group_data['GroupName']:
                raise ValueError("GroupName is required")
            if not group_data['Code']:
                raise ValueError("Code is required")
                
            return group_data
            
        except Exception as e:
            logger.error(f"Error transforming Shopify collection to SAP: {str(e)}")
            raise

    def list_groups(self, source: str) -> None:
        """List groups/collections from the specified system.
        
        Args:
            source: Source system to list groups from ('sap' or 'shopify')
        """
        try:
            if source == 'sap':
                groups = self.sap_client.get_groups()
                console.print("\n[blue]SAP Groups:[/blue]")
                for group in groups:
                    console.print(f"ID: {group.get('Number')}, Name: {group.get('GroupName')}")
            else:
                # Get custom collections with cursor-based pagination
                console.print("\n[blue]Custom Collections:[/blue]")
                next_page_info = None
                limit = 250  # Maximum allowed by Shopify
                
                while True:
                    params = {'limit': limit}
                    if next_page_info:
                        params['page_info'] = next_page_info
                        
                    custom_collections = self.shopify_client.get('custom_collections.json', params=params)
                    if not custom_collections.get('custom_collections'):
                        break
                    
                    for collection in custom_collections['custom_collections']:
                        console.print(f"ID: {collection['id']}, Handle: {collection['handle']}, Title: {collection['title']}")
                    
                    # Check for Link header in response for next page
                    next_page_info = self.shopify_client.get_next_page_info()
                    if not next_page_info:
                        break

                # Get smart collections with cursor-based pagination
                console.print("\n[blue]Smart Collections:[/blue]")
                next_page_info = None
                
                while True:
                    params = {'limit': limit}
                    if next_page_info:
                        params['page_info'] = next_page_info
                        
                    smart_collections = self.shopify_client.get('smart_collections.json', params=params)
                    if not smart_collections.get('smart_collections'):
                        break
                    
                    for collection in smart_collections['smart_collections']:
                        console.print(f"ID: {collection['id']}, Handle: {collection['handle']}, Title: {collection['title']}")
                    
                    # Check for Link header in response for next page
                    next_page_info = self.shopify_client.get_next_page_info()
                    if not next_page_info:
                        break

        except Exception as e:
            console.print(f"[red]Error listing groups: {str(e)}[/red]")

    def _transform_sap_item_to_shopify(self, item: Dict) -> Dict:
        """Transform SAP item to Shopify product format.
        
        Args:
            item: SAP item data
            
        Returns:
            Shopify product data
        """
        try:
            # Get SKU from ItemCode
            sku = str(item.get('ItemCode', ''))
            
            # Basic product data
            product_data = {
                'product': {
                    'title': item.get('ItemName', ''),
                    'body_html': item.get('U_Description', ''),
                    'vendor': 'SAP',
                    'product_type': item.get('U_ProductType', ''),
                    'status': 'active',
                    'published': True,
                    'variants': [{
                        'sku': sku,  # Set SKU in variant
                        'price': str(item.get('Price', '0.00')),
                        'inventory_management': 'shopify',
                        'inventory_policy': 'continue',
                        'inventory_quantity': int(item.get('Quantity', 0)),
                        'requires_shipping': True,
                        'taxable': True,
                        'barcode': item.get('BarCode', ''),  # Add barcode if available
                        'weight': float(item.get('Weight', 0)),  # Add weight if available
                        'weight_unit': item.get('WeightUnit', 'kg')  # Add weight unit if available
                    }],
                    'options': [{
                        'name': 'Title',
                        'values': ['Default Title']
                    }]
                }
            }
            
            # Add metafields for SAP data
            product_data['product']['metafields'] = [
                {
                    'key': 'sap_item_code',
                    'value': sku,
                    'type': 'single_line_text_field',
                    'namespace': 'sap'
                },
                {
                    'key': 'sap_sync_date',
                    'value': datetime.now().isoformat(),
                    'type': 'single_line_text_field',
                    'namespace': 'sap'
                }
            ]
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error transforming SAP item to Shopify product: {str(e)}")
            logger.debug(f"SAP item data: {json.dumps(item, indent=2)}")
            return None

    def _transform_shopify_product_to_sap(self, product: Dict) -> Dict:
        """Transform Shopify product to SAP item format.
        
        Args:
            product: Shopify product data
            
        Returns:
            SAP item data
        """
        # Get SKU from first variant or metafields
        sku = None
        if product.get('variants'):
            sku = product['variants'][0].get('sku')
        
        # If no SKU in variant, check metafields
        if not sku and product.get('metafields'):
            for metafield in product['metafields']:
                if metafield.get('namespace') == 'sap' and metafield.get('key') == 'sap_item_code':
                    sku = metafield.get('value')
                    break
        
        # If still no SKU, use a portion of the product ID
        if not sku and product.get('id'):
            sku = f"SHOP-{str(product['id'])[-8:]}"
            logger.warning(f"No SKU found for product {product.get('title')}, using generated SKU: {sku}")

        item_data = {
            'ItemCode': sku,
            'ItemName': product.get('title', ''),
            'Description': BeautifulSoup(product.get('body_html', ''), 'html.parser').get_text(),
            'U_ProductType': product.get('product_type', ''),
            'U_Vendor': product.get('vendor', ''),
            'U_ShopifyID': str(product.get('id', '')),
            'U_LastSyncDate': datetime.now().isoformat()
        }
        
        # Get price and inventory from first variant
        if product.get('variants'):
            variant = product['variants'][0]
            item_data.update({
                'Price': float(variant.get('price', 0.0)),
                'Quantity': int(variant.get('inventory_quantity', 0)),
                'BarCode': variant.get('barcode', ''),
                'Weight': float(variant.get('weight', 0.0)),
                'WeightUnit': variant.get('weight_unit', 'kg')
            })
        
        return item_data

    def _display_sync_progress(self, collection: Dict, status: str, error: str = None) -> None:
        """Display sync progress in a table format.
        
        Args:
            collection: Collection being synced
            status: Sync status (success, failed, skipped)
            error: Optional error message
        """
        table = Table(title="Sync Progress", show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="green")
        
        # Collection details
        table.add_row("Collection ID", str(collection.get('id', '')))
        table.add_row("Title", collection.get('title', ''))
        table.add_row("Handle", collection.get('handle', ''))
        table.add_row("Type", 'Smart' if 'rules' in collection else 'Custom')
        table.add_row("Published", '✓' if collection.get('published', False) else '✗')
        table.add_row("Status", f"[green]SUCCESS[/green]" if status == 'success' 
                              else f"[yellow]SKIPPED[/yellow]" if status == 'skipped'
                              else f"[red]FAILED[/red]")
        if error:
            table.add_row("Error", f"[red]{error}[/red]")
            
        console.print(table)
        console.print("")  # Add spacing between tables

    def _display_sync_summary(self, results: Dict) -> None:
        """Display sync summary in a table format.
        
        Args:
            results: Sync results dictionary
        """
        # Summary table
        summary_table = Table(title="Sync Summary", show_header=True, header_style="bold blue")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", style="green", justify="right")
        
        summary_table.add_row("Created", str(results['created']))
        summary_table.add_row("Updated", str(results['updated']))
        summary_table.add_row("Skipped", str(results['skipped']))
        summary_table.add_row("Failed", f"[red]{str(results['failed'])}[/red]" if results['failed'] > 0 else "0")
        summary_table.add_row("Total Processed", str(results['created'] + results['updated'] + results['skipped'] + results['failed']))
        
        console.print(summary_table)
        
        # If there are errors, show error details
        if results['errors']:
            console.print("\n[red]Errors:[/red]")
            error_table = Table(show_header=True, header_style="bold red")
            error_table.add_column("Collection", style="cyan")
            error_table.add_column("Error", style="red")
            
            for error in results['errors']:
                error_table.add_row(
                    f"{error.get('title', '')} ({error.get('collection_id', '')})",
                    str(error.get('error', error.get('errors', [])))
                )
            
            console.print(error_table)
