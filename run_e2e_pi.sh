#!/bin/sh
# Linux/Pi bootstrap only. All E2E policy lives in the shared Python entrypoint.
set -eu
REPO_ROOT=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_RUNTIME="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_RUNTIME=$(command -v python3)
else
    printf '%s\n' 'Python runtime not found. See RASPBERRY_PI_E2E.md setup.' >&2
    exit 2
fi
cd "$REPO_ROOT"
exec "$PYTHON_RUNTIME" "$REPO_ROOT/scripts/e2e/run_dataset_case.py" "$@"
