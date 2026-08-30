import unittest
import os
import sys
from unittest.mock import MagicMock

# Mock discord and wavelink before import
mock_discord = MagicMock()
sys.modules['discord'] = mock_discord
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['wavelink'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
mock_app_commands = MagicMock()
sys.modules['discord.app_commands'] = mock_app_commands

# Set env vars to prevent import errors or side effects
os.environ["DISCORD_TOKEN"] = "dummy_token"
os.environ["LAVALINK_URI"] = "http://dummy:2333"
os.environ["LAVALINK_PASSWORD"] = "dummy_pass"

from bot import parse_lavalink_uri

class TestLavalinkUriParsing(unittest.TestCase):
    def test_http_uri(self):
        uri = "http://localhost:2333"
        result = parse_lavalink_uri(uri)
        self.assertEqual(result, "http://localhost:2333")

    def test_https_uri(self):
        uri = "https://secure.lavalink:443"
        result = parse_lavalink_uri(uri)
        self.assertEqual(result, "https://secure.lavalink:443")

    def test_no_scheme_default_port(self):
        uri = "localhost"
        result = parse_lavalink_uri(uri)
        self.assertEqual(result, "http://localhost:2333")

    def test_no_scheme_custom_port(self):
        uri = "localhost:8080"
        result = parse_lavalink_uri(uri)
        self.assertEqual(result, "http://localhost:8080")

if __name__ == "__main__":
    unittest.main()
