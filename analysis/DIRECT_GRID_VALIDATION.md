# Direct Grid Validation

This folder contains the local QE/PBE grid-validation runner for ActiStruct.
It is meant for expensive validation runs, not for CI.

## Setup

Configure Quantum ESPRESSO and pseudopotentials before launching real grids:

```bash
cd <ACTISTRUCT_ROOT>
source .venv/bin/activate

export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun --oversubscribe -np 2 /path/to/pw.x"
```

Use `np=2` or another value that is safe for your machine. Avoid oversubscribing
if you are already running several grid points in separate shells.

## Preview

Dry-run does not start QE:

```bash
python analysis/direct_grid_validation.py dry-run
```

## Run One Grid

```bash
python analysis/direct_grid_validation.py run --system bulk_mgo
python analysis/direct_grid_validation.py run --system bulk_si_optional
```

The wrapper is equivalent:

```bash
bash analysis/run_direct_grid_validations.sh run --system bulk_mgo
```

## Recommended Order

Run the currently published validation systems:

```bash
python analysis/direct_grid_validation.py run --system bulk_cu
python analysis/direct_grid_validation.py run --system mos2
python analysis/direct_grid_validation.py run --system bulk_mgo
python analysis/direct_grid_validation.py run --system bulk_si_optional
```

## Resume

The runner writes one CSV per system in:

```text
analysis/outputs/raw/direct_grid/
```

Completed `status=ok` rows are reused. If a run stops, rerun the same command
and it will continue from missing rows.

For a small test without committing to a full grid:

```bash
python analysis/direct_grid_validation.py run --system bulk_mgo --max-points 1
```

## Summarize

```bash
python analysis/direct_grid_validation.py summarize
```

The combined deliverable is:

```text
analysis/outputs/raw/direct_grid_validations.csv
```

Columns include:

```text
system, dim, grid_points, AL_calls, grid_min_energy, AL_min_energy,
delta_eV_per_atom, pass_fail
```

## Compatibility Note

The public summary is intentionally pass-only. Local exploratory or incomplete
grid runs should stay in local scratch files until they have compatible
active-learning reports and complete QE/PBE grid data.
