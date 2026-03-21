# New Machine Setup

The hook commands in `.claude/settings.json` require an absolute path to the project on the current machine. This path is **not** committed — it lives in `scripts/local.env.sh` (gitignored).

When starting on a new machine:
1. Create `scripts/local.env.sh` with the correct path for that machine:
   ```bash
   #!/usr/bin/env bash
   UA_PROJECT_DIR="/c/Users/<username>/path/to/UniversalAssemblers"
   # UA_PYTHON="/path/to/python.exe"  # uncomment if auto-detection fails
   ```
2. Update every hook command path in `.claude/settings.json` to match `UA_PROJECT_DIR`.
   There are four commands — all follow the pattern `bash <UA_PROJECT_DIR>/scripts/<script>.sh`.
3. Verify hooks are working by editing any `src/` file and checking that `[smoke]` and `[lint]` output appears.

`env.sh` sources `local.env.sh` automatically (if present) and applies `UA_PYTHON` if set. All other paths in the hook scripts are derived dynamically from the script's own location and require no manual changes.
