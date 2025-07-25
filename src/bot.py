import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'logs/bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=os.getenv('BOT_PREFIX', '!'), intents=intents)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} servers')

@bot.command(name='status')
async def status_command(ctx):
    """Bot status command - proof of concept"""
    embed = discord.Embed(
        title="AI Voice Bot - Help",
        description="Basic Discord bot ready for voice integration",
        color=0x00ff00
    )
    embed.add_field(
        name="Commands",
        value="!status - Show bot status",
        inline=False
    )
    embed.add_field(
        name="Status",
        value="✅ Connected and ready\n⏳ Voice features coming in Phase 1",
        inline=False
    )
    await ctx.send(embed=embed)

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        exit(1)
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")