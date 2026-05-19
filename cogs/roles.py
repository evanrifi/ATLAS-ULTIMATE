import discord
from discord.ext import commands
import json
import os
import logging
from config import Config

logger = logging.getLogger(__name__)

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'role-panels.json')

def load_role_panels():
    if not os.path.exists(DATA_PATH):
        return {"guilds": {}}
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading role-panels.json: {e}")
        return {"guilds": {}}

class RoleButton(discord.ui.Button):
    def __init__(self, label, emoji, role_id, exclusive, panel_id):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"rb:{panel_id}:{role_id}"
        )
        self.role_id = int(role_id)
        self.exclusive = exclusive
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("Role not found.", ephemeral=True)

        if interaction.guild.me.top_role.position <= role.position:
            return await interaction.response.send_message("I cannot manage this role (higher than mine).", ephemeral=True)

        member = interaction.user
        has_role = member.get_role(self.role_id)

        try:
            if self.exclusive:
                # Remove other roles in the same panel
                data = load_role_panels()
                guild_data = data.get("guilds", {}).get(str(interaction.guild.id), {})
                panels = guild_data.get("panels", [])
                panel = next((p for p in panels if p["id"] == self.panel_id), None)
                
                if panel:
                    roles_to_remove = []
                    for opt in panel["options"]:
                        rid = int(opt["roleId"])
                        if rid != self.role_id and member.get_role(rid):
                            roles_to_remove.append(interaction.guild.get_role(rid))
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove)
                
                await member.add_roles(role)
                await interaction.response.send_message(f"✅ Your role has been updated to **{role.name}**.", ephemeral=True)
            else:
                if has_role:
                    await member.remove_roles(role)
                    await interaction.response.send_message(f"❌ Removed role **{role.name}**.", ephemeral=True)
                else:
                    await member.add_roles(role)
                    await interaction.response.send_message(f"✅ Added role **{role.name}**.", ephemeral=True)
        except Exception as e:
            logger.error(f"Role button error: {e}")
            await interaction.response.send_message("Failed to update roles. Check my permissions.", ephemeral=True)

class RoleSelect(discord.ui.Select):
    def __init__(self, panel):
        options = []
        for opt in panel.get("options", []):
            options.append(discord.SelectOption(
                label=opt.get("label"),
                value=opt.get("roleId"),
                emoji=opt.get("emoji")
            ))
        super().__init__(
            placeholder=panel.get("placeholder", "Select a role..."),
            options=options,
            custom_id=f"rs:{panel['id']}"
        )
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        # ... same logic as button but for select ...
        # (Shortened for brevity but I'll implement it fully)
        member = interaction.user
        exclusive = self.panel.get("exclusive", True)
        
        try:
            if exclusive:
                roles_to_remove = []
                for opt in self.panel["options"]:
                    rid = int(opt["roleId"])
                    if rid != role_id and member.get_role(rid):
                        roles_to_remove.append(interaction.guild.get_role(rid))
                if roles_to_remove: await member.remove_roles(*roles_to_remove)
                await member.add_roles(role)
            else:
                if member.get_role(role_id): await member.remove_roles(role)
                else: await member.add_roles(role)
            await interaction.response.send_message(f"✅ Updated your roles for **{self.panel['title']}**.", ephemeral=True)
        except:
            await interaction.response.send_message("Error updating roles.", ephemeral=True)

class PremiumRoleView(discord.ui.View):
    def __init__(self, panel):
        super().__init__(timeout=None)
        options = panel.get("options", [])
        if len(options) <= 5:
            for opt in options:
                self.add_item(RoleButton(opt["label"], opt.get("emoji"), opt["roleId"], panel.get("exclusive", True), panel["id"]))
        else:
            self.add_item(RoleSelect(panel))

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.register_views())

    async def register_views(self):
        await self.bot.wait_until_ready()
        data = load_role_panels()
        for g_id, g_data in data.get("guilds", {}).items():
            for p in g_data.get("panels", []):
                self.bot.add_view(PremiumRoleView(p))

    @discord.app_commands.command(name="post_roles", description="Post the self-assign role panels with professional UI")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def post_roles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = load_role_panels()
        guild_data = data.get("guilds", {}).get(str(interaction.guild.id))
        
        if not guild_data or not guild_data.get("panels"):
            return await interaction.followup.send("No role panels configured.")

        for panel in guild_data["panels"]:
            embed = discord.Embed(
                title=f" {panel['title']}",
                description=f"{panel['description']}\n\n" + "\n".join([f"**{line}**" for line in panel.get("bodyLines", [])]),
                color=panel.get("color", Config.COLOR_PRIMARY)
            )
            
            # Professional styling
            embed.set_author(name="ATLAS ULTIMATE ROLE SYSTEM", icon_url=self.bot.user.display_avatar.url)
            if Config.BANNER_GIF_URL:
                embed.set_image(url=Config.BANNER_GIF_URL)
            
            embed.set_footer(text="Select a role below to update your profile", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            
            view = PremiumRoleView(panel)
            await interaction.channel.send(embed=embed, view=view)
            
        await interaction.followup.send("Professional Role Panels deployed! ✅")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # 1. Assign Auto Role
        if Config.AUTO_ROLE_ID:
            role = member.guild.get_role(Config.AUTO_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role)
                    logger.info(f"✅ Automatically assigned role {role.name} to {member.name}")
                except Exception as e:
                    logger.warning(f"❌ Failed to assign auto-role to {member.name}: {e}")

        # 2. Send Welcome Message
        if Config.WELCOME_CHANNEL_ID:
            channel = member.guild.get_channel(Config.WELCOME_CHANNEL_ID)
            if channel:
                from datetime import datetime
                age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
                account_age_str = f"{age} days ago" if age > 0 else "Today"
                
                # Color processing
                color_val = 0x00E5FF
                if Config.WELCOME_COLOR:
                    try:
                        color_val = int(Config.WELCOME_COLOR.strip("#"), 16)
                    except:
                        pass
                
                embed = discord.Embed(
                    title=f"✨ Welcome to {member.guild.name}!",
                    description=(
                        f"Welcome to the community, {member.mention}! We're thrilled to have you join us.\n\n"
                        f"📋 **Server Guidelines & Verification**:\n"
                        f"• Be sure to read the rules carefully.\n"
                        f"• Assign yourself self-roles in the server panels.\n"
                        f"• Get verified if needed to access all rooms.\n\n"
                        f"📈 **Community Statistics**:\n"
                        f"• Member Position: **#{member.guild.member_count}**\n"
                        f"• Account Age: `{account_age_str}`"
                    ),
                    color=color_val
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                
                # Logo / Banner logic
                if Config.WELCOME_LOGO_URL:
                    embed.set_image(url=Config.WELCOME_LOGO_URL)
                elif Config.BANNER_GIF_URL:
                    embed.set_image(url=Config.BANNER_GIF_URL)
                    
                embed.set_footer(
                    text="Atlas Ultimate • User Joined",
                    icon_url=self.bot.user.display_avatar.url if self.bot.user else None
                )
                try:
                    await channel.send(embed=embed)
                    logger.info(f"✨ Successfully sent welcome message for {member.name} in channel {channel.name}")
                except Exception as e:
                    logger.error(f"❌ Failed to send welcome message for {member.name}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
