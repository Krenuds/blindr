# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
The user is that you tutor them as they learn about AI models and MCP. Please take it slow. This should be a learning experience for them.


**RULES**
- No ephemeral information should be stored in this file.
- Always begin sessions by reading the latest 3 commits in git_logs.md
- Read requirements.txt
- Always consult online documentation for each module while planning. 
- Test all code after finishing each task before moving on by reading the service logs.
- All commits end with "- UNTESTED" unless using /ready command.  
- Git commit and comment after successfully completing untested tasks.

**PROJECT OVERVIEW** 

## Target Architecture
Discord User → Voice Channel → Bot (py-cord)
    ↓
[Audio Processing - src/bot/]
VoiceBot → StreamingAudioSink → Whisper Service (:9000) → Text
    ↓
[Intelligence - src/llm/]
Text → Intent Classification → Model Selection
    ↓
[Models via Ollama:11434]
- Conversational → Llama 3.2 (3B)
- Coding/Tools → Qwen 2.5-Coder (7B)
    ↓
[Response]
Generated Text → Discord Text Channel
    ↓
[Future: TTS Integration]
Generated Text → Piper TTS (Docker:10200) → Audio → Bot → User

## Target Package Structure
```
src/
├── bot/                     # Discord voice bot domain
│   ├── voice_bot.py        # Main Discord bot class
│   └── audio_processing.py # Audio components
├── whisper/                # Speech-to-text domain
│   ├── client.py           # HTTP client
│   └── service.py          # FastAPI service
├── llm/                    # LLM integration domain
│   ├── client.py           # Ollama HTTP client
│   └── classifier.py       # Intent classification
├── tts/                    # Text-to-speech domain (future)
│   ├── client.py           # Piper TTS client
│   └── service.py          # TTS processing
├── config/                 # Configuration domain
│   └── loader.py           # Config utilities
└── main.py                 # Entry point
```

