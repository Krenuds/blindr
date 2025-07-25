#!/usr/bin/env python3
"""
BLINDR Roadmap Tracker
Tracks current development phase and progress through the 18-week roadmap
"""

import re
import json
import os
from datetime import datetime

def get_current_phase():
    """Determine current phase based on completed tasks in ROADMAP.md"""
    roadmap_file = "ROADMAP.md"
    if not os.path.exists(roadmap_file):
        return "Phase 1", "ROADMAP.md not found"
    
    with open(roadmap_file, 'r') as f:
        content = f.read()
    
    # Extract phases and their completion status
    phases = []
    current_phase = None
    
    for line in content.split('\n'):
        if line.startswith('## Phase'):
            current_phase = line.strip()
            phases.append({
                'name': current_phase,
                'total_tasks': 0,
                'completed_tasks': 0,
                'tasks': []
            })
        elif line.startswith('- ['):
            if current_phase and phases:
                task = line.strip()
                phases[-1]['tasks'].append(task)
                phases[-1]['total_tasks'] += 1
                if '- [x]' in task.lower():
                    phases[-1]['completed_tasks'] += 1
    
    # Determine current active phase
    for i, phase in enumerate(phases):
        completion_rate = phase['completed_tasks'] / phase['total_tasks'] if phase['total_tasks'] > 0 else 0
        if completion_rate < 1.0:  # Phase not fully complete
            return phase['name'], phases
    
    # All phases complete
    return "All Phases Complete", phases

def generate_progress_report():
    """Generate a progress report for Claude's context"""
    current_phase, phases = get_current_phase()
    
    report = f"""
=== ROADMAP PROGRESS REPORT ===
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎯 CURRENT PHASE: {current_phase}

📊 PHASE PROGRESS:
"""
    
    if isinstance(phases, list):
        for phase in phases:
            completion = phase['completed_tasks'] / phase['total_tasks'] if phase['total_tasks'] > 0 else 0
            status = "✅ COMPLETE" if completion == 1.0 else f"🔄 {completion:.1%} ({phase['completed_tasks']}/{phase['total_tasks']})"
            report += f"  {phase['name']}: {status}\n"
    
    report += f"""
📋 NEXT STEPS:
Based on current progress, focus on {current_phase} tasks.
Refer to ROADMAP.md for detailed task breakdown.

=== END ROADMAP REPORT ===
"""
    
    return report

def update_task_status(phase_num, task_description, completed=True):
    """Update a specific task's completion status"""
    roadmap_file = "ROADMAP.md"
    if not os.path.exists(roadmap_file):
        print("ROADMAP.md not found")
        return False
    
    with open(roadmap_file, 'r') as f:
        content = f.read()
    
    # Find and update the task
    checkbox = "[x]" if completed else "[ ]"
    pattern = rf"(- \[[ x]\] {re.escape(task_description)})"
    replacement = f"- {checkbox} {task_description}"
    
    updated_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    if updated_content != content:
        with open(roadmap_file, 'w') as f:
            f.write(updated_content)
        print(f"✅ Updated task: {task_description}")
        return True
    else:
        print(f"❌ Task not found: {task_description}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # Default: show progress report
        print(generate_progress_report())
    elif sys.argv[1] == "complete" and len(sys.argv) >= 3:
        # Mark task as complete
        task = " ".join(sys.argv[2:])
        update_task_status(None, task, completed=True)
    elif sys.argv[1] == "incomplete" and len(sys.argv) >= 3:
        # Mark task as incomplete  
        task = " ".join(sys.argv[2:])
        update_task_status(None, task, completed=False)
    else:
        print("Usage:")
        print("  roadmap_tracker.py                    # Show progress report")
        print("  roadmap_tracker.py complete 'task'    # Mark task complete")
        print("  roadmap_tracker.py incomplete 'task'  # Mark task incomplete")