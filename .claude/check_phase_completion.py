#!/usr/bin/env python3
"""
Check if any phases were just completed and commit changes if so
"""

import os
import subprocess
import json
from datetime import datetime

def get_phase_completion_status():
    """Get completion status of all phases"""
    roadmap_file = "ROADMAP.md"
    if not os.path.exists(roadmap_file):
        return []
    
    with open(roadmap_file, 'r') as f:
        content = f.read()
    
    phases = []
    current_phase = None
    
    for line in content.split('\n'):
        if line.startswith('## Phase'):
            current_phase = {
                'name': line.strip(),
                'total_tasks': 0,
                'completed_tasks': 0
            }
            phases.append(current_phase)
        elif line.startswith('- [') and current_phase:
            current_phase['total_tasks'] += 1
            if '- [x]' in line.lower():
                current_phase['completed_tasks'] += 1
    
    # Calculate completion rates
    for phase in phases:
        phase['completion_rate'] = phase['completed_tasks'] / phase['total_tasks'] if phase['total_tasks'] > 0 else 0
        phase['is_complete'] = phase['completion_rate'] == 1.0
    
    return phases

def check_for_newly_completed_phases():
    """Check if any phases were just completed by comparing with last known state"""
    state_file = ".claude/phase_state.json"
    current_phases = get_phase_completion_status()
    
    # Load previous state
    previous_phases = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                previous_phases = json.load(f)
        except:
            previous_phases = {}
    
    # Find newly completed phases
    newly_completed = []
    for phase in current_phases:
        phase_name = phase['name']
        was_complete_before = previous_phases.get(phase_name, {}).get('is_complete', False)
        is_complete_now = phase['is_complete']
        
        if is_complete_now and not was_complete_before:
            newly_completed.append(phase)
    
    # Save current state
    current_state = {phase['name']: {'is_complete': phase['is_complete'], 'completion_rate': phase['completion_rate']} 
                    for phase in current_phases}
    with open(state_file, 'w') as f:
        json.dump(current_state, f, indent=2)
    
    return newly_completed

def create_phase_completion_commit(completed_phases):
    """Create git commit for completed phases"""
    if not completed_phases:
        return False
    
    try:
        # Check if there are changes to commit
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, check=True)
        
        if not result.stdout.strip():
            # No changes to commit
            return False
        
        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Create commit message
        phase_names = [phase['name'] for phase in completed_phases]
        if len(phase_names) == 1:
            subject = f"Complete {phase_names[0]}"
        else:
            subject = f"Complete {len(phase_names)} phases: " + ", ".join(phase_names)
        
        commit_message = f"""{subject}

🎯 PHASE COMPLETION MILESTONE

Completed phases:
{chr(10).join(f"✅ {phase['name']} - {phase['completed_tasks']}/{phase['total_tasks']} tasks" for phase in completed_phases)}

This represents a major milestone in the BLINDR Discord AI voice bot
development. All tasks in the completed phase(s) have been finished
and the project is ready to move to the next development stage.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
        
        # Create commit
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        
        # Optional: Push to remote (uncomment if desired)
        # subprocess.run(['git', 'push'], check=True)
        
        print(f"✅ Created phase completion commit for: {', '.join(phase_names)}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating commit: {e}")
        return False

def main():
    # Check for newly completed phases
    newly_completed = check_for_newly_completed_phases()
    
    if newly_completed:
        success = create_phase_completion_commit(newly_completed)
        if success:
            # Output for hook (minimal)
            phase_names = [phase['name'] for phase in newly_completed]
            print(f"Phase completion detected and committed: {', '.join(phase_names)}")
    
    # Always exit successfully for hook
    return 0

if __name__ == "__main__":
    exit(main())