import os
import asyncio
import itertools
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import wavelink
from bot_logic import (
    on_wavelink_track_end as on_wavelink_track_end_logic,
    validate_query,
    search_with_cache,
)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_URI = os.getenv("LAVALINK_URI", "http://lavalink:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")


# Parse host/port from LAVALINK_URI
# supports forms like http://host:2333 or host:2333
def parse_host_port(uri: str) -> tuple[str, int]:
    u = uri.replace("http://", "").replace("https://", "")
    host, _, port = u.partition(":")
    return host, int(port) if port else 2333


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Wavelink 3 client
wl: wavelink.Node | None = None


@bot.event
async def on_ready():
    print(f"{bot.user} is online in {len(bot.guilds)} guild(s).")
    try:
        host, port = parse_host_port(LAVALINK_URI)
        uri = f"http://{host}:{port}"

        # Build node object
        node = wavelink.Node(uri=uri, password=LAVALINK_PASSWORD)

        # Connect via Pool
        await wavelink.Pool.connect(nodes=[node], client=bot)

        print(f"Connected/registered Lavalink node: {uri}")
    except Exception as e:
        print(f"Failed to connect to Lavalink node: {e}")


# Events (3.x)
@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    print(f"Node '{node.identifier}' is ready.")


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    await on_wavelink_track_end_logic(payload)


async def get_or_connect_player(
    inter: discord.Interaction,
) -> wavelink.Player | None:
    """Get or create a Player bound to the user's voice channel."""
    if (
        not isinstance(inter.user, discord.Member)
        or not inter.user.voice
        or not inter.user.voice.channel
    ):
        await inter.response.send_message(
            "You must be connected to a voice channel.", ephemeral=True
        )
        return None

    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if (
        player
        and player.connected
        and player.channel.id == inter.user.voice.channel.id
    ):
        return player

    try:
        # Create a player by connecting to the voice channel
        # Wavelink 3: pass cls=wavelink.Player is still valid
        player = await inter.user.voice.channel.connect(cls=wavelink.Player)
        return player
    except Exception as e:
        # Security: Don't leak exception details (e.g., internal IPs) to user
        print(f"Voice connection error: {e}")
        msg = "Failed to connect to voice channel. Please check permissions and try again."
        if not inter.response.is_done():
            await inter.response.send_message(msg, ephemeral=True)
        else:
            await inter.followup.send(msg, ephemeral=True)
        return None


def is_privileged(inter: discord.Interaction, player: wavelink.Player) -> bool:
    """
    Check if the user is privileged to modify playback state.
    User must be in the same voice channel as the bot.
    """
    if not isinstance(inter.user, discord.Member) or not inter.user.voice or not inter.user.voice.channel:
        return False
    return inter.user.voice.channel.id == player.channel.id


# Slash commands via app_commands (commands.Bot + bot.tree)
@bot.tree.command(
    name="join", description="Invite the bot to your current voice channel"
)
async def join(inter: discord.Interaction):
    player = await get_or_connect_player(inter)
    if not player:
        return
    await inter.response.send_message(f"Joined: {player.channel.name}", ephemeral=True)


