---
name: commit-impl
description: Create a context-preserving git commit at the end of the implement phase. Use this after finishing a feature so the git log can serve as a context recovery source for future Claude sessions and subagents.
---

You are creating a git commit at the end of the **implement** phase.

This commit is the primary source of context for future Claude sessions and subagents. Write it as if you are briefing a future Claude that has no memory of this conversation.

## Commit message format

```
<type>(<scope>): <what was done — one line, ≤ 72 chars>

Why: <one phrase or sentence>
What: <2-3 tight bullets — one key fact each>
Next: <what comes after>

Files: <key files, comma-separated>
```

### Types
- `feat` — new feature or significant addition
- `fix` — bug fix
- `refactor` — restructuring without behavior change
- `test` — test additions / updates
- `chore` — config, scripts, tooling

### Scope
Use the primary module or feature area: `entity-view`, `tech-tree`, `game-state`, `simulation`, `overlay`, `hooks`, etc.

## Example

```
feat(overlay): add QueueView overlay and tooltip system

Why: Player needs a global view of all task queues without clicking each entity.
What:
  - QueueView: filterable overlay for bot/factory/shipyard queues
  - Tooltip: 420ms hover delay; hover-ID change resets timer
  - ESC priority: queue_view > energy_view > tech_view > entity_view
Next: orbital structure icon on map.

Files: src/gui/queue_view.py, src/gui/tooltip.py, src/gui/app.py, src/gui/taskbar.py
```

## Steps

1. Run `git diff HEAD` (or `git diff --cached`) to see all changes
2. Run `git status` to see which files are modified/untracked
3. Draft the commit message following the format above
4. Stage only relevant src/ files (not build/, dist/, __pycache__)
5. Commit with the message
6. The Stop hook will push automatically — do NOT push manually

## Critical rule

**Always create this commit before the session ends.** The Stop hook's auto-commit is a safety net with minimal context. If you commit first, the Stop hook stages nothing and skips. If you forget, the auto-commit fires — but it now includes a file stat body, which is better than nothing.

## For agent handoffs

When this commit is done and you are about to spawn a subagent, include in the agent prompt:

```
## Context handoff
Recent commit: <hash or subject from git log -1>
Just implemented: <what was just committed>
Your task: <what the agent should do>
Return: <what you need back — format and content>
```
