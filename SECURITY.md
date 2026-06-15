# Security Policy

## Supported Versions

ActiStruct is a research codebase. Security fixes are applied to the current main branch.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a Vulnerability

Please report security concerns privately through the GitHub repository owner or by opening a minimal issue that does not expose sensitive details.

## Computational Safety Notes

- Review all Quantum ESPRESSO input settings before long production runs.
- Do not commit proprietary pseudopotentials, credentials, cluster account details, or private paths.
- Raw QE scratch folders can be large and may contain environment-specific paths; they are ignored by default.