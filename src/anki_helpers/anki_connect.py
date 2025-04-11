"""AnkiConnect API client for Anki Helpers."""

from typing import Any, List

import requests


class AnkiConnectError(Exception):
    """Base exception for AnkiConnect related errors."""

    pass


class AnkiConnect:
    """Client for interacting with AnkiConnect API."""

    def __init__(self, url: str = "http://localhost:8765"):
        """Initialize AnkiConnect client.

        Args:
            url: The URL where AnkiConnect is running.
                Defaults to localhost:8765.
        """
        self.url = url

    def _invoke(self, action: str, **params) -> Any:
        """Invoke an AnkiConnect action.

        Args:
            action: The AnkiConnect action to invoke.
            **params: Additional parameters for the action.

        Returns:
            The response from AnkiConnect.

        Raises:
            AnkiConnectError: If the request fails or returns
                an error.
        """
        try:
            response = requests.post(
                self.url, json={"action": action, "version": 6, "params": params}
            )
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                msg = f"AnkiConnect error: {result['error']}"
                raise AnkiConnectError(msg)

            return result.get("result")
        except requests.RequestException as e:
            msg = f"Failed to connect to AnkiConnect: {str(e)}"
            raise AnkiConnectError(msg)

    def get_deck_names(self) -> List[str]:
        """Get a list of all deck names.

        Returns:
            A list of deck names.
        """
        return self._invoke("deckNames")
