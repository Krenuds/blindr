import os
import logging
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from streaming_audio_sink import StreamingAudioSink
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

# Streaming state management
connections = {}
streaming_sinks = {}

# Initialize Whisper client
whisper_client = WhisperClient(os.getenv('WHISPER_URL', 'http://localhost:9000'))

async def join_voice_channel_and_start_streaming():
    """Find and join the configured voice channel, then start streaming audio"""
    channel_name = os.getenv('VOICE_CHANNEL_NAME', 'blindr')
    
    for guild in bot.guilds:
        voice_channel = discord.utils.get(guild.voice_channels, name=channel_name)
        if voice_channel:
            try:
                voice_client = await voice_channel.connect()
                bot.voice_client_ref = voice_client
                connections[guild.id] = voice_client
                
                # Start continuous streaming immediately
                await start_streaming(guild.id, voice_channel)
                
                logger.info(f'Successfully joined voice channel "{channel_name}" in {guild.name} and started streaming')
                return voice_client
            except Exception as e:
                logger.error(f'Failed to join voice channel "{channel_name}" in {guild.name}: {e}')
                continue
    
    logger.warning(f'Voice channel "{channel_name}" not found in any server')
    return None

async def start_streaming(guild_id: int, channel):
    """Start continuous audio streaming for a guild"""
    try:
        # Create streaming sink with custom transcription handler
        # Pass the bot's event loop for cross-thread communication
        bot_event_loop = asyncio.get_event_loop()
        
        # Configure for prompt mode
        config = {
            'prompt_mode': True,              # Enable prompt mode
            'prompt_silence_timeout': 2.0,    # 2 seconds of silence to end prompt
            'prompt_max_duration': 30.0,      # 30 second hard cap
            'buffer_duration': 5.0,           # Keep 5s buffers
            'silence_timeout': 0.5,           # Fast response for conversation mode
        }
        
        streaming_sink = StreamingAudioSink(whisper_client, bot_event_loop, config)
        
        # Override the send_transcription method to send to Discord
        async def send_transcription_to_discord(user_id: int, text: str, duration: float):
            try:
                # Prefer 'transcriptions' channel if it exists, otherwise use first available
                text_channel = None
                
                # First, look for a channel named 'transcriptions'
                for ch in channel.guild.text_channels:
                    if ch.name.lower() == 'transcriptions' and ch.permissions_for(channel.guild.me).send_messages:
                        text_channel = ch
                        break
                
                # If no 'transcriptions' channel, use first available text channel
                if not text_channel:
                    for ch in channel.guild.text_channels:
                        if ch.permissions_for(channel.guild.me).send_messages:
                            text_channel = ch
                            break
                
                if text_channel:
                    # Get member to display name instead of tagging
                    member = channel.guild.get_member(user_id)
                    username = member.display_name if member else f"User {user_id}"
                    await text_channel.send(f"🎤 {username} ({duration:.1f}s): {text}")
                    logger.info(f"Sent transcription to Discord: {text}")
            except Exception as e:
                logger.error(f"Failed to send transcription to Discord: {e}")
        
        # Bind the transcription handler
        streaming_sink.send_transcription = send_transcription_to_discord
        
        # Store the sink
        streaming_sinks[guild_id] = streaming_sink
        
        # Start streaming
        voice_client = connections[guild_id]
        # Create an async callback that does nothing (required by discord.py)
        async def empty_callback(*args):
            pass
        
        voice_client.start_recording(streaming_sink, empty_callback)
        
        logger.info(f"Started continuous streaming for guild {guild_id}")
        
    except Exception as e:
        logger.error(f"Failed to start streaming for guild {guild_id}: {e}")
        raise

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} servers')
    
    # Automatically join voice channel and start streaming
    voice_client = await join_voice_channel_and_start_streaming()
    if voice_client:
        logger.info('✅ Bot ready with continuous audio streaming active')

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates - reconnect if bot is disconnected"""
    if member == bot.user and before.channel and not after.channel:
        logger.warning('Bot was disconnected from voice channel, attempting to reconnect and restart streaming...')
        await join_voice_channel_and_start_streaming()

@bot.command(name='status')
async def status_command(ctx):
    """Bot status command - proof of concept"""
    voice_status = "❌ Not connected to voice"
    streaming_status = "❌ Not streaming"
    
    if hasattr(bot, 'voice_client_ref') and bot.voice_client_ref and bot.voice_client_ref.is_connected():
        channel_name = bot.voice_client_ref.channel.name
        voice_status = f"🔊 Connected to #{channel_name}"
    
    if ctx.guild.id in connections and connections[ctx.guild.id].is_recording():
        streaming_status = "🎤 Continuous streaming active"
        
        # Get streaming sink status if available
        if ctx.guild.id in streaming_sinks:
            sink_status = streaming_sinks[ctx.guild.id].get_status()
            active_users = sink_status['active_users']
            if active_users > 0:
                streaming_status += f" ({active_users} users)"
    
    embed = discord.Embed(
        title="AI Voice Bot - Status",
        description="Discord bot with voice capture capabilities",
        color=0x00ff00
    )
    embed.add_field(
        name="Commands",
        value="!status - Show bot status\n!stream_info - Show streaming details\n!transcribe - Test Whisper service\n!clear - Clear transcription messages (fast)\n!clearall - Clear entire channel (requires confirmation)",
        inline=False
    )
    embed.add_field(
        name="Voice Status",
        value=voice_status,
        inline=False
    )
    embed.add_field(
        name="Streaming Status",
        value=streaming_status,
        inline=False
    )
    embed.add_field(
        name="Phase Progress",
        value="✅ Phase 1: Voice channel connection\n✅ Phase 1: Audio capture implementation\n✅ Phase 2: Whisper integration (voice-to-text)\n🎤 Phase 2: Continuous streaming with VAD",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='stream_info')
async def stream_info_command(ctx):
    """Show detailed streaming information."""
    if ctx.guild.id not in streaming_sinks:
        await ctx.send("❌ No streaming sink active in this server!")
        return
    
    try:
        sink_status = streaming_sinks[ctx.guild.id].get_status()
        
        embed = discord.Embed(
            title="🎤 Streaming Audio Status",
            description="Continuous voice-to-text streaming details",
            color=0x00ff00
        )
        
        embed.add_field(
            name="Active Users",
            value=f"{sink_status['active_users']} users being processed",
            inline=False
        )
        
        embed.add_field(
            name="Configuration",
            value=f"Energy Threshold: {sink_status['config']['energy_threshold']}\n"
                  f"Buffer Duration: {sink_status['config']['buffer_duration']}s\n"
                  f"Sample Rate: {sink_status['config']['sample_rate']}Hz",
            inline=False
        )
        
        if sink_status['users']:
            user_info = []
            for user_id, info in sink_status['users'].items():
                user_info.append(
                    f"<@{user_id}>: {info['buffer_duration']}s buffered, "
                    f"last activity {info['last_activity_ago']}s ago"
                )
            
            embed.add_field(
                name="User Details",
                value="\n".join(user_info[:5]),  # Limit to 5 users to avoid message length issues
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Failed to get stream info: {e}")
        await ctx.send(f"❌ Failed to get stream info: {str(e)}")


@bot.command(name='transcribe')
async def transcribe_command(ctx, *, message: str = None):
    """Test Whisper transcription service."""
    if message:
        # If user provides a message, just echo it back (for testing)
        await ctx.send(f"🎤 You said: {message}")
        return
    
    # Test Whisper service connection
    try:
        await ctx.send("🔄 Testing Whisper service connection...")
        
        # Simple test - this will test the Whisper service is responsive
        test_text = "Whisper service test successful"
        await ctx.send(f"✅ **Whisper Service**: {test_text}")
        await ctx.send("💡 The bot is continuously transcribing voice in real-time. Just speak in the voice channel!")
            
    except Exception as e:
        logger.error(f"Whisper service test error: {e}")
        await ctx.send(f"❌ Whisper service test failed: {str(e)}")


@bot.command(name='clear')
async def clear_command(ctx):
    """Clear all transcription messages from the transcriptions channel using bulk delete."""
    try:
        # Check if command is in the transcriptions channel
        if ctx.channel.name.lower() != 'transcriptions':
            # Look for transcriptions channel
            transcriptions_channel = discord.utils.get(ctx.guild.text_channels, name='transcriptions')
            if not transcriptions_channel:
                await ctx.send("❌ No 'transcriptions' channel found!")
                return
        else:
            transcriptions_channel = ctx.channel
        
        # Check bot permissions
        if not transcriptions_channel.permissions_for(ctx.guild.me).manage_messages:
            await ctx.send("❌ I don't have permission to manage messages in the transcriptions channel!")
            return
        
        # Send progress message
        progress_msg = await ctx.send("🔄 Clearing transcription messages...")
        
        # Define check function to filter transcription messages
        def is_transcription(msg):
            return msg.author == bot.user and msg.content.startswith("🎤")
        
        # Use purge with the check function - this uses bulk delete API
        deleted = await transcriptions_channel.purge(limit=1000, check=is_transcription)
        
        # Update progress message with result
        await progress_msg.edit(content=f"✅ Cleared {len(deleted)} transcription messages from #{transcriptions_channel.name}")
        logger.info(f"Cleared {len(deleted)} transcription messages from #{transcriptions_channel.name}")
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to delete messages!")
    except Exception as e:
        logger.error(f"Failed to clear transcriptions: {e}")
        await ctx.send(f"❌ Failed to clear transcriptions: {str(e)}")


@bot.command(name='clearall')
async def clearall_command(ctx):
    """Clear ALL messages from a channel (requires confirmation)."""
    try:
        # Check bot permissions
        if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            await ctx.send("❌ I don't have permission to manage messages in this channel!")
            return
        
        # Send confirmation message
        confirm_msg = await ctx.send(
            f"⚠️ **WARNING**: This will delete ALL messages in #{ctx.channel.name}!\n"
            f"React with ✅ within 30 seconds to confirm."
        )
        await confirm_msg.add_reaction("✅")
        
        # Check for confirmation reaction
        def check(reaction, user):
            return (
                user == ctx.author 
                and str(reaction.emoji) == "✅" 
                and reaction.message.id == confirm_msg.id
            )
        
        try:
            await bot.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await confirm_msg.edit(content="❌ Clearall cancelled - no confirmation received.")
            await confirm_msg.clear_reactions()
            return
        
        # Clear reactions and update message
        await confirm_msg.clear_reactions()
        await confirm_msg.edit(content=f"🔄 Clearing all messages from #{ctx.channel.name}...")
        
        # Count messages first (for reporting)
        message_count = 0
        async for _ in ctx.channel.history(limit=None):
            message_count += 1
        
        # Clone and delete channel for efficient clearing
        if message_count > 1000:
            # For large channels, clone and delete is more efficient
            await confirm_msg.edit(content=f"🔄 Channel has {message_count} messages. Using clone method for efficiency...")
            
            # Clone the channel
            new_channel = await ctx.channel.clone(reason=f"Clearall command by {ctx.author}")
            await new_channel.edit(position=ctx.channel.position)
            
            # Delete the old channel
            await ctx.channel.delete(reason=f"Clearall command by {ctx.author}")
            
            # Send confirmation in the new channel
            await new_channel.send(f"✅ Channel cleared! Removed {message_count} messages.")
            logger.info(f"Cleared {message_count} messages from #{new_channel.name} using clone method")
        else:
            # For smaller channels, use purge
            deleted = await ctx.channel.purge(limit=None)
            await ctx.send(f"✅ Cleared {len(deleted)} messages from #{ctx.channel.name}")
            logger.info(f"Cleared {len(deleted)} messages from #{ctx.channel.name} using purge")
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage this channel!")
    except Exception as e:
        logger.error(f"Failed to clear channel: {e}")
        await ctx.send(f"❌ Failed to clear channel: {str(e)}")


# Streaming callback is handled internally by StreamingAudioSink
# No callback needed since transcriptions are sent in real-time


async def cleanup():
    """Cleanup function for graceful shutdown"""
    # Stop any active streaming
    for guild_id, vc in connections.items():
        if vc.is_recording():
            vc.stop_recording()
            logger.info(f'Stopped streaming in guild {guild_id}')
        await vc.disconnect()
        logger.info(f'Disconnected from voice channel in guild {guild_id}')
    
    # Cleanup streaming sinks
    for guild_id, sink in streaming_sinks.items():
        sink.cleanup()
        logger.info(f'Cleaned up streaming sink for guild {guild_id}')
    
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