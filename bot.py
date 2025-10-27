import os
import re
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import wavelink

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_URI = os.getenv("LAVALINK_URI")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    """Set up the Wavelink node pool."""
    print(f"{bot.user} is online in {len(bot.guilds)} guild(s).")
    try:
        node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)
        await wavelink.NodePool.connect(client=bot, nodes=[node])
        print(f"Connected to Lavalink node: {node.uri}")
    except Exception as e:
        print(f"Failed to connect to Lavalink node: {e}")


@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    """Event fired when a node has finished connecting."""
    print(f"Node '{node.uri}' is ready.")


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    player = payload.player
    if not player:
        return

    try:
        await player.play_next()
    except Exception as e:
        print(f"Error playing next track: {e}")


async def get_or_connect_player(
    ctx: discord.ApplicationContext,
) -> wavelink.Player | None:
    """Gets the player for the guild, or connects if not present."""
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.respond("You must be connected to a voice channel.", ephemeral=True)
        return None

    player: wavelink.Player = ctx.voice_client
    if (
        player
        and player.is_connected()
        and player.channel.id == ctx.author.voice.channel.id
    ):
        return player

    try:
        player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        return player
    except Exception as e:
        await ctx.respond(f"Failed to connect to voice channel: {e}", ephemeral=True)
        return None


@bot.slash_command(
    name="join", description="Invite the bot to your current voice channel"
)
async def join(ctx: discord.ApplicationContext):
    player = await get_or_connect_player(ctx)
    if player:
        await ctx.respond(f"Joined: {player.channel.name}", ephemeral=True)


@bot.slash_command(name="leave", description="Disconnect the bot from voice")
async def leave(ctx: discord.ApplicationContext):
    player: wavelink.Player = ctx.voice_client
    if not player or not player.is_connected():
        await ctx.respond("I'm not connected to any voice channel.", ephemeral=True)
        return

    await player.disconnect()
    await ctx.respond("Disconnected.", ephemeral=True)


@bot.slash_command(name="stop", description="Stop playback and clear queue")
async def stop(ctx: discord.ApplicationContext):
    player: wavelink.Player = ctx.voice_client
    if not player or not player.is_connected():
        await ctx.respond("I'm not in a voice channel.", ephemeral=True)
        return

    if not player.is_playing() and player.queue.is_empty:
        await ctx.respond("Nothing is playing.", ephemeral=True)
        return

    player.queue.clear()
    await player.stop()
    await ctx.respond("Stopped playback and cleared queue.", ephemeral=True)


@bot.slash_command(
    name="play",
    description="Play a song from query, URL (YouTube, SoundCloud, Spotify)",
)
async def play(ctx: discord.ApplicationContext, query: str):
    await ctx.defer()

    player = await get_or_connect_player(ctx)
    if not player:
        return

    try:
        tracks: wavelink.Search = await wavelink.search(query)
        if not tracks:
            await ctx.respond(f"No results found for: `{query}`")
            return

    except Exception as e:
        await ctx.respond(f"An error occurred during search: {e}")
        return

    if isinstance(tracks, wavelink.Playlist):
        added_count = await player.queue.put_wait(tracks)
        await ctx.respond(
            f"Added **{added_count}** tracks from playlist `{tracks.name}` to the queue."
        )
    else:
        track = tracks[0]
        await player.queue.put_wait(track)
        await ctx.respond(f"Added to queue: **{track.title}**")

    if not player.is_playing():
        await player.play_next()


@bot.slash_command(name="queue", description="View the current song queue")
async def queue_cmd(ctx: discord.ApplicationContext):
    player: wavelink.Player = ctx.voice_client
    if not player:
        await ctx.respond("I'm not connected to voice.", ephemeral=True)
        return

    embed = discord.Embed(title="🎵 Song Queue", color=discord.Color.blue())

    if player.current:
        embed.add_field(
            name="Now Playing", value=f"**{player.current.title}**", inline=False
        )

    if player.queue.is_empty:
        embed.description = "Queue is empty."
    else:
        queue_list = "\n".join(
            [
                f"{i + 1}. {track.title}"
                for i, track in enumerate(player.queue)
                if i < 10
            ]
        )
        if len(player.queue) > 10:
            queue_list += f"\n... and {len(player.queue) - 10} more"

        embed.add_field(
            name=f"Up Next ({len(player.queue)} songs)", value=queue_list, inline=False
        )

    await ctx.respond(embed=embed)


@bot.slash_command(name="skip", description="Skip the current song")
async def skip(ctx: discord.ApplicationContext):
    player: wavelink.Player = ctx.voice_client
    if not player or not player.is_playing():
        await ctx.respond("Nothing is playing.", ephemeral=True)
        return

    await player.stop()
    await ctx.respond("Skipped!", ephemeral=True)


@bot.slash_command(name="clear", description="Clear the entire queue")
async def clear(ctx: discord.ApplicationContext):
    player: wavelink.Player = ctx.voice_client
    if not player or player.queue.is_empty:
        await ctx.respond("Queue is already empty.", ephemeral=True)
        return

    count = len(player.queue)
    player.queue.clear()
    await ctx.respond(f"Cleared {count} song(s) from queue.", ephemeral=True)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing")
    if not LAVALINK_URI or not LAVALINK_PASSWORD:
        raise RuntimeError("Lavalink credentials missing in .env")

    bot.run(DISCORD_TOKEN)
