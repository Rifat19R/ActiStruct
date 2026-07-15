# Draft: Prof. Kulik Outreach

Status: draft for Rifat review before sending.

## Positioning

The strongest external-facing result is the ferrocene conformer barrier:

- Real QE/PBE relaxation data, not a toy example.
- Ferrocene reference geometry is primary-PDF verified against Haaland and
  Nilsson 1968, Table 1.
- The +36 degree Cp-ring perturbation relaxes to the staggered-like D5d basin.
- Computed barrier: dE = 41.68 meV.
- This matches the known experimental ferrocene rotational barrier of about
  4 kJ/mol, approximately 41 meV.

This result is independent of the three remaining primary-PDF checks for
Ni(CO)4, Cr(CO)6, and Fe(CO)5 bond lengths. Those PDFs affect only whether the
specific geometry-comparison reference values for those three systems can be
cited as primary-verified.

## Evidence Links

- Public release: https://github.com/Rifat19R/ActiStruct/releases/tag/v1.0
- Repository: https://github.com/Rifat19R/ActiStruct
- Benchmark report: `reports/tmc_benchmark_v1.0.md`
- Feature report: `reports/feature_report_v0.1.md`
- GP baseline report: `reports/baseline_model_report_v0.1.md`
- AL demo report: `reports/active_learning_demo_v0.1.md`

## Safe Claims

- ActiStruct now has a public TMC Reliability Benchmark release with 16
  QE-relaxed transition-metal complex structures.
- The benchmark includes four primary systems and twelve perturbation
  relaxations: ferrocene, Ni(CO)4, Cr(CO)6, and Fe(CO)5.
- The ferrocene D5h to D5d conformer barrier is dE = 41.68 meV, matching the
  known experimental scale.
- Fe cutoff convergence is explicitly checked; 90 Ry is adopted for Fe energy
  claims.
- The software pipeline now covers feature extraction, a GP uncertainty
  baseline, and one complete retrospective AL iteration:
  model -> acquisition -> DFT-oracle reveal -> model update.
- The test suite is green locally and in CI across Python 3.11 and 3.12.

## Caveat To Keep

Three geometry-reference PDFs are still pending primary-table verification:

- Ni(CO)4: Hedberg, Iijima, and Hedberg 1979, DOI `10.1063/1.437911`.
- Cr(CO)6: Whitaker and Jeffery 1967, DOI `10.1107/S0365110X67004153`.
- Fe(CO)5: McClelland et al. 2001, DOI `10.1021/ic001114e`.

This caveat does not weaken the ferrocene barrier result, the Fe cutoff study,
the AL demo, or the software-quality claims. It only limits how strongly the
three specific geometry-comparison numbers should be cited until their primary
PDF tables are checked.

## Email Draft

Subject: ActiStruct TMC reliability benchmark with DFT-validated ferrocene barrier

Dear Prof. Kulik,

I am Md. Rifat Khandaker, an undergraduate researcher working on ActiStruct, an
active-learning workflow for DFT-guided structure exploration. I have prepared a
small transition-metal complex reliability benchmark to test whether the workflow
can handle chemically meaningful molecular DFT data, not only synthetic examples.

The strongest result is ferrocene: a QE/PBE relaxation starting from a +36 degree
Cp-ring perturbation reaches the staggered-like D5d conformer, with a computed
D5h to D5d energy difference of 41.68 meV. This matches the known experimental
rotational-barrier scale of about 4 kJ/mol, or roughly 41 meV. The ferrocene
reference geometry has been checked against the primary Haaland and Nilsson
electron-diffraction PDF.

The public release is here:
https://github.com/Rifat19R/ActiStruct/releases/tag/v1.0

The benchmark currently includes 16 QE-relaxed structures across ferrocene,
Ni(CO)4, Cr(CO)6, and Fe(CO)5. I also added the software layer around the data:
Coulomb-matrix features, a Gaussian-process uncertainty baseline, and a
retrospective active-learning iteration that performs the full loop
model -> acquisition -> oracle reveal -> model update using the held-out DFT
data. The goal is not to claim predictive ML performance from 16 points; it is
to show that the DFT, parsing, dataset, uncertainty, and AL-control interfaces
are working end to end with honest limitations.

One caveat: I still need to primary-PDF verify three supporting bond-length
reference tables for Ni(CO)4, Cr(CO)6, and Fe(CO)5. This does not affect the
ferrocene barrier result or the software demonstration, but I am keeping that
citation caveat explicit before using those three geometry comparisons as
primary-verified values.

If useful, I would be grateful for any feedback on whether this benchmark is
framed in a scientifically appropriate way and what next transition-metal
complex systems would make it more relevant to uncertainty-aware DFT workflows.

Sincerely,
Md. Rifat Khandaker

## Next Update Commits

When the remaining PDFs are obtained, update and commit each reference
separately:

- `data: verify Ni(CO)4 reference against primary PDF`
- `data: verify Cr(CO)6 reference against primary PDF`
- `data: verify Fe(CO)5 reference against primary PDF`
