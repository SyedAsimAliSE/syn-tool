"""CLI commands for order operations."""

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import json

from ..services.order_service import OrderService
from ..clients.sap_client import SAPClient
from ..clients.shopify_client import ShopifyClient

console = Console()

def register_order_commands(cli):
    """Register order-related commands with the CLI."""
    
    @cli.group()
    def order():
        """Commands for order operations."""
        pass

    @order.command()
    @click.option('--status', type=click.Choice(['paid', 'unpaid', 'pending']),
                 help='Filter by order financial status')
    @click.option('--limit', type=int, default=50,
                 help='Maximum number of orders to retrieve')
    @click.pass_context
    def list(ctx, status: str, limit: int):
        """List orders from Shopify.
        
        Example:
            syn order list
            syn order list --status paid --limit 10
        """
        service = OrderService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        
        try:
            orders = service.list_orders(status=status, limit=limit)
            
            table = Table(title=f"Shopify Orders (Total: {len(orders)})")
            table.add_column("Order ID")
            table.add_column("Order Number")
            table.add_column("Date")
            table.add_column("Status")
            table.add_column("Total")
            
            for order in orders:
                table.add_row(
                    str(order['id']),
                    str(order['order_number']),
                    order['created_at'].split('T')[0],
                    order.get('financial_status', 'unknown'),
                    f"{order['currency']} {order['total_price']}"
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error listing orders: {str(e)}[/red]")

    @order.command()
    @click.argument('order_id')
    @click.pass_context
    def status(ctx, order_id: str):
        """Check sync status of a specific order.
        
        Example:
            syn order status 12345678
        """
        service = OrderService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        
        try:
            status = service.get_order_status(order_id)
            
            if status['status'] == 'error':
                console.print(f"[red]Error: {status['message']}[/red]")
                return
            
            table = Table(title=f"Order Status - {order_id}")
            table.add_column("System")
            table.add_column("Status")
            
            table.add_row("Sync Status", status['status'])
            table.add_row("Shopify Status", status['shopify_status'] or 'N/A')
            table.add_row("SAP Status", status['sap_status'] or 'N/A')
            
            if status.get('sap_doc_entry'):
                table.add_row("SAP Doc Entry", str(status['sap_doc_entry']))
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error checking order status: {str(e)}[/red]")

    @order.command()
    @click.option('--batch-size', type=int, default=10,
                 help='Number of orders to sync in each batch')
    @click.option('--order-id', type=str,
                 help='Specific order ID to sync')
    @click.pass_context
    def sync(ctx, batch_size: int, order_id: str):
        """Sync orders from Shopify to SAP.
        
        Example:
            syn order sync
            syn order sync --batch-size 20
            syn order sync --order-id 12345678
        """
        service = OrderService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Syncing orders...", total=None)
            
            try:
                if order_id:
                    # Sync single order
                    result = service.sync_single_order(order_id, progress=progress)
                else:
                    # Sync batch of orders
                    result = service.sync_orders(mode='shopify_to_sap',
                                              batch_size=batch_size,
                                              progress=progress)
                
                table = Table(title="Sync Results")
                table.add_column("Metric")
                table.add_column("Count")
                
                table.add_row("Synced", str(result['synced']))
                table.add_row("Failed", str(result['failed']))
                table.add_row("Skipped", str(result['skipped']))
                
                console.print(table)
                
            except Exception as e:
                console.print(f"[red]Error syncing orders: {str(e)}[/red]")

    @order.command()
    @click.pass_context
    def describe(ctx):
        """Show order structure in both systems.
        
        Example:
            syn order describe
        """
        service = OrderService(ctx.obj['sap_client'], ctx.obj['shopify_client'])
        
        try:
            structure = service.describe_structure()
            
            console.print("\n[cyan]Shopify Order Structure:[/cyan]")
            console.print(json.dumps(structure['shopify'], indent=2))
            
            console.print("\n[cyan]SAP Order Structure:[/cyan]")
            console.print(json.dumps(structure['sap'], indent=2))
            
            console.print(f"\n[green]Sync Direction: {structure['sync_direction']}[/green]")
            
        except Exception as e:
            console.print(f"[red]Error describing order structure: {str(e)}[/red]")
