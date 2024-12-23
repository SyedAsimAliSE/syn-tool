"""
CLI commands for group/collection operations.
"""
import click
from rich.console import Console
from rich.table import Table
import json

from ..services.group_service import GroupService
from ..clients.sap_client import SAPClient
from ..clients.shopify_client import ShopifyClient
from ..core.config import Config

console = Console()

def register_group_commands(cli):
    """Register group-related commands with the CLI."""
    
    @cli.group()
    def describe():
        """Commands for describing entities."""
        pass

    @describe.command()
    @click.argument('entity', type=click.Choice(['group']))
    @click.argument('source', type=click.Choice(['sap', 'shopify']))
    @click.pass_context
    def entity(ctx, entity: str, source: str):
        """Show entity structure.
        
        Example:
            syn describe entity group sap
            syn describe entity group shopify
        """
        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        service.describe_structure(source)

    @describe.command()
    @click.argument('entity', type=click.Choice(['group']))
    @click.argument('source', type=click.Choice(['sap', 'shopify']))
    @click.option('--id', help='Show specific item details')
    @click.pass_context
    def list(ctx, entity: str, source: str, id: str):
        """List items of an entity type.
        
        Example:
            syn describe list group sap
            syn describe list group shopify
            syn describe list group sap --id "G001"
        """
        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        service.list_items(source, id)

    @describe.command()
    @click.argument('entity', type=click.Choice(['group']))
    @click.pass_context
    def mapping(ctx, entity: str):
        """Show field mappings between systems."""
        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        service.show_mappings()

    @cli.group()
    def sync():
        """Commands for syncing entities."""
        pass

    @sync.command()
    @click.argument('entity', type=click.Choice(['group']))
    @click.option('--direction', type=click.Choice(['sap-to-shopify', 'shopify-to-sap']), required=True,
                help='Direction of synchronization')
    @click.option('--mode', type=click.Choice(['full', 'incremental']), default='incremental',
                help='Sync mode')
    @click.pass_context
    def entity(ctx, entity: str, direction: str, mode: str):
        """Sync entities between systems.
        
        Example:
            syn sync group --direction sap-to-shopify --mode full
            syn sync group --direction shopify-to-sap --mode incremental
        """
        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        
        with console.status(f"[bold blue]Syncing {entity}s from {direction}..."):
            try:
                results = service.sync(direction, mode)
                
                # Display results
                table = Table(title=f"Sync Results: {direction}")
                table.add_column("Metric", style="cyan")
                table.add_column("Count", style="green")
                
                table.add_row("Created", str(results['created']))
                table.add_row("Updated", str(results['updated']))
                table.add_row("Failed", str(results['failed']))
                table.add_row("Skipped", str(results['skipped']))
                
                console.print(table)
                
                if results['errors']:
                    console.print("\n[red]Errors:[/red]")
                    for error in results['errors']:
                        console.print(f"- {error}")
                        
            except Exception as e:
                console.print(f"[red]Error during sync: {str(e)}[/red]")

    @cli.group()
    def group():
        """Commands for managing groups/collections."""
        pass

    @group.command(name='list-items')
    @click.argument('source', type=click.Choice(['sap', 'shopify']))
    @click.option('--group-id', help='ID of the group/collection')
    @click.option('--name', help='Name of the group/collection (alternative to ID)')
    @click.option('--status', type=click.Choice(['active', 'inactive', 'all']), default='all', help='Filter items by status')
    @click.option('--search', help='Search items by name or SKU')
    @click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table', help='Output format')
    @click.pass_context
    def list_items_cmd(ctx, source: str, group_id: str, name: str, status: str, search: str, output_format: str):
        """List all items in a group/collection.
        
        Examples:
            syn group list-items sap --group-id "G001"
            syn group list-items shopify --name "Summer Collection" --status active
            syn group list-items sap --group-id "G001" --search "SKU123" --format json
        """
        if not group_id and not name:
            console.print("[red]Error: Either --group-id or --name must be provided[/red]")
            return

        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        service.list_group_items(source, group_id, name, status, search, output_format)

    @group.command()
    @click.argument('direction', type=click.Choice(['sap-to-shopify', 'shopify-to-sap', 'both']))
    @click.option('--group-id', help='ID of specific group to sync')
    @click.option('--name', help='Name of specific group to sync')
    @click.option('--with-items', is_flag=True, help='Also sync items within the group')
    @click.option('--mode', type=click.Choice(['full', 'incremental']), default='incremental',
                help='Sync mode')
    @click.pass_context
    def sync(ctx, direction: str, group_id: str, name: str, with_items: bool, mode: str):
        """Sync groups/collections between systems.
        
        Example:
            syn group sync sap-to-shopify --group-id "G001"
            syn group sync both --with-items
        """
        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        service.sync_groups(direction, mode, group_id, name, with_items)

    @group.command()
    @click.option('--source', type=click.Choice(['sap', 'shopify']), required=True, help='Source system to query')
    @click.option('--show-incomplete', is_flag=True, help='Show items with missing information')
    @click.pass_context
    def check_items(ctx, source: str, show_incomplete: bool):
        """Check items for completeness of important fields like SKU, Price, etc."""
        try:
            service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
            
            if source == 'sap':
                items = service.sap_client.get_items()
                console.print(f"\n[bold blue]SAP Items Analysis[/bold blue]")
                console.print(f"Total items found: [green]{len(items)}[/green]")
                
                complete_items = []
                incomplete_items = []
                
                for item in items:
                    missing_fields = []
                    
                    # Check required fields
                    if not item.get('ItemCode'):
                        missing_fields.append('ItemCode/SKU')
                    if not item.get('ItemName'):
                        missing_fields.append('ItemName')
                    if not item.get('ItemPrices') or not any(price.get('Price') for price in item.get('ItemPrices', [])):
                        missing_fields.append('Price')
                    if not item.get('QuantityOnStock') and item.get('QuantityOnStock') != 0:
                        missing_fields.append('Stock')
                    
                    if missing_fields:
                        incomplete_items.append((item, missing_fields))
                    else:
                        complete_items.append(item)
                
                console.print(f"\nItems with complete information: [green]{len(complete_items)}[/green]")
                console.print(f"Items with missing information: [yellow]{len(incomplete_items)}[/yellow]")
                
                if complete_items:
                    console.print("\n[bold green]Sample Complete Items:[/bold green]")
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("SKU")
                    table.add_column("Name")
                    table.add_column("Price")
                    table.add_column("Stock")
                    table.add_column("Group")
                    
                    for item in complete_items[:5]:  # Show first 5 complete items
                        price = next((p['Price'] for p in item.get('ItemPrices', []) if p.get('Price') is not None), 'N/A')
                        table.add_row(
                            str(item.get('ItemCode', '')),
                            str(item.get('ItemName', '')),
                            str(price),
                            str(item.get('QuantityOnStock', '')),
                            str(item.get('ItemsGroupCode', ''))
                        )
                    console.print(table)
                
                if show_incomplete and incomplete_items:
                    console.print("\n[bold yellow]Items with Missing Information:[/bold yellow]")
                    for item, missing in incomplete_items:
                        console.print(f"- {item.get('ItemCode', 'Unknown SKU')}: Missing {', '.join(missing)}")
            
            else:  # shopify
                products = service.shopify_client.get_products()
                console.print(f"\n[bold blue]Shopify Products Analysis[/bold blue]")
                console.print(f"Total products found: [green]{len(products)}[/green]")
                
                complete_products = []
                incomplete_products = []
                
                for product in products:
                    missing_fields = []
                    
                    # Check required fields
                    if not product.get('title'):
                        missing_fields.append('Title')
                    
                    variants = product.get('variants', [])
                    if not variants:
                        missing_fields.append('Variants')
                    else:
                        variant = variants[0]  # Check first variant
                        if not variant.get('sku'):
                            missing_fields.append('SKU')
                        if not variant.get('price'):
                            missing_fields.append('Price')
                        if not variant.get('inventory_quantity') and variant.get('inventory_quantity') != 0:
                            missing_fields.append('Inventory')
                    
                    if missing_fields:
                        incomplete_products.append((product, missing_fields))
                    else:
                        complete_products.append(product)
                
                console.print(f"\nProducts with complete information: [green]{len(complete_products)}[/green]")
                console.print(f"Products with missing information: [yellow]{len(incomplete_products)}[/yellow]")
                
                if complete_products:
                    console.print("\n[bold green]Sample Complete Products:[/bold green]")
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("SKU")
                    table.add_column("Title")
                    table.add_column("Price")
                    table.add_column("Stock")
                    table.add_column("Collections")
                    
                    for product in complete_products[:5]:  # Show first 5 complete products
                        variant = product['variants'][0]
                        collections = service.shopify_client.get_product_collections(product['id'])
                        collection_names = [c['title'] for c in collections]
                        
                        table.add_row(
                            str(variant.get('sku', '')),
                            str(product.get('title', '')),
                            str(variant.get('price', '')),
                            str(variant.get('inventory_quantity', '')),
                            ', '.join(collection_names) if collection_names else 'None'
                        )
                    console.print(table)
                
                if show_incomplete and incomplete_products:
                    console.print("\n[bold yellow]Products with Missing Information:[/bold yellow]")
                    for product, missing in incomplete_products:
                        console.print(f"- {product.get('title', 'Unknown Title')}: Missing {', '.join(missing)}")
        
        except Exception as e:
            console.print(f"[red]Error checking items: {str(e)}[/red]")

    @group.command()
    @click.option('--source', type=click.Choice(['sap', 'shopify']), required=True, help='Source system to query')
    @click.option('--verbose', '-v', is_flag=True, help='Show detailed debugging information')
    @click.pass_context
    def debug_items(ctx, source: str, verbose: bool):
        """Show debugging information about items in the system."""
        try:
            service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
            
            if source == 'sap':
                # Get all items from SAP
                items = service.sap_client.get_items()
                console.print(f"\n[bold blue]SAP System Overview[/bold blue]")
                console.print(f"Total items found: [green]{len(items)}[/green]")
                
                # Group items by ItemsGroupCode
                groups = {}
                for item in items:
                    group_code = item.get('ItemsGroupCode')
                    if group_code not in groups:
                        groups[group_code] = []
                    groups[group_code].append(item)
                
                # Show items per group
                console.print("\n[bold]Items per Group:[/bold]")
                for group_code, group_items in sorted(groups.items()):
                    group_name = next((g['GroupName'] for g in service.sap_client.get_groups(group_id=group_code)), 'Unknown')
                    console.print(f"Group {group_code} ({group_name}): [green]{len(group_items)}[/green] items")
                
                if verbose:
                    # Show sample item structure
                    if items:
                        console.print("\n[bold]Sample Item Structure:[/bold]")
                        console.print(json.dumps(items[0], indent=2))
                    
                    # Show groups with no items
                    all_groups = service.sap_client.get_groups()
                    empty_groups = [g for g in all_groups if str(g.get('Number')) not in groups]
                    if empty_groups:
                        console.print("\n[bold yellow]Empty Groups:[/bold yellow]")
                        for g in empty_groups:
                            console.print(f"- {g.get('Number')}: {g.get('GroupName')}")
                
            else:  # shopify
                # Get all products from Shopify
                products = service.shopify_client.get_products()
                console.print(f"\n[bold blue]Shopify System Overview[/bold blue]")
                console.print(f"Total products found: [green]{len(products)}[/green]")
                
                # Get all collections
                collections = service.shopify_client.get_collections()
                console.print(f"Total collections found: [green]{len(collections)}[/green]")
                
                if verbose:
                    # Show collections and their product counts
                    console.print("\n[bold]Collections:[/bold]")
                    for collection in collections:
                        products = service.shopify_client.get_collection_products(collection['id'])
                        console.print(f"Collection {collection['title']}: [green]{len(products)}[/green] products")
                    
                    # Show sample product structure
                    if products:
                        console.print("\n[bold]Sample Product Structure:[/bold]")
                        console.print(json.dumps(products[0], indent=2))
        
        except Exception as e:
            console.print(f"[red]Error getting debug information: {str(e)}[/red]")

    @group.command()
    @click.option('--source', type=click.Choice(['sap', 'shopify']), required=True, help='Source system to list groups from')
    @click.pass_context
    def list(ctx, source: str):
        """List groups/collections from the specified system."""
        service = GroupService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        service.list_groups(source)
