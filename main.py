#!/usr/bin/env python3
"""
Bot runner script that properly imports from the new package structure
"""

from src.bot import VoiceBot

if __name__ == "__main__":
    voice_bot = VoiceBot()
    voice_bot.run()