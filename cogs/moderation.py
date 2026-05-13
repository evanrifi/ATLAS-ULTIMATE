import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import Config
from datetime import datetime

logger = logging.getLogger(__name__)

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def log_mod_action(self, guild: discord.Guild, title: str, description: str, color: int = Config.COLOR_INFO):
        # Find log channel from security settings or config
        security_cog = self.bot.get_cog("Security")
        channel_id = Config.MOD_LOG_CHANNEL_ID
        if security_cog:
            settings = await security_cog.get_settings(guild.id)
            if settings and settings.get("log_channel_id"):
                channel_id = settings["log_channel_id"]
        
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title=f"🛠️ Mod Action: {title}",
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Atlas Moderation Engine")
        try:
            await channel.send(embed=embed)
        except:
            pass

    @app_commands.command(name="clear", description="Clear a specified number of messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        
        if amount < 1 or amount > 100:
            return await interaction.followup.send("❌ Please specify an amount between 1 and 100.", ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"✅ Successfully cleared **{len(deleted)}** messages.", ephemeral=True)
            await self.log_mod_action(interaction.guild, "Messages Cleared", f"**Mod**: {interaction.user.mention}\n**Channel**: {interaction.channel.mention}\n**Amount**: {len(deleted)}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot kick someone with a higher or equal role.", ephemeral=True)
        
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f"✅ **{member}** has been kicked.", ephemeral=True)
            await self.log_mod_action(interaction.guild, "Member Kicked", f"**User**: {member.mention}\n**Mod**: {interaction.user.mention}\n**Reason**: {reason}", Config.COLOR_WARNING)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to kick: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot ban someone with a higher or equal role.", ephemeral=True)
        
        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(f"✅ **{member}** has been banned.", ephemeral=True)
            await self.log_mod_action(interaction.guild, "Member Banned", f"**User**: {member.mention}\n**Mod**: {interaction.user.mention}\n**Reason**: {reason}", Config.COLOR_ERROR)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban: {e}", ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(duration="Timeout duration in minutes")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot timeout someone with a higher or equal role.", ephemeral=True)
        
        try:
            from datetime import timedelta
            await member.timeout(timedelta(minutes=duration), reason=reason)
            await interaction.response.send_message(f"✅ **{member}** has been timed out for {duration} minutes.", ephemeral=True)
            await self.log_mod_action(interaction.guild, "Member Timeout", f"**User**: {member.mention}\n**Mod**: {interaction.user.mention}\n**Duration**: {duration}m\n**Reason**: {reason}", Config.COLOR_WARNING)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to timeout: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"✅ **{user}** has been unbanned.", ephemeral=True)
            await self.log_mod_action(interaction.guild, "Member Unbanned", f"**User**: {user.name} ({user_id})\n**Mod**: {interaction.user.mention}", Config.COLOR_SUCCESS)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unban: {e}", ephemeral=True)

    @app_commands.command(name="lock", description="Lock the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
            await interaction.response.send_message(f"🔒 Channel has been **locked**.\n**Reason**: {reason}")
            await self.log_mod_action(interaction.guild, "Channel Locked", f"**Channel**: {interaction.channel.mention}\n**Mod**: {interaction.user.mention}\n**Reason**: {reason}", Config.COLOR_ERROR)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to lock channel: {e}", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlock the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = True
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            await interaction.response.send_message("🔓 Channel has been **unlocked**.")
            await self.log_mod_action(interaction.guild, "Channel Unlocked", f"**Channel**: {interaction.channel.mention}\n**Mod**: {interaction.user.mention}", Config.COLOR_SUCCESS)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unlock channel: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
