import discord
from discord.ext import commands

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket will be closed in 5 seconds...", ephemeral=False)
        
        # Simple text transcript
        try:
            import io
            messages = [msg async for msg in interaction.channel.history(limit=200, oldest_first=True)]
            transcript = "\n".join([f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author}: {msg.content}" for msg in messages])
            
            transcript_file = discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"{interaction.channel.name}-transcript.txt")
            await interaction.user.send(f"Your ticket `{interaction.channel.name}` was closed. Here is your transcript:", file=transcript_file)
        except Exception:
            pass # DMs could be closed or permission error
            
        import asyncio
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Ticket closed by user.")
        except:
            pass

class TicketMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='General Support', description='Need help with something?', value='Support', emoji='📝'),
            discord.SelectOption(label='Billing / Purchases', description='Questions about shop items?', value='Billing', emoji='💳'),
            discord.SelectOption(label='Report User', description='Report a rule breaker.', value='Report', emoji='🚨')
        ]
        super().__init__(placeholder='Select a department...', min_values=1, max_values=1, options=options, custom_id='ticket_dropdown')

    async def callback(self, interaction: discord.Interaction):
        dept = self.values[0]
        guild = interaction.guild
        
        import re
        clean_name = re.sub(r'[^a-z0-9-]', '', interaction.user.name.lower())
        channel_name = f"ticket-{clean_name}"
        
        existing = discord.utils.get(guild.channels, name=channel_name)
        if existing:
            return await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason="User created a ticket"
            )

            embed = discord.Embed(
                title=f"🎫 {dept} Ticket",
                description=f"Hello {interaction.user.mention}, a staff member will be with you shortly.\n\nTo close this ticket and generate a transcript, click the button below.",
                color=0x1dc9d8
            )
            await channel.send(content=f"{interaction.user.mention}", embed=embed, view=TicketCloseView())
            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Failed to create ticket channel.", ephemeral=True)

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketMenu())

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketCloseView())

    @discord.app_commands.command(name="setup_tickets", description="Deploy the support ticket panel")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 ATLAS Support System",
            description="Need assistance? Select a department from the menu below to open a private ticket.",
            color=0x1dc9d8
        )
        embed.set_footer(text="ATLAS ULTIMATE Support")
        
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message("Ticket panel deployed.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
