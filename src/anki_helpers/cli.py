"""Command-line interface for Anki Helpers."""

import click

from .anki_connect import AnkiConnect, AnkiConnectError


@click.group()
def cli():
    """Anki Helpers - A CLI tool to help with Anki flashcards."""
    pass


@cli.command()
def version():
    """Show the version of Anki Helpers."""
    from anki_helpers import __version__

    click.echo(f"Anki Helpers version {__version__}")


@cli.command()
def hello_world():
    """Print a hello world message."""
    click.echo("Hello World!")


@cli.command()
def list_deck():
    """List all available Anki decks."""
    try:
        anki = AnkiConnect()
        decks = anki.get_deck_names()

        if not decks:
            click.echo("No decks found.")
            return

        click.echo("Available decks:")
        for deck in sorted(decks):
            click.echo(f"  • {deck}")

    except AnkiConnectError as e:
        click.echo(f"Error: {str(e)}", err=True)
        msg = "Make sure Anki is running with AnkiConnect plugin installed."
        click.echo(msg, err=True)


if __name__ == "__main__":
    cli()
