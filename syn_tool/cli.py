"""
CLI module for syn-tool.
"""
import click
from rich.console import Console

from .core.sync_manager import SyncManager
from .core.config import Config
from .utils.logger import setup_logger
from .commands.group_commands import register_group_commands
from .commands.order_commands import register_order_commands
from .clients.sap_client import SAPClient
from .clients.shopify_client import ShopifyClient

console = Console()
logger = setup_logger()

def create_cli():
    """Create the CLI application."""
    
    @click.group()
    @click.pass_context
    def cli(ctx):
        """Syn-tool CLI for SAP and Shopify synchronization."""
        ctx.ensure_object(dict)
        
        config = Config.from_env()
        
        ctx.obj['sap_client'] = SAPClient(config.sap)
        ctx.obj['shopify_client'] = ShopifyClient(config.shopify)

    # Register commands
    register_group_commands(cli)
    register_order_commands(cli)
    
    @cli.group()
    def sync():
        """Synchronize data between SAP and Shopify."""
        pass

    @sync.command()
    @click.option('--direction', type=click.Choice(['sap-to-shopify', 'shopify-to-sap', 'both']),
                required=True, help='Direction of synchronization')
    @click.option('--mode', type=click.Choice(['full', 'incremental']), default='incremental',
                help='Sync mode')
    def products(direction, mode):
        """Sync products between SAP and Shopify."""
        try:
            sync_manager = SyncManager()
            sync_manager.sync_products(direction, mode)
            console.print("[green]Product sync completed successfully![/]")
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")
            logger.error(f"Product sync failed: {str(e)}")

    @sync.command()
    @click.option('--mode', type=click.Choice(['full', 'incremental']), default='incremental',
                help='Sync mode')
    @click.option('--batch-size', type=int, default=100,
                help='Number of orders to sync in each batch')
    def orders(mode, batch_size):
        """Sync orders from Shopify to SAP."""
        try:
            sync_manager = SyncManager()
            sync_manager.sync_orders(mode, batch_size)
            console.print("[green]Order sync completed successfully![/]")
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")
            logger.error(f"Order sync failed: {str(e)}")

    @cli.group()
    def test():
        """Test operations and connections."""
        pass

    @test.command()
    @click.argument('system', type=click.Choice(['sap', 'shopify', 'all']))
    def connection(system):
        """Test connection to SAP and/or Shopify."""
        try:
            sync_manager = SyncManager()
            
            if system in ['sap', 'all']:
                sync_manager.test_sap_connection()
                console.print("[green]SAP connection test passed![/]")
                
            if system in ['shopify', 'all']:
                sync_manager.test_shopify_connection()
                console.print("[green]Shopify connection test passed![/]")
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")

    @cli.group()
    def status():
        """Check sync status and view failed records."""
        pass

    @status.command()
    def failed():
        """View failed sync records."""
        try:
            sync_manager = SyncManager()
            failed_records = sync_manager.get_failed_records()
            
            if not failed_records:
                console.print("[green]No failed records found![/]")
                return
                
            console.print("[yellow]Failed Records:[/]")
            for record in failed_records:
                console.print(f"- {record}")
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")

    @status.command()
    def retry():
        """Retry failed sync records."""
        try:
            sync_manager = SyncManager()
            retry_count = sync_manager.retry_failed_records()
            
            if retry_count == 0:
                console.print("[green]No failed records to retry![/]")
            else:
                console.print(f"[green]Successfully retried {retry_count} records![/]")
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")
    
    return cli

if __name__ == "__main__":
    cli = create_cli()
    cli()
