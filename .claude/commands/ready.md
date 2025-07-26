---
description: "Run tests and commit as READY if they pass"
---

# Ready Command

This command runs tests and creates a production-ready commit.

## Usage
```
/ready [optional commit message]
```

## What it does:
1. Runs project tests (if available)
2. Checks service health
3. If tests pass: commits with "- READY ✅" 
4. If tests fail: reports issues without committing

## Arguments
- `$ARGUMENTS` - Optional custom commit message

## Example
```
/ready "fix audio processing pipeline"
```

This will create: `fix audio processing pipeline - READY ✅`