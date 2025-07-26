#!/usr/bin/env python3
"""
Documentation Checking Hook for Claude Code
Reminds Claude to consult official documentation before implementing APIs/integrations
"""

import json
import sys
import re
from pathlib import Path

def analyze_tool_use(tool_data):
    """Analyze the tool use to determine if documentation should be consulted"""
    tool_name = tool_data.get('tool_name', '')
    tool_params = tool_data.get('parameters', {})
    
    # Check if this involves API integration or library usage
    needs_docs_check = False
    documentation_suggestions = []
    
    # Check file content for API/library patterns
    file_path = tool_params.get('file_path', '')
    content = tool_params.get('content', '') or tool_params.get('new_string', '')
    
    if content:
        # API/Integration patterns that should use documentation
        api_patterns = [
            (r'discord\.py|discord\.', 'Discord.py official documentation and examples'),
            (r'whisper|openai', 'OpenAI Whisper documentation and GitHub examples'),
            (r'fastapi|FastAPI', 'FastAPI official documentation and tutorials'),
            (r'ollama', 'Ollama official documentation and API reference'),
            (r'redis|Redis', 'Redis-py documentation and Redis official docs'),
            (r'docker|Docker', 'Official Docker documentation and best practices'),
            (r'requests\.|urllib|http', 'Official API documentation for target service'),
            (r'asyncio|async\s+def', 'Python asyncio documentation and patterns'),
            (r'websocket|WebSocket', 'WebSocket library documentation'),
            (r'jwt|JWT|oauth|OAuth', 'Official authentication provider documentation'),
        ]
        
        for pattern, suggestion in api_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                needs_docs_check = True
                documentation_suggestions.append(suggestion)
    
    # Check file extensions for specific technologies
    if file_path:
        path = Path(file_path)
        if path.suffix in ['.py', '.js', '.ts', '.yaml', '.yml', '.json']:
            if any(tech in path.name.lower() for tech in ['docker', 'compose', 'config', 'api']):
                needs_docs_check = True
                documentation_suggestions.append("Official documentation for the service being configured")
    
    return needs_docs_check, documentation_suggestions

def create_documentation_reminder(suggestions):
    """Create a reminder message about consulting documentation"""
    if not suggestions:
        return None
    
    message = """
🔍 DOCUMENTATION REMINDER

Before implementing this code, ensure you're following proven patterns by consulting:

"""
    for i, suggestion in enumerate(set(suggestions), 1):
        message += f"{i}. {suggestion}\n"
    
    message += """
📋 Recommended approach:
- Check official API documentation against our current code
- Look for official examples or sample code
"""
    
    return message

def main():
    try:
        # Read hook input from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(0)  # No input, proceed normally
        
        hook_data = json.loads(input_data)
        tool_data = hook_data.get('toolUse', {})
        
        # Analyze if documentation should be consulted
        needs_docs, suggestions = analyze_tool_use(tool_data)
        
        if needs_docs and suggestions:
            # Create reminder message
            reminder = create_documentation_reminder(suggestions)
            
            # Output reminder to stdout (will be shown to user)
            print(reminder)
            
            # Also output as JSON for hook system
            output = {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": f"Documentation check: {len(suggestions)} API/integration patterns detected. Consult official docs before proceeding."
                }
            }
            
            # Write JSON to stderr for hook system (stdout is for user message)
            sys.stderr.write(json.dumps(output) + '\n')
    
    except Exception as e:
        # Don't block tool use on errors
        sys.stderr.write(f"Documentation check error: {e}\n")
    
    # Always allow the tool to proceed
    sys.exit(0)

if __name__ == "__main__":
    main()