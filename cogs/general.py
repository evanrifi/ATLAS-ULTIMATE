import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available commands and their descriptions")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 Atlas Ultimate Help Menu",
            description="Welcome to the Atlas help center. Here are all the available slash commands:",
            color=0x2b2d31
        )
        
        # Group commands by Cog
        for cog_name, cog in self.bot.cogs.items():
            commands_list = cog.get_app_commands()
            if not commands_list:
                continue
                
            cmd_info = []
            for cmd in commands_list:
                cmd_info.append(f"`/{cmd.name}` - {cmd.description}")
            
            if cmd_info:
                embed.add_field(
                    name=f"✨ {cog_name}",
                    value="\n".join(cmd_info),
                    inline=False
                )
        
        embed.set_footer(text="Atlas Ultimate • Your Premium Discord Solution", icon_url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
