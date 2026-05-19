import os
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
# Diagnostic logging for cookies
COOKIE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt')

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
    'cachedir': False,
    'youtube_include_dash_manifest': True,
    'youtube_include_hls_manifest': True,
    'cookiefile': COOKIE_PATH if os.path.exists(COOKIE_PATH) else None,
}

if os.path.exists(COOKIE_PATH):
    logger.info(f"🍪 Found cookies.txt at {COOKIE_PATH} - Size: {os.path.getsize(COOKIE_PATH)} bytes")
else:
    logger.warning(f"⚠️ No cookies.txt found at {COOKIE_PATH}")

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


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
        self.panel_message = None

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    def is_paused(self):
        return self.voice_client and self.voice_client.is_paused()

    async def play_next(self):
        if not self.queue:
            self.current = None
            # Update panel if queue goes idle
            if self.panel_message:
                music_cog = self.bot.get_cog("Music")
                if music_cog:
                    embed = music_cog.build_player_embed(self)
                    try:
                        await self.panel_message.edit(embed=embed)
                    except Exception:
                        pass
            return

        self.current = self.queue.popleft()
        self.start_time = time.time()
        
        logger.info(f"Attempting to play next: {self.current['title']}")
        logger.info(f"Stream URL: {self.current['url'][:100]}...")
        
        try:
            source = discord.FFmpegPCMAudio(self.current['url'], executable=FFMPEG_PATH, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=self.volume)
            
            if not self.voice_client:
                logger.error("❌ Voice client is None in play_next!")
                return

            def after_playing(error):
                if error:
                    logger.error(f"❌ Player error in guild {self.guild_id}: {error}")
                else:
                    logger.info(f"✅ Finished playing: {self.current['title']}")
                
                # Loop support
                if self.loop and self.current:
                    self.queue.appendleft(self.current)

                coro = self.play_next()
                asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

            self.voice_client.play(source, after=after_playing)
            logger.info(f"🎶 Playback started successfully for: {self.current['title']}")
            
            # Auto-update panel message
            if self.panel_message:
                music_cog = self.bot.get_cog("Music")
                if music_cog:
                    embed = music_cog.build_player_embed(self)
                    try:
                        await self.panel_message.edit(embed=embed)
                    except Exception as ex:
                        logger.warning(f"Could not auto-update panel message: {ex}")
        except Exception as e:
            logger.error(f"❌ Error starting playback for {self.current['title']}: {e}")
            await self.play_next()

# ─────────────────────────────────────────
#  UI Components
# ─────────────────────────────────────────

