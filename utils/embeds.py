import discord
from config import Config

class EmbedBuilder:
    @staticmethod
    def create(title: str = None, description: str = None, color: int = Config.COLOR_PRIMARY, **kwargs) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color, **kwargs)
        # Add default styling, footers, or authors here
        return embed
    
    @staticmethod
    def success(description: str) -> discord.Embed:
        return EmbedBuilder.create(title="✅ Success", description=description, color=Config.COLOR_SUCCESS)

    @staticmethod
    def error(description: str) -> discord.Embed:
        return EmbedBuilder.create(title="❌ Error", description=description, color=Config.COLOR_ERROR)

    @staticmethod
    def info(description: str) -> discord.Embed:
        return EmbedBuilder.create(title="ℹ️ Info", description=description, color=Config.COLOR_INFO)
