#!/bin/bash
# Stop Whisper Service for Discord Bot

cd "$(dirname "$0")"

echo "Stopping Whisper service..."

# Kill the whisper service process
if pgrep -f "whisper_service.py" > /dev/null; then
    pkill -f "whisper_service.py"
    sleep 2
    
    # Check if it's still running
    if pgrep -f "whisper_service.py" > /dev/null; then
        echo "Force killing Whisper service..."
        pkill -9 -f "whisper_service.py"
        sleep 1
    fi
    
    if ! pgrep -f "whisper_service.py" > /dev/null; then
        echo "✅ Whisper service stopped successfully"
    else
        echo "❌ Failed to stop Whisper service"
        exit 1
    fi
else
    echo "Whisper service is not running"
fi