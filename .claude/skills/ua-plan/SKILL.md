---
name: ua-plan
description: Plan a Universal Assemblers feature. Spawns parallel research + design agents, presents findings for review, writes docs/PLAN.md, then auto-launches a background implementation agent on approval. Use this instead of /plan for UA feature work.
---

You are running the Universal Assemblers feature planning workflow. This is a structured multi-phase process. Follow every step in order.

## Phase 1 — Parallel research (do this immediately, before writing anything)

Spawn **both** agents at the same time in a single message, both `run_in_background: true`:

**Agent 1 — `planner-research`** (`subagent_type: "planner-research"`)
Prompt: Explore the UA codebase (`C:/Users/Admin/code/UniversalAssemblers/`) for the feature described below. Return: relevant files + line numbers, existing patterns to reuse, architecture constraints, risk areas, and what doesn't exist yet that must be created.
Feature: `$ARGUMENTS`

**Agent 2 — `planner-design`** (`subagent_type: "planner-design"`)
Prompt: Design the implementation approach for the UA feature described below. Return: ordered implementation steps with file paths, integration points (especially GUI overlay/event routing chain), verification steps, and gotchas.
Feature: `$ARGUMENTS`

Wait for both agents to return before proceeding.

## Phase 2 — Present findings and get user sign-off

Synthesize both agents' findings into a clear summary:
- What exists already (reusable code, patterns)
- What needs to be created or modified (with file paths)
- Key risks or gotchas
- Proposed implementation order

**Present this to the user and wait for their feedback.** Do NOT write `docs/PLAN.md` yet. The user may adjust scope, priority, or approach.

## Phase 3 — Write the plan

Once the user gives the go-ahead (or adjustments), write the final plan to:
`C:/Users/Admin/code/UniversalAssemblers/docs/PLAN.md`

Plan format:
```markdown
# Plan: <feature name>

## Goal
<one paragraph>

## Affected files
<bullet list of file paths with brief role>

## Implementation steps
<numbered, ordered steps — each step names the file and what changes>

## Verification steps
<how to confirm it works — run commands, visual checks, smoke tests>

## Context handoff
Recent commit: <run git log -1 --oneline>
Diagnosed: <key findings from research agent>
Task: <what the implementation agent must do>
Return: Summarize what was implemented and any deviations from the plan.
```

The plan must be sized for a fresh Claude session to implement without additional context.

## Phase 4 — Launch implementation agent

After writing `docs/PLAN.md`, immediately spawn a background `general-purpose` agent (`run_in_background: true`) with this prompt:

```
Read UniversalAssemblers/docs/PLAN.md and implement the plan fully.

## Context handoff
<paste the Context Handoff section from PLAN.md>

Rules:
- Work in C:/Users/Admin/code/UniversalAssemblers/
- Use Python at /c/Users/Admin/anaconda3/python.exe
- After implementing, run: python -c "from src.gui.app import App; print('OK')"
- When done, run /commit-impl to create a context-preserving commit
- On success, delete docs/PLAN.md (it is ephemeral scaffolding)
```

Notify the user that implementation is running in the background and they can continue working.

**If the implementation agent reports that Bash was blocked mid-task:**
The agent cannot commit or run verification. The user should:
1. Review what the agent completed (`git status` + inspect edited files).
2. Fix any gaps manually.
3. Run `/commit-impl` themselves to create the context-preserving commit.
This fallback is expected — it is not a failure of the skill.
