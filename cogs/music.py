import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import time
import logging
from collections import deque
import aiohttp
from config import Config
from utils.ui_views import ConfirmationView

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch1',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'no_warnings': True,
    'extract_flat': False,
    'skip_download': True,
    'source_address': '0.0.0.0',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

import os
if os.name == 'nt': # Windows
    # Try to find ffmpeg in the static folder from previous project
    FFMPEG_PATH = r"c:\Users\wassim\Documents\atlas-unit\node_modules\ffmpeg-static\ffmpeg.exe"
    if not os.path.exists(FFMPEG_PATH):
        FFMPEG_PATH = "ffmpeg" # Fallback
else:
    FFMPEG_PATH = "ffmpeg" # Linux/Railway

# ─────────────────────────────────────────
#  Custom Player Logic
# ─────────────────────────────────────────

class GuildPlayer:
    def __init__(self, guild_id, bot):
        self.guild_id = guild_id
        self.bot = bot
        self.queue = deque()
        self.current = None
        self.start_time = None
        self.text_channel = None
        self.voice_client = None
        self.volume = 1.0
        self.loop = False

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    def is_paused(self):
        return self.voice_client and self.voice_client.is_paused()

    async def play_next(self):
        if not self.queue:
            self.current = None
            return

        self.current = self.queue.popleft()
        self.start_time = time.time()
        
        logger.info(f"Attempting to play next: {self.current['title']}")
        logger.info(f"Stream URL: {self.current['url'][:50]}...")
        
        try:
            source = discord.FFmpegPCMAudio(self.current['url'], executable=FFMPEG_PATH, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=self.volume)
            
            def after_playing(error):
                if error:
                    logger.error(f"Player error in guild {self.guild_id}: {error}")
                else:
                    logger.info(f"Finished playing: {self.current['title']}")
                coro = self.play_next()
                asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

            if self.voice_client:
                self.voice_client.play(source, after=after_playing)
                logger.info(f"Playback started for: {self.current['title']}")
                # Update the hub if it exists
                # We'll implement this later
        except Exception as e:
            logger.error(f"Error starting playback for {self.current['title']}: {e}")
            await self.play_next()

# ─────────────────────────────────────────
#  UI Components
# ─────────────────────────────────────────

class MusicPlayerView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    async def check_owner(self, interaction: discord.Interaction):
        # Admin bypass
        if interaction.user.guild_permissions.administrator:
            return True
        # Check temporary channel owner
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if vc:
            from cogs.voice_hub import VoiceHub
            owner_id = VoiceHub.temp_channel_owners.get(vc.id)
            if owner_id and interaction.user.id != owner_id:
                await interaction.response.send_message("❌ Only the owner of this temporary channel can use these buttons.", ephemeral=True)
                return False
        return True

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="m_prev")
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        await interaction.response.send_message("⏮️ Previous track is not supported in this mode.", ephemeral=True)

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, custom_id="m_play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        if not self.player: return await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.defer()

        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed", ephemeral=True)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="m_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped", ephemeral=True)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="m_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        vc = interaction.guild.voice_client
        if vc:
            self.player.queue.clear()
            vc.stop()
            await vc.disconnect()
            await interaction.response.send_message("⏹️ Stopped and Disconnected", ephemeral=True)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Play Song", emoji="🎵", style=discord.ButtonStyle.success, custom_id="m_play_modal", row=2)
    async def play_modal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        class PlayModal(discord.ui.Modal, title="Play Music"):
            query = discord.ui.TextInput(label="Song Name or URL", placeholder="Enter song name...", min_length=1)
            
            def __init__(self, bot):
                super().__init__()
                self.bot = bot

            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.defer(ephemeral=True)
                music_cog = self.bot.get_cog("Music")
                if music_cog:
                    await music_cog._play_internal(modal_interaction, self.query.value)

        await interaction.response.send_modal(PlayModal(interaction.client))

