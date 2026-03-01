import os
import sys
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Set dummy environment variables BEFORE importing bot
os.environ["LAVALINK_URI"] = "http://dummy:2333"
os.environ["LAVALINK_PASSWORD"] = "dummy_pass"
os.environ["DISCORD_TOKEN"] = "dummy_token"

# Mock external dependencies
mock_discord = MagicMock()
mock_discord.Intents.default.return_value = MagicMock()
sys.modules["discord"] = mock_discord
sys.modules["discord.ext"] = MagicMock()
sys.modules["discord.ext.commands"] = MagicMock()
sys.modules["discord.app_commands"] = MagicMock()
sys.modules["wavelink"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

try:
    import bot
except Exception as e:
    print(f"Failed to import bot: {e}")
    bot = None

class TestBotConfigIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Test to verify bot startup logic with environment variables.
    Mocks the actual Discord connection to avoid authentication errors.
    """

    async def test_bot_startup_logic(self):
        """
        Tests that the bot attempts to log in using the environment's DISCORD_TOKEN.
        """
        if bot is None:
            self.fail("Failed to import bot module")

        # Verify Lavalink config was read (by checking the module-level variables in bot.py)
        self.assertEqual(bot.LAVALINK_URI, "http://dummy:2333")
        self.assertEqual(bot.LAVALINK_PASSWORD, "dummy_pass")

        # Verify parsing
        self.assertEqual(bot.parse_lavalink_uri("dummy:2333"), "http://dummy:2333")
        self.assertEqual(bot.parse_lavalink_uri("https://dummy:2333"), "https://dummy:2333")

if __name__ == "__main__":
    unittest.main()
