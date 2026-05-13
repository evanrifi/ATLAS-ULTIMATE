import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from config import Config
from database import Database

logger = logging.getLogger(__name__)

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, emoji="✅", custom_id="atlas_verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if Database.db is None:
            await interaction.response.send_message("Database connection error.", ephemeral=True)
            return

        settings = await Database.db.security_settings.find_one({"guild_id": interaction.guild_id})
        if not settings or not settings.get("verified_role_id"):
            await interaction.response.send_message("Verification is not setup for this server.", ephemeral=True)
            return

        role_id = settings["verified_role_id"]
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Verification role not found. Please contact an admin.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("You are already verified!", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You have been verified and granted access to the server!", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to add verification role: {e}")
            await interaction.response.send_message("I don't have permission to give you the role. Please contact an admin.", ephemeral=True)

class Security(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.spam_cache: Dict[int, List[float]] = {} 
        self.message_cache: Dict[int, List[str]] = {} 
        self.join_cache: List[float] = [] 
        self.violation_cache: Dict[int, int] = {} 
        self.settings_cache = {} 
        
        # Regex for link detection
        self.url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
        
        # Periodic cache cleanup
        self.bot.loop.create_task(self.cleanup_caches())

    async def cog_unload(self):
        await self.session.close()

    async def cleanup_caches(self):
        """Periodically clears old cache entries to prevent memory bloat."""
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(300) # Every 5 minutes
                now = time.time()
                # Cleanup spam cache
                for uid in list(self.spam_cache.keys()):
                    self.spam_cache[uid] = [t for t in self.spam_cache[uid] if now - t < 10]
                    if not self.spam_cache[uid]:
                        del self.spam_cache[uid]
                
                if len(self.violation_cache) > 1000:
                    self.violation_cache.clear()
                
                if len(self.message_cache) > 1000:
                    self.message_cache.clear()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    async def get_settings(self, guild_id: int):
        settings = self.settings_cache.get(guild_id)
        if settings:
            return settings
        
        if Database.db is None:
            return None
            
        settings = await Database.db.security_settings.find_one({"guild_id": guild_id})
        if not settings:
            settings = {
                "guild_id": guild_id,
                "anti_spam": True,
                "anti_link": True,
                "anti_mass_mention": True,
                "mention_limit": 5,
                "min_account_age_days": 3,
                "log_channel_id": None,
                "whitelisted_roles": [],
                "whitelisted_users": []
            }
            await Database.db.security_settings.insert_one(settings)
        
        self.settings_cache[guild_id] = settings
        return settings

    async def log_security_event(self, guild: discord.Guild, title: str, description: str, color: int = Config.COLOR_WARNING):
        settings = await self.get_settings(guild.id)
        channel_id = settings.get("log_channel_id") or Config.MOD_LOG_CHANNEL_ID
        
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title=f"🛡️ Security Alert: {title}",
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Atlas Security System")
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send security log: {e}")

    async def handle_violation(self, message: discord.Message, reason: str):
        user_id = message.author.id
        self.violation_cache[user_id] = self.violation_cache.get(user_id, 0) + 1
        
        count = self.violation_cache[user_id]
        if count >= 3:
            try:
                duration = timedelta(minutes=10)
                await message.author.timeout(duration, reason=f"Atlas Security: Repeated {reason}")
                await self.log_security_event(
                    message.guild,
                    "User Timed Out",
                    f"User: {message.author.mention} ({message.author.id})\nReason: Repeated {reason} (3+ violations)\nDuration: 10 minutes",
                    Config.COLOR_ERROR
                )
                self.violation_cache[user_id] = 0 
            except Exception as e:
                logger.error(f"Failed to timeout user: {e}")
        else:
            await self.log_security_event(
                message.guild,
                "Spam Detected",
                f"User: {message.author.mention} ({message.author.id})\nChannel: {message.channel.mention}\nReason: {reason}\nViolation Count: {count}/3",
                Config.COLOR_WARNING
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Fast Cache Lookup
        settings = self.settings_cache.get(message.guild.id)
        if not settings:
            settings = await self.get_settings(message.guild.id)
            if not settings: return

        if message.author.guild_permissions.administrator:
            return
        
        if settings.get("whitelisted_roles") and any(role.id in settings["whitelisted_roles"] for role in message.author.roles):
            return
        
        if settings.get("whitelisted_users") and message.author.id in settings["whitelisted_users"]:
            return

        # Anti-Mass Mention
        if settings.get("anti_mass_mention") and len(message.mentions) > settings.get("mention_limit", 5):
            await message.delete()
            await self.log_security_event(
                message.guild, 
                "Mass Mention Detected", 
                f"User: {message.author.mention} ({message.author.id})\nChannel: {message.channel.mention}\nMentions: {len(message.mentions)}",
                Config.COLOR_ERROR
            )
            return

        # Anti-Spam
        if settings.get("anti_spam"):
            now = time.time()
            user_id = message.author.id
            if user_id not in self.spam_cache:
                self.spam_cache[user_id] = []
            
            self.spam_cache[user_id].append(now)
            self.spam_cache[user_id] = [t for t in self.spam_cache[user_id] if now - t < 5]
            
            if len(self.spam_cache[user_id]) > 5:
                await message.delete()
                await self.handle_violation(message, "Frequency Spam")
                return

            if user_id not in self.message_cache:
                self.message_cache[user_id] = []
            
            self.message_cache[user_id].append(message.content)
            if len(self.message_cache[user_id]) > 3:
                self.message_cache[user_id].pop(0)
            
            if len(self.message_cache[user_id]) >= 3 and len(set(self.message_cache[user_id])) == 1:
                await message.delete()
                await self.handle_violation(message, "Duplicate Spam")
                return

        # Anti-Link
        if settings.get("anti_link"):
            links = self.url_pattern.findall(message.content)
            if links:
                scam_keywords = ["discord-gift", "nitro", "free-nitro", "steam-community-nitro"]
                if any(k in message.content.lower() for k in scam_keywords):
                    await message.delete()
                    await self.log_security_event(
                        message.guild,
                        "Potential Scam Link",
                        f"User: {message.author.mention} ({message.author.id})\nLink: {links[0]}",
                        Config.COLOR_ERROR
                    )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await self.get_settings(member.guild.id)
        if not settings:
            return

        # 1. Anti-Alt / Account Age Protection
        min_age = settings.get("min_account_age_days", 3)
        account_age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days

        if account_age < min_age:
            # If anti_alt is enabled, kick the user
            if settings.get("anti_alt", False):
                try:
                    await member.send(f"⚠️ You have been automatically kicked from **{member.guild.name}** because your account is too new ({account_age} days old). We require accounts to be at least {min_age} days old to prevent alts.")
                    await member.kick(reason=f"Atlas Anti-Alt: Account age ({account_age} days) < {min_age} days")
                    await self.log_security_event(
                        member.guild,
                        "Alt Account Kicked",
                        f"**User**: {member.mention} ({member.id})\n**Account Age**: {account_age} days\n**Action**: Automatically Kicked",
                        Config.COLOR_ERROR
                    )
                    return
                except:
                    pass
            else:
                # Just log it if anti_alt is disabled
                await self.log_security_event(
                    member.guild,
                    "Suspicious New Account",
                    f"**User**: {member.mention} ({member.id})\n**Account Age**: {account_age} days\n**Action**: Logged Only",
                    Config.COLOR_WARNING
                )

        # 2. Raid Detection
        now = time.time()
        self.join_cache.append(now)
        self.join_cache = [t for t in self.join_cache if now - t < 30]

        if len(self.join_cache) > 5: 
            await self.log_security_event(
                member.guild,
                "Potential Raid Detected",
                f"Warning: {len(self.join_cache)} members joined in the last 30 seconds.",
                Config.COLOR_ERROR
            )
            self.join_cache = []

    # Slash Commands Group
    security = app_commands.Group(name="security", description="Manage security settings")

    @security.command(name="setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Setup security logging channel"""
        logger.info(f"Command /security setup started by {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        try:
            if Database.db is None:
                return await interaction.followup.send("Database not connected.", ephemeral=True)

            await Database.db.security_settings.update_one(
                {"guild_id": interaction.guild_id},
                {"$set": {"log_channel_id": channel.id}},
                upsert=True
            )
            self.settings_cache[interaction.guild_id] = await Database.db.security_settings.find_one({"guild_id": interaction.guild_id})
            await interaction.followup.send(f"✅ Security logging channel set to {channel.mention}", ephemeral=True)
            logger.info(f"Command /security setup finished successfully")
        except Exception as e:
            logger.exception("Error in /security setup")
            await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)

    @security.command(name="toggle")
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_cmd(self, interaction: discord.Interaction, feature: str, enabled: bool):
        """Toggle security features"""
        logger.info(f"Command /security toggle started: {feature}={enabled}")
        await interaction.response.defer(ephemeral=True)
        try:
            valid = ["anti_spam", "anti_link", "anti_mass_mention", "anti_alt"]
            if feature not in valid:
                return await interaction.followup.send(f"Invalid feature. Use: {', '.join(valid)}", ephemeral=True)

            if Database.db is None:
                return await interaction.followup.send("Database not connected.", ephemeral=True)

            await Database.db.security_settings.update_one(
                {"guild_id": interaction.guild_id},
                {"$set": {feature: enabled}},
                upsert=True
            )
            self.settings_cache[interaction.guild_id] = await Database.db.security_settings.find_one({"guild_id": interaction.guild_id})
            status = "enabled" if enabled else "disabled"
            await interaction.followup.send(f"✅ Feature `{feature}` has been {status}.", ephemeral=True)
            logger.info(f"Command /security toggle finished successfully")
        except Exception as e:
            logger.exception("Error in /security toggle")
            await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)

    @security.command(name="status")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_cmd(self, interaction: discord.Interaction):
        """View security status"""
        logger.info("Command /security status started")
        await interaction.response.defer()
        try:
            settings = await self.get_settings(interaction.guild_id)
            if not settings:
                return await interaction.followup.send("No settings found.", ephemeral=True)

            embed = discord.Embed(title="🛡️ Atlas Security Status", color=Config.COLOR_PRIMARY)
            embed.add_field(name="Anti-Spam", value="✅ Enabled" if settings.get("anti_spam") else "❌ Disabled")
            embed.add_field(name="Anti-Link", value="✅ Enabled" if settings.get("anti_link") else "❌ Disabled")
            embed.add_field(name="Anti-Alt (Kick)", value="✅ Enabled" if settings.get("anti_alt") else "❌ Disabled")
            embed.add_field(name="Anti-Mass Mention", value="✅ Enabled" if settings.get("anti_mass_mention") else "❌ Disabled")
            embed.add_field(name="Min Age Kick", value=f"{settings.get('min_account_age_days', 3)} days")
            
            log_channel = interaction.guild.get_channel(settings.get("log_channel_id"))
            embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not set", inline=False)
            
            await interaction.followup.send(embed=embed)
            logger.info("Command /security status finished successfully")
        except Exception as e:
            logger.exception("Error in /security status")
            await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)

    @security.command(name="verify_setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_setup_cmd(self, interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel):
        """Setup verification system"""
        await interaction.response.defer(ephemeral=True)
        if Database.db is None:
            return await interaction.followup.send("Database not connected.", ephemeral=True)

        await Database.db.security_settings.update_one(
            {"guild_id": interaction.guild_id},
            {"$set": {"verified_role_id": role.id}},
            upsert=True
        )
        self.settings_cache[interaction.guild_id] = await Database.db.security_settings.find_one({"guild_id": interaction.guild_id})

        embed = discord.Embed(
            title="🛡️ Server Verification",
            description=f"Welcome to **{interaction.guild.name}**!\n\nPlease click the button below to verify yourself.",
            color=Config.COLOR_PRIMARY
        )
        await channel.send(embed=embed, view=VerificationView())
        await interaction.followup.send(f"✅ Verification setup in {channel.mention}", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Security(bot)
    await bot.add_cog(cog)
    bot.add_view(VerificationView())
