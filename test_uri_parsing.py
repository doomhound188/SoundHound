import unittest
import os
import sys

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
