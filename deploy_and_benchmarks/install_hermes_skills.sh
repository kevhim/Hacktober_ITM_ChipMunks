#!/usr/bin/env bash
# Compatibility wrapper for the portable installer. Existing skills are preserved.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON_BIN:-python3}" "${SCRIPT_DIR}/install_skills.py" "$@"
