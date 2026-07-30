# Ti3C2-O hydrogen-adsorption campaign

## Scientific purpose

Compare three candidate-selection tracks for low-fidelity H adsorption-site
screening on one Ti3C2-O system under a frozen five-iteration budget.

## Systems and tracks

- one Ti3C2-O 2x2 slab and a frozen six-site seed set;
- GNN-embedding GP;
- plain GP on periodic coordinate features;
- seeded random baseline.

The original plain-GP campaign exposed periodic-coordinate and duplicate
behavior. Its append-only log is retained. A protocol amendment fixed the
kernel and a separate five-iteration plain-GP rerun was performed.

## Protocol and evidence

- Frozen protocol and dated amendments: `docs/BENCHMARK_PROTOCOL.md`
- Full result interpretation: `docs/TI3C2O_LF_CAMPAIGN_RESULTS.md`
- Original campaign log:
  `outputs/campaigns/ti3c2_o_lf_campaign.jsonl`
- Corrected plain-GP log:
  `outputs/campaigns/ti3c2_o_lf_campaign_plain_gp_rerun_amend5.jsonl`
- Oracle and drivers: `examples/manual_qe/`

## Completed result

There were five iterations per track and 14 physical DFT calls across the
original three-track run plus the corrected plain-GP rerun. The corrected
periodic GP found this campaign's best new value:
`|DeltaG_H| = 0.0020 eV`.

## Reproduction commands

Fast integrity check:

```bash
python -m pytest -q tests/test_repository_integrity.py
```

Live reproduction, which may take many hours and requires QE:

```bash
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_grid_campaign
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_al_loop
```

Expected live outputs are append-only JSONL records and local QE/cache
artifacts described by the protocol. Do not launch live reproduction as an
installation smoke test.

## Limitations

This is one low-fidelity system, seed set, and budget. It does not show that
GP generally beats GNN or random search, or that active learning universally
reduces DFT cost. HF validation was attempted and deferred; no HF scientific
result exists, and partial HF output is not used for scientific claims. No
experimental validation is included.