class MusicPlayerView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player
        # Initialize button style for loop
        for child in self.children:
            if child.custom_id == "m_loop":
                child.style = discord.ButtonStyle.success if player.loop else discord.ButtonStyle.secondary

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

    async def update_panel(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Music")
        if cog:
            embed = cog.build_player_embed(self.player)
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                try:
                    await interaction.followup.edit_message(message_id="@original", embed=embed, view=self)
                except Exception:
                    pass

    @discord.ui.button(label="Pause / Resume", emoji="⏯️", style=discord.ButtonStyle.primary, custom_id="m_play_pause", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        if not self.player: return await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.defer()

        if vc.is_playing():
            vc.pause()
        elif vc.is_paused():
            vc.resume()
        
        await self.update_panel(interaction)

    @discord.ui.button(label="Skip Track", emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="m_skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        
        await asyncio.sleep(0.5)
        await self.update_panel(interaction)

    @discord.ui.button(label="Toggle Loop", emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="m_loop", row=0)
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        if not self.player: return await interaction.response.defer()
        
        self.player.loop = not self.player.loop
        button.style = discord.ButtonStyle.success if self.player.loop else discord.ButtonStyle.secondary
        await self.update_panel(interaction)

    @discord.ui.button(label="Disconnect", emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="m_stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        vc = interaction.guild.voice_client
        if vc:
            self.player.queue.clear()
            vc.stop()
            await vc.disconnect()
        await self.update_panel(interaction)

    @discord.ui.button(label="Add Song to Queue", emoji="🎵", style=discord.ButtonStyle.success, custom_id="m_play_modal", row=1)
    async def play_modal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction): return
        class PlayModal(discord.ui.Modal, title="🎵 Add Song to Queue"):
            query = discord.ui.TextInput(label="Song Name or YouTube URL", placeholder="Enter query...", min_length=1)
            
            def __init__(self, bot, parent_view):
                super().__init__()
                self.bot = bot
                self.parent_view = parent_view

            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.defer(ephemeral=True)
                music_cog = self.bot.get_cog("Music")
                if music_cog:
                    await music_cog._play_internal(modal_interaction, self.query.value)
                    embed = music_cog.build_player_embed(self.parent_view.player)
                    if self.parent_view.player.panel_message:
                        try:
                            await self.parent_view.player.panel_message.edit(embed=embed, view=self.parent_view)
                        except Exception:
                            pass

        await interaction.response.send_modal(PlayModal(interaction.client, self))

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
        logger.info(f"🔍 Fetching track info for: {query}")
        if "open.spotify.com" in query:
            spotify_query = await self.get_spotify_info(query)
            if spotify_query:
                query = spotify_query
                logger.info(f"✅ Spotify track resolved to: {query}")
            else:
                logger.warning(f"❌ Failed to resolve Spotify link: {query}")
                return {"error": "Could not resolve Spotify link. Make sure it's a public track or album."}

        loop = asyncio.get_event_loop()
        
        # 1. Try with cookies first (if they exist)
        info = None
        primary_failed = False
        err_str = ""
        
        if YTDL_OPTIONS.get('cookiefile'):
            try:
                logger.info("🍪 Fetching track info WITH cookies...")
                with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                    info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                    if info and 'entries' in info:
                        info = info['entries'][0]
                    
                    # If we only extracted storyboards/images (sign of expired/corrupt cookies)
                    if info and not info.get('url'):
                        logger.warning("⚠️ Warning: Extracted metadata with cookies but no stream URL was found. Expired cookies likely blocked stream decryption.")
                        info = None
                        primary_failed = True
            except Exception as e:
                err_str = str(e)
                logger.error(f"⚠️ YTDL Primary Attempt with cookies failed: {err_str[:100]}")
                primary_failed = True

        # 2. Try WITHOUT cookies as fallback (if primary failed or cookies don't exist)
        if not info or primary_failed:
            try:
                logger.info("🔄 Retrying/Fetching track info WITHOUT cookies (Anonymous Mode)...")
                opts = YTDL_OPTIONS.copy()
                opts['cookiefile'] = None
                
                # If it's a direct URL, don't use ytsearch prefix
                if "youtube.com" in query or "youtu.be" in query:
                    opts['default_search'] = 'auto'
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                    if info and 'entries' in info:
                        info = info['entries'][0]
            except Exception as e2:
                err_str = str(e2)
                logger.error(f"❌ Anonymous extraction also failed: {err_str[:100]}")

        if info:
            # We succeeded! Let's return the track details
            return {
                'url': info.get('url') or info.get('webpage_url'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', info.get('channel', 'Unknown Channel')),
                'duration': info.get('duration', 0),
                'webpage': info.get('webpage_url', ''),
                'thumbnail': info.get('thumbnail', ''),
            }
        
        # If both attempts failed, return the appropriate error message
        if "403" in err_str:
            return {"error": "YouTube blocked the bot (403). Try fresh cookies or wait a while."}
        elif "sign in" in err_str.lower() or "age verification" in err_str.lower():
            return {"error": "YouTube bot detection triggered. Please update cookies.txt with fresh ones from an active browser session."}
        return {"error": f"Search/Format Error: {err_str[:200]}"}

    def build_player_embed(self, player):
        track = player.current
        embed = discord.Embed(color=0x00E5FF) # Glassmorphism neon cyan accent
        
        # Premium header
        embed.set_author(
            name="ATLAS ULTIMATE MUSIC SYSTEM",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )

        if not track:
            embed.title = "💤 Player Standing By"
            embed.description = (
                "```\n"
                "SYSTEM STATUS : STANDBY (IDLE)\n"
                "ACTIVE ROOM   : None\n"
                "QUEUE SIZE    : 0 Tracks\n"
                "```\n"
                "Welcome to the **Atlas Premium Music Control Center**.\n\n"
                "To stream music with ultra-low latency, click the **Add Song to Queue** button below or use `/play`."
            )
            embed.color = 0x2b2d31 # Slate Dark
        else:
            status_text = "🟢 Playing Track" if not player.is_paused() else "⏸️ Track Paused"
            embed.title = f"{status_text} | {track['title']}"
            embed.url = track['webpage']
            
            # Progress bar calculation
            duration = track['duration']
            if duration > 0 and player.start_time:
                elapsed = min(duration, int(time.time() - player.start_time))
                percentage = min(100, int((elapsed / duration) * 100))
                bar_len = 12
                filled = int((elapsed / duration) * bar_len)
                progress_bar = "▬" * filled + "🔘" + "▬" * (bar_len - filled - 1 if bar_len - filled > 0 else 0)
                time_str = f"`{time.strftime('%M:%S', time.gmtime(elapsed))} / {time.strftime('%M:%S', time.gmtime(duration))}`"
            else:
                progress_bar = "▬▬▬▬▬▬▬▬▬▬▬▬🔘"
                time_str = "`Live Stream`"

            embed.description = (
                f"**Connected Channel**: {player.voice_client.channel.mention if player.voice_client else 'None'}\n"
                f"**Engine Mode**: Direct High-Fidelity Audio\n\n"
                f"**Progress**:\n"
                f"{progress_bar} {time_str}\n"
            )
            
            embed.add_field(name="🎙️ Channel / Creator", value=f"`{track.get('author', 'Unknown')}`", inline=True)
            embed.add_field(name="🔁 Loop Mode", value=f"`{'Enabled' if player.loop else 'Disabled'}`", inline=True)
            embed.add_field(name="🔊 Volume Level", value=f"`{int(player.volume * 100)}%`", inline=True)
            
            queue_text = f"Queue: **{len(player.queue)}** track(s) pending" if player.queue else "Queue is empty."
            embed.add_field(name="📋 Upcoming Stream Playlist", value=queue_text, inline=False)
            
            if track['thumbnail']:
                embed.set_thumbnail(url=track['thumbnail'])

        if Config.BANNER_GIF_URL:
            embed.set_image(url=Config.BANNER_GIF_URL)
            
        embed.set_footer(
            text="Atlas Ultimate • Low-Latency Audio Streaming",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
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
            player.panel_message = await interaction.followup.send(embed=embed, view=MusicPlayerView(player))
        else:
            await interaction.followup.send(f"✅ Added **{track['title']}** to queue (Position: {len(player.queue)})", ephemeral=True)

    @discord.app_commands.command(name="play", description="Play music directly using yt-dlp")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._play_internal(interaction, query)

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
