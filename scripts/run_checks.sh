#!/usr/bin/env bash
# Full quality gate: environment check + regression tests.
set -euo pipefail

cd "$(dirname "$0")/.."

.venv/bin/python scripts/check_environment.py || true
echo
.venv/bin/python -m unittest discover -s tests -v
