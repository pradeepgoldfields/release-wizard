---
name: review
description: Run a full code review of staged or recent changes using the code-reviewer agent. Reports blocking and non-blocking issues before committing.
argument-hint: "[staged|last-commit|branch <name>]"
---

# Code Review — Conduit

Reviewing: **$ARGUMENTS** (defaults to `staged` if empty)

## Step 1 — Get the diff

```bash
# staged changes
git diff --staged

# last commit
git diff HEAD~1

# specific branch vs main
git diff main...$ARGUMENTS
```

## Step 2 — Identify changed files

```bash
git diff --staged --name-only
# or
git diff HEAD~1 --name-only
```

## Step 3 — Delegate to the code-reviewer agent

Pass the diff and the full content of each changed file to the `code-reviewer` agent for analysis against the checklist in `.claude/agents/code-reviewer/AGENT.md`.

The reviewer checks:
- ✅ Correctness and edge cases
- ✅ Security (injection, XSS, auth bypass, hardcoded secrets)
- ✅ Style (ruff-compliant, correct imports, no Windows paths)
- ✅ Architecture (business logic in services, models registered, permissions updated)
- ✅ Tests (every new endpoint/function has coverage)

## Step 4 — Output

```
## Review Result: ✅ Approved / ⚠ Approved with comments / ❌ Changes required

### Blocking Issues
...

### Non-Blocking Comments
...

### Summary
```

If there are **blocking issues**, do not proceed to commit. Fix them first and re-run `/review`.
