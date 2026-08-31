#!/usr/bin/env bash
# Linux/dev smoke of the same entrypoint used by the Windows EXE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export CRYPTO_HOME="${CRYPTO_HOME:-$(mktemp -d /tmp/crypto-smoke.XXXXXX)}"
python -m crypto --smoke
python -m crypto --paths
python -m crypto --version
echo "dev smoke OK root=$CRYPTO_HOME"
