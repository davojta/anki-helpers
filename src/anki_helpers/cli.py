"""Command-line interface for Anki Helpers."""

import click


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


if __name__ == "__main__":
    cli()
