import discord
from discord.ext import commands
from config import Config

class VoicePanel(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    def check_owner(self, interaction: discord.Interaction):
        return interaction.user.id == self.owner_id

    @discord.ui.button(emoji=discord.PartialEmoji(name="rename", id=1492523171373645905), style=discord.ButtonStyle.secondary, custom_id="btn_rename", row=0)
    async def rename_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            return await interaction.response.send_message("Only the channel owner can do this.", ephemeral=True)
        class RenameModal(discord.ui.Modal, title="Rename Channel"):
            name = discord.ui.TextInput(label="New Channel Name", placeholder="My chill room")
            async def on_submit(self, modal_interaction: discord.Interaction):
                channel = modal_interaction.user.voice.channel if modal_interaction.user.voice else None
                if channel:
                    await channel.edit(name=self.name.value)
                    await modal_interaction.response.send_message(f"Channel renamed to `{self.name.value}`", ephemeral=True)
        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(emoji=discord.PartialEmoji(name="limit", id=1493352536206479482), style=discord.ButtonStyle.secondary, custom_id="btn_limit", row=0)
    async def limit_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            return await interaction.response.send_message("Only the channel owner can do this.", ephemeral=True)
        class LimitModal(discord.ui.Modal, title="Set User Limit"):
            limit = discord.ui.TextInput(label="Number of users (0 for unlimited)", placeholder="e.g. 5")
            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    val = int(self.limit.value)
                    channel = modal_interaction.user.voice.channel if modal_interaction.user.voice else None
                    if channel:
                        await channel.edit(user_limit=val)
                        await modal_interaction.response.send_message(f"Channel limit set to {val if val > 0 else 'unlimited'}.", ephemeral=True)
                except ValueError:
                    await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(emoji=discord.PartialEmoji(name="lock", id=1492523136694878350), style=discord.ButtonStyle.secondary, custom_id="btn_lock", row=0)
    async def lock_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            return await interaction.response.send_message("Only the channel owner can do this.", ephemeral=True)
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if channel:
            await channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("Channel Locked. No new users can join.", ephemeral=True)

    @discord.ui.button(emoji=discord.PartialEmoji(name="unlock", id=1492523245117640936), style=discord.ButtonStyle.secondary, custom_id="btn_unlock", row=0)
    async def unlock_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            return await interaction.response.send_message("Only the channel owner can do this.", ephemeral=True)
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if channel:
            await channel.set_permissions(interaction.guild.default_role, connect=None)
            await interaction.response.send_message("Channel Unlocked. Your channel is now open.", ephemeral=True)

    @discord.ui.button(emoji=discord.PartialEmoji(name="kick", id=1492523028959985704), style=discord.ButtonStyle.secondary, custom_id="btn_kick", row=1)
    async def kick_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            return await interaction.response.send_message("Only the channel owner can do this.", ephemeral=True)
        
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)

        class KickSelect(discord.ui.UserSelect):
            def __init__(self, owner_id):
                super().__init__(placeholder="Select a user to kick...")
                self.owner_id = owner_id

            async def callback(self, select_interaction: discord.Interaction):
                target = self.values[0]
                if target.id == self.owner_id:
                    return await select_interaction.response.send_message("You cannot kick yourself!", ephemeral=True)
                
                if target not in channel.members:
                    return await select_interaction.response.send_message("That user is not in your channel.", ephemeral=True)

                try:
                    await target.move_to(None)
                    await select_interaction.response.send_message(f"✅ **{target.display_name}** has been kicked from the channel.", ephemeral=True)
                except:
                    await select_interaction.response.send_message("❌ Failed to kick user. Check bot permissions.", ephemeral=True)

        view = discord.ui.View()
        view.add_item(KickSelect(self.owner_id))
        await interaction.response.send_message("Who do you want to kick?", view=view, ephemeral=True)

    @discord.ui.button(emoji=discord.PartialEmoji(name="transfer", id=1492523205309763585), style=discord.ButtonStyle.secondary, custom_id="btn_transfer", row=1)
    async def transfer_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            return await interaction.response.send_message("Only the channel owner can do this.", ephemeral=True)
        
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)

        class TransferSelect(discord.ui.UserSelect):
            def __init__(self, owner_id, parent_view):
                super().__init__(placeholder="Select the new owner...")
                self.owner_id = owner_id
                self.parent_view = parent_view

            async def callback(self, select_interaction: discord.Interaction):
                target = self.values[0]
                if target.id == self.owner_id:
                    return await select_interaction.response.send_message("You are already the owner!", ephemeral=True)
                
                if target not in channel.members:
                    return await select_interaction.response.send_message("The new owner must be in the voice channel.", ephemeral=True)

                # Update the mapping in VoiceHub
                from cogs.voice_hub import VoiceHub
                VoiceHub.temp_channel_owners[channel.id] = target.id
                
                # Update the parent view's owner_id for future button clicks if it's still the same message
                self.parent_view.owner_id = target.id
                
                await select_interaction.response.send_message(f"👑 Ownership transferred to **{target.display_name}**!", ephemeral=False)

        view = discord.ui.View()
        view.add_item(TransferSelect(self.owner_id, self))
        await interaction.response.send_message("Who do you want to transfer ownership to?", view=view, ephemeral=True)

    @discord.ui.button(emoji=discord.PartialEmoji(name="info", id=1492522998371057825), style=discord.ButtonStyle.secondary, custom_id="btn_info", row=1)
    async def info_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("This channel is a temporary voice channel.", ephemeral=True)

class VoiceHub(commands.Cog):
    temp_channels = set()
    temp_channel_owners = {} # channel_id -> owner_id

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_channel_type(self, channel_id):
        types = {
            Config.JTC_GAMING: {"emoji": "🎮", "label": "Gaming Room", "name": "Gaming"},
            Config.JTC_STUDY: {"emoji": "📚", "label": "Study Room", "name": "Study"},
            Config.JTC_MUSIC: {"emoji": "🎵", "label": "Music Room", "name": "Music"},
            Config.JTC_CHILL: {"emoji": "🌙", "label": "Chill Room", "name": "Chill"},
            Config.JOIN_TO_CREATE_ID: {"emoji": "🔷", "label": "Voice Room", "name": "Room"}
        }
        return types.get(channel_id, {"emoji": "🔷", "label": "Voice Room", "name": "Room"})

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Only proceed if the user actually switched channels
        if before.channel == after.channel:
            return

        if after.channel and after.channel.id in Config.JTC_IDS:
            category = after.channel.category
            ch_type = self.get_channel_type(after.channel.id)
            channel_name = f"{ch_type['emoji']} {member.display_name}'s {ch_type['name']}"
            
            try:
                new_channel = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    user_limit=after.channel.user_limit
                )
                
                await member.move_to(new_channel)
                VoiceHub.temp_channels.add(new_channel.id)
                VoiceHub.temp_channel_owners[new_channel.id] = member.id
                
                embed = discord.Embed(color=0x00e5ff)
                if Config.BANNER_GIF_URL and Config.BANNER_GIF_URL.startswith('http'):
                    embed.set_image(url=Config.BANNER_GIF_URL)
                else:
                    embed.description = "\u200b" # Fallback if no GIF
                
                await new_channel.send(content=member.mention, embed=embed, view=VoicePanel(member.id))
            except discord.Forbidden:
                pass

        # 2. Handle leaving a channel
        if before.channel and before.channel.id in VoiceHub.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    VoiceHub.temp_channels.discard(before.channel.id)
                    VoiceHub.temp_channel_owners.pop(before.channel.id, None)
                except Exception as e:
                    pass

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceHub(bot))
