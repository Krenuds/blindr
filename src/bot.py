import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from audio_sinks import PCMRecordingSink, WAVRecordingSink, MultiFormatSink
from whisper_client import WhisperClient

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

# Initialize Whisper client
whisper_client = WhisperClient(os.getenv('WHISPER_URL', 'http://localhost:9000'))

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
        value="!status - Show bot status\n!start_recording - Start audio capture\n!stop_recording - Stop and save audio\n!transcribe - Transcribe latest audio file",
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
        value="✅ Phase 1: Voice channel connection\n✅ Phase 1: Audio capture implementation\n✅ Phase 2: Whisper integration (voice-to-text)",
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


@bot.command(name='transcribe')
async def transcribe_command(ctx, *, message: str = None):
    """Transcribe the most recent audio file or test Whisper service."""
    if message:
        # If user provides a message, just echo it back (for testing)
        await ctx.send(f"🎤 You said: {message}")
        return
    
    # Check if there are any recent audio files
    import glob
    from pathlib import Path
    
    audio_dir = Path("recorded_audio")
    if not audio_dir.exists():
        await ctx.send("❌ No recorded audio directory found. Record some audio first with `!start_recording`")
        return
    
    # Find the most recent audio file
    audio_files = list(audio_dir.glob("*.wav"))
    if not audio_files:
        await ctx.send("❌ No audio files found. Record some audio first with `!start_recording`")
        return
    
    # Get the most recent file
    latest_file = max(audio_files, key=lambda f: f.stat().st_mtime)
    
    try:
        await ctx.send(f"🔄 Transcribing {latest_file.name}...")
        
        # Transcribe using Whisper
        result = await whisper_client.transcribe_file(latest_file)
        
        if result and result.get('text'):
            transcribed_text = result['text'].strip()
            if transcribed_text:
                await ctx.send(f"📝 **Transcription**: {transcribed_text}")
            else:
                await ctx.send("⚠️ No speech detected in the audio file.")
        else:
            await ctx.send("❌ Transcription failed - no text returned.")
            
    except FileNotFoundError:
        await ctx.send(f"❌ Audio file not found: {latest_file}")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        await ctx.send(f"❌ Transcription failed: {str(e)}")


async def recording_finished_callback(sink, channel, *args):
    """Callback function called when recording finishes."""
    try:
        # Get list of users who were recorded
        recorded_users = [f"<@{user_id}>" for user_id in sink.audio_data.keys()]
        
        if not recorded_users:
            await channel.send("⚠️ No audio was recorded (no users were speaking).")
            return
        
        # Create Discord file objects from recorded audio and transcribe
        files = []
        transcriptions = []
        
        for user_id, audio in sink.audio_data.items():
            if audio.file.tell() > 0:  # Only include files with actual audio data
                filename = f"user_{user_id}.{sink.encoding}"
                audio.file.seek(0)
                files.append(discord.File(audio.file, filename))
                
                # Attempt to transcribe the audio
                try:
                    audio.file.seek(0)
                    audio_bytes = audio.file.read()
                    
                    if len(audio_bytes) > 1000:  # Only transcribe if there's substantial audio
                        result = await whisper_client.transcribe_bytes(
                            audio_bytes, 
                            filename=filename
                        )
                        
                        if result and result.get('text'):
                            transcribed_text = result['text'].strip()
                            if transcribed_text:
                                transcriptions.append(f"<@{user_id}>: {transcribed_text}")
                
                except Exception as e:
                    logger.warning(f"Failed to transcribe audio for user {user_id}: {e}")
                    continue
        
        # Send results
        if files:
            message_parts = [f"🎵 Recording complete! Captured audio from: {', '.join(recorded_users)}"]
            
            if transcriptions:
                message_parts.append("\n📝 **Transcriptions:**")
                message_parts.extend(transcriptions)
            
            message = "\n".join(message_parts)
            
            # Split message if too long for Discord (2000 char limit)
            if len(message) > 1900:
                await channel.send(f"🎵 Recording complete! Captured audio from: {', '.join(recorded_users)}", files=files)
                if transcriptions:
                    await channel.send("📝 **Transcriptions:**\n" + "\n".join(transcriptions))
            else:
                await channel.send(message, files=files)
                
            logger.info(f"Sent {len(files)} recorded audio files to channel with {len(transcriptions)} transcriptions")
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
    
    # Close Whisper client
    await whisper_client.close()
    logger.info('Closed Whisper client connection')

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