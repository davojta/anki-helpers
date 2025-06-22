"""Command-line interface for Anki Helpers."""

import html
import os
import re
import time
from pathlib import Path

import click
from openai import OpenAI

from .anki_connect import AnkiConnect, AnkiConnectError
from .prompts.examples_for_red_cards import get_prompt


# Manually load .env file
def load_dotenv():
    """Load environment variables from a .env file.

    Searches for a .env file in the current directory and loads
    environment variables from it if found. Variables are only set
    if they don't already exist in the environment.
    """
    env_path = Path(".") / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    # Only set environment variable if it doesn't already exist
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip().strip("\"'")


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
    # Hardcoded version to avoid importing from anki_helpers
    __version__ = "0.1.0"

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


@cli.command()
@click.argument("output-dir", type=click.Path(file_okay=False, dir_okay=True))
@click.option(
    "--limit", default=None, type=int, help="Limit the number of words to process"
)
def get_examples_for_red_flags_cards(output_dir, limit):
    """Generate example sentences for red flag cards.

    This command:
    1. Queries cards with red flags
    2. Creates a markdown file with the content of these cards
    3. Calls OpenAI API to generate example sentences
    4. Outputs the response to console and file

    Args:
        output_dir: Directory where output files will be saved
        limit: Maximum number of words to process (default: all words)
    """
    try:
        # Load API key from .env file
        load_dotenv()
        api_key = os.getenv("API_KEY")

        if not api_key:
            click.echo("Error: API_KEY not found in .env file", err=True)
            return

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Query cards with red flags
        anki = AnkiConnect()
        cards = anki.find_cards_with_red_flag_sorted()

        if not cards:
            click.echo("No cards with red flags found.")
            return

        # Extract words from cards
        words = []
        # Apply limit if specified
        cards_to_process = cards[:limit] if limit is not None else cards

        for card in cards_to_process:
            fields = card.get("noteFields", {})
            front_field_name = next(iter(fields.keys()), None)

            if front_field_name:
                front_content = fields[front_field_name].get("value", "")
                # Clean the HTML content
                front_content = clean_html_content(front_content)
                words.append(front_content)

        # Create input-words.md file
        input_file_path = output_path / "input-words.md"
        with open(input_file_path, "w") as f:
            f.write("\n".join(words))

        click.echo(f"Created input file with {len(words)} words at {input_file_path}")

        # Prepare prompt for OpenAI
        with open(input_file_path, "r") as f:
            words_content = f.read()

        prompt = get_prompt(words_content)

        model = "gpt-4o"
        # Log details about the API call
        click.echo("Preparing OpenAI API call:")
        click.echo(f"- Model: {model}")
        click.echo(f"- Input words count: {len(words)}")
        click.echo(f"- Prompt length: {len(prompt)} characters")
        click.echo(
            "- System message: 'You are a helpful assistant for language learning.'"
        )

        # Write prompt to a debug file
        debug_prompt_path = output_path / "debug-prompt.txt"
        with open(debug_prompt_path, "w") as f:
            f.write(f"MODEL: {model}\n\n")
            f.write(
                "SYSTEM MESSAGE:\nYou are a helpful assistant for language learning.\n\n"
            )
            f.write(f"USER MESSAGE:\n{prompt}")
        click.echo(f"- Full prompt saved to: {debug_prompt_path}")

        # Call OpenAI API
        client = OpenAI(api_key=api_key)
        # create a system prompt as a variable and pass it here
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant for language learning.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        # Get response content
        response_content = response.choices[0].message.content

        # Output to console
        click.echo("\nOpenAI Response:")
        click.echo(response_content)

        # Save to results.md
        results_file_path = output_path / "results.md"
        with open(results_file_path, "w") as f:
            f.write(response_content)

        click.echo(f"\nResults saved to {results_file_path}")

    except AnkiConnectError as e:
        click.echo(f"Error: {str(e)}", err=True)
        msg = "Make sure Anki is running with AnkiConnect plugin installed."
        click.echo(msg, err=True)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


if __name__ == "__main__":
    cli()
