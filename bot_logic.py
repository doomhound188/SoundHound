import wavelink

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

async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    player = payload.player
    if not player or player.queue.is_empty:
        return

    try:
        await player.play_next()
    except Exception as e:
        print(f"Error playing next track: {e}")
