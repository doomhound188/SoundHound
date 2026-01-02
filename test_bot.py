import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, PropertyMock

# Mock wavelink
# We need to ensure wavelink.Playable is also mocked properly before importing bot_logic
mock_wavelink = MagicMock()
sys.modules['wavelink'] = mock_wavelink

import bot_logic


class TestOnWavelinkTrackEnd(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the on_wavelink_track_end event handler in bot_logic.py.
    """

    async def test_on_wavelink_track_end_empty_queue_does_not_play_next(self):
        """
        It checks that play is NOT called when the queue is empty.
        """
        # Arrange
        mock_player = MagicMock()
        mock_player.play = AsyncMock()

        mock_queue = MagicMock()
        mock_queue.is_empty = True
        type(mock_player).queue = PropertyMock(return_value=mock_queue)

        mock_payload = MagicMock()
        mock_payload.player = mock_player

        # Act
        await bot_logic.on_wavelink_track_end(mock_payload)

        # Assert
        mock_player.play.assert_not_called()

    async def test_on_wavelink_track_end_non_empty_queue_plays_next(self):
        """
        It checks that play IS called with the next track when the queue is not empty.
        """
        # Arrange
        mock_player = MagicMock()
        mock_player.play = AsyncMock()

        mock_queue = MagicMock()
        mock_queue.is_empty = False
        mock_track = MagicMock()
        mock_queue.get.return_value = mock_track
        type(mock_player).queue = PropertyMock(return_value=mock_queue)

        mock_payload = MagicMock()
        mock_payload.player = mock_player

        # Act
        await bot_logic.on_wavelink_track_end(mock_payload)

        # Assert
        mock_player.play.assert_called_once_with(mock_track)


class TestValidateQuery(unittest.TestCase):
    """
    Tests for the validate_query function in bot_logic.py.
    """

    def test_validate_query_valid(self):
        query = "valid query"
        result = bot_logic.validate_query(query)
        self.assertEqual(result, query)

    def test_validate_query_empty(self):
        with self.assertRaises(ValueError):
            bot_logic.validate_query("")
        with self.assertRaises(ValueError):
            bot_logic.validate_query("   ")

    def test_validate_query_too_long(self):
        query = "a" * 1001
        with self.assertRaises(ValueError):
            bot_logic.validate_query(query)

    def test_validate_query_max_length(self):
        query = "a" * 1000
        result = bot_logic.validate_query(query)
        self.assertEqual(result, query)


class TestSearchWithCache(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the search_with_cache function in bot_logic.py.
    """

    def setUp(self):
        # Clear the cache before each test
        bot_logic._search_cache.clear()
        # Reset mock
        bot_logic.wavelink.Playable.search = AsyncMock()

    async def test_search_cache_hit(self):
        query = "cached song"
        mock_result = ["track1", "track2"]
        bot_logic.wavelink.Playable.search.return_value = mock_result

        # First call: Cache miss
        res1 = await bot_logic.search_with_cache(query)
        self.assertEqual(res1, mock_result)
        bot_logic.wavelink.Playable.search.assert_called_once_with(query)

        # Second call: Cache hit
        res2 = await bot_logic.search_with_cache(query)
        self.assertEqual(res2, mock_result)
        # Verify search was NOT called again
        bot_logic.wavelink.Playable.search.assert_called_once()

    async def test_search_cache_miss_different_queries(self):
        query1 = "song A"
        query2 = "song B"
        bot_logic.wavelink.Playable.search.side_effect = [["A"], ["B"]]

        # First call
        await bot_logic.search_with_cache(query1)
        # Second call
        await bot_logic.search_with_cache(query2)

        self.assertEqual(bot_logic.wavelink.Playable.search.call_count, 2)

    async def test_cache_eviction(self):
        # Decrease max size for testing
        original_max = bot_logic.MAX_CACHE_SIZE
        bot_logic.MAX_CACHE_SIZE = 2
        try:
            bot_logic.wavelink.Playable.search.return_value = ["res"]

            await bot_logic.search_with_cache("q1")
            await bot_logic.search_with_cache("q2")
            await bot_logic.search_with_cache("q3") # q1 should be evicted

            # Cache should contain q2 and q3
            self.assertIn("q2", bot_logic._search_cache)
            self.assertIn("q3", bot_logic._search_cache)
            self.assertNotIn("q1", bot_logic._search_cache)

            # Accessing q2 should move it to end (most recent)
            await bot_logic.search_with_cache("q2")

            # Add q4 -> q3 should be evicted (LRU), q2 stays
            await bot_logic.search_with_cache("q4")

            self.assertIn("q2", bot_logic._search_cache)
            self.assertIn("q4", bot_logic._search_cache)
            self.assertNotIn("q3", bot_logic._search_cache)

        finally:
            bot_logic.MAX_CACHE_SIZE = original_max

if __name__ == '__main__':
    unittest.main()
