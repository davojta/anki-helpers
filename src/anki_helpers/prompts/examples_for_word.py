"""Prompt templates for generating examples for specific words."""


def get_prompt(words_content: str, topics: list | None = None) -> str:
    """Generate prompt for getting examples for specific words.

    Args:
        words_content: Content containing the words to generate examples for
        topics: List of topics to generate examples for

    Returns:
        Formatted prompt string
    """
    if topics is None:
        topics = ["well-being", "nature", "artificial intelligence"]

    return f"""I'm learning finnish language on level A2.
Please generate 5 example sentences for each words provided below with translation to english.
- one simple and short sentence (near 7 words)
- one medium (7-12 words) length sentence on theme of AI
- one medium (7-12 words) length sentence on theme of well-being
- one medium (7-12 words) length sentence on theme of ecology and responsible consumption
- one medium (7-12 words) length sentence on theme of cycling as a hobby in finland
Words:
{words_content}"""
