import discord
from discord.ext import commands
from discord import app_commands
import random
import time
import logging
from database import Database
from config import Config

logger = logging.getLogger(__name__)

class LevelXP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns = {} # user_id -> last_xp_time

    def get_xp_for_level(self, level):
        return level * level * 100

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        now = time.time()

        # Cooldown: 1 minute between XP gains
        if user_id in self.cooldowns and now - self.cooldowns[user_id] < 60:
            return

        if Database.db is None:
            return

        self.cooldowns[user_id] = now

        # Get user data
        user_data = await Database.db.users.find_one({"user_id": user_id, "guild_id": guild_id})
        
        if not user_data:
            user_data = {
                "user_id": user_id,
                "guild_id": guild_id,
                "xp": 0,
                "level": 0
            }
            await Database.db.users.insert_one(user_data)

        old_level = user_data.get("level", 0)
        xp_to_add = random.randint(15, 25)
        new_xp = user_data.get("xp", 0) + xp_to_add
        
        # Calculate new level
        # XP = Level^2 * 100 => Level = sqrt(XP/100)
        new_level = int((new_xp / 100) ** 0.5)

        await Database.db.users.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {"$set": {"xp": new_xp, "level": new_level}}
        )

        if new_level > old_level:
            await self.handle_level_up(message, new_level)

    async def handle_level_up(self, message, level):
        embed = discord.Embed(
            title="🎊 Level Up!",
            description=f"Congratulations {message.author.mention}! You've reached **Level {level}**!",
            color=Config.COLOR_SUCCESS
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        
        # Determine where to send level up message
        channel_id = Config.LEVEL_UP_CHANNEL_ID
        channel = message.guild.get_channel(channel_id) if channel_id else message.channel
        
        try:
            await channel.send(embed=embed)
        except:
            pass

        # Handle Role Rewards
        role_map = {
            5: Config.ROLE_LEVEL_5,
            10: Config.ROLE_LEVEL_10,
            20: Config.ROLE_LEVEL_20
        }
        
        role_id = role_map.get(level)
        if role_id:
            role = message.guild.get_role(role_id)
            if role:
                try:
                    await message.author.add_roles(role)
                    await channel.send(f"🏆 {message.author.mention} has been awarded the **{role.name}** role!")
                except:
                    pass

    @app_commands.command(name="rank", description="Check your current level and XP progress")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        
        target = member or interaction.user
        if Database.db is None:
            return await interaction.followup.send("Database connection error.")

        user_data = await Database.db.users.find_one({"user_id": target.id, "guild_id": interaction.guild_id})
        
        if not user_data:
            return await interaction.followup.send(f"{target.display_name} hasn't earned any XP yet!")

        level = user_data.get("level", 0)
        xp = user_data.get("xp", 0)
        
        next_level_xp = self.get_xp_for_level(level + 1)
        current_level_xp = self.get_xp_for_level(level)
        
        progress_xp = xp - current_level_xp
        needed_xp = next_level_xp - current_level_xp
        percentage = min(100, int((progress_xp / needed_xp) * 100))
        
        # Create a progress bar
        bar_length = 10
        filled = int(percentage / 10)
        bar = "▰" * filled + "▱" * (bar_length - filled)

        embed = discord.Embed(title=f"📊 Rank: {target.display_name}", color=Config.COLOR_PRIMARY)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{xp}**", inline=True)
        embed.add_field(name="Progress", value=f"`{bar}` {percentage}%\n{progress_xp}/{needed_xp} XP to next level", inline=False)
        
        embed.set_footer(text="Keep chatting to earn more XP!")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top members by XP")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if Database.db is None:
            return await interaction.followup.send("Database connection error.")

        # Get top 10 users
        cursor = Database.db.users.find({"guild_id": interaction.guild_id}).sort("xp", -1).limit(10)
        top_users = await cursor.to_list(length=10)

        if not top_users:
            return await interaction.followup.send("No one has earned XP yet!")

        description = ""
        for i, data in enumerate(top_users, 1):
            try:
                user = await self.bot.fetch_user(data["user_id"])
                name = user.display_name
            except:
                name = f"User {data['user_id']}"
            
            description += f"**{i}.** {name} — Level {data['level']} ({data['xp']} XP)\n"

        embed = discord.Embed(
            title=f"🏆 {interaction.guild.name} Leaderboard",
            description=description,
            color=Config.COLOR_WARNING
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
            
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelXP(bot))
