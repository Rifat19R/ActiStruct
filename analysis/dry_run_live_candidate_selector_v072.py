"""v0.7.2 QE-free dry-run live-candidate selector.

This script does NOT run QE/DFT, does NOT train a Gaussian process, and
does NOT compute any real predicted value, uncertainty, or failure risk.

The v0.7.1 audit (`reports/live_candidate_source_audit_v071.md`) found that
no standing, unresolved future-candidate pool exists, and that the real
GP/LCB proposal path (`qe_active_inverse_common.py::_propose_inverse`) can
only produce a genuine candidate after training on real (params, energy)
pairs. Those pairs only exist either in local, gitignored QE caches
(`outputs/cache/*.pkl`, not committed, not portable) or by running new
QE/DFT (forbidden here). Fabricating energies to bootstrap a GP would be
fabricating a scientific result, which is also forbidden.

This is therefore Approach B from the v0.7.2 design brief: a schema-valid
dry-run template generator. It only reads already-committed,
already-public `generated_models/*.py` workflow *definitions* (importing
them is safe — every `ActiveSystem` is built at module level and QE is only
launched inside an `if __name__ == "__main__":` guard, exactly as
`tests/test_generated_workflows.py` already relies on for all 50
workflows). From each workflow's real, documented design-variable range
(`Variable.lo`/`Variable.hi`), it picks an arithmetic placeholder point
deliberately distinct from the workflow's own documented `Variable.initial`
seed values, to reduce (but not guarantee, since this script does not read
local QE caches) the chance that the point coincides with an
already-completed calculation.

Every output row has `status = dry_run_only` and every
prediction/uncertainty/failure-risk/acquisition field is explicitly
`not_computed` — never a fabricated number. `selection_category` reflects
only the design intent for a future scored selector, not an actual score.
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "data" / "dry_run_live_candidates_v072.csv"

NOT_COMPUTED = "not_computed"
STATUS = "dry_run_only"
REVIEW_NOTE = (
    "Proposal-review artifact only; not selected for QE/PBE execution; "
    "requires human review before QE/PBE."
)

OUTPUT_COLUMNS = [
    "candidate_id",
    "material_id",
    "material_family",
    "formula_composition",
    "structure_source",
    "candidate_variables",
    "predicted_value",
    "uncertainty_lcb_score",
    "failure_risk",
    "acquisition_score",
    "selection_reason",
    "selection_category",
    "DFT_settings_profile",
    "pseudopotential_family",
    "expected_runtime_risk",
    "status",
    "notes",
]

# (generated_models module name, selection_category, fraction-of-range per
# variable). Fractions are arithmetic placeholders chosen to fall between
# each workflow's documented Variable.initial seed values, not to mimic a
# real acquisition score.
CANDIDATE_PLAN: tuple[tuple[str, str, tuple[float, ...]], ...] = (
    ("bulk_al_qe_active_inverse", "exploitation", (0.30,)),
    ("bulk_al_qe_active_inverse", "exploitation", (0.65,)),
    ("mos2_qe_active_inverse", "uncertainty_exploration", (0.05, 0.10)),
    ("mos2_qe_active_inverse", "uncertainty_exploration", (0.95, 0.90)),
    ("bulk_mgo_generated_qe_active_inverse", "low_failure_risk", (0.40,)),
    ("bulk_mgo_generated_qe_active_inverse", "low_failure_risk", (0.75,)),
    ("bulk_si_generated_qe_active_inverse", "failure_risk_challenge", (0.10,)),
    ("bulk_si_generated_qe_active_inverse", "failure_risk_challenge", (0.90,)),
    ("graphene_generated_qe_active_inverse", "diversity", (0.50,)),
)

SELECTION_REASONS = {
    "exploitation": (
        "Placeholder for a future exploitation candidate: a design-space "
        "point near the documented range, NOT scored by a real GP "
        "surrogate. A real selector would pick the lowest predicted_value "
        "at low uncertainty here."
    ),
    "uncertainty_exploration": (
        "Placeholder for a future exploration candidate: chosen near the "
        "edge of the documented range as a structural stand-in for 'least "
        "explored', NOT a real GP uncertainty estimate."
    ),
    "low_failure_risk": (
        "Placeholder for a future low-failure-risk candidate. No "
        "failure-risk model was run; this category label is aspirational "
        "until a real classifier score is attached."
    ),
    "failure_risk_challenge": (
        "Placeholder for a future failure-risk-challenge candidate: chosen "
        "near the edge of the documented range as a structural stand-in "
        "for 'more likely to stress QE settings', NOT a real failure-risk "
        "score."
    ),
    "diversity": (
        "Placeholder diversity candidate: a different material from every "
        "other row in this dry-run table."
    ),
}


def _load_system(module_name: str):
    module = importlib.import_module(f"generated_models.{module_name}")
    return module.SYSTEM


def _candidate_variables_str(system, fracs: tuple[float, ...]) -> str:
    parts = []
    for variable, frac in zip(system.variables, fracs):
        value = variable.lo + frac * (variable.hi - variable.lo)
        if any(abs(value - seed) < 1e-6 for seed in variable.initial):
            raise ValueError(
                f"Dry-run placeholder value {value} for {system.key}:{variable.name} "
                "coincides with a documented Variable.initial seed - this would risk "
                "presenting an already-evaluated design point as an unresolved candidate. "
                "Choose a different fraction."
            )
        parts.append(f"{variable.name}={value:.4f}")
    return "; ".join(parts)


def _dft_settings_profile(system) -> str:
    return (
        f"ecutwfc={system.ecutwfc};ecutrho={system.ecutrho};"
        f"kpts={system.kpts};smearing={system.smearing};degauss={system.degauss}"
    )


def _pseudopotential_family(system) -> str:
    return ";".join(f"{el}:{pp}" for el, pp in sorted(system.pseudopotentials.items()))


def build_rows(plan: tuple[tuple[str, str, tuple[float, ...]], ...] = CANDIDATE_PLAN) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    counters: dict[str, int] = {}
    for module_name, category, fracs in plan:
        system = _load_system(module_name)
        counters[module_name] = counters.get(module_name, 0) + 1
        candidate_id = f"dryrun_{module_name}_{counters[module_name]}"
        rows.append({
            "candidate_id": candidate_id,
            "material_id": system.key,
            "material_family": system.category or NOT_COMPUTED,
            "formula_composition": ",".join(sorted(system.pseudopotentials)),
            "structure_source": f"generated_models/{module_name}.py:ActiveSystem.builder",
            "candidate_variables": _candidate_variables_str(system, fracs),
            "predicted_value": NOT_COMPUTED,
            "uncertainty_lcb_score": NOT_COMPUTED,
            "failure_risk": NOT_COMPUTED,
            "acquisition_score": NOT_COMPUTED,
            "selection_reason": SELECTION_REASONS[category],
            "selection_category": category,
            "DFT_settings_profile": _dft_settings_profile(system),
            "pseudopotential_family": _pseudopotential_family(system),
            "expected_runtime_risk": NOT_COMPUTED,
            "status": STATUS,
            "notes": REVIEW_NOTE,
        })
    return rows


def write_table(rows: list[dict[str, str]], path: str | Path = DEFAULT_OUTPUT) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = build_rows()
    write_table(rows)
    print(f"Wrote {DEFAULT_OUTPUT} ({len(rows)} dry-run review rows)")
    print("No QE/DFT was run. No live validation has started.")
    print("These rows are proposal-review artifacts only; not QE/PBE inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
