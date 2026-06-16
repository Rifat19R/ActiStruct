# Contributing

Contributions should keep ActiStruct reproducible, conservative, and easy to audit.

## Guidelines

- Keep generated benchmark scripts small and explicit.
- Do not commit pseudopotential binaries.
- Keep raw QE scratch output out of git unless there is a specific archival reason.
- Prefer adding reports, plots, and concise analysis summaries over large transient files.
- Run smoke tests before submitting changes:

```bash
python tests/test_builders_and_config.py
```

## Style

Use clear Python, explicit structure builders, and deterministic random seeds for active-learning workflows.

## Issues and Support

Use GitHub Issues to report bugs, request features, ask support questions, or
flag unclear documentation. Please include the operating system, Python version,
Quantum ESPRESSO version, relevant environment variables, the command you ran,
and the shortest log excerpt that reproduces the problem.
