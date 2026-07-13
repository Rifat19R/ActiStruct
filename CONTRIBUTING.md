# Contributing

Contributions should keep ActiStruct reproducible, conservative, and easy to audit.

## Development environment

```bash
git clone https://github.com/Rifat19R/ActiStruct.git
cd ActiStruct

# WSL2 / Linux (QE runs require Linux; tests work on any OS)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[test]"

# Verify
pytest -q   # 281 passed, 0 warnings
```

## Running tests

```bash
pytest -q
```

No QE/DFT is launched by any test. All tests are offline and should take under
3 minutes on a modern laptop.

## Code style

- Format with `black` (line length 88, default settings).
- Lint with `ruff` (default rules).
- Only mention tools actually configured in `pyproject.toml`.
- ASCII-only in comments, docstrings, and print statements. No Unicode box-
  drawing, em-dashes, or section signs.

## Guidelines

- Keep generated benchmark scripts small and explicit.
- Do not commit pseudopotential binaries.
- Do not commit private paths or machine-specific files (personal directory
  paths, usernames, hostnames).
- Keep raw QE scratch output out of git. `outputs/cache/` and `*.pwo` files
  are gitignored.
- Prefer adding reports, plots, and concise analysis summaries over large
  transient files.
- Do not run QE/DFT as part of normal tests. The test suite is offline by
  design.
- Do not delete or relabel failed records to improve metrics. Failures are
  training signal, not noise to be cleaned away.

## Reporting bugs

Open a GitHub Issue and include:

- Operating system and Python version (`python --version`).
- Quantum ESPRESSO version (`pw.x --version`) if the bug involves DFT.
- Relevant environment variables (`ESPRESSO_PSEUDO`, `ESPRESSO_COMMAND`,
  `FIDELITY`).
- The command you ran and the shortest log excerpt that reproduces the problem.

For QE-related bugs, include a minimal reproducer (`.pwi` input file) that
does not depend on proprietary pseudopotentials. Use SSSP 1.3.0 PBE efficiency
UPF files; they are freely downloadable from the SSSP Materials Cloud page.

## Integrity rules (mandatory)

- Do not change the GP RBF kernel lower bound from `1e-2`. ConvergenceWarnings
  on small/synthetic datasets are expected and suppressed in pytest config.
- Escalation strategy (TroubleshootingStrategy) must remain cumulative. Group
  4 (`electron_maxstep=300`) retains groups 1-3.
- `electron_maxstep` value is 300, not 40.
- QE `outdir` must always be under `/tmp/` or `/home/`. Never under `/mnt/d/`
  (NTFS does not support POSIX file locking).
- Do not fabricate benchmark numbers. Every quantitative claim must be
  grounded in a file on disk or a passing test.
