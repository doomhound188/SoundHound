import wavelink

async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    player = payload.player
    if not player or player.queue.is_empty:
        return

    try:
        await player.play_next()
    except Exception as e:
        print(f"Error playing next track: {e}")
