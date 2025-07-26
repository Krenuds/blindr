#!/usr/bin/env python3

import os
import re
import argparse
from pathlib import Path

def remove_python_comments(content):
    """Remove comments from Python code while preserving strings and docstrings."""
    lines = content.split('\n')
    result_lines = []
    in_triple_quote = False
    triple_quote_type = None
    
    for line in lines:
        if not in_triple_quote:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                quote_type = stripped[:3]
                if stripped.count(quote_type) >= 2:
                    result_lines.append(line)
                    continue
                else:
                    in_triple_quote = True
                    triple_quote_type = quote_type
                    result_lines.append(line)
                    continue
            
            comment_pos = find_comment_position(line)
            if comment_pos != -1:
                line = line[:comment_pos].rstrip()
            
            if line.strip():
                result_lines.append(line)
        else:
            result_lines.append(line)
            if triple_quote_type in line:
                in_triple_quote = False
                triple_quote_type = None
    
    return '\n'.join(result_lines)

def find_comment_position(line):
    """Find the position of # that starts a comment (not in strings)."""
    in_string = False
    string_char = None
    escape_next = False
    
    for i, char in enumerate(line):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if not in_string:
            if char in ['"', "'"]:
                in_string = True
                string_char = char
            elif char == '#':
                return i
        else:
            if char == string_char:
                in_string = False
                string_char = None
    
    return -1

def remove_js_comments(content):
    """Remove comments from JavaScript/TypeScript code."""
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    lines = content.split('\n')
    return '\n'.join(line for line in lines if line.strip())

def remove_css_comments(content):
    """Remove comments from CSS code."""
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    lines = content.split('\n')
    return '\n'.join(line for line in lines if line.strip())

def remove_html_comments(content):
    """Remove comments from HTML code."""
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    lines = content.split('\n')
    return '\n'.join(line for line in lines if line.strip())

def remove_shell_comments(content):
    """Remove comments from shell scripts."""
    lines = content.split('\n')
    result_lines = []
    
    for line in lines:
        if line.strip().startswith('#!'):
            result_lines.append(line)
            continue
            
        comment_pos = find_shell_comment_position(line)
        if comment_pos != -1:
            line = line[:comment_pos].rstrip()
        
        if line.strip():
            result_lines.append(line)
    
    return '\n'.join(result_lines)

def find_shell_comment_position(line):
    """Find the position of # that starts a comment in shell (not in strings)."""
    in_single_quote = False
    in_double_quote = False
    escape_next = False
    
    for i, char in enumerate(line):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if not in_single_quote and not in_double_quote:
            if char == "'":
                in_single_quote = True
            elif char == '"':
                in_double_quote = True
            elif char == '#':
                return i
        elif in_single_quote and char == "'":
            in_single_quote = False
        elif in_double_quote and char == '"':
            in_double_quote = False
    
    return -1

def get_comment_remover(file_path):
    """Get the appropriate comment removal function based on file extension."""
    ext = Path(file_path).suffix.lower()
    
    if ext == '.py':
        return remove_python_comments
    elif ext in ['.js', '.ts', '.jsx', '.tsx']:
        return remove_js_comments
    elif ext == '.css':
        return remove_css_comments
    elif ext in ['.html', '.htm']:
        return remove_html_comments
    elif ext in ['.sh', '.bash']:
        return remove_shell_comments
    else:
        return None

def process_file(file_path, dry_run=False):
    """Process a single file to remove comments."""
    remover = get_comment_remover(file_path)
    if not remover:
        print(f"Skipping {file_path}: unsupported file type")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        new_content = remover(original_content)
        
        if dry_run:
            print(f"Would process: {file_path}")
            lines_removed = len(original_content.split('\n')) - len(new_content.split('\n'))
            print(f"  Lines that would be removed: {lines_removed}")
            return True
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        lines_removed = len(original_content.split('\n')) - len(new_content.split('\n'))
        print(f"Processed: {file_path} (removed {lines_removed} lines)")
        return True
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Remove comments from source code files')
    parser.add_argument('directory', nargs='?', default='src', 
                       help='Directory to process (default: src)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--extensions', nargs='+', 
                       default=['.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html', '.htm', '.sh', '.bash'],
                       help='File extensions to process')
    
    args = parser.parse_args()
    
    src_path = Path(args.directory)
    if not src_path.exists():
        print(f"Error: Directory '{args.directory}' does not exist")
        return 1
    
    processed = 0
    errors = 0
    
    print(f"{'DRY RUN: ' if args.dry_run else ''}Removing comments from files in {src_path}")
    print(f"Processing extensions: {args.extensions}")
    
    for ext in args.extensions:
        pattern = f"**/*{ext}"
        files = list(src_path.glob(pattern))
        
        for file_path in files:
            if process_file(file_path, args.dry_run):
                processed += 1
            else:
                errors += 1
    
    print(f"\nSummary:")
    print(f"  Files processed: {processed}")
    print(f"  Errors: {errors}")
    
    return 0 if errors == 0 else 1

if __name__ == '__main__':
    exit(main())