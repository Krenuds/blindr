#!/bin/bash

# Generate git logs
makeGitLogs 10

# Generate roadmap progress report
echo "=== PROJECT CONTEXT FOR CLAUDE ==="
echo ""

# Show roadmap progress
.claude/roadmap_tracker.py

echo ""
echo "=== LATEST 3 COMMITS FOR CONTEXT ==="
echo ""

# Extract first 3 commit sections from git_logs.md
if [ -f "git_logs.md" ]; then
    # Use awk to extract first 3 commit sections (between ### and ---) 
    awk '
    /^### [0-9]+\./ { 
        if (count < 3) {
            print_section = 1
            count++
        } else {
            print_section = 0
        }
    }
    /^---$/ && print_section {
        print
        print_section = 0
        next
    }
    print_section { print }
    ' git_logs.md
else
    echo "No git_logs.md file found"
fi

echo ""
echo "=== END PROJECT CONTEXT ==="