#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python}"
LOG_DIR="${ACTISTRUCT_LOG_DIR:-run_logs}"
mkdir -p "$LOG_DIR"

SOLIDS=(
  generated_models/bulk_al_qe_active_inverse.py
  generated_models/bulk_cu_generated_qe_active_inverse.py
  generated_models/bulk_ni_qe_active_inverse.py
  generated_models/bulk_ag_qe_active_inverse.py
  generated_models/bulk_au_qe_active_inverse.py
  generated_models/bulk_fe_bcc_qe_active_inverse.py
  generated_models/bulk_mo_bcc_qe_active_inverse.py
  generated_models/bulk_w_bcc_qe_active_inverse.py
  generated_models/bulk_si_generated_qe_active_inverse.py
  generated_models/bulk_ge_qe_active_inverse.py
  generated_models/bulk_gaas_qe_active_inverse.py
  generated_models/bulk_alas_qe_active_inverse.py
  generated_models/bulk_inp_qe_active_inverse.py
  generated_models/bulk_sic_qe_active_inverse.py
  generated_models/bulk_mgo_generated_qe_active_inverse.py
  generated_models/bulk_cao_qe_active_inverse.py
  generated_models/bulk_zno_qe_active_inverse.py
  generated_models/bulk_tio2_rutile_qe_active_inverse.py
  generated_models/bulk_al2o3_qe_active_inverse.py
  generated_models/bulk_sio2_qe_active_inverse.py
)

TWO_D=(
  generated_models/graphene_generated_qe_active_inverse.py
  generated_models/hbn_qe_active_inverse.py
  generated_models/silicene_qe_active_inverse.py
  generated_models/mos2_qe_active_inverse.py
  generated_models/ws2_qe_active_inverse.py
  generated_models/aln_2d_qe_active_inverse.py
)

MOLECULES=(
  generated_models/h2_generated_qe_active_inverse.py
  generated_models/n2_qe_active_inverse.py
  generated_models/co_qe_active_inverse.py
  generated_models/h2o_generated_qe_active_inverse.py
  generated_models/nh3_qe_active_inverse.py
  generated_models/ch4_generated_qe_active_inverse.py
)

BATTERY=(
  generated_models/bulk_licoo2_generated_qe_active_inverse.py
  generated_models/bulk_nacoo2_qe_active_inverse.py
  generated_models/bulk_lifepo4_qe_active_inverse.py
  generated_models/bulk_limn2o4_qe_active_inverse.py
  generated_models/bulk_limnpo4_qe_active_inverse.py
  generated_models/bulk_litio2_qe_active_inverse.py
  generated_models/bulk_srtio3_qe_active_inverse.py
  generated_models/bulk_batio3_qe_active_inverse.py
  generated_models/bulk_cspbi3_qe_active_inverse.py
  generated_models/bulk_nial_qe_active_inverse.py
  generated_models/bulk_co2feal_qe_active_inverse.py
)

ADSORPTION=(
  generated_models/h_on_cu111_qe_active_inverse.py
  generated_models/o_on_cu111_qe_active_inverse.py
  generated_models/co_on_cu111_qe_active_inverse.py
  generated_models/h_on_ni111_qe_active_inverse.py
  generated_models/o_on_ni111_qe_active_inverse.py
  generated_models/co_on_ni111_qe_active_inverse.py
  generated_models/h_on_pt111_qe_active_inverse.py
  generated_models/co_on_pt111_qe_active_inverse.py
)

run_script() {
  local script="$1"
  if [[ ! -f "$script" ]]; then
    echo "Missing script: $script" >&2
    return 2
  fi
  local stem
  stem="$(basename "$script" .py)"
  local log="$LOG_DIR/${stem}.log"
  echo
  echo ">>> $PYTHON_BIN $script"
  "$PYTHON_BIN" "$script" 2>&1 | tee "$log"
}

run_many() {
  local script
  for script in "$@"; do
    run_script "$script"
  done
}

usage() {
  cat <<'USAGE'
Usage:
  bash run.sh [all|solids|two-d|molecules|battery|adsorption]
  bash run.sh one generated_models/<script>.py

Environment:
  PYTHON=/path/to/python       Python executable, default: python
  ACTISTRUCT_LOG_DIR=run_logs  Directory for per-script logs
USAGE
}

case "${1:-all}" in
  all)
    run_many "${SOLIDS[@]}" "${TWO_D[@]}" "${MOLECULES[@]}" "${BATTERY[@]}" "${ADSORPTION[@]}"
    ;;
  solids)
    run_many "${SOLIDS[@]}"
    ;;
  two-d|2d)
    run_many "${TWO_D[@]}"
    ;;
  molecules)
    run_many "${MOLECULES[@]}"
    ;;
  battery)
    run_many "${BATTERY[@]}"
    ;;
  adsorption)
    run_many "${ADSORPTION[@]}"
    ;;
  one)
    shift
    if [[ $# -ne 1 ]]; then
      usage >&2
      exit 2
    fi
    run_script "$1"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac