import os
import time
import asyncio
import logging
from collections import deque
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MultiBotManager")

# ─────────────────────────────────────────
#  Environment & Configurations
# ─────────────────────────────────────────

BOT_TOKENS = [
    os.getenv("BOT_TOKEN_1"),
    os.getenv("BOT_TOKEN_2"),
    os.getenv("BOT_TOKEN_3"),
    os.getenv("BOT_TOKEN_4")
]
# Filter out None values in case some tokens are not configured in the host
BOT_TOKENS = [t for t in BOT_TOKENS if t]

GUILD_ID = int(os.getenv("GUILD_ID", "1474938766824050883"))

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# Try to find ffmpeg in typical static folders, or fallback to environment path
FFMPEG_PATH = r"c:\Users\wassim\Documents\atlas-unit\node_modules\ffmpeg-static\ffmpeg.exe"
if not os.path.exists(FFMPEG_PATH):
    FFMPEG_PATH = "ffmpeg"

# ─────────────────────────────────────────
#  Bot Swarm Coordination Manager
# ─────────────────────────────────────────

class BotManager:
    bots = []
    
    # Precise, event-driven in-memory tracker of which bot name is connected to which voice channel ID
    # e.g., { "Atlas 1": 123456789 }
    active_connections = {}

    @classmethod
    def get_handler_bot(cls, guild, voice_channel):
        if not voice_channel:
            # Designate Atlas 1 as fallback to report user voice channel errors
            return cls.bots[0] if cls.bots else None

        # 1. First, check if one of our swarm bots is ALREADY inside this specific voice channel
        for bot in cls.bots:
            conn_channel_id = cls.active_connections.get(bot.name)
            if conn_channel_id == voice_channel.id:
                # Double-check that the voice client is active
                g = bot.get_guild(guild.id)
                if g and g.voice_client and g.voice_client.is_connected():
                    return bot
                else:
                    # Clean up stale track state
                    cls.active_connections[bot.name] = None

        # 2. If no bot is in the channel, look for a bot that is IDLE in this guild
        for bot in cls.bots:
            conn_channel_id = cls.active_connections.get(bot.name)
            if not conn_channel_id:
                # Double check with internal client voice client cache
                g = bot.get_guild(guild.id)
                if not g or not g.voice_client or not g.voice_client.is_connected():
                    return bot
                else:
                    # Re-align cache in case of disconnect miss
                    cls.active_connections[bot.name] = g.voice_client.channel.id

        # 3. All bot instances are currently occupied
        return None

# ─────────────────────────────────────────
#  Custom Bot Instance class
# ─────────────────────────────────────────

class AtlasMusicBot(commands.Bot):
    def __init__(self, name):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.name = name
        
        # Audio Player States
        self.queue = deque()
        self.current_track = None
        self.start_time = None
        self.loop = False
        self.text_channel = None
        self.guild_id = None

    async def setup_hook(self):
        # Register Slash Commands Cog
        await self.add_cog(MusicSlash(self))
        
        # Sync command tree to target guild for instant testing updates
        if GUILD_ID:
            try:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"[{self.name}] Synchronized {len(synced)} Slash Command(s) to guild {GUILD_ID}")
            except Exception as e:
                logger.error(f"[{self.name}] Slash command sync failed: {e}")

    async def on_ready(self):
        logger.info(f"🟢 Bot Instance Connected: {self.name} | Logged in as {self.user} (ID: {self.user.id})")

    async def on_voice_state_update(self, member, before, after):
        # Event listener to update active connection tracker instantly
        if member.id == self.user.id:
            if after.channel:
                BotManager.active_connections[self.name] = after.channel.id
                logger.info(f"[{self.name}] Cache Sync: Connected to voice channel {after.channel.name} ({after.channel.id})")
            else:
                BotManager.active_connections[self.name] = None
                logger.info(f"[{self.name}] Cache Sync: Disconnected from voice channel")

    async def fetch_track_info(self, query: str):
        """Fetch track streaming info using anonymous-fallback extraction"""
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                if 'entries' in info:
                    info = info['entries'][0]
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'url': info.get('url'),
                    'webpage': info.get('webpage_url', query),
                    'duration': info.get('duration', 0),
                    'author': info.get('uploader', 'Unknown Creator'),
                    'thumbnail': info.get('thumbnail')
                }
        except Exception as e:
            logger.warning(f"[{self.name}] Extraction failure, trying Anonymous fallback: {e}")
            
        anon_opts = dict(YTDL_OPTIONS)
        anon_opts['cookiefile'] = None
        try:
            with yt_dlp.YoutubeDL(anon_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                if 'entries' in info:
                    info = info['entries'][0]
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'url': info.get('url'),
                    'webpage': info.get('webpage_url', query),
                    'duration': info.get('duration', 0),
                    'author': info.get('uploader', 'Unknown Creator'),
                    'thumbnail': info.get('thumbnail')
                }
        except Exception as e:
            logger.error(f"[{self.name}] Anonymous extraction fallback failed: {e}")
            return {"error": str(e)}

    async def delegate_play(self, voice_channel, text_channel, guild_id, query):
        """Delegated play task called dynamically when routed by the swarm"""
        guild = self.get_guild(guild_id)
        vc = guild.voice_client if guild else None
        
        try:
            if not vc:
                vc = await voice_channel.connect()
            elif vc.channel.id != voice_channel.id:
                await vc.move_to(voice_channel)
        except Exception as e:
            logger.error(f"[{self.name}] Voice Connection error: {e}")
            return await text_channel.send(f"❌ **{self.name}** failed to connect to voice channel: {e}")

        self.text_channel = text_channel
        self.guild_id = guild_id

        # Direct announcement in the routed text channel
        await self.text_channel.send(f"🔍 **{self.name}** is searching for `{query}`...")
        track = await self.fetch_track_info(query)
        
        if "error" in track:
            return await self.text_channel.send(f"❌ **Search Error**: {track['error']}")
            
        self.queue.append(track)
        
        if not vc.is_playing() and not vc.is_paused():
            await self.play_next()
        else:
            await self.text_channel.send(f"✅ Added **{track['title']}** to playlist (Position: #{len(self.queue)} in queue)")

    async def play_next(self):
        if not self.queue:
            self.current_track = None
            if self.text_channel:
                try:
                    await self.text_channel.send(f"💤 **{self.name}** queue is empty. Standing by...")
                except:
                    pass
            return

        self.current_track = self.queue.popleft()
        self.start_time = time.time()
        
        try:
            source = discord.FFmpegPCMAudio(self.current_track['url'], executable=FFMPEG_PATH, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=1.0)
            
            def after_playing(error):
                if error:
                    logger.error(f"[{self.name}] Player Error: {error}")
                
                # Looping track implementation
                if self.loop and self.current_track:
                    self.queue.appendleft(self.current_track)
                
                coro = self.play_next()
                asyncio.run_coroutine_threadsafe(coro, self.loop)

            guild = self.get_guild(self.guild_id)
            vc = guild.voice_client if guild else None
            
            if vc:
                vc.play(source, after=after_playing)
                
                embed = discord.Embed(
                    title=f"🎶 Now Playing on {self.name}",
                    description=f"**[{self.current_track['title']}]({self.current_track['webpage']})**",
                    color=0x00E5FF
                )
                embed.add_field(name="🎙️ Channel", value=f"`{self.current_track['author']}`", inline=True)
                embed.add_field(name="🕒 Duration", value=f"`{time.strftime('%M:%S', time.gmtime(self.current_track['duration']))}`", inline=True)
                embed.set_thumbnail(url=self.current_track['thumbnail'])
                embed.set_footer(text=f"Connected Voice: {vc.channel.name}")
                
                if self.text_channel:
                    await self.text_channel.send(embed=embed)
            
        except Exception as e:
            logger.exception(f"[{self.name}] Playback execution failed")
            if self.text_channel:
                await self.text_channel.send(f"❌ Playback failed: {e}")
            await self.play_next()

# ─────────────────────────────────────────
#  Music Slash Command Cog
# ─────────────────────────────────────────

class MusicSlash(commands.Cog):
    def __init__(self, bot: AtlasMusicBot):
        self.bot = bot

    @app_commands.command(name="play", description="Play music in your voice channel")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be connected to a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        designated = BotManager.get_handler_bot(interaction.guild, voice_channel)
        
        if designated is None:
            return await interaction.response.send_message(
                "❌ **System Offline**: All available music bot accounts are currently occupied in other voice channels!",
                ephemeral=True
            )
            
        # Send confirmation immediately to the client invoking the slash command
        if designated == self.bot:
            await interaction.response.send_message(f"⚡ Running command directly on **{self.bot.name}**...", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"🚀 **Swarm Routing**: Routed request to **{designated.name}** (I am playing elsewhere / active). Check your channel!",
                ephemeral=True
            )
            
        # Launch direct delegated play task on the assigned bot in the background
        asyncio.create_task(designated.delegate_play(
            voice_channel=voice_channel,
            text_channel=interaction.channel,
            guild_id=interaction.guild_id,
            query=query
        ))

    @app_commands.command(name="pause", description="Pause active music playback in your channel")
    async def pause(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be inside a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        active_bot = None
        for bot in BotManager.bots:
            if BotManager.active_connections.get(bot.name) == voice_channel.id:
                active_bot = bot
                break
                
        if not active_bot:
            return await interaction.response.send_message("❌ No active Atlas bot found in your voice channel.", ephemeral=True)
            
        guild = active_bot.get_guild(interaction.guild_id)
        vc = guild.voice_client if guild else None
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(f"⏸️ **{active_bot.name}** has been paused.")
        else:
            await interaction.response.send_message(f"❌ **{active_bot.name}** is not playing anything.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume paused music playback in your channel")
    async def resume(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be inside a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        active_bot = None
        for bot in BotManager.bots:
            if BotManager.active_connections.get(bot.name) == voice_channel.id:
                active_bot = bot
                break
                
        if not active_bot:
            return await interaction.response.send_message("❌ No active Atlas bot found in your voice channel.", ephemeral=True)
            
        guild = active_bot.get_guild(interaction.guild_id)
        vc = guild.voice_client if guild else None
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(f"▶️ **{active_bot.name}** has resumed playback.")
        else:
            await interaction.response.send_message(f"❌ **{active_bot.name}** is not paused.", ephemeral=True)

    @app_commands.command(name="skip", description="Skip the currently playing track in your channel")
    async def skip(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be inside a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        active_bot = None
        for bot in BotManager.bots:
            if BotManager.active_connections.get(bot.name) == voice_channel.id:
                active_bot = bot
                break
                
        if not active_bot:
            return await interaction.response.send_message("❌ No active Atlas bot found in your voice channel.", ephemeral=True)
            
        guild = active_bot.get_guild(interaction.guild_id)
        vc = guild.voice_client if guild else None
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message(f"⏭️ **{active_bot.name}** track skipped.")
        else:
            await interaction.response.send_message(f"❌ **{active_bot.name}** is not playing anything.", ephemeral=True)

    @app_commands.command(name="stop", description="Disconnect and clear the bot's queue in your channel")
    async def stop(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be inside a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        active_bot = None
        for bot in BotManager.bots:
            if BotManager.active_connections.get(bot.name) == voice_channel.id:
                active_bot = bot
                break
                
        if not active_bot:
            return await interaction.response.send_message("❌ No active Atlas bot found in your voice channel.", ephemeral=True)
            
        guild = active_bot.get_guild(interaction.guild_id)
        vc = guild.voice_client if guild else None
        if vc:
            active_bot.queue.clear()
            vc.stop()
            await vc.disconnect()
            BotManager.active_connections[active_bot.name] = None
            await interaction.response.send_message(f"⏹️ **{active_bot.name}** disconnected and playlist wiped.")
        else:
            await interaction.response.send_message(f"❌ **{active_bot.name}** is not connected to voice.", ephemeral=True)

    @app_commands.command(name="loop", description="Toggle loop mode for the active track in your channel")
    async def loop(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be inside a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        active_bot = None
        for bot in BotManager.bots:
            if BotManager.active_connections.get(bot.name) == voice_channel.id:
                active_bot = bot
                break
                
        if not active_bot:
            return await interaction.response.send_message("❌ No active Atlas bot found in your voice channel.", ephemeral=True)
            
        active_bot.loop = not active_bot.loop
        status = "enabled" if active_bot.loop else "disabled"
        await interaction.response.send_message(f"🔁 Looping is now **{status}** for **{active_bot.name}**.")

    @app_commands.command(name="queue", description="Show upcoming track queue list in your channel")
    async def queue_list(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be inside a Voice Channel.", ephemeral=True)
            
        voice_channel = interaction.user.voice.channel
        active_bot = None
        for bot in BotManager.bots:
            if BotManager.active_connections.get(bot.name) == voice_channel.id:
                active_bot = bot
                break
                
        if not active_bot:
            return await interaction.response.send_message("❌ No active Atlas bot found in your voice channel.", ephemeral=True)
            
        if not active_bot.queue and not active_bot.current_track:
            return await interaction.response.send_message(f"📋 **{active_bot.name}**'s playlist is empty.")
            
        desc = f"🎶 **Now Playing**: {active_bot.current_track['title'] if active_bot.current_track else 'None'}\n\n"
        for idx, track in enumerate(active_bot.queue, start=1):
            desc += f"#{idx} - `{track['title']}`\n"
            
        embed = discord.Embed(title=f"📋 Queue for {active_bot.name}", description=desc, color=0x00E5FF)
        await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────
#  Execution Entrypoint
# ─────────────────────────────────────────

async def start_all_bots():
    logger.info("Initializing multi-token bot instances...")
    
    # Initialize the 4 bot instances
    for idx, token in enumerate(BOT_TOKENS, start=1):
        bot = AtlasMusicBot(name=f"Atlas {idx}")
        BotManager.bots.append(bot)

    # Launch bots simultaneously using asyncio.gather
    tasks = [bot.start(token) for bot, token in zip(BotManager.bots, BOT_TOKENS)]
    
    logger.info(f"Spinning up {len(tasks)} bot tasks...")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(start_all_bots())
    except KeyboardInterrupt:
        logger.info("Bots shutting down...")
