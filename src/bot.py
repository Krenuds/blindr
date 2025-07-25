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
intents.voice_states = True
bot = commands.Bot(command_prefix=os.getenv('BOT_PREFIX', '!'), intents=intents)

async def join_voice_channel():
    """Find and join the configured voice channel"""
    channel_name = os.getenv('VOICE_CHANNEL_NAME', 'blindr')
    
    for guild in bot.guilds:
        voice_channel = discord.utils.get(guild.voice_channels, name=channel_name)
        if voice_channel:
            try:
                voice_client = await voice_channel.connect()
                bot.voice_client_ref = voice_client
                logger.info(f'Successfully joined voice channel "{channel_name}" in {guild.name}')
                return voice_client
            except Exception as e:
                logger.error(f'Failed to join voice channel "{channel_name}" in {guild.name}: {e}')
                continue
    
    logger.warning(f'Voice channel "{channel_name}" not found in any server')
    return None

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} servers')
    
    # Automatically join voice channel
    await join_voice_channel()

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates - reconnect if bot is disconnected"""
    if member == bot.user and before.channel and not after.channel:
        logger.warning('Bot was disconnected from voice channel, attempting to reconnect...')
        await join_voice_channel()

@bot.command(name='status')
async def status_command(ctx):
    """Bot status command - proof of concept"""
    voice_status = "❌ Not connected to voice"
    
    if hasattr(bot, 'voice_client_ref') and bot.voice_client_ref and bot.voice_client_ref.is_connected():
        channel_name = bot.voice_client_ref.channel.name
        voice_status = f"🔊 Connected to #{channel_name}"
    
    embed = discord.Embed(
        title="AI Voice Bot - Status",
        description="Discord bot with automatic voice channel integration",
        color=0x00ff00
    )
    embed.add_field(
        name="Commands",
        value="!status - Show bot status",
        inline=False
    )
    embed.add_field(
        name="Voice Status",
        value=voice_status,
        inline=False
    )
    embed.add_field(
        name="Phase Progress",
        value="✅ Phase 1: Voice channel connection\n⏳ Next: Audio capture implementation",
        inline=False
    )
    await ctx.send(embed=embed)

async def cleanup():
    """Cleanup function for graceful shutdown"""
    if hasattr(bot, 'voice_client_ref') and bot.voice_client_ref:
        await bot.voice_client_ref.disconnect()
        logger.info('Disconnected from voice channel')

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        exit(1)
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info('Bot shutdown requested')
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
    finally:
        # Cleanup is handled automatically by discord.py
        pass