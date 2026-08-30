import wavelink
import asyncio
import socket
import ipaddress
from collections import OrderedDict
from urllib.parse import urlparse

# LRU Cache settings
MAX_CACHE_SIZE = 100
_search_cache = OrderedDict()
_pending_searches = {}

# Security: Max Queue Size to prevent memory exhaustion
MAX_QUEUE_SIZE = 500

async def validate_query(query: str) -> str:
    """
    Validates the search query asynchronously.
    Raises ValueError if the query is invalid (too long or empty) or points to a blocked host.
    """
    # Optimization: Perform strip once to avoid redundant allocation
    if not query:
        raise ValueError("Query cannot be empty.")

    # Optimization: Check length BEFORE strip to prevent DoS from massive allocations (e.g. 10MB whitespace)
    if len(query) > 1000:
        raise ValueError("Query is too long (max 1000 characters).")

    query = query.strip()
    if not query:
        raise ValueError("Query cannot be empty.")

    # Security: Prevent usage of dangerous protocols (LFI risk)
    # Optimization: Check prefix using slicing to avoid lowercasing the entire string (O(1) vs O(N))
    if query[:7].lower() == "file://":
        raise ValueError("This protocol is not supported for security reasons.")

    # Security: Prevent SSRF (Server-Side Request Forgery)
    # Block requests to local/metadata addresses
    # Optimization: Check prefix before parsing to avoid overhead on regular search queries
    lower_query = query.lower()
    if lower_query.startswith("http://") or lower_query.startswith("https://"):
        hostname = None
        try:
            parsed = urlparse(query)
            hostname = parsed.hostname
        except ValueError:
            # If urlparse fails, we might still want to be careful, but we proceed
            pass

        if hostname:
            clean_hostname = hostname.strip("[]")
            loop = asyncio.get_running_loop()
            try:
                # Use type=socket.SOCK_STREAM to limit returned results and mitigate thread pool exhaustion
                addr_info = await asyncio.wait_for(
                    loop.getaddrinfo(clean_hostname, None, type=socket.SOCK_STREAM),
                    timeout=2.0
                )
                for res in addr_info:
                    ip_str = res[4][0]
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified:
                            raise ValueError("This host is blocked for security reasons.")
                    except ValueError as e:
                        if str(e) == "This host is blocked for security reasons.":
                            raise e
                        pass
            except (socket.gaierror, asyncio.TimeoutError):
                raise ValueError("Could not resolve host or timed out.")
            except ValueError as e:
                raise e

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
