import os
import re
import asyncio
import discord
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import yt_dlp
import shutil
from collections import deque

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

spotify = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
    )
)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

VOICE_CLIENTS = {}
QUEUES = {}

YTDLP_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -loglevel error",
}

SPOTIFY_TRACK_RE = re.compile(r"https?://open\.spotify\.com/track/([a-zA-Z0-9]+)")
YOUTUBE_URL_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+")


def get_queue(guild_id: int) -> deque:
    if guild_id not in QUEUES:
        QUEUES[guild_id] = deque()
    return QUEUES[guild_id]


def assert_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg not found in PATH. Install FFmpeg and ensure it's accessible."
        )


def get_youtube_audio_source(query_or_url: str) -> tuple[str, str]:
    with yt_dlp.YoutubeDL(YTDLP_OPTS) as ytdl:
        info = ytdl.extract_info(query_or_url, download=False)
        if "entries" in info:
            info = info["entries"][0]
        if not info:
            raise RuntimeError("No results found")
        stream_url = info.get("url")
        title = info.get("title", "Unknown")
        if not stream_url:
            raise RuntimeError("Could not get audio stream URL")
        return stream_url, title


def spotify_track_to_search_query(url: str) -> str:
    m = SPOTIFY_TRACK_RE.match(url)
    if not m:
        raise ValueError("Not a Spotify track URL")
    track_id = m.group(1)
    track = spotify.track(track_id)
    title = track["name"]
    artists = ", ".join(a["name"] for a in track["artists"])
    return f"{title} - {artists}"


async def ensure_voice(
    ctx: discord.ApplicationContext, timeout: float = 10.0
) -> discord.VoiceClient:
    if not ctx.author.voice or not ctx.author.voice.channel:
        raise RuntimeError("You must be connected to a voice channel.")

    voice_channel = ctx.author.voice.channel
    vc: discord.VoiceClient = ctx.voice_client

    if vc and vc.is_connected() and vc.channel.id == voice_channel.id:
        VOICE_CLIENTS[ctx.guild_id] = vc
        return vc

    if vc and vc.is_connected():
        await vc.move_to(voice_channel)
        VOICE_CLIENTS[ctx.guild_id] = vc
        return vc

    vc = await voice_channel.connect(timeout=timeout, reconnect=True)
    if not vc or not vc.is_connected():
        raise RuntimeError("Failed to connect to voice channel.")

    VOICE_CLIENTS[ctx.guild_id] = vc
    return vc


async def play_next(guild_id: int):
    queue = get_queue(guild_id)
    vc = VOICE_CLIENTS.get(guild_id)

    if not vc or not vc.is_connected():
        return

    if not queue:
        return

    stream_url, title = queue.popleft()

    try:
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        audio = discord.PCMVolumeTransformer(source, volume=0.5)

        def after_playback(error):
            if error:
                print(f"Playback error: {error}")
            asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop)

        vc.play(audio, after=after_playback)
        print(f"Now playing: {title}")
    except Exception as e:
        print(f"Play error: {e}")
        asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop)


@bot.event
async def on_ready():
    assert_ffmpeg()
    print(f"{bot.user} is online in {len(bot.guilds)} guild(s).")
    # print("FFmpeg check: OK")


@bot.slash_command(
    name="join", description="Invite the bot to your current voice channel"
)
async def join(ctx: discord.ApplicationContext):
    try:
        vc = await ensure_voice(ctx)
        await ctx.respond(f"Joined: {vc.channel.name}", ephemeral=True)
    except Exception as e:
        await ctx.respond(f"Join failed: {e}", ephemeral=True)


@bot.slash_command(name="leave", description="Disconnect the bot from voice")
async def leave(ctx: discord.ApplicationContext):
    vc = ctx.voice_client or VOICE_CLIENTS.get(ctx.guild_id)
    if not vc or not vc.is_connected():
        await ctx.respond("I'm not connected to any voice channel.", ephemeral=True)
        return
    try:
        await vc.disconnect(force=True)
        VOICE_CLIENTS.pop(ctx.guild_id, None)
        await ctx.respond("Disconnected.", ephemeral=True)
    except Exception as e:
        await ctx.respond(f"Leave failed: {e}", ephemeral=True)


@bot.slash_command(name="stop", description="Stop playback and clear queue")
async def stop(ctx: discord.ApplicationContext):
    vc = ctx.voice_client or VOICE_CLIENTS.get(ctx.guild_id)
    queue = get_queue(ctx.guild_id)

    if not vc or not vc.is_connected():
        await ctx.respond("I'm not in a voice channel.", ephemeral=True)
        return

    queue.clear()
    if vc.is_playing():
        vc.stop()
        await ctx.respond("Stopped playback and cleared queue.", ephemeral=True)
    else:
        await ctx.respond("Nothing is playing.", ephemeral=True)


@bot.slash_command(
    name="play",
    description="Play audio from a query, YouTube URL, or Spotify track URL",
)
async def play(ctx: discord.ApplicationContext, query: str):
    await ctx.defer()

    try:
        vc = await ensure_voice(ctx)
    except Exception as e:
        await ctx.respond(f"Connection failed: {e}")
        return

    try:
        if SPOTIFY_TRACK_RE.match(query):
            search_query = spotify_track_to_search_query(query)
            stream_url, title = get_youtube_audio_source(search_query)
        elif YOUTUBE_URL_RE.match(query):
            stream_url, title = get_youtube_audio_source(query)
        else:
            stream_url, title = get_youtube_audio_source(query)
    except Exception as e:
        await ctx.respond(f"Lookup failed: {e}")
        return

    queue = get_queue(ctx.guild_id)
    queue.append((stream_url, title))

    if not vc.is_playing():
        await play_next(ctx.guild_id)
        await ctx.respond(f"Now playing: **{title}**")
    else:
        await ctx.respond(f"Added to queue: **{title}** (position {len(queue)})")


