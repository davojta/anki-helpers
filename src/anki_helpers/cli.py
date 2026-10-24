"""Command-line interface for Anki Helpers."""

import html
import json
import os
import re
import signal
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import click
from openai import OpenAI

from . import fake_anki
from .anki_connect import AnkiConnect, AnkiConnectError
from .prompts.examples_for_red_cards import get_prompt


# Manually load .env file
def load_dotenv() -> None:
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
def cli() -> None:
    """Anki Helpers - A CLI tool to help with Anki flashcards."""
    load_dotenv()


@cli.command()
def version() -> None:
    """Show the version of Anki Helpers."""
    # Hardcoded version to avoid importing from anki_helpers
    __version__ = "0.1.0"

    click.echo(f"Anki Helpers version {__version__}")


@cli.command()
def hello_world() -> None:
    """Print a hello world message."""
    click.echo("Hello World!")


@cli.command()
def list_deck() -> None:
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
        click.echo(f"Error: {e!s}", err=True)
        msg = "Make sure Anki is running with AnkiConnect plugin installed."
        click.echo(msg, err=True)


@cli.command()
@click.option("--limit", default=5, help="Limit the number of cards displayed")
def list_red_flags(limit: int) -> None:
    """List all words with red flags in Anki, sorted by due date (ascending, most urgent first)."""
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
                    click.echo(f"Some error with formatting: {e!s}", err=True)
                    due_date = "Error"

                # Display the card information
                click.echo(f"  • {front_content}")
                click.echo(f"    Due: {due_date}")
                if tags:
                    click.echo(f"    Tags: {', '.join(tags)}")
                click.echo("")

    except AnkiConnectError as e:
        click.echo(f"Error: {e!s}", err=True)
        msg = "Make sure Anki is running with AnkiConnect plugin installed."
        click.echo(msg, err=True)


@cli.command()
@click.argument("output-dir", type=click.Path(file_okay=False, dir_okay=True))
@click.option(
    "--limit", default=None, type=int, help="Limit the number of words to process"
)
def get_examples_for_red_flags_cards(output_dir: str, limit: int | None) -> None:
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
        # API key comes from the environment (.env is loaded by the cli group)
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
        words: list[str] = []
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
        with open(input_file_path) as f:
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
            f.write(cast("str", response_content))

        click.echo(f"\nResults saved to {results_file_path}")

    except AnkiConnectError as e:
        click.echo(f"Error: {e!s}", err=True)
        msg = "Make sure Anki is running with AnkiConnect plugin installed."
        click.echo(msg, err=True)
    except Exception as e:
        click.echo(f"Error: {e!s}", err=True)


def _load_seed(seed: str | None, empty: bool) -> dict[str, Any]:
    if empty:
        return {}
    if seed is None:
        return fake_anki.sample_seed()
    try:
        data = cast("dict[str, Any]", json.loads(Path(seed).read_text()))
        fake_anki.load_state(data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise click.ClickException(f"bad seed {seed}: {e!r}") from e
    return data


_seed_options = [
    click.option(
        "--seed",
        type=click.Path(exists=True, dir_okay=False),
        help="Seed collection JSON (default: bundled sample).",
    ),
    click.option("--empty", is_flag=True, help="Start with an empty collection."),
]


def seed_options(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Add ``--seed`` and ``--empty`` to a command."""
    for option in reversed(_seed_options):
        fn = option(fn)
    return fn


@cli.group()
def mock() -> None:
    """Fake AnkiConnect for testing without a running Anki."""


@mock.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@seed_options
@click.option(
    "--dump-on-exit",
    type=click.Path(dir_okay=False),
    help="Write the final collection to this JSON file on exit.",
)
def serve(
    host: str, port: int, seed: str | None, empty: bool, dump_on_exit: str | None
) -> None:
    """Serve a fake AnkiConnect v6 API over HTTP until Ctrl+C."""
    server = fake_anki.make_server(_load_seed(seed, empty), host, port)
    click.echo(f"Fake AnkiConnect listening on {server.url}")
    click.echo("Debug: GET /_state, GET /_log, POST /_reset, /_seed, /_faults")

    def stop(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    # SIGTERM (docker stop, kill) and SIGINT (ignored when backgrounded) both
    # end the server cleanly so --dump-on-exit runs.
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.httpd.server_close()
        if dump_on_exit:
            with server.anki.lock:
                state = fake_anki.dump_state(server.anki.state)
            Path(dump_on_exit).write_text(json.dumps(state, indent=2) + "\n")
            click.echo(f"State written to {dump_on_exit}")


@mock.command()
@click.argument("query")
@seed_options
@click.option("--cards", is_flag=True, help="Match cards instead of notes.")
def query(query: str, seed: str | None, empty: bool, cards: bool) -> None:
    """Run an Anki search QUERY against the fake collection and print matches."""
    anki = fake_anki.FakeAnki(state=fake_anki.load_state(_load_seed(seed, empty)))
    reply = anki.handle(
        {"action": "findCards" if cards else "findNotes", "version": 6,
         "params": {"query": query}}
    )  # fmt: skip
    if reply["error"]:
        raise click.ClickException(reply["error"])
    ids = cast("list[int]", reply["result"])
    click.echo(f"{len(ids)} {'card' if cards else 'note'}(s) match {query!r}")
    for id_ in ids:
        card = anki.state.cards[id_] if cards else None
        note = anki.state.notes[card.note_id if card else id_]
        front = clean_html_content(next(iter(note.fields.values()), ""))
        where = f"{card.deck} ord={card.ord}" if card else ", ".join(note.tags)
        click.echo(f"  {id_}  {front}  [{where}]")


if __name__ == "__main__":
    cli()
