import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, PropertyMock

# Mock wavelink
sys.modules['wavelink'] = MagicMock()

import bot_logic


class TestOnWavelinkTrackEnd(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the on_wavelink_track_end event handler in bot_logic.py.
    """

    async def test_on_wavelink_track_end_empty_queue_does_not_play_next(self):
        """
        This test is expected to FAIL before the fix.
        It checks that play_next is NOT called when the queue is empty.
        """
        # Arrange
        mock_player = MagicMock()
        mock_player.play_next = AsyncMock()

        mock_queue = MagicMock()
        mock_queue.is_empty = True
        type(mock_player).queue = PropertyMock(return_value=mock_queue)

        mock_payload = MagicMock()
        mock_payload.player = mock_player

        # Act
        await bot_logic.on_wavelink_track_end(mock_payload)

        # Assert
        mock_player.play_next.assert_not_called()

    async def test_on_wavelink_track_end_non_empty_queue_plays_next(self):
        """
        This test is expected to PASS before and after the fix.
        It checks that play_next IS called when the queue is not empty.
        """
        # Arrange
        mock_player = MagicMock()
        mock_player.play_next = AsyncMock()

        mock_queue = MagicMock()
        mock_queue.is_empty = False
        type(mock_player).queue = PropertyMock(return_value=mock_queue)

        mock_payload = MagicMock()
        mock_payload.player = mock_player

        # Act
        await bot_logic.on_wavelink_track_end(mock_payload)

        # Assert
        mock_player.play_next.assert_called_once()


if __name__ == '__main__':
    unittest.main()