@bot.tree.command(name="leave", description="Disconnect the bot from voice")
async def leave(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or not player.connected:
        await inter.response.send_message(
            "I'm not connected to any voice channel.", ephemeral=True
        )
        return

    if not is_privileged(inter, player):
        await inter.response.send_message(
            "You must be in the same voice channel to use this command.", ephemeral=True
        )
        return

    await player.disconnect()
    await inter.response.send_message("Disconnected.", ephemeral=True)


@bot.tree.command(name="stop", description="Stop playback and clear queue")
async def stop(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or not player.connected:
        await inter.response.send_message("I'm not in a voice channel.", ephemeral=True)
        return

    if not is_privileged(inter, player):
        await inter.response.send_message(
            "You must be in the same voice channel to use this command.", ephemeral=True
        )
        return

    if not player.playing and player.queue.is_empty:
        await inter.response.send_message("Nothing is playing.", ephemeral=True)
        return

    player.queue.clear()
    try:
        await player.stop()
    except Exception:
        pass
    await inter.response.send_message(
        "Stopped playback and cleared queue.", ephemeral=True
    )


@bot.tree.command(
    name="play",
    description="Play a song from query, URL (YouTube, SoundCloud, Spotify)",
)
@app_commands.describe(query="Song name or URL")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: (i.guild_id, i.user.id))
async def play(inter: discord.Interaction, query: str):
    await inter.response.defer(thinking=True)

    # 1. Security: Validate input
    try:
        query = validate_query(query)
    except ValueError as e:
        await inter.followup.send(f"Invalid query: {e}")
        return

    # Optimize: concurrently connect to voice and search for tracks
    # This reduces the total time by overlapping the voice connection and search latency.
    player_task = asyncio.create_task(get_or_connect_player(inter))
    search_task = asyncio.create_task(search_with_cache(query))

    player = await player_task
    if not player:
        # If connection failed, we don't need the search results
        search_task.cancel()
        return

    try:
        # Wavelink 3.x search API
        results = await search_task
        if not results:
            # We sanitize the query in the output just in case, though backticks help
            # Limiting the output length of query prevents massive messages if query was just under limit
            safe_query = query[:100] + "..." if len(query) > 100 else query
            await inter.followup.send(f"No results found for: `{safe_query}`")
            return
    except Exception as e:
        # 2. Security: Don't leak exception details to user
        # Sanitize query in logs to prevent log injection
        safe_query_log = query.replace("\n", " ").replace("\r", " ")
        print(f"Search error for query '{safe_query_log}': {e}")
        await inter.followup.send("An error occurred during search. Please try again later.")
        return

    # results can be a list of Tracks or a Playlist object (depends on source)
    if isinstance(results, wavelink.Playlist):
        # Playlist: add all tracks
        # Optimization: play the first track immediately if idle
        tracks = results.tracks
        if not tracks:
            await inter.followup.send("Playlist is empty.")
            return

        start_index = 0
        if not player.playing:
            await player.play(tracks[0])
            start_index = 1

        for t in itertools.islice(tracks, start_index, None):
            player.queue.put(t)

        await inter.followup.send(
            f"Added {len(tracks)} tracks from playlist `{results.name}` to the queue."
        )
    else:
        # Assume list of tracks
        track = results[0]

        # Optimization: play immediately if idle, skipping queue operations
        if not player.playing:
            await player.play(track)
            await inter.followup.send(f"Playing: **{track.title}**")
        else:
            player.queue.put(track)
            await inter.followup.send(f"Added to queue: **{track.title}**")


@bot.tree.command(name="queue", description="View the current song queue")
async def queue_cmd(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player:
        await inter.response.send_message("I'm not connected to voice.", ephemeral=True)
        return

    embed = discord.Embed(title="🎵 Song Queue", color=discord.Color.blue())

    if player.current:
        embed.add_field(
            name="Now Playing", value=f"**{player.current.title}**", inline=False
        )

    if player.queue.is_empty:
        embed.description = "Queue is empty."
    else:
        # Optimize: Iterate directly over queue instead of copying to list
        # Wavelink 3 queue is iterable; use islice to get first 10 items
        queue_list = "\n".join(
            [f"{i + 1}. {t.title}" for i, t in enumerate(itertools.islice(player.queue, 10))]
        )

        queue_len = len(player.queue)
        if queue_len > 10:
            queue_list += f"\n... and {queue_len - 10} more"

        embed.add_field(
            name=f"Up Next ({queue_len} songs)", value=queue_list, inline=False
        )

    await inter.response.send_message(embed=embed)


@bot.tree.command(name="skip", description="Skip the current song")
async def skip(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or not player.playing:
        await inter.response.send_message("Nothing is playing.", ephemeral=True)
        return

    if not is_privileged(inter, player):
        await inter.response.send_message(
            "You must be in the same voice channel to use this command.", ephemeral=True
        )
        return

    await player.stop()
    await inter.response.send_message("Skipped!", ephemeral=True)


@bot.tree.command(name="clear", description="Clear the entire queue")
async def clear(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or player.queue.is_empty:
        await inter.response.send_message("Queue is already empty.", ephemeral=True)
        return

    if not is_privileged(inter, player):
        await inter.response.send_message(
            "You must be in the same voice channel to use this command.", ephemeral=True
        )
        return

    count = len(player.queue)
    player.queue.clear()
    await inter.response.send_message(
        f"Cleared {count} song(s) from queue.", ephemeral=True
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"Slow down! Try again in {error.retry_after:.2f}s", ephemeral=True
        )
    else:
        print(f"App command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "An error occurred while processing the command.", ephemeral=True
            )


@bot.event
async def setup_hook():
    # For fast dev sync, you can target a specific guild:
    # guild = discord.Object(id=YOUR_GUILD_ID)
    # await bot.tree.sync(guild=guild)
    # print("Slash commands synced (guild).")
    try:
        await bot.tree.sync()
        print("Slash commands synced (global).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing")
    if not LAVALINK_URI or not LAVALINK_PASSWORD:
        raise RuntimeError("Lavalink credentials missing in .env")

    bot.run(DISCORD_TOKEN)
