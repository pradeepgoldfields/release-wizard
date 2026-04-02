---
name: test
description: Run the Conduit test suite — lint, unit tests, integration tests, E2E stubs, and coverage. Use after any code change.
argument-hint: "[unit|integration|e2e|all|coverage] [test-file-or-pattern]"
---

# Run Tests — Conduit

## Steps

### 1. Free port 8080 (in case server is running)
```bash
powershell -Command "Get-NetTCPConnection -LocalPort 8080 -EA SilentlyContinue | %{ Stop-Process -Id \$_.OwningProcess -Force -EA SilentlyContinue }"
```

### 2. Activate virtualenv and lint
```bash
source venv/Scripts/activate
ruff check .
ruff format --check .
```

If lint fails, stop and report the errors. Do not proceed to tests.

### 3. Run tests

$ARGUMENTS controls what runs:

| Argument | Command |
|---|---|
| (empty) or `unit` | `pytest tests/unit/ -v` |
| `integration` | `pytest tests/integration/ -v` |
| `e2e` | `pytest tests/e2e/ -v` |
| `e2e lifecycle` | `pytest tests/e2e/test_e2e_release_lifecycle.py -v` |
| `e2e rbac` | `pytest tests/e2e/test_e2e_rbac.py -v` |
| `e2e execution` | `pytest tests/e2e/test_e2e_pipeline_execution.py -v` |
| `e2e compliance` | `pytest tests/e2e/test_e2e_compliance_and_audit.py -v` |
| `e2e vault` | `pytest tests/e2e/test_e2e_vault_and_agents.py -v` |
| `e2e environments` | `pytest tests/e2e/test_e2e_environments_and_applications.py -v` |
| `all` | `pytest -v` (unit + integration + e2e) |
| `coverage` | `pytest tests/unit/ --cov=app --cov-report=term-missing` |
| anything else | treat as pytest `-k` pattern: `pytest tests/unit/ -v -k "$ARGUMENTS"` |

E2E tests use `pytest.skip()` stubs. When running `e2e` or `all`:
- **skipped** tests (`s`) are expected — they are unimplemented stubs waiting for code.
- **failed** tests (`F`) indicate a stub that was implemented but is broken.
- Report the skip count, pass count, and fail count separately.
- If any E2E test *fails* (not skipped), show the failure and identify the stub that needs fixing.

### 4. Report
- If all pass (or all E2E are skipped): "✅ Tests passed. (N skipped stubs)"
- If any fail: show the failure output and identify which file/function needs fixing.
- If coverage < 70% on a changed file: flag it.
