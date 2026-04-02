---
name: new-feature
description: Full agentic workflow to implement a new feature in Conduit — from requirements to committed code. Orchestrates business-analyst → developer → tester → code-reviewer → git-committer agents in sequence.
argument-hint: "<feature description>"
---

# New Feature Workflow — Conduit

Feature request: **$ARGUMENTS**

This skill runs the full agentic development loop. Each phase must complete before the next begins.

---

## Phase 1 — Requirements (business-analyst agent)

Delegate to the `business-analyst` agent:

> Analyse this feature request for Conduit and produce:
> - User stories
> - Acceptance criteria
> - API contract (endpoints, request/response shapes, status codes)
> - Data model changes required
> - Edge cases and error scenarios
> - What is explicitly out of scope
>
> Feature: $ARGUMENTS

**Gate**: Do not proceed until acceptance criteria are defined and confirmed.

---

## Phase 2 — Implementation plan (orchestrator agent)

Delegate to the `orchestrator` agent:

> Break down this feature into ordered implementation tasks for developer, tester, and documentation:
> [paste acceptance criteria from Phase 1]

**Gate**: Review the plan. Adjust scope if needed before coding begins.

---

## Phase 3 — Implementation (developer agent)

Delegate to the `developer` agent with the full plan from Phase 2.

The developer must:
1. Implement the model/route/service changes
2. Update `scripts/seed_data.py` if new resource type
3. Update `app/services/authz_service.py` PERMISSION_CATALOG if new resource
4. Update `docs/technical-documentation.md`
5. Run `ruff check . && pytest tests/unit/ -q` before reporting done

**Gate**: Developer confirms ruff and tests pass.

---

## Phase 4 — Tests (tester agent)

Delegate to the `tester` agent:

> Write unit tests for the following changes:
> [paste list of changed functions/endpoints from Phase 3]
>
> Cover: happy path, validation errors, auth failures, edge cases.

Run: `pytest tests/unit/ -v`

**Gate**: All tests pass.

---

## Phase 5 — Security review (optional, run `/scan` if touching auth/routes)

```
/scan sast
```

Fix any CRITICAL or HIGH findings before proceeding.

---

## Phase 6 — Code review (code-reviewer agent)

```
/review staged
```

**Gate**: No blocking issues. Non-blocking comments noted for follow-up.

---

## Phase 7 — Commit (git-committer agent)

```
/commit feat(<scope>): $ARGUMENTS
```

The git-committer will:
1. Re-run quality gate (lint + tests)
2. Stage only relevant files
3. Commit with conventional message
4. Push to origin

---

## Completion

Report:
- ✅ Feature implemented: <summary>
- Files changed: <list>
- Tests added: <count>
- Commit: <SHA>
