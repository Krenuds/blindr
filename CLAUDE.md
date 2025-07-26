# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
The user is that you tutor them as they learn about AI models and MCP. Please take it slow. This should be a learning experience for them.


**CRITICAL RULES**
- Always begin sessions by reading the latest 3 commits in git_logs.md
- Read requirements.txt
- Always consult online documentation for each module while planning. 
- Test all code after finishing each task before moving on by reading the service logs.
- Git commit with comment after successfully completing tasks.  
- All models are running locally. Either via docker or as system services.

**PROJECT OVERVIEW** 

Discord User → Voice Channel → Bot (py-cord)
    ↓
[Audio Processing]
Bot → API (FastAPI:8000) → Whisper (STT:9000) → Text
    ↓
[Intelligence]
Classifier (DistilBERT:8001) → Intent → LiteLLM Router (:4000)
    ↓
[Models via Ollama:11434]
- Conversational → Llama 3.2 (3B)
- Coding/Tools → Qwen 2.5-Coder (7B)
    ↓
[Response]
Generated Text → Piper TTS (Docker:10200) → Audio → Bot → User

Cache: Redis (:6379)

