import {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  ChatInputCommandInteraction,
  SlashCommandBuilder,
  EmbedBuilder,
  GuildMember,
} from "discord.js";
import { Shoukaku, Connectors, Player, Track } from "shoukaku";
import dotenv from "dotenv";
import { validateQuery, searchWithCache, MAX_QUEUE_SIZE } from "./botLogic";

dotenv.config();

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const LAVALINK_URI = process.env.LAVALINK_URI || "http://lavalink:2333";
const LAVALINK_PASSWORD = process.env.LAVALINK_PASSWORD;

if (!DISCORD_TOKEN) throw new Error("DISCORD_TOKEN missing");
if (!LAVALINK_URI || !LAVALINK_PASSWORD) throw new Error("Lavalink credentials missing");

function parseLavalinkUri(uri: string) {
  const scheme = uri.startsWith("https://") ? "https" : "http";
  const secure = scheme === "https";
  let u = uri.replace("http://", "").replace("https://", "");
  const parts = u.split(":");
  const url = parts[0];
  const port = parts.length > 1 ? parseInt(parts[1]!) : 2333;
  return { url, port, secure };
}

const lavalinkConfig = parseLavalinkUri(LAVALINK_URI);

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates, GatewayIntentBits.GuildMessages],
});

const Nodes = [
  {
    name: "Lavalink",
    url: `${lavalinkConfig.url}:${lavalinkConfig.port}`,
    auth: LAVALINK_PASSWORD,
    secure: lavalinkConfig.secure,
  },
];

const shoukaku = new Shoukaku(new Connectors.DiscordJS(client), Nodes);

shoukaku.on("error", (_, error) => console.error(error));
shoukaku.on("ready", (name) => console.log(`Node ${name} is ready!`));

client.once("ready", () => {
  console.log(`${client.user?.tag} is online!`);
});

interface PlayerQueue {
  currentTrack?: Track;
  tracks: Track[];
}

// A simple queue manager attached to the player (shoukaku Player doesn't have a built-in Queue class like Wavelink)
const playerQueues = new Map<string, PlayerQueue>();

// Cooldown map
const cooldowns = new Map<string, number>();

function isPrivileged(interaction: ChatInputCommandInteraction, player: Player): boolean {
  const member = interaction.member as GuildMember;
  if (!member || !member.voice.channelId) return false;
  return member.voice.channelId === player.connection.channelId;
}

const commands = [
  new SlashCommandBuilder().setName("join").setDescription("Invite the bot to your current voice channel"),
  new SlashCommandBuilder().setName("leave").setDescription("Disconnect the bot from voice"),
  new SlashCommandBuilder().setName("stop").setDescription("Stop playback and clear queue"),
  new SlashCommandBuilder()
    .setName("play")
    .setDescription("Play a song from query, URL (YouTube, SoundCloud, Spotify)")
    .addStringOption((option) => option.setName("query").setDescription("Song name or URL").setRequired(true)),
  new SlashCommandBuilder().setName("queue").setDescription("View the current song queue"),
  new SlashCommandBuilder().setName("skip").setDescription("Skip the current song"),
  new SlashCommandBuilder().setName("clear").setDescription("Clear the entire queue"),
].map((command) => command.toJSON());

const rest = new REST({ version: "10" }).setToken(DISCORD_TOKEN);

(async () => {
  try {
    console.log("Started refreshing application (/) commands.");
    await rest.put(Routes.applicationCommands(Buffer.from(DISCORD_TOKEN.split('.')[0]!, 'base64').toString()), {
      body: commands,
    });
    console.log("Successfully reloaded application (/) commands.");
  } catch (error) {
    // It will throw if DISCORD_TOKEN is fake (like in tests) but we can ignore it
    console.error(error);
  }
})();

async function getOrConnectPlayer(interaction: ChatInputCommandInteraction): Promise<Player | null> {
  const member = interaction.member as GuildMember;
  if (!member.voice.channelId) {
    const msg = "You must be connected to a voice channel.";
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp({ content: msg, ephemeral: true });
    } else {
      await interaction.reply({ content: msg, ephemeral: true });
    }
    return null;
  }

  let player = shoukaku.players.get(interaction.guildId!);
  if (player && player.connection.channelId === member.voice.channelId) {
    return player;
  }

  try {
    player = await shoukaku.joinVoiceChannel({
      guildId: interaction.guildId!,
      channelId: member.voice.channelId,
      shardId: 0,
    });

    // Initialize queue for this player
    if (!playerQueues.has(interaction.guildId!)) {
      playerQueues.set(interaction.guildId!, { tracks: [] });
    }

    player.on("end", async (payload) => {
      // Auto-play next track
      const queue = playerQueues.get(interaction.guildId!);
      if (queue) {
        if (queue.tracks.length > 0) {
          const nextTrack = queue.tracks.shift()!;
          queue.currentTrack = nextTrack;
          try {
            await player!.playTrack({ track: nextTrack.encoded });
          } catch (e) {
            console.error(`Error playing next track: ${e}`);
          }
        } else {
          queue.currentTrack = undefined;
        }
      }
    });

    return player;
  } catch (e) {
    console.error(`Voice connection error: ${e}`);
    const msg = "Failed to connect to voice channel. Please check permissions and try again.";
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp({ content: msg, ephemeral: true });
    } else {
      await interaction.reply({ content: msg, ephemeral: true });
    }
    return null;
  }
}

client.on("interactionCreate", async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  try {
    const { commandName } = interaction;

    if (commandName === "join") {
    const player = await getOrConnectPlayer(interaction);
    if (!player) return;
    const channel = client.channels.cache.get(player.connection.channelId!);
    // @ts-ignore
    await interaction.reply({ content: `Joined: ${channel?.name || "Voice Channel"}`, ephemeral: true });
  }

  else if (commandName === "leave") {
    const player = shoukaku.players.get(interaction.guildId!);
    if (!player) {
      return interaction.reply({ content: "I'm not connected to any voice channel.", ephemeral: true });
    }

    if (!isPrivileged(interaction, player)) {
      return interaction.reply({ content: "You must be in the same voice channel to use this command.", ephemeral: true });
    }

      await shoukaku.leaveVoiceChannel(interaction.guildId!);
      playerQueues.delete(interaction.guildId!);
      return interaction.reply({ content: "Disconnected.", ephemeral: true });
    }

    else if (commandName === "stop") {
    const player = shoukaku.players.get(interaction.guildId!);
    if (!player) {
      return interaction.reply({ content: "I'm not in a voice channel.", ephemeral: true });
    }

    if (!isPrivileged(interaction, player)) {
      return interaction.reply({ content: "You must be in the same voice channel to use this command.", ephemeral: true });
    }

      const queue = playerQueues.get(interaction.guildId!) || { tracks: [] };
      if (!player.track && queue.tracks.length === 0) {
        return interaction.reply({ content: "Nothing is playing.", ephemeral: true });
      }

      playerQueues.set(interaction.guildId!, { tracks: [] });
      try {
        await player.stopTrack();
      } catch (e) {}
      return interaction.reply({ content: "Stopped playback and cleared queue.", ephemeral: true });
    }

    else if (commandName === "play") {
    // Cooldown logic (1 request per 5 seconds per user per guild)
    const cooldownKey = `${interaction.guildId}-${interaction.user.id}`;
    const now = Date.now();
    const cooldownTime = 5000;
    if (cooldowns.has(cooldownKey)) {
      const expiration = cooldowns.get(cooldownKey)! + cooldownTime;
      if (now < expiration) {
        const timeLeft = (expiration - now) / 1000;
        return interaction.reply({ content: `Slow down! Try again in ${timeLeft.toFixed(2)}s`, ephemeral: true });
      }
    }
    cooldowns.set(cooldownKey, now);

    await interaction.deferReply({ ephemeral: false });
    let query = interaction.options.getString("query", true);

    try {
      query = await validateQuery(query);
    } catch (e: any) {
      return interaction.followUp({ content: `Invalid query: ${e.message}` });
    }

    const playerPromise = getOrConnectPlayer(interaction);
    const node = shoukaku.options.nodeResolver(shoukaku.nodes);

    // searchWithCache expects a function returning results
    const searchPromise = searchWithCache(query, async (q) => {
      if (!node) throw new Error("No available nodes");
      return await node.rest.resolve(q);
    });

    const [player, result] = await Promise.all([playerPromise, searchPromise]);

    if (!player) {
      return;
    }

    try {
      if (!result || result.loadType === 'empty' || result.loadType === 'error') {
        const safeQuery = query.length > 100 ? query.substring(0, 100) + "..." : query;
        return interaction.followUp({ content: `No results found for: \`${safeQuery}\`` });
      }
    } catch (e: any) {
      const safeQueryLog = query.replace(/\n/g, " ").replace(/\r/g, " ");
      console.error(`Search error for query '${safeQueryLog}': ${e}`);
      return interaction.followUp({ content: "An error occurred during search. Please try again later." });
    }

      const queue = playerQueues.get(interaction.guildId!) || { tracks: [] };

      if (result.loadType === 'playlist') {
        const tracks = result.data.tracks;
        if (!tracks || tracks.length === 0) {
          return interaction.followUp({ content: "Playlist is empty." });
        }

        if (queue.tracks.length + tracks.length > MAX_QUEUE_SIZE) {
          return interaction.followUp({ content: `Cannot add playlist: Queue limit (${MAX_QUEUE_SIZE}) would be exceeded.` });
        }

        let startIndex = 0;
        if (!player.track) {
          queue.currentTrack = tracks[0];
          await player.playTrack({ track: tracks[0].encoded });
          startIndex = 1;
        }

        for (let i = startIndex; i < tracks.length; i++) {
          queue.tracks.push(tracks[i]);
        }
        playerQueues.set(interaction.guildId!, queue);

        return interaction.followUp({ content: `Added ${tracks.length} tracks from playlist \`${result.data.info.name}\` to the queue.` });
      } else {
        const track = result.loadType === 'search' ? result.data[0] : result.data;

        if (!player.track) {
          queue.currentTrack = track;
          playerQueues.set(interaction.guildId!, queue);
          await player.playTrack({ track: track.encoded });
          return interaction.followUp({ content: `Playing: **${track.info.title}**` });
        } else {
          if (queue.tracks.length >= MAX_QUEUE_SIZE) {
            return interaction.followUp({ content: `Queue is full (max ${MAX_QUEUE_SIZE}). Please wait for tracks to finish.` });
          }
          queue.tracks.push(track);
          playerQueues.set(interaction.guildId!, queue);
          return interaction.followUp({ content: `Added to queue: **${track.info.title}**` });
        }
      }
    }

    else if (commandName === "queue") {
    const player = shoukaku.players.get(interaction.guildId!);
    if (!player) {
      return interaction.reply({ content: "I'm not connected to voice.", ephemeral: true });
    }

      const queue = playerQueues.get(interaction.guildId!) || { tracks: [] };
      const embed = new EmbedBuilder().setTitle("🎵 Song Queue").setColor(0x0099ff);

      if (player.track && queue.currentTrack) {
        embed.addFields({ name: "Now Playing", value: `**${queue.currentTrack.info.title}**`, inline: false });
      } else if (player.track) {
        embed.addFields({ name: "Now Playing", value: "Track currently playing", inline: false });
      }

      if (queue.tracks.length === 0) {
        embed.setDescription("Queue is empty.");
      } else {
        const slice = queue.tracks.slice(0, 10);
        let queueList = slice.map((t, i) => `${i + 1}. ${t.info.title}`).join("\n");
        if (queue.tracks.length > 10) {
          queueList += `\n... and ${queue.tracks.length - 10} more`;
        }
        embed.addFields({ name: `Up Next (${queue.tracks.length} songs)`, value: queueList, inline: false });
      }

      return interaction.reply({ embeds: [embed] });
    }

    else if (commandName === "skip") {
    const player = shoukaku.players.get(interaction.guildId!);
    if (!player || !player.track) {
      return interaction.reply({ content: "Nothing is playing.", ephemeral: true });
    }

    if (!isPrivileged(interaction, player)) {
      return interaction.reply({ content: "You must be in the same voice channel to use this command.", ephemeral: true });
    }

      await player.stopTrack(); // This triggers the "end" event and auto-plays next
      return interaction.reply({ content: "Skipped!", ephemeral: true });
    }

    else if (commandName === "clear") {
      const player = shoukaku.players.get(interaction.guildId!);
      const queue = playerQueues.get(interaction.guildId!) || { tracks: [] };

      if (!player || queue.tracks.length === 0) {
        return interaction.reply({ content: "Queue is already empty.", ephemeral: true });
      }

      if (!isPrivileged(interaction, player)) {
        return interaction.reply({ content: "You must be in the same voice channel to use this command.", ephemeral: true });
      }

      const count = queue.tracks.length;
      queue.tracks = [];
      playerQueues.set(interaction.guildId!, queue);
      return interaction.reply({ content: `Cleared ${count} song(s) from queue.`, ephemeral: true });
    }
  } catch (err) {
    console.error(`Error handling interaction: ${err}`);
    const msg = "An error occurred while processing the command.";
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp({ content: msg, ephemeral: true }).catch(() => {});
    } else {
      await interaction.reply({ content: msg, ephemeral: true }).catch(() => {});
    }
  }
});

client.login(DISCORD_TOKEN);

export { parseLavalinkUri }; // Export for testing
