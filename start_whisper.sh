#!/bin/bash
# Start Whisper Service for Discord Bot
# This script starts the native Python Whisper service on port 9000

cd "$(dirname "$0")"

# Check if service is already running
if pgrep -f "whisper_service.py" > /dev/null; then
    echo "Whisper service is already running"
    exit 0
fi

# Activate virtual environment
source venv/bin/activate

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Whisper service in background
echo "Starting Whisper service on port 9000..."
nohup python src/whisper_service.py > logs/whisper.log 2>&1 &

# Wait a moment for startup
sleep 3

# Test if service is running
if curl -s http://localhost:9000/health > /dev/null; then
    echo "✅ Whisper service started successfully"
    echo "📊 Service running with GPU acceleration (NVIDIA RTX 2080)"
    echo "🔍 Check logs: tail -f logs/whisper.log"
    echo "🌐 Health check: curl http://localhost:9000/health"
else
    echo "❌ Failed to start Whisper service"
    echo "Check logs: tail logs/whisper.log"
    exit 1
fi