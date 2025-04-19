"""Command-line interface for Anki Helpers."""

import html
import re
import time

import click

from .anki_connect import AnkiConnect, AnkiConnectError


def clean_html_content(content: str) -> str:
    """Clean HTML content for terminal display.

    Args:
        content: HTML formatted string

    Returns:
        Clean text suitable for terminal display
    """
    # Replace &nbsp; with regular space
    content = content.replace("&nbsp;", " ")

    # Decode other HTML entities
    content = html.unescape(content)

    # Remove HTML tags
    content = re.sub(r"<[^>]+>", "", content)

    # Remove [sound:...] tags
    content = re.sub(r"\[sound:[^\]]+\]", "", content)

    # Clean up multiple spaces
    content = " ".join(content.split())

    return content.strip()


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


@cli.command()
@click.option("--limit", default=5, help="Limit the number of cards displayed")
def list_red_flags(limit):
    """List all words with red flags in Anki, sorted by due date (descending)."""
    try:
        anki = AnkiConnect()
        cards = anki.find_cards_with_red_flag_sorted()

        if not cards:
            click.echo("No cards with red flags found.")
            return

        # Sort cards by due date (ascending)
        sorted_cards = sorted(cards, key=lambda card: card.get("dueQuery", 0))

        click.echo(f"Cards with red flags (sorted by due date, showing top {limit}):")
        for card in sorted_cards[:limit]:
            # Extract the front field (usually contains the word)
            fields = card.get("noteFields", {})
            front_field_name = next(iter(fields.keys()), None)

            if front_field_name:
                front_content = fields[front_field_name].get("value", "")
                # Clean the HTML content before displaying
                front_content = clean_html_content(front_content)
                tags = card.get("noteTags", [])
                due_date = "N/A"
                dueQuery = card.get("dueQuery", 90)

                if dueQuery > -1:
                    # Calculate due date as today + interval
                    today_timestamp = time.time()
                    due_date_timestamp = today_timestamp + (
                        dueQuery * 86400
                    )  # Convert days to seconds
                    try:
                        due_date = time.strftime(
                            "%Y-%m-%d", time.localtime(due_date_timestamp)
                        )
                    except Exception as e:
                        # Log the error but continue processing
                        click.echo(f"Some error with formatting: {str(e)}", err=True)
                        due_date = "Error"

                # Display the card information
                click.echo(f"  • {front_content}")
                click.echo(f"    Due: {due_date}")
                if tags:
                    click.echo(f"    Tags: {', '.join(tags)}")
                click.echo("")

    except AnkiConnectError as e:
        click.echo(f"Error: {str(e)}", err=True)
        msg = "Make sure Anki is running with AnkiConnect plugin installed."
        click.echo(msg, err=True)


if __name__ == "__main__":
    cli()