@bot.slash_command(name="queue", description="View the current song queue")
async def queue_cmd(ctx: discord.ApplicationContext):
    queue = get_queue(ctx.guild_id)
    vc = ctx.voice_client or VOICE_CLIENTS.get(ctx.guild_id)

    if not queue and (not vc or not vc.is_playing()):
        await ctx.respond("Queue is empty.", ephemeral=True)
        return

    embed = discord.Embed(title="🎵 Song Queue", color=discord.Color.blue())

    if vc and vc.is_playing():
        embed.add_field(name="Now Playing", value="Current song", inline=False)

    if queue:
        queue_list = "\n".join(
            [f"{i + 1}. {title}" for i, (_, title) in enumerate(list(queue)[:10])]
        )
        if len(queue) > 10:
            queue_list += f"\n... and {len(queue) - 10} more"
        embed.add_field(
            name=f"Up Next ({len(queue)} songs)", value=queue_list, inline=False
        )

    await ctx.respond(embed=embed)


@bot.slash_command(name="skip", description="Skip the current song")
async def skip(ctx: discord.ApplicationContext):
    vc = ctx.voice_client or VOICE_CLIENTS.get(ctx.guild_id)

    if not vc or not vc.is_playing():
        await ctx.respond("Nothing is playing.", ephemeral=True)
        return

    vc.stop()  # Triggers after_playback -> play_next
    await ctx.respond("Skipped!", ephemeral=True)


@bot.slash_command(
    name="remove", description="Remove a song from the queue by position"
)
async def remove(ctx: discord.ApplicationContext, position: int):
    queue = get_queue(ctx.guild_id)

    if position < 1 or position > len(queue):
        await ctx.respond(
            f"Invalid position. Queue has {len(queue)} songs.", ephemeral=True
        )
        return

    # Convert deque to list, remove, convert back
    queue_list = list(queue)
    removed = queue_list.pop(position - 1)
    QUEUES[ctx.guild_id] = deque(queue_list)

    await ctx.respond(f"Removed: **{removed[1]}**", ephemeral=True)


@bot.slash_command(name="clear", description="Clear the entire queue")
async def clear(ctx: discord.ApplicationContext):
    queue = get_queue(ctx.guild_id)

    if not queue:
        await ctx.respond("Queue is already empty.", ephemeral=True)
        return

    count = len(queue)
    queue.clear()
    await ctx.respond(f"Cleared {count} song(s) from queue.", ephemeral=True)


@bot.slash_command(name="search", description="Search for a track on Spotify")
async def search(ctx: discord.ApplicationContext, query: str):
    await ctx.defer()
    try:
        results = spotify.search(q=query, limit=5, type="track")
        tracks = results["tracks"]["items"]
        if not tracks:
            await ctx.respond("No tracks found!")
            return
        embed = discord.Embed(
            title=f"Search Results for: {query}", color=discord.Color.green()
        )
        for i, track in enumerate(tracks, 1):
            artists = ", ".join([artist["name"] for artist in track["artists"]])
            embed.add_field(
                name=f"{i}. {track['name']}",
                value=f"Artist(s): {artists}\nAlbum: {track['album']['name']}\n[Listen on Spotify]({track['external_urls']['spotify']})",
                inline=False,
            )
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")


@bot.slash_command(name="artist", description="Get information about an artist")
async def artist(ctx: discord.ApplicationContext, artist_name: str):
    await ctx.defer()
    try:
        results = spotify.search(q=artist_name, limit=1, type="artist")
        artists = results["artists"]["items"]
        if not artists:
            await ctx.respond("Artist not found!")
            return
        artist = artists[0]
        embed = discord.Embed(
            title=artist["name"],
            url=artist["external_urls"]["spotify"],
            color=discord.Color.green(),
        )
        if artist.get("images"):
            embed.set_thumbnail(url=artist["images"][0]["url"])
        embed.add_field(
            name="Followers", value=f"{artist['followers']['total']:,}", inline=True
        )
        embed.add_field(
            name="Popularity", value=f"{artist['popularity']}/100", inline=True
        )
        embed.add_field(
            name="Genres",
            value=", ".join(artist["genres"]) if artist["genres"] else "N/A",
            inline=False,
        )
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")


@bot.slash_command(name="album", description="Get information about an album")
async def album(ctx: discord.ApplicationContext, album_name: str):
    await ctx.defer()
    try:
        results = spotify.search(q=album_name, limit=1, type="album")
        albums = results["albums"]["items"]
        if not albums:
            await ctx.respond("Album not found!")
            return
        album = albums[0]
        embed = discord.Embed(
            title=album["name"],
            url=album["external_urls"]["spotify"],
            color=discord.Color.green(),
        )
        if album.get("images"):
            embed.set_thumbnail(url=album["images"][0]["url"])
        artists = ", ".join([artist["name"] for artist in album["artists"]])
        embed.add_field(name="Artist(s)", value=artists, inline=True)
        embed.add_field(name="Release Date", value=album["release_date"], inline=True)
        embed.add_field(name="Total Tracks", value=album["total_tracks"], inline=True)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing")
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError("Spotify credentials missing")
    bot.run(DISCORD_TOKEN)
