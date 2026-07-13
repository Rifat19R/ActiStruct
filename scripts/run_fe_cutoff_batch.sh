#!/usr/bin/env bash
# Fe(CO)5 cutoff convergence batch — restart-aware, power-outage resilient.
#
# Behaviour for each ecutwfc in (60, 75, 90, 105):
#   1. Already converged ("bfgs converged" in output)  → SKIP
#   2. Checkpoint exists (save dir non-empty)          → restart_mode='restart'
#   3. Otherwise                                       → restart_mode='from_scratch'
#
# disk_io='medium' is now set in all input files so QE writes a checkpoint
# after every completed ionic (BFGS) step, not only at the end.
#
# Usage (from inside WSL):
#   bash /mnt/d/Research/Dr.Kulik_MIT/scripts/run_fe_cutoff_batch.sh 2>&1 | tee /tmp/fe_cutoff_batch.log
#
# Monitor live (second WSL terminal):
#   tail -f /tmp/fe_cutoff_batch.log
#   tail -f /mnt/d/Research/Dr.Kulik_MIT/qe/outputs/cutoff_test/fe_co5_cutoff_60.out

set -euo pipefail

PW=/home/duets/q-e-qe-7.4.1/bin/pw.x
PROJECT=/mnt/d/Research/Dr.Kulik_MIT
INPUT_DIR="${PROJECT}/qe/inputs/relax"
OUTPUT_DIR="${PROJECT}/qe/outputs/cutoff_test"
WORKDIR_BASE=/home/duets/qe_workdirs

mkdir -p "${OUTPUT_DIR}"

CUTOFFS=(60 75 90 105)

for EC in "${CUTOFFS[@]}"; do
    PREFIX="fe_co5_cutoff_${EC}"
    INPUT_BASE="${INPUT_DIR}/${PREFIX}.in"
    OUTPUT="${OUTPUT_DIR}/${PREFIX}.out"
    ERRFILE="${OUTPUT_DIR}/${PREFIX}.err"
    SAVEDIR="${WORKDIR_BASE}/${PREFIX}/${PREFIX}.save"
    TMP_INPUT="/tmp/${PREFIX}_run.in"

    # ── Step 1: already converged? ──────────────────────────────────────────
    if [ -f "${OUTPUT}" ] && grep -q -E "bfgs converged|JOB DONE" "${OUTPUT}"; then
        echo "[SKIP]  ecutwfc=${EC} — already converged in ${OUTPUT}"
        continue
    fi

    # ── Step 2: choose restart_mode ─────────────────────────────────────────
    # A non-empty .save directory means QE wrote at least one BFGS checkpoint.
    if [ -d "${SAVEDIR}" ] && [ -n "$(ls -A "${SAVEDIR}" 2>/dev/null)" ]; then
        RMODE="restart"
        echo "[INFO]  ecutwfc=${EC} — checkpoint found, using restart_mode='restart'"
    else
        RMODE="from_scratch"
        echo "[INFO]  ecutwfc=${EC} — no checkpoint, using restart_mode='from_scratch'"
        # Remove any stale incomplete output so the grep above doesn't trigger
        rm -f "${OUTPUT}" "${ERRFILE}"
    fi

    # Patch restart_mode in a temp copy of the input
    sed "s/restart_mode = 'from_scratch'/restart_mode = '${RMODE}'/" \
        "${INPUT_BASE}" > "${TMP_INPUT}"

    echo ""
    echo "======================================================="
    echo " Running ecutwfc=${EC} Ry  (ecutrho=$(( EC * 8 )) Ry)"
    echo " restart_mode = ${RMODE}"
    echo " Input:  ${INPUT_BASE}  →  temp: ${TMP_INPUT}"
    echo " Output: ${OUTPUT}"
    echo "======================================================="
    START_EPOCH=$(date +%s)

    mpirun --oversubscribe -np 4 "${PW}" -in "${TMP_INPUT}" \
        > "${OUTPUT}" 2> "${ERRFILE}"
    EXIT_CODE=$?

    END_EPOCH=$(date +%s)
    WALLTIME=$(( END_EPOCH - START_EPOCH ))

    rm -f "${TMP_INPUT}"

    if [ ${EXIT_CODE} -ne 0 ]; then
        echo "[ERROR] pw.x exited with code ${EXIT_CODE} for ecutwfc=${EC}"
        echo "        Check: ${ERRFILE}"
        echo "        Walltime: ${WALLTIME}s"
        exit 1
    fi

    if grep -q "bfgs converged" "${OUTPUT}"; then
        echo "[OK]    ecutwfc=${EC} — bfgs converged  (walltime=${WALLTIME}s)"
        # Warn if slow, but do NOT stop — the run succeeded and we need all 4 for analysis.
        if [ ${WALLTIME} -gt 14400 ]; then
            echo "[WARN]  ecutwfc=${EC} took ${WALLTIME}s (>4h) but DID converge — continuing."
        fi
    elif grep -q "JOB DONE" "${OUTPUT}"; then
        echo "[WARN]  ecutwfc=${EC} — JOB DONE but no 'bfgs converged' — check manually"
        # Still continue; analysis script will handle this case.
    else
        echo "[FAIL]  ecutwfc=${EC} — no convergence marker and no JOB DONE found"
        echo "        Walltime: ${WALLTIME}s — STOPPING as instructed (did not converge)"
        exit 1
    fi
done

echo ""
echo "======================================================="
echo " All cutoff runs finished successfully."
echo "======================================================="
