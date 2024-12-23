"""Main entry point for syn-tool."""

from .cli import create_cli

if __name__ == "__main__":
    cli = create_cli()
    cli()
