"""Command-line interface for Anki Helpers."""

import html
import json
import math
import os
import re
import time
from pathlib import Path

import click
from openai import OpenAI

from .anki_connect import AnkiConnect, AnkiConnectError
from .data_transform import merge_notes_and_cards
from .prompts.examples_for_red_cards import get_prompt
from .prompts.examples_for_word import get_prompt as get_word_prompt
from .sqlite_storage import SQLiteStorage


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
def sync():
    """Sync Anki data into local SQLite cache.

    Performs an initial full load on first run, then incremental
    updates on subsequent runs.
    """
    try:
        anki = AnkiConnect()
        db_path = Path(".anki-cache.db")

        with SQLiteStorage(db_path) as storage:
            last_sync = storage.get_last_sync()

            if last_sync is None:
                # Initial sync
                click.echo("Performing initial sync...")

                notes_info = anki.get_all_notes_info()
                if not notes_info:
                    click.echo("No notes found in Anki.")
                    return

                # Collect all card IDs from notes
                card_ids = []
                for note in notes_info:
                    card_ids.extend(note.get("cards", []))

                if not card_ids:
                    click.echo("No cards found.")
                    return

                cards_info = anki.get_cards_info(card_ids)
                days_elapsed = anki.get_days_elapsed()

                rows = merge_notes_and_cards(notes_info, cards_info, days_elapsed)
                storage.replace_all(rows)

                total_cards = storage.get_total_cards()
                deck_count = len(storage.get_deck_names())
                storage.add_sync_log(
                    total_cards=total_cards,
                    deck_count=deck_count,
                    new_cards=total_cards,
                    updated_cards=0,
                )

                click.echo("Initial sync complete.")
                click.echo(f"  Total cards: {total_cards}")
                click.echo(f"  Decks: {deck_count}")
            else:
                # Incremental sync
                synced_at_epoch = last_sync["synced_at_epoch"]
                now_epoch = int(time.time())
                days_since = max(1, math.ceil((now_epoch - synced_at_epoch) / 86400) + 1)

                note_ids = anki.find_edited_notes(days_since)
                if not note_ids:
                    click.echo(f"No changes since last sync ({last_sync['synced_at']}).")
                    return

                notes_info = anki.find_notes_info(note_ids)

                # Client-side precision filter
                filtered = [n for n in notes_info if n.get("mod", 0) > synced_at_epoch]
                if not filtered:
                    click.echo(f"No changes since last sync ({last_sync['synced_at']}).")
                    return

                # Collect card IDs from filtered notes
                card_ids = []
                for note in filtered:
                    card_ids.extend(note.get("cards", []))

                if not card_ids:
                    click.echo("No cards to update.")
                    return

                cards_info = anki.get_cards_info(card_ids)
                days_elapsed = anki.get_days_elapsed()

                rows = merge_notes_and_cards(filtered, cards_info, days_elapsed)
                new_count, updated_count = storage.upsert_notes(rows)

                total_cards = storage.get_total_cards()
                deck_count = len(storage.get_deck_names())
                storage.add_sync_log(
                    total_cards=total_cards,
                    deck_count=deck_count,
                    new_cards=new_count,
                    updated_cards=updated_count,
                )

                click.echo("Incremental sync complete.")
                click.echo(f"  New cards: {new_count}")
                click.echo(f"  Updated cards: {updated_count}")
                click.echo(f"  Total cards: {total_cards}")

    except AnkiConnectError as e:
        click.echo(f"Error: {str(e)}", err=True)
        click.echo("Make sure Anki is running with AnkiConnect plugin installed.", err=True)


def _warn_stale_data(storage: SQLiteStorage) -> None:
    """Warn if cached data is stale or missing.

    Args:
        storage: SQLiteStorage instance to check.
    """
    last_sync = storage.get_last_sync()
    if last_sync is None:
        click.echo("Warning: No cached data found. Run 'sync' first.", err=True)
        return
    synced_at_epoch = last_sync["synced_at_epoch"]
    age_seconds = int(time.time()) - synced_at_epoch
    if age_seconds > 86400:  # 24 hours
        click.echo(
            f"Warning: Cached data is {age_seconds // 3600} hours old. Run 'sync' to update.",
            err=True,
        )


