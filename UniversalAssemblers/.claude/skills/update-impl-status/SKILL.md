---
name: update-impl-status
description: Scan the UniversalAssemblers codebase and update the "Implementation status" section in CLAUDE.md to reflect current reality. Run after completing a feature sprint to prevent context rot.
---

You are updating the **Implementation status** section of `UniversalAssemblers/CLAUDE.md`.

## Steps

1. Read `UniversalAssemblers/CLAUDE.md` and extract:
   - The current **Implemented** bullet list
   - The current **Not yet implemented** bullet list

2. For each item in **Not yet implemented**, search `src/` for concrete evidence of implementation. Use Grep and Read. Evidence thresholds:
   - A dedicated Python module with a matching class that has `draw()` and `handle_events()` → **implemented**
   - A method or feature referenced but no module found → **not yet implemented**
   - Partial scaffolding (stubs, TODOs, no real logic) → **not yet implemented**

3. Present a clear diff to the user:
   ```
   Moving to Implemented:
     ✓ [item] — found in src/gui/foo.py (FooClass)

   Staying as Not Yet Implemented:
     ✗ [item] — no evidence found
   ```

4. Ask the user: "Apply these changes to CLAUDE.md?" — wait for confirmation.

5. On confirmation: use Edit to update only the **Implementation status** section of `UniversalAssemblers/CLAUDE.md`. Do not touch any other section.

## Rules

- Be conservative: only mark something implemented if you find clear, complete evidence
- Do not add new "Not yet implemented" items unless the user explicitly asks
- Do not reformat or rewrite text outside the Implementation status section
- Keep bullet descriptions concise — match the style already in the file
