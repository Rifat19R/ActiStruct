#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec bash generated_models/run_all_generated_models.sh "$@"