@cli.command()
@click.option("--limit", default=5, help="Limit the number of cards displayed")
@click.option("--local", is_flag=True, default=False, help="Read from local SQLite cache")
def list_red_flags(limit, local):
    """List all words with red flags in Anki, sorted by due date (descending)."""
    if local:
        db_path = Path(".anki-cache.db")
        if not db_path.exists():
            click.echo("No local database found. Run 'sync' first.", err=True)
            return

        with SQLiteStorage(db_path) as storage:
            _warn_stale_data(storage)
            cards = storage.get_cards_by_flag(1)

            if not cards:
                click.echo("No cards with red flags found.")
                return

            click.echo(f"Cards with red flags (sorted by due date, showing top {limit}):")
            for card in cards[:limit]:
                fields = json.loads(card.get("fields", "{}"))
                front_field_name = next(iter(fields.keys()), None)
                if front_field_name:
                    front_content = clean_html_content(fields[front_field_name])
                    tags = json.loads(card.get("tags", "[]"))
                    due_query = card.get("due_query", 90)

                    today_timestamp = time.time()
                    due_date_timestamp = today_timestamp + (due_query * 86400)
                    due_date = "N/A"
                    try:
                        due_date = time.strftime("%Y-%m-%d", time.localtime(due_date_timestamp))
                    except (OSError, ValueError):
                        due_date = "Error"

                    click.echo(f"  • {front_content}")
                    click.echo(f"    Due: {due_date}")
                    if tags:
                        click.echo(f"    Tags: {', '.join(tags)}")
                    click.echo("")
        return

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
                due_date_timestamp = today_timestamp + (dueQuery * 86400)  # Convert days to seconds
                try:
                    due_date = time.strftime("%Y-%m-%d", time.localtime(due_date_timestamp))
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


@cli.group()
def query_anki():
    """Query Anki directly via AnkiConnect."""
    pass


FLAG_MAP = {
    "none": 0,
    "red": 1,
    "orange": 2,
    "green": 3,
    "blue": 4,
    "pink": 5,
    "turquoise": 6,
    "purple": 7,
}


def parse_filters(filter_str: str) -> list[tuple[str, str]]:
    """Parse filter string into list of (key, value) pairs.

    Args:
        filter_str: Filter string like "flag=red:due_date=<10d"

    Returns:
        List of (key, value) tuples.

    Raises:
        click.BadParameter: If filter key is unknown or value is invalid.
    """
    filters = []
    for part in filter_str.split(":"):
        if "=" not in part:
            msg = f"Invalid filter format: {part}. Use key=value"
            raise click.BadParameter(msg)
        key, value = part.split("=", 1)
        if key not in ("flag", "due_date"):
            msg = f"Unknown filter: {key}. Supported filters: flag, due_date"
            raise click.BadParameter(msg)
        if key == "flag" and value not in FLAG_MAP:
            valid = ", ".join(FLAG_MAP.keys())
            msg = f"Invalid flag value: {value}. Supported: {valid}"
            raise click.BadParameter(msg)
        if key == "due_date" and not value.endswith("d"):
            msg = f"Invalid due_date format: {value}. Use <Nd or >Nd"
            raise click.BadParameter(msg)
        filters.append((key, value))
    return filters


def filters_to_anki_query(filters: list[tuple[str, str]]) -> str:
    """Convert filter pairs to Anki search query string.

    Args:
        filters: List of (key, value) tuples.

    Returns:
        Anki search query string.
    """
    parts = []
    for key, value in filters:
        if key == "flag":
            parts.append(f"flag:{FLAG_MAP[value]}")
        elif key == "due_date":
            operator = value[0]
            days = value[1:-1]  # strip operator and 'd'
            parts.append(f"prop:due{operator}{days}")
    return " ".join(parts)


@query_anki.command()
@click.option(
    "--filter", "filter_str", required=True, help="Filter: key=value, multiple with : separator"
)
@click.option("--sort", default="due", type=click.Choice(["due", "interval"]), help="Sort field")
def list_cards(filter_str, sort):
    """List cards matching filters from Anki.

    Supports --filter flag=red:due_date=<10d and --sort due|interval.
    """
    try:
        filters = parse_filters(filter_str)
        anki_query = filters_to_anki_query(filters)

        anki = AnkiConnect()
        card_ids = anki.find_cards(anki_query)

        if not card_ids:
            click.echo("No cards found.")
            return

        cards_info = anki.get_cards_info(card_ids)

        # Get note IDs and fetch note info
        note_ids = [int(c["note"]) for c in cards_info if c.get("note")]
        notes_info = anki.find_notes_info(list(note_ids))
        notes_by_id = {n["noteId"]: n for n in notes_info}

        # Sort
        if sort == "due":
            cards_info.sort(key=lambda c: c.get("due", 0))
        elif sort == "interval":
            cards_info.sort(key=lambda c: c.get("interval", 0))

        # Print table
        click.echo(
            f"{'Card ID':<10} {'Note ID':<10} {'Deck':<20} {'Due':<6} {'Flag':<5} {'Fields':<30} {'Tags'}"
        )
        click.echo("-" * 100)
        for card in cards_info:
            note = notes_by_id.get(card.get("note"), {})
            fields = note.get("fields", {})
            first_field = next(iter(fields.values()), {}).get("value", "")
            first_field = clean_html_content(first_field)[:30]
            tags = ", ".join(note.get("tags", []))
            click.echo(
                f"{card.get('cardId', ''):<10} "
                f"{card.get('note', ''):<10} "
                f"{card.get('deckName', ''):<20} "
                f"{card.get('due', ''):<6} "
                f"{card.get('flags', ''):<5} "
                f"{first_field:<30} "
                f"{tags}"
            )

    except click.BadParameter as e:
        click.echo(f"Error: {str(e)}", err=True)
    except AnkiConnectError as e:
        click.echo(f"Error: {str(e)}", err=True)
        click.echo("Make sure Anki is running with AnkiConnect plugin installed.", err=True)


@cli.command()
@click.argument("output-dir", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--limit", default=None, type=int, help="Limit the number of words to process")
@click.option("--local", is_flag=True, default=False, help="Read from local SQLite cache")
def get_examples_for_red_flags_cards(output_dir, limit, local):
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
        if local:
            db_path = Path(".anki-cache.db")
            if not db_path.exists():
                click.echo("No local database found. Run 'sync' first.", err=True)
                return

            with SQLiteStorage(db_path) as storage:
                _warn_stale_data(storage)
                cards = storage.get_cards_by_flag(1)

            if not cards:
                click.echo("No cards with red flags found.")
                return

            # Extract words from cached cards
            words = []
            cards_to_process = cards[:limit] if limit is not None else cards
            for card in cards_to_process:
                fields = json.loads(card.get("fields", "{}"))
                front_field_name = next(iter(fields.keys()), None)
                if front_field_name:
                    front_content = clean_html_content(fields[front_field_name])
                    words.append(front_content)
        else:
            anki = AnkiConnect()
            cards = anki.find_cards_with_red_flag_sorted()

            if not cards:
                click.echo("No cards with red flags found.")
                return

            # Extract words from cards
            words = []
            cards_to_process = cards[:limit] if limit is not None else cards

            for card in cards_to_process:
                fields = card.get("noteFields", {})
                front_field_name = next(iter(fields.keys()), None)

                if front_field_name:
                    front_content = fields[front_field_name].get("value", "")
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
        click.echo("- System message: 'You are a helpful assistant for language learning.'")

        # Write prompt to a debug file
        debug_prompt_path = output_path / "debug-prompt.txt"
        with open(debug_prompt_path, "w") as f:
            f.write(f"MODEL: {model}\n\n")
            f.write("SYSTEM MESSAGE:\nYou are a helpful assistant for language learning.\n\n")
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
        if not response_content:
            click.echo("Error: Empty response from OpenAI", err=True)
            return

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


@cli.command()
@click.argument("sql")
def query_local(sql):
    """Execute a SQL query against the local Anki cache.

    Only SELECT statements are allowed. Run 'sync' first to create
    the local database.
    """
    db_path = Path(".anki-cache.db")
    if not db_path.exists():
        click.echo("No local database found. Run 'sync' first.", err=True)
        return

    try:
        with SQLiteStorage(db_path) as storage:
            results = storage.execute_sql(sql)

            if not results:
                click.echo("No results.")
                return

            # Print as table
            columns = list(results[0].keys())
            # Header
            click.echo(" | ".join(columns))
            click.echo("-+-".join("-" * len(c) for c in columns))
            # Rows
            for row in results:
                click.echo(" | ".join(str(row.get(c, "")) for c in columns))

    except ValueError as e:
        click.echo(f"Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"SQL error: {str(e)}", err=True)


@cli.command()
@click.argument("words-file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option(
    "--topics",
    default="well-being,nature,artificial intelligence",
    help="Comma-separated list of topics for example sentences",
)
def generate_examples_for_word(words_file, topics):
    """Generate example sentences for words from a file.

    This command:
    1. Reads words from the specified file
    2. Calls OpenAI API to generate examples in markdown table format
    3. Outputs the response to console and saves to examples-table.md

    Args:
        words_file: Path to markdown file containing words in Finnish
        topics: Comma-separated topics for example sentences
    """
    try:
        # Load API key from .env file
        load_dotenv()
        api_key = os.getenv("API_KEY")

        if not api_key:
            click.echo("Error: API_KEY not found in .env file", err=True)
            return

        # Read words from file
        words_path = Path(words_file)
        with open(words_path, encoding="utf-8") as f:
            words_content = f.read()

        if not words_content.strip():
            click.echo("Error: Words file is empty", err=True)
            return

        # Parse topics
        topics_list = [topic.strip() for topic in topics.split(",")]

        # Prepare prompt for OpenAI
        prompt = get_word_prompt(words_content, topics_list)

        model = "gpt-4o"
        # Log details about the API call
        click.echo("Preparing OpenAI API call:")
        click.echo(f"- Model: {model}")
        click.echo(f"- Input file: {words_path}")
        click.echo(f"- Topics: {', '.join(topics_list)}")
        click.echo(f"- Prompt length: {len(prompt)} characters")

        # Call OpenAI API
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant for language learning."
                        " Always format your response as a proper markdown table."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        # Get response content
        response_content = response.choices[0].message.content

        # Output to console
        if not response_content:
            click.echo("Error: Empty response from OpenAI", err=True)
            return

        click.echo("\nGenerated Examples Table:")
        click.echo(response_content)

        # Save to examples-table.md in the same directory as input file
        output_file_path = words_path.parent / "examples-table.md"
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(response_content)

        click.echo(f"\nResults saved to {output_file_path}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


if __name__ == "__main__":
    cli()
