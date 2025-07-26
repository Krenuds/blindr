import os
import logging
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from .audio_processing import StreamingAudioSink
from ..whisper import WhisperClient
from ..config import get_streaming_config

load_dotenv()
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE", "logs/bot.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class VoiceBot:
    """Discord voice bot for audio transcription with LLM integration."""

    def __init__(self):
        """Initialize the VoiceBot with Discord client and audio processing."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        self.bot = commands.Bot(
            command_prefix=os.getenv("BOT_PREFIX", "!"), intents=intents
        )
        self.connections = {}
        self.streaming_sinks = {}
        self.transcription_enabled = True
        self.whisper_client = WhisperClient(
            os.getenv("WHISPER_URL", "http://localhost:9000")
        )
        self._setup_events()
        self._setup_commands()
        logger.info("VoiceBot initialized")

    def _setup_events(self):
        """Setup Discord bot event handlers."""

        @self.bot.event
        async def on_ready():
            logger.info(f"{self.bot.user} has connected to Discord!")
            logger.info(f"Bot is in {len(self.bot.guilds)} servers")
            voice_client = await self.join_voice_channel()
            if voice_client:
                logger.info("✅ Bot ready with continuous audio streaming active")

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """Handle voice state updates - reconnect if bot is disconnected"""
            if member == self.bot.user and before.channel and not after.channel:
                logger.warning(
                    "Bot was disconnected from voice channel, attempting to reconnect..."
                )
                await self.join_voice_channel()

    def _setup_commands(self):
        """Setup Discord bot commands."""

        @self.bot.command(name="transcribe")
        async def transcribe_command(ctx):
            """Toggle voice transcription on/off."""
            await self.toggle_transcription(ctx)

        @self.bot.command(name="clearall")
        async def clearall_command(ctx):
            """Clear ALL messages from a channel (requires confirmation)."""
            await self.clear_channel_messages(ctx)

    async def join_voice_channel(self):
        """Find and join the configured voice channel, then start streaming."""
        channel_name = os.getenv("VOICE_CHANNEL_NAME", "blindr")
        for guild in self.bot.guilds:
            voice_channel = discord.utils.get(guild.voice_channels, name=channel_name)
            if voice_channel:
                try:
                    voice_client = await voice_channel.connect()
                    self.bot.voice_client_ref = voice_client
                    self.connections[guild.id] = voice_client
                    await self.start_streaming(guild.id, voice_channel)
                    logger.info(
                        f'Successfully joined voice channel "{channel_name}" in {guild.name}'
                    )
                    return voice_client
                except Exception as e:
                    logger.error(
                        f'Failed to join voice channel "{channel_name}" in {guild.name}: {e}'
                    )
                    continue
        logger.warning(f'Voice channel "{channel_name}" not found in any server')
        return None

    def find_text_channel(self, guild):
        """Find the best text channel for transcriptions."""
        for channel in guild.text_channels:
            if (
                channel.name.lower() == "transcriptions"
                and channel.permissions_for(guild.me).send_messages
            ):
                return channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
        return None

    async def resolve_username(self, user_id: int, guild):
        """Resolve username with simplified fallback logic."""
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        user = self.bot.get_user(user_id)
        if user:
            return user.display_name
        return f"User {user_id}"

    async def start_streaming(self, guild_id: int, channel):
        """Start continuous audio streaming for a guild."""
        try:
            audio_sink = self.create_audio_sink()
            self.setup_transcription_handler(audio_sink, channel)
            self.begin_recording(guild_id, audio_sink)
            logger.info(f"Started continuous streaming for guild {guild_id}")
        except Exception as e:
            logger.error(f"Failed to start streaming for guild {guild_id}: {e}")
            raise

    def create_audio_sink(self):
        """Create and configure the audio processing sink."""
        bot_event_loop = asyncio.get_event_loop()
        config = get_streaming_config()
        return StreamingAudioSink(self.whisper_client, bot_event_loop, config)

    def setup_transcription_handler(self, audio_sink, channel):
        """Setup the transcription handler for the audio sink."""

        async def send_transcription_to_discord(
            user_id: int, text: str, duration: float
        ):
            try:
                if not self.transcription_enabled:
                    return
                text_channel = self.find_text_channel(channel.guild)
                if text_channel:
                    username = await self.resolve_username(user_id, channel.guild)
                    await text_channel.send(f"🎤 {username} ({duration:.1f}s): {text}")
                    logger.info(f"Sent transcription: {text} (from {username})")
            except Exception as e:
                logger.error(f"Failed to send transcription to Discord: {e}")

        audio_sink.send_transcription = send_transcription_to_discord

    def begin_recording(self, guild_id: int, audio_sink):
        """Begin audio recording with the configured sink."""
        self.streaming_sinks[guild_id] = audio_sink
        voice_client = self.connections[guild_id]

        async def empty_callback(*args):
            pass

        voice_client.start_recording(audio_sink, empty_callback)

    async def toggle_transcription(self, ctx):
        """Toggle voice transcription on/off."""
        self.transcription_enabled = not self.transcription_enabled
        status = "🔊 ON" if self.transcription_enabled else "🔇 OFF"
        emoji = "✅" if self.transcription_enabled else "❌"
        embed = discord.Embed(
            title=f"{emoji} Transcription {status}",
            description=f"Voice transcription is now **{status}**",
            color=0x00FF00 if self.transcription_enabled else 0xFF0000,
        )
        if self.transcription_enabled:
            embed.add_field(
                name="📢 Active",
                value="Voice messages will be transcribed to Discord",
                inline=False,
            )
        else:
            embed.add_field(
                name="🤫 Disabled",
                value="Voice messages will not be transcribed",
                inline=False,
            )
        embed.add_field(
            name="Commands",
            value="!transcribe - Toggle transcription on/off\n!clearall - Clear entire channel (requires confirmation)",
            inline=False,
        )
        await ctx.send(embed=embed)
        logger.info(f"Transcription toggled to: {self.transcription_enabled}")

    async def clear_channel_messages(self, ctx):
        """Clear ALL messages from a channel (requires confirmation)."""
        try:
            if not self.validate_clear_permissions(ctx):
                await ctx.send(
                    "❌ I don't have permission to manage messages in this channel!"
                )
                return
            confirmed = await self.get_user_confirmation(ctx)
            if not confirmed:
                return
            await self.clear_messages(ctx)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage this channel!")
        except Exception as e:
            logger.error(f"Failed to clear channel: {e}")
            await ctx.send(f"❌ Failed to clear channel: {str(e)}")

    def validate_clear_permissions(self, ctx):
        """Check if bot has permission to clear messages."""
        return ctx.channel.permissions_for(ctx.guild.me).manage_messages

    async def get_user_confirmation(self, ctx):
        """Get user confirmation for clearing messages."""
        confirm_msg = await ctx.send(
            f"⚠️ **WARNING**: This will delete ALL messages in #{ctx.channel.name}!\n"
            f"React with ✅ within 30 seconds to confirm."
        )
        await confirm_msg.add_reaction("✅")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) == "✅"
                and reaction.message.id == confirm_msg.id
            )

        try:
            await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            await confirm_msg.clear_reactions()
            await confirm_msg.edit(
                content=f"🔄 Clearing all messages from #{ctx.channel.name}..."
            )
            return True
        except asyncio.TimeoutError:
            await confirm_msg.edit(
                content="❌ Clearall cancelled - no confirmation received."
            )
            await confirm_msg.clear_reactions()
            return False

    async def clear_messages(self, ctx):
        """Clear messages using the most efficient method."""
        deleted = await ctx.channel.purge(limit=None)
        await ctx.send(f"✅ Cleared {len(deleted)} messages from #{ctx.channel.name}")
        logger.info(f"Cleared {len(deleted)} messages from #{ctx.channel.name}")

    async def cleanup(self):
        """Cleanup function for graceful shutdown."""
        for guild_id, vc in self.connections.items():
            if vc.is_recording():
                vc.stop_recording()
                logger.info(f"Stopped streaming in guild {guild_id}")
            await vc.disconnect()
            logger.info(f"Disconnected from voice channel in guild {guild_id}")
        for guild_id, sink in self.streaming_sinks.items():
            sink.cleanup()
            logger.info(f"Cleaned up streaming sink for guild {guild_id}")
        if hasattr(self.bot, "voice_client_ref") and self.bot.voice_client_ref:
            await self.bot.voice_client_ref.disconnect()
            logger.info("Disconnected from voice channel")
        await self.whisper_client.close()
        logger.info("Closed Whisper client connection")

    def run(self):
        """Start the Discord bot."""
        # Clear logs on startup
        log_file = os.getenv("LOG_FILE", "logs/bot.log")
        if os.path.exists(log_file):
            open(log_file, 'w').close()
            logger.info("Log file cleared on startup")
        
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            logger.error("DISCORD_BOT_TOKEN not found in environment variables")
            exit(1)
        try:
            self.bot.run(token)
        except KeyboardInterrupt:
            logger.info("Bot shutdown requested")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
        finally:
            pass


if __name__ == "__main__":
    voice_bot = VoiceBot()
    voice_bot.run()