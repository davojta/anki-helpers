"""Tests for prompt templates."""

from anki_helpers.prompts.examples_for_red_cards import get_prompt as get_red_cards_prompt
from anki_helpers.prompts.examples_for_word import get_prompt as get_word_prompt


class TestRedCardsPrompt:
    """Tests for examples_for_red_cards.get_prompt."""

    def test_returns_prompt_with_words(self):
        """Test prompt includes the words content."""
        words = "kissa\nkoira"
        result = get_red_cards_prompt(words)

        assert "kissa" in result
        assert "koira" in result

    def test_prompt_structure(self):
        """Test prompt has expected structure."""
        result = get_red_cards_prompt("testword")

        assert "I'm learning finnish" in result
        assert "5 example sentences" in result
        assert "AI" in result
        assert "well-being" in result
        assert "ecology" in result
        assert "cycling" in result

    def test_multiple_words(self):
        """Test prompt with multiple words."""
        words = "word1\nword2\nword3"
        result = get_red_cards_prompt(words)

        assert "word1" in result
        assert "word2" in result
        assert "word3" in result


class TestWordPrompt:
    """Tests for examples_for_word.get_prompt."""

    def test_returns_prompt_with_words(self):
        """Test prompt includes the words content."""
        words = "kissa\nkoira"
        result = get_word_prompt(words)

        assert "kissa" in result
        assert "koira" in result

    def test_default_topics(self):
        """Test prompt has hardcoded topics (topics param not used in current impl)."""
        result = get_word_prompt("testword")

        # The prompt template has hardcoded themes
        assert "AI" in result
        assert "well-being" in result
        assert "ecology" in result
        assert "cycling" in result

    def test_custom_topics_ignored(self):
        """Test topics param is currently not incorporated into prompt."""
        # The function accepts topics but doesn't use them in the prompt template
        result_with_custom = get_word_prompt("testword", topics=["food", "music", "travel"])
        result_without = get_word_prompt("testword")

        # Currently both produce the same result
        assert result_with_custom == result_without

    def test_none_topics(self):
        """Test None topics uses default."""
        result = get_word_prompt("testword", topics=None)

        assert "I'm learning finnish" in result

    def test_prompt_structure(self):
        """Test prompt has expected structure."""
        result = get_word_prompt("testword")

        assert "I'm learning finnish" in result
        assert "5 example sentences" in result
