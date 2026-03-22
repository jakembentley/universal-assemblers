---
name: run-lint
description: Run ruff linting on Universal Assemblers source files and interpret the results. Use after editing src/ Python files.
---

# Running lint for Universal Assemblers

## Linter: `ruff`

Config file: `UniversalAssemblers/ruff.toml`

Rules enabled: `F` (pyflakes), `E` (pycodestyle errors), `W` (pycodestyle warnings)

Notable ignores (intentional — do NOT "fix" these):
- `E501` — line length. Layout math and constant tables are intentionally wide.
- `E402` — module-level imports not at top. `sys.path.insert` pattern in test scripts.
- `E741` — ambiguous variable names. `l`, `x`, `y` are fine in layout/math contexts.

## Running lint

### Single file (after editing):
```bash
cd ~/universal-assemblers/UniversalAssemblers && ~/anaconda3/python.exe -m ruff check <file_path> --config ruff.toml 2>&1
```

### All source files:
```bash
cd ~/universal-assemblers/UniversalAssemblers && ~/anaconda3/python.exe -m ruff check src/ --config ruff.toml 2>&1
```

### Install ruff if missing:
```bash
~/anaconda3/python.exe -m pip install ruff --quiet
```

## Interpreting results

Clean output:
```
All checks passed!
```

Issue output format:
```
src/gui/entity_view.py:142:5: F841 Local variable `x` is assigned to but never used
src/models/entity.py:88:1: E302 Expected 2 blank lines, got 1
```

Format: `file:line:col: CODE message`

## Priority

| Code | Severity | Action |
|------|----------|--------|
| `F8xx` | High — undefined name, unused import | Fix immediately |
| `F841` | Medium — unused variable | Fix or prefix with `_` |
| `E302/E303` | Low — blank line counts | Fix if convenient |
| `W` warnings | Low | Fix if convenient |

## Auto-fix (safe subset only)

```bash
~/anaconda3/python.exe -m ruff check src/ --config ruff.toml --fix 2>&1
```

Only use `--fix` for whitespace/import ordering issues. Never auto-fix logic-touching rules.

## Never suppress with noqa

Do not add `# noqa` comments to silence errors. Instead either fix the code or update `ruff.toml` if the rule is genuinely wrong for this codebase.
