#!/bin/bash
# Start Discord Bot with Log Clearing
# This script clears logs and starts the Discord bot

cd "$(dirname "$0")"

# Check if CLEAR_LOGS_ON_START environment variable is set (default: true)
CLEAR_LOGS=${CLEAR_LOGS_ON_START:-true}

if [ "$CLEAR_LOGS" = "true" ]; then
    echo "🧹 Clearing session logs..."
    # Clear log files if they exist
    [ -f "logs/bot.log" ] && > logs/bot.log && echo "  ✅ Cleared bot.log"
    [ -f "logs/bot_output.log" ] && > logs/bot_output.log && echo "  ✅ Cleared bot_output.log"
    [ -f "logs/whisper.log" ] && > logs/whisper.log && echo "  ✅ Cleared whisper.log"
    echo "🎯 Fresh session logs ready"
else
    echo "📝 Preserving existing logs (CLEAR_LOGS_ON_START=false)"
fi

# Check if bot is already running
if pgrep -f "src/bot.py" > /dev/null; then
    echo "🤖 Discord bot is already running"
    exit 0
fi

# Activate virtual environment
source venv/bin/activate

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Discord bot
echo "🚀 Starting Discord bot..."
python src/bot.py

# Note: Bot runs in foreground for debugging
# Use Ctrl+C to stop the bot gracefully