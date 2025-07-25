#!/usr/bin/env python3
"""
Provide project context to Claude without displaying to user
"""

import json
import subprocess
import sys
import os

def get_git_context():
    """Get latest 3 commits from git logs"""
    try:
        # Generate git logs
        subprocess.run(['makeGitLogs', '10'], check=True, capture_output=True)
        
        # Read and parse the git_logs.md file
        if os.path.exists('git_logs.md'):
            with open('git_logs.md', 'r') as f:
                content = f.read()
            
            # Extract first 3 commit sections
            lines = content.split('\n')
            commits = []
            current_commit = []
            commit_count = 0
            in_commit = False
            
            for line in lines:
                if line.startswith('### ') and '. Commit:' in line:
                    if commit_count >= 3:
                        break
                    if current_commit:
                        commits.append('\n'.join(current_commit))
                    current_commit = [line]
                    commit_count += 1
                    in_commit = True
                elif line.startswith('---') and in_commit:
                    current_commit.append(line)
                    commits.append('\n'.join(current_commit))
                    current_commit = []
                    in_commit = False
                elif in_commit:
                    current_commit.append(line)
            
            return '\n\n'.join(commits)
    except Exception as e:
        return f"Error getting git context: {e}"
    
    return "No git context available"

def get_roadmap_context():
    """Get roadmap progress report"""
    try:
        result = subprocess.run(['.claude/roadmap_tracker.py'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error getting roadmap context: {e}"

def main():
    # Gather all context
    git_context = get_git_context()
    roadmap_context = get_roadmap_context()
    
    full_context = f"""PROJECT CONTEXT FOR CLAUDE:

{roadmap_context}

RECENT GIT HISTORY:
{git_context}

This context helps Claude understand the current project state and development progress."""

    # Output JSON for Claude's context (not displayed to user)
    context_output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": full_context
        }
    }
    
    print(json.dumps(context_output))

if __name__ == "__main__":
    main()