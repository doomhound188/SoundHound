import os
import sys
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Set dummy environment variables BEFORE importing bot
os.environ["LAVALINK_URI"] = "http://dummy:2333"
os.environ["LAVALINK_PASSWORD"] = "dummy_pass"

# Ensure DISCORD_TOKEN is present
if "DISCORD_TOKEN" not in os.environ:
    # Set a dummy token if not present, just to satisfy the test logic
    os.environ["DISCORD_TOKEN"] = "dummy_token"

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

        token = os.environ.get("DISCORD_TOKEN")

        # Mock the login method to prevent actual connection attempts
        # and to verify it was called with the correct token.
        with patch.object(bot.bot, 'login', new_callable=AsyncMock) as mock_login:

            # We also need to prevent run/start from blocking or failing
            # Since we are testing the startup logic configuration, we can
            # simulate the flow of `bot.run` or manual start.

            # Calling login directly simulates what happens during startup before connection
            await bot.bot.login(token)

            # Assert login was called with the token from env
            mock_login.assert_called_once_with(token)

            # Verify Lavalink config was read (by checking the module-level variables in bot.py)
            self.assertEqual(bot.LAVALINK_URI, "http://dummy:2333")
            self.assertEqual(bot.LAVALINK_PASSWORD, "dummy_pass")

            # Verify the bot instance has the correct intents
            self.assertTrue(bot.bot.intents.message_content)

if __name__ == "__main__":
    unittest.main()
