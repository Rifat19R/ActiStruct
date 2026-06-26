# Contributing

Contributions should keep ActiStruct reproducible, conservative, and easy to audit.

## Guidelines

- Keep generated benchmark scripts small and explicit.
- Do not commit pseudopotential binaries.
- Do not commit private paths or machine-specific files (personal directory
  paths, usernames, hostnames).
- Keep raw QE scratch output out of git unless there is a specific archival reason.
- Prefer adding reports, plots, and concise analysis summaries over large transient files.
- Do not run QE/DFT as part of normal tests; the test suite is offline by design.
- Do not delete or relabel failed records to improve metrics — failures are
  training signal, not noise to be cleaned away.
- Install and run the full test suite before submitting changes:

```bash
pip install -r requirements.txt
pip install -e ".[test]"
pytest -q
```

This currently passes with 73 tests. See `docs/model_and_tests.md` for what
each test file covers.

## Style

Use clear Python, explicit structure builders, and deterministic random seeds for active-learning workflows.

## Issues and Support

Use GitHub Issues to report bugs, request features, ask support questions, or
flag unclear documentation. Please include the operating system, Python version,
Quantum ESPRESSO version, relevant environment variables, the command you ran,
and the shortest log excerpt that reproduces the problem.
