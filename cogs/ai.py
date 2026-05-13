import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
from config import Config
import logging
import asyncio

logger = logging.getLogger(__name__)

class AIAssistant(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.model = None
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-flash-latest')
                logger.info("Gemini AI Assistant initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found in config. AI Assistant will be disabled.")

    @app_commands.command(name="ask", description="Ask the Atlas AI assistant anything")
    async def ask(self, interaction: discord.Interaction, question: str):
        if not self.model:
            await interaction.response.send_message("❌ AI Assistant is not configured. Please set GEMINI_API_KEY in .env", ephemeral=True)
            return

        await interaction.response.defer()
        
        try:
            # Use executor to run the synchronous library call if needed, 
            # but google-generativeai supports async generation in newer versions
            response = await self.model.generate_content_async(
                contents=question,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=800,
                    temperature=0.7,
                )
            )
            
            text = response.text
            
            # Handle empty responses
            if not text:
                await interaction.followup.send("🤖 The AI couldn't generate a response. Please try a different question.")
                return

            # Discord has a 4096 character limit for embed descriptions
            # and 2000 for messages. Embed description is better.
            if len(text) > 1900:
                text = text[:1890] + "..."
                
            embed = discord.Embed(
                title="✨ Atlas AI Assistant",
                description=text,
                color=0x5865F2
            )
            embed.set_author(name=f"Query by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="Powered by Google Gemini", icon_url="https://www.gstatic.com/lamda/images/favicon_v2_16x16.png")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"AI Error: {e}")
            await interaction.followup.send(f"❌ An error occurred while processing your request: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AIAssistant(bot))
