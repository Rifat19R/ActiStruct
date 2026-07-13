#!/usr/bin/env bash
# Task 2: Ferrocene PBE-D3 relax — restart-aware, power-outage resilient.
#
# Usage (from inside WSL):
#   bash /mnt/d/Research/Dr.Kulik_MIT/scripts/run_ferrocene_pbed3.sh 2>&1 | tee /tmp/ferrocene_pbed3.log
#
# Monitor live (second WSL terminal):
#   tail -f /tmp/ferrocene_pbed3.log
#   tail -f /mnt/d/Research/Dr.Kulik_MIT/qe/outputs/relax/ferrocene_pbed3.out

set -euo pipefail

PW=/home/duets/q-e-qe-7.4.1/bin/pw.x
PROJECT=/mnt/d/Research/Dr.Kulik_MIT
INPUT="${PROJECT}/qe/inputs/relax/ferrocene_pbed3.in"
OUTPUT_DIR="${PROJECT}/qe/outputs/relax"
OUTPUT="${OUTPUT_DIR}/ferrocene_pbed3.out"
ERRFILE="${OUTPUT_DIR}/ferrocene_pbed3.err"
SAVEDIR="/home/duets/qe_workdirs/ferrocene_pbed3/ferrocene_pbed3.save"
TMP_INPUT="/tmp/ferrocene_pbed3_run.in"

mkdir -p "${OUTPUT_DIR}"

echo "======================================================="
echo " Task 2: Ferrocene PBE-D3 relax"
echo " ecutwfc=90 Ry, vdw_corr=grimme-d3, disk_io=medium"
echo " Input:  ${INPUT}"
echo " Output: ${OUTPUT}"
echo "======================================================="

# Step 1: already converged?
if [ -f "${OUTPUT}" ] && grep -q -E "bfgs converged|JOB DONE" "${OUTPUT}"; then
    echo "[SKIP] Already converged — nothing to do."
    exit 0
fi

# Step 2: choose restart_mode
if [ -d "${SAVEDIR}" ] && [ -n "$(ls -A "${SAVEDIR}" 2>/dev/null)" ]; then
    RMODE="restart"
    echo "[INFO] Checkpoint found — restart_mode='restart'"
else
    RMODE="from_scratch"
    echo "[INFO] No checkpoint — restart_mode='from_scratch'"
    rm -f "${OUTPUT}" "${ERRFILE}"
fi

# Patch restart_mode into temp input
sed "s/restart_mode = 'from_scratch'/restart_mode = '${RMODE}'/" \
    "${INPUT}" > "${TMP_INPUT}"

START_EPOCH=$(date +%s)
echo "[START] $(date)"

mpirun --oversubscribe -np 4 "${PW}" -in "${TMP_INPUT}" \
    > "${OUTPUT}" 2> "${ERRFILE}"
EXIT_CODE=$?

END_EPOCH=$(date +%s)
WALLTIME=$(( END_EPOCH - START_EPOCH ))
rm -f "${TMP_INPUT}"

if [ ${EXIT_CODE} -ne 0 ]; then
    echo "[ERROR] pw.x exited with code ${EXIT_CODE} — check ${ERRFILE}"
    exit 1
fi

if grep -q "bfgs converged" "${OUTPUT}"; then
    echo "[OK] bfgs converged  (walltime=${WALLTIME}s / $(( WALLTIME/3600 ))h$(( (WALLTIME%3600)/60 ))m)"
elif grep -q "JOB DONE" "${OUTPUT}"; then
    echo "[WARN] JOB DONE but no 'bfgs converged' — check output manually"
else
    echo "[FAIL] No convergence marker found  (walltime=${WALLTIME}s) — STOPPING"
    exit 1
fi

echo "======================================================="
echo " Run complete. Now run the analysis:"
echo "   source .venv/bin/activate"
echo "   python scripts/16_ferrocene_pbed3_analysis.py"
echo "======================================================="
