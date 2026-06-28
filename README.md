# ActiStruct-nebwalk Transition-Metal Complex Reliability Benchmark

Reliability-aware active-learning workflow for DFT-guided transition-metal
complex optimization. Built on top of [ActiStruct](https://github.com/Rifat19R/ActiStruct)
(`actistruct`, installed editable from `D:/Rifat_kh/inverse_active`). nebwalk is
used only as a secondary demonstration after reliable endpoints exist.

See [`CLAUDE_ACTISTRUCT_TMC_PLAN.md`](CLAUDE_ACTISTRUCT_TMC_PLAN.md) for the
full plan, scope, and non-negotiable scientific rules.

## Status: Phase 1 (scaffold)

Primary benchmark systems: ferrocene, Ni(CO)4, Cr(CO)6, Fe(CO)5 — neutral,
closed-shell first pass. No charged complexes or SSE17 systems until phase 1
is validated.

QE (`pw.x` v7.4.1) runs via WSL at `/home/duets/q-e-qe-7.4.1/bin/pw.x`, not on
Windows PATH and not inside the `actistruct` venv.

## Professor-safe framing

> This project presents an early-stage reliability-aware active-learning
> workflow for DFT-guided transition-metal complex optimization. The workflow
> does not replace electronic-structure calculations. Instead, it organizes
> DFT inputs and outputs, tracks convergence and failure behavior, estimates
> uncertainty, and selects informative candidate geometries for validation.
> The first benchmark focuses on neutral organometallic complexes to keep the
> demonstration chemically controlled and reproducible.
