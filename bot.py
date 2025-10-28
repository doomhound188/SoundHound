import os
import re
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import wavelink

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_URI = os.getenv("LAVALINK_URI")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


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
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Event fired when a track ends. Used for auto-play."""
    player = payload.player
    if not player:
        return

    try:
        await player.play_next()
    except Exception as e:
        print(f"Error playing next track: {e}")


async def get_or_connect_player(ctx) -> wavelink.Player | None:
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
    if not player or not player.is_connected():
        await inter.response.send_message(
            "I'm not connected to any voice channel.", ephemeral=True
        )
        return
    await player.disconnect()
    await inter.response.send_message("Disconnected.", ephemeral=True)


@bot.tree.command(name="stop", description="Stop playback and clear queue")
async def stop(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or not player.is_connected():
        await inter.response.send_message("I'm not in a voice channel.", ephemeral=True)
        return
    if not player.is_playing() and player.queue.is_empty:
        await inter.response.send_message("Nothing is playing.", ephemeral=True)
        return
    player.queue.clear()
    await player.stop()
    await inter.response.send_message(
        "Stopped playback and cleared queue.", ephemeral=True
    )


@bot.tree.command(
    name="play",
    description="Play a song from query, URL (YouTube, SoundCloud, Spotify)",
)
@app_commands.describe(query="Song name or URL")
async def play(inter: discord.Interaction, query: str):
    await inter.response.defer(thinking=True, ephemeral=False)

    player = await get_or_connect_player(inter)
    if not player:
        return

    try:
        tracks: wavelink.Search = await wavelink.search(query)
        if not tracks:
            await inter.followup.send(f"No results found for: `{query}`")
            return
    except Exception as e:
        await inter.followup.send(f"An error occurred during search: {e}")
        return

    if isinstance(tracks, wavelink.Playlist):
        added_count = await player.queue.put_wait(tracks)
        await inter.followup.send(
            f"Added {added_count} tracks from playlist `{tracks.name}` to the queue."
        )
    else:
        track = tracks[0]
        await player.queue.put_wait(track)
        await inter.followup.send(f"Added to queue: **{track.title}**")

    if not player.is_playing():
        await player.play_next()


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

    await inter.response.send_message(embed=embed)


@bot.tree.command(name="skip", description="Skip the current song")
async def skip(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or not player.is_playing():
        await inter.response.send_message("Nothing is playing.", ephemeral=True)
        return
    await player.stop()
    await inter.response.send_message("Skipped!", ephemeral=True)


@bot.tree.command(name="clear", description="Clear the entire queue")
async def clear(inter: discord.Interaction):
    player: wavelink.Player = inter.guild.voice_client if inter.guild else None
    if not player or player.queue.is_empty:
        await inter.response.send_message("Queue is already empty.", ephemeral=True)
        return
    count = len(player.queue)
    player.queue.clear()
    await inter.response.send_message(
        f"Cleared {count} song(s) from queue.", ephemeral=True
    )


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing")
    if not LAVALINK_URI or not LAVALINK_PASSWORD:
        raise RuntimeError("Lavalink credentials missing in .env")

    bot.run(DISCORD_TOKEN)