# ─────────────────────────────────────────
#  Music Cog
# ─────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {} # guild_id -> GuildPlayer

    def get_player(self, guild_id):
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer(guild_id, self.bot)
        return self.players[guild_id]

    async def get_spotify_info(self, url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"https://open.spotify.com/oembed?url={url}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Clean the title (remove " - song by" or "by")
                        title = data.get('title', '')
                        author = data.get('author_name', '')
                        return f"{author} {title}"
            except Exception as e:
                logger.error(f"Spotify parse error: {e}")
        return None

    async def fetch_track_info(self, query):
        logger.info(f"Fetching track info for: {query}")
        if "open.spotify.com" in query:
            spotify_query = await self.get_spotify_info(query)
            if spotify_query:
                query = spotify_query
                logger.info(f"Spotify track resolved to: {query}")
            else:
                logger.warning(f"Failed to resolve Spotify link: {query}")
                return {"error": "Could not resolve Spotify link. Make sure it's a public track or album."}

        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                if not info:
                    return {"error": "No results found for this query."}
                
                if 'entries' in info:
                    if not info['entries']:
                        return {"error": "No entries found in the search result."}
                    info = info['entries'][0]
                
                return {
                    'url': info.get('url') or info.get('webpage_url'),
                    'title': info.get('title', 'Unknown'),
                    'author': info.get('uploader', info.get('channel', 'Unknown Channel')),
                    'duration': info.get('duration', 0),
                    'webpage': info.get('webpage_url', ''),
                    'thumbnail': info.get('thumbnail', ''),
                }
            except Exception as e:
                logger.error(f"YTDL Error for query '{query}': {e}")
                err_str = str(e)
                if "403" in err_str:
                    return {"error": "YouTube blocked this request (403). The bot might need fresh cookies.txt or a different IP."}
                elif "sign in" in err_str.lower():
                    return {"error": "This video requires age verification or sign-in. Use cookies.txt."}
                elif "not found" in err_str.lower():
                    return {"error": "Video not found or is unavailable."}
                return {"error": f"Search Error: {err_str[:200]}"}

    def build_player_embed(self, player):
        track = player.current
        if not track:
            embed = discord.Embed(
                title="🎶 Atlas Ultimate Music Hub",
                description="Welcome to the premium music control center.\n\nClick **Play Song** to start.",
                color=0x2b2d31
            )
        else:
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"**[{track['title']}]({track['webpage']})**",
                color=0x2b2d31
            )
            embed.add_field(name="Author", value=track.get('author', 'Unknown Channel'), inline=True)
            embed.add_field(name="Duration", value=time.strftime('%H:%M:%S', time.gmtime(track['duration'])), inline=True)
            if track['thumbnail']:
                embed.set_thumbnail(url=track['thumbnail'])
        
        if Config.BANNER_GIF_URL:
            embed.set_image(url=Config.BANNER_GIF_URL)
        embed.set_footer(text="Atlas Ultimate • Premium Music Experience")
        return embed

    async def check_permissions(self, interaction: discord.Interaction):
        # Allow administrators always
        if interaction.user.guild_permissions.administrator:
            return True
            
        # Check if we are in a temporary channel
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc:
            return True # Let the play command handle "no voice" error
            
        # Access VoiceHub owners (late import to avoid circular dependency)
        from cogs.voice_hub import VoiceHub
        owner_id = VoiceHub.temp_channel_owners.get(vc.id)
        
        if owner_id and interaction.user.id != owner_id:
            await interaction.response.send_message("❌ Only the owner of this temporary channel can control the music.", ephemeral=True)
            return False
        return True

    async def _play_internal(self, interaction: discord.Interaction, query: str):
        if not await self.check_permissions(interaction):
            return

        if not interaction.user.voice:
            return await interaction.followup.send("❌ You must be in a voice channel.", ephemeral=True)
            
        vc = interaction.guild.voice_client
        player = self.get_player(interaction.guild_id)
        
        # If already in a different channel, move and clear queue
        if vc and vc.channel.id != interaction.user.voice.channel.id:
            player.queue.clear()
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await vc.move_to(interaction.user.voice.channel)
            await interaction.followup.send(f"🚚 Moved to {interaction.user.voice.channel.mention} and cleared previous queue.", ephemeral=True)
        elif not vc:
            vc = await interaction.user.voice.channel.connect()
        
        player.voice_client = vc
        player.text_channel = interaction.channel
        
        track = await self.fetch_track_info(query)
        if not track:
            return await interaction.followup.send("❌ An unexpected error occurred while searching (Result was None).", ephemeral=True)
            
        if "error" in track:
            return await interaction.followup.send(f"❌ **Music Error**: {track['error']}", ephemeral=True)
        
        if not track.get('url'):
            return await interaction.followup.send("❌ Could not retrieve a valid stream URL for this track.", ephemeral=True)
        
        player.queue.append(track)
        if not vc.is_playing() and not vc.is_paused():
            await player.play_next()
            embed = self.build_player_embed(player)
            await interaction.followup.send(embed=embed, view=MusicPlayerView(player))
        else:
            await interaction.followup.send(f"✅ Added **{track['title']}** to queue (Position: {len(player.queue)})", ephemeral=True)

    @discord.app_commands.command(name="play", description="Play music directly using yt-dlp")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._play_internal(interaction, query)

    @discord.app_commands.command(name="panel", description="Send the premium music control panel")
    async def panel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player = self.get_player(interaction.guild_id)
        embed = self.build_player_embed(player)
        await interaction.followup.send(embed=embed, view=MusicPlayerView(player))

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
