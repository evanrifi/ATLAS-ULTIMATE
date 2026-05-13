import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import os
from config import Config
from database import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AtlasBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        logger.info("Initializing database...")
        await Database.connect()

        logger.info("Loading cogs...")
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}")

        logger.info("Syncing application commands...")
        try:
            # Global sync
            synced_global = await self.tree.sync()
            logger.info(f"Synced {len(synced_global)} global command(s).")
            
            if Config.GUILD_ID:
                guild = discord.Object(id=Config.GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced_guild = await self.tree.sync(guild=guild)
                logger.info(f"Synced {len(synced_guild)} command(s) to guild {Config.GUILD_ID}.")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        # Add error handler for slash commands
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.MissingPermissions):
                message = f"❌ You are missing permissions: {', '.join(error.missing_permissions)}"
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    await interaction.response.send_message(message, ephemeral=True)
            else:
                logger.error(f"Slash command error: {error}")
                message = f"❌ An error occurred: {error}"
                if len(message) > 1900:
                    message = message[:1890] + "..."
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    try:
                        await interaction.response.send_message(message, ephemeral=True)
                    except discord.errors.InteractionResponded:
                        await interaction.followup.send(message, ephemeral=True)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        logger.info("Atlas Ultimate is online and ready!")

    async def on_interaction(self, interaction: discord.Interaction):
        logger.info(f"Interaction received: ID={interaction.id}, Type={interaction.type}, User={interaction.user}, PID={os.getpid()}")
        if interaction.type == discord.InteractionType.application_command:
            logger.info(f"Command: {interaction.data.get('name')} with data: {interaction.data.get('options')}")
        # Process the interaction

    async def close(self):
        await Database.close()
        await super().close()

async def main():
    if not Config.BOT_TOKEN:
        logger.error("BOT_TOKEN (DISCORD_TOKEN) is not set properly in the .env file.")
        return

    # Single instance lock (Simple file-based)
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file) # Try to remove stale lock
        except:
            logger.error("Another instance of the bot is already running. Exiting.")
            return
            
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))

    try:
        bot = AtlasBot()
        async with bot:
            await bot.start(Config.BOT_TOKEN)
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

if __name__ == "__main__":
    asyncio.run(main())
