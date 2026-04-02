---
name: commit
description: Stage, lint, test, commit, and push Conduit changes with a conventional commit message. Runs the full quality gate before committing.
argument-hint: "<type>(<scope>): <summary>  — e.g. feat(agents): add skills field"
---

# Commit & Push — Conduit

Commit message to use: **$ARGUMENTS**

If no message is provided, ask for one before proceeding.

## Steps

### 1. Check what's changed
```bash
git status
git diff --stat
```

### 2. Quality gate — must pass before staging
```bash
source venv/Scripts/activate
ruff check . && ruff format --check .
pytest tests/unit/ -q
```

Stop immediately if lint or tests fail. Report what failed.

### 3. Safety check — never commit these
```bash
# Verify no secrets are staged
git diff | grep -iE "(password|secret|token|api.?key)\s*=" && echo "⚠ Possible secret found" || echo "✓ No secrets found"
```

Files that must never be committed:
- `instance/*.db`
- `*.log`
- `.env`
- `venv/`
- `terraform.tfvars`

### 4. Stage specific files
Stage only the files relevant to the change — not `git add -A`:
```bash
# Review which files to stage based on git status output
git add <specific files>
git diff --staged --stat
```

### 5. Commit
```bash
git commit -m "$ARGUMENTS"
```

### 6. Push
```bash
git push origin main
```

### 7. Confirm
```bash
git log --oneline -3
```
Report the new commit SHA and summary.
