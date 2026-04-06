"""Tests for CLI utility functions."""

from anki_helpers.cli import clean_html_content, load_dotenv


class TestCleanHtmlContent:
    """Tests for clean_html_content."""

    def test_html_tags_removed(self):
        """Test HTML tags are stripped."""
        result = clean_html_content("<p>Hello <strong>world</strong></p>")
        assert result == "Hello world"

    def test_nbsp_replaced(self):
        """Test non-breaking spaces are replaced."""
        result = clean_html_content("Hello&nbsp;world")
        assert result == "Hello world"

    def test_html_entities_decoded(self):
        """Test HTML entities are decoded."""
        result = clean_html_content("&eacute;cole &amp; more")
        assert result == "école & more"

    def test_sound_tags_removed(self):
        """Test [sound:...] tags are removed."""
        result = clean_html_content("Hello[sound:hello.mp3]world")
        assert result == "Helloworld"

    def test_multiple_spaces_cleaned(self):
        """Test multiple spaces are collapsed."""
        result = clean_html_content("Hello    world   test")
        assert result == "Hello world test"

    def test_leading_trailing_whitespace(self):
        """Test leading and trailing whitespace is stripped."""
        result = clean_html_content("  Hello world  ")
        assert result == "Hello world"

    def test_mixed_html_and_sound(self):
        """Test mixed HTML and sound tags."""
        result = clean_html_content("<div>Hello&nbsp;[sound:test.mp3] <strong>world</strong></div>")
        assert result == "Hello world"

    def test_empty_string(self):
        """Test empty string."""
        assert clean_html_content("") == ""

    def test_only_whitespace(self):
        """Test string with only whitespace."""
        assert clean_html_content("   \n\t  ") == ""

    def test_plain_text_unchanged(self):
        """Test plain text passes through."""
        result = clean_html_content("Hello world")
        assert result == "Hello world"


class TestLoadDotenv:
    """Tests for load_dotenv."""

    def test_loads_env_file(self, tmp_path, monkeypatch):
        """Test loading variables from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")

        monkeypatch.chdir(tmp_path)
        load_dotenv()

        import os

        assert os.getenv("KEY1") == "value1"
        assert os.getenv("KEY2") == "value2"

    def test_comments_ignored(self, tmp_path, monkeypatch):
        """Test comments are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nKEY=value\n")

        monkeypatch.chdir(tmp_path)
        load_dotenv()

        import os

        assert os.getenv("KEY") == "value"

    def test_empty_lines_ignored(self, tmp_path, monkeypatch):
        """Test empty lines are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nKEY=value\n\n")

        monkeypatch.chdir(tmp_path)
        load_dotenv()

        import os

        assert os.getenv("KEY") == "value"

    def test_quotes_stripped(self, tmp_path, monkeypatch):
        """Test quotes are stripped from values."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=\"value1\"\nKEY2='value2'\n")

        monkeypatch.chdir(tmp_path)
        load_dotenv()

        import os

        assert os.getenv("KEY1") == "value1"
        assert os.getenv("KEY2") == "value2"

    def test_does_not_override_existing(self, tmp_path, monkeypatch):
        """Test existing env vars are not overridden."""
        import os

        monkeypatch.setenv("EXISTING_KEY", "original_value")

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=new_value\nNEW_KEY=new_value\n")

        monkeypatch.chdir(tmp_path)
        load_dotenv()

        assert os.getenv("EXISTING_KEY") == "original_value"
        assert os.getenv("NEW_KEY") == "new_value"

    def test_no_file_no_error(self, tmp_path, monkeypatch):
        """Test no error when .env file doesn't exist."""
        monkeypatch.chdir(tmp_path)
        load_dotenv()  # Should not raise

    def test_whitespace_around_key_value(self, tmp_path, monkeypatch):
        """Test whitespace around keys and values is handled."""
        env_file = tmp_path / ".env"
        env_file.write_text("  KEY  =  value  \n")

        monkeypatch.chdir(tmp_path)
        load_dotenv()

        import os

        assert os.getenv("KEY") == "value"
