import wavelink
import asyncio
from collections import OrderedDict
from urllib.parse import urlparse

# LRU Cache settings
MAX_CACHE_SIZE = 100
_search_cache = OrderedDict()
_pending_searches = {}

# Security: Max Queue Size to prevent memory exhaustion
MAX_QUEUE_SIZE = 500

def validate_query(query: str) -> str:
    """
    Validates the search query.
    Raises ValueError if the query is invalid (too long or empty).
    """
    # Optimization: Perform strip once to avoid redundant allocation
    if not query:
        raise ValueError("Query cannot be empty.")

    query = query.strip()
    if not query:
        raise ValueError("Query cannot be empty.")

    if len(query) > 1000:
        raise ValueError("Query is too long (max 1000 characters).")

    # Security: Prevent usage of dangerous protocols (LFI risk)
    # Optimization: Check prefix using slicing to avoid lowercasing the entire string (O(1) vs O(N))
    if query[:7].lower() == "file://":
        raise ValueError("This protocol is not supported for security reasons.")

    # Security: SSRF Protection
    # Prevent requests to local or metadata services
    try:
        parsed = urlparse(query)
    except ValueError:
        # urlparse might raise ValueError for some invalid inputs, but we let them pass
        # as they might be valid search queries that Lavalink handles.
        parsed = None

    if parsed and parsed.scheme in ("http", "https") and parsed.hostname:
        hostname = parsed.hostname.lower()
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254"):
            raise ValueError("This host is not supported for security reasons.")

    return query

async def search_with_cache(query: str):
    """
    Searches for tracks using Wavelink, with LRU caching and Request Coalescing.
    """
    if query in _search_cache:
        # Move to end to mark as recently used
        _search_cache.move_to_end(query)
        return _search_cache[query]

    # Request Coalescing: Check if a search for this query is already in progress
    if query in _pending_searches:
        return await _pending_searches[query]

    # Perform search
    # Create a task to be shared among concurrent requests
    task = asyncio.create_task(wavelink.Playable.search(query))
    _pending_searches[query] = task

    try:
        results = await task

        # Store in cache only on success
        _search_cache[query] = results
        if len(_search_cache) > MAX_CACHE_SIZE:
            _search_cache.popitem(last=False)  # Remove first (oldest) item

        return results
    finally:
        # Always remove from pending, whether success, error, or cancellation
        if query in _pending_searches:
            del _pending_searches[query]

async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    player = payload.player
    if not player or player.queue.is_empty:
        return

    try:
        # Optimization: Prevent costly exception handling by calling the correct method directly.
        # Wavelink 3.x Player does not have a play_next() method, which caused an AttributeError
        # and stopped playback. Using queue.get() restores O(1) track transition.
        await player.play(player.queue.get())
    except Exception as e:
        print(f"Error playing next track: {e}")
