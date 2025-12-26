import wavelink
from collections import OrderedDict

# LRU Cache settings
MAX_CACHE_SIZE = 100
_search_cache = OrderedDict()

def validate_query(query: str) -> str:
    """
    Validates the search query.
    Raises ValueError if the query is invalid (too long or empty).
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if len(query) > 1000:
        raise ValueError("Query is too long (max 1000 characters).")

    return query

async def search_with_cache(query: str):
    """
    Searches for tracks using Wavelink, with LRU caching.
    """
    if query in _search_cache:
        # Move to end to mark as recently used
        _search_cache.move_to_end(query)
        return _search_cache[query]

    # Perform search
    results = await wavelink.Playable.search(query)

    # Store in cache
    _search_cache[query] = results
    if len(_search_cache) > MAX_CACHE_SIZE:
        _search_cache.popitem(last=False)  # Remove first (oldest) item

    return results

async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    player = payload.player
    if not player or player.queue.is_empty:
        return

    try:
        await player.play_next()
    except Exception as e:
        print(f"Error playing next track: {e}")
