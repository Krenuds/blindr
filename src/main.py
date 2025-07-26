"""
Main entry point for the Discord Voice Bot
"""

from .bot import VoiceBot

if __name__ == "__main__":
    voice_bot = VoiceBot()
    voice_bot.run()