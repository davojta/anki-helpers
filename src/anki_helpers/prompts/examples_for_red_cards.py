"""Prompt templates for generating example sentences for red flagged cards."""

from .examples_for_word import get_prompt as get_word_prompt


def get_prompt(words_content: str) -> str:
    """Generate prompt for getting example sentences for red flag cards.

    Args:
        words_content: Content containing the words to generate examples for

    Returns:
        Formatted prompt string
    """
    return get_word_prompt(words_content)
