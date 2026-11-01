"""Prompt template for generating example sentences for a list of words."""

DEFAULT_TOPICS = (
    "AI",
    "well-being",
    "ecology and responsible consumption",
    "cycling as a hobby in finland",
)


def get_prompt(words_content: str, topics: tuple[str, ...] = DEFAULT_TOPICS) -> str:
    """Generate the prompt asking for example sentences for each word.

    Args:
        words_content: The words, one per line.
        topics: One medium-length sentence is requested per topic.

    Returns:
        Formatted prompt string.
    """
    themed = "".join(
        f"- one medium (7-12 words) length sentence on theme of {topic}\n"
        for topic in topics
    )
    return f"""I'm learning finnish language on level A2.
Please generate {len(topics) + 1} example sentences for each words provided below with translation to english.
- one simple and short sentence (near 7 words)
{themed}Words:
{words_content}"""
