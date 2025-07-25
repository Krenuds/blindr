import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from audio_sinks import PCMRecordingSink, WAVRecordingSink, MultiFormatSink

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

# Recording state management
connections = {}
recording_sinks = {}

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
    voice_client = await join_voice_channel()
    if voice_client:
        connections[voice_client.guild.id] = voice_client

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
    recording_status = "❌ Not recording"
    
    if hasattr(bot, 'voice_client_ref') and bot.voice_client_ref and bot.voice_client_ref.is_connected():
        channel_name = bot.voice_client_ref.channel.name
        voice_status = f"🔊 Connected to #{channel_name}"
    
    if ctx.guild.id in connections and connections[ctx.guild.id].is_recording():
        recording_status = "🎤 Currently recording"
    
    embed = discord.Embed(
        title="AI Voice Bot - Status",
        description="Discord bot with voice capture capabilities",
        color=0x00ff00
    )
    embed.add_field(
        name="Commands",
        value="!status - Show bot status\n!start_recording - Start audio capture\n!stop_recording - Stop and save audio",
        inline=False
    )
    embed.add_field(
        name="Voice Status",
        value=voice_status,
        inline=False
    )
    embed.add_field(
        name="Recording Status",
        value=recording_status,
        inline=False
    )
    embed.add_field(
        name="Phase Progress",
        value="✅ Phase 1: Voice channel connection\n🎤 Phase 1: Audio capture implementation",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='start_recording')
async def start_recording_command(ctx, format_type: str = "wav"):
    """Start recording audio from the voice channel."""
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in a voice channel to start recording!")
        return
    
    if ctx.guild.id in connections and connections[ctx.guild.id].is_recording():
        await ctx.send("❌ Already recording in this server!")
        return
    
    voice_channel = ctx.author.voice.channel
    
    try:
        # Connect to voice channel if not already connected
        if ctx.guild.id not in connections:
            vc = await voice_channel.connect()
            connections[ctx.guild.id] = vc
        else:
            vc = connections[ctx.guild.id]
        
        # Set up recording sink based on format
        if format_type.lower() == "pcm":
            sink = PCMRecordingSink("recorded_audio")
        else:
            sink = WAVRecordingSink("recorded_audio")
        
        recording_sinks[ctx.guild.id] = sink
        
        # Start recording
        vc.start_recording(
            sink,
            recording_finished_callback,
            ctx.channel
        )
        
        await ctx.send(f"🎤 Started recording in {format_type.upper()} format! Use `!stop_recording` to stop and save.")
        logger.info(f"Started recording in guild {ctx.guild.id} with format {format_type}")
        
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        await ctx.send(f"❌ Failed to start recording: {str(e)}")


@bot.command(name='stop_recording')
async def stop_recording_command(ctx):
    """Stop recording and save audio files."""
    if ctx.guild.id not in connections:
        await ctx.send("❌ Not connected to a voice channel in this server!")
        return
    
    vc = connections[ctx.guild.id]
    
    if not vc.is_recording():
        await ctx.send("❌ Not currently recording!")
        return
    
    try:
        vc.stop_recording()
        await ctx.send("⏹️ Stopped recording! Processing audio files...")
        logger.info(f"Stopped recording in guild {ctx.guild.id}")
        
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        await ctx.send(f"❌ Failed to stop recording: {str(e)}")


async def recording_finished_callback(sink, channel, *args):
    """Callback function called when recording finishes."""
    try:
        # Get list of users who were recorded
        recorded_users = [f"<@{user_id}>" for user_id in sink.audio_data.keys()]
        
        if not recorded_users:
            await channel.send("⚠️ No audio was recorded (no users were speaking).")
            return
        
        # Create Discord file objects from recorded audio
        files = []
        for user_id, audio in sink.audio_data.items():
            if audio.file.tell() > 0:  # Only include files with actual audio data
                filename = f"user_{user_id}.{sink.encoding}"
                audio.file.seek(0)
                files.append(discord.File(audio.file, filename))
        
        if files:
            await channel.send(
                f"🎵 Recording complete! Captured audio from: {', '.join(recorded_users)}",
                files=files
            )
            logger.info(f"Sent {len(files)} recorded audio files to channel")
        else:
            await channel.send("⚠️ Recording complete, but no audio data was captured.")
            
    except Exception as e:
        logger.error(f"Error in recording callback: {e}")
        await channel.send(f"❌ Error processing recorded audio: {str(e)}")


async def cleanup():
    """Cleanup function for graceful shutdown"""
    # Stop any active recordings
    for guild_id, vc in connections.items():
        if vc.is_recording():
            vc.stop_recording()
            logger.info(f'Stopped recording in guild {guild_id}')
        await vc.disconnect()
        logger.info(f'Disconnected from voice channel in guild {guild_id}')
    
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