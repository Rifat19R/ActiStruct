#!/usr/bin/env bash
# Sequential WSL batch runner for the 12 audited+selected perturbation
# candidates (qe/run_manifest_candidates_v0.csv). Always sequential, never
# parallel: cr_co6 candidates alone need ~14GB/process against this
# machine's 16GB WSL ceiling (see docs/PHASE1_SUMMARY.md) - running two at
# once would risk the same OOM this project already hit once.
#
# Idempotent: skips any candidate whose existing output already shows
# "bfgs converged" or "JOB DONE" - this project has already hit partial-
# failure reruns twice (cr_co6's first BFGS failure, ferrocene's 9p-mount
# crash), so resuming a partially-completed batch is a real, not
# speculative, need.
#
# Usage (run inside WSL, from the project root):
#   bash scripts/06b_run_qe_candidates_batch.sh
set -euo pipefail

PROJECT_ROOT="/mnt/d/Research/Dr.Kulik_MIT"
PWX="/home/duets/q-e-qe-7.4.1/bin/pw.x"
WORKDIR_ROOT="/home/duets/qe_workdirs"
NPROC=4
MANIFEST="$PROJECT_ROOT/qe/run_manifest_candidates_v0.csv"
RUNS_DIR="$PROJECT_ROOT/runs/perturbation_relax"

cd "$PROJECT_ROOT"

if [ ! -f "$MANIFEST" ]; then
  echo "Manifest not found: $MANIFEST" >&2
  echo "Run: python scripts/06_build_qe_inputs.py --source candidates" >&2
  exit 1
fi

candidate_ids=$(tail -n +2 "$MANIFEST" | cut -d',' -f1)
total=$(echo "$candidate_ids" | wc -l)
n=0

for candidate_id in $candidate_ids; do
  n=$((n + 1))
  out_file="$RUNS_DIR/$candidate_id/$candidate_id.relax.out"

  if [ -f "$out_file" ] && grep -qE "bfgs converged|JOB DONE" "$out_file"; then
    echo "=== [$n/$total] skipping $candidate_id (already has bfgs converged / JOB DONE) ==="
    continue
  fi

  echo "=== [$n/$total] starting $candidate_id ==="
  mkdir -p "$WORKDIR_ROOT/$candidate_id" "$RUNS_DIR/$candidate_id"
  start_time=$(date +%s)

  set +e
  mpirun --oversubscribe -np "$NPROC" "$PWX" -in "qe/inputs/relax/$candidate_id.in" \
    > "$out_file" \
    2> "$RUNS_DIR/$candidate_id/$candidate_id.relax.err"
  exit_code=$?
  set -e

  elapsed=$(($(date +%s) - start_time))
  echo "=== [$n/$total] finished $candidate_id (exit $exit_code, ${elapsed}s) ==="
done

echo "ALL DONE - check each runs/perturbation_relax/<candidate_id>/*.relax.out for 'bfgs converged' before trusting any result (exit 0 does not mean converged)."
