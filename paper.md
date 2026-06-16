---
title: 'ActiStruct: Active-Learning Inverse Design for DFT Structure Optimization'
tags:
  - Python
  - density functional theory
  - active learning
  - Gaussian processes
  - Quantum ESPRESSO
  - materials science
authors:
  - name: Md. Rifat Khandaker
    orcid: 0000-0003-0520-4654
    affiliation: 1
affiliations:
  - name: Department of Chemical Engineering, Dhaka University of Engineering & Technology, Gazipur 1700, Dhaka, Bangladesh
    index: 1
date: 16 June 2026
bibliography: paper.bib
---

# Summary

ActiStruct is an open source Python tool that uses Quantum ESPRESSO [@giannozzi2017] for density functional theory (DFT) calculations together with Gaussian process active learning to find the best value of a structural parameter, such as a lattice constant, bond length, layer spacing, or adsorption height, using far fewer DFT calculations than a normal grid scan. It is built on top of the Atomic Simulation Environment [@larsen2017]. The program fits a Gaussian process to the energies it has already computed, then picks the next geometry to test by minimizing a lower confidence bound acquisition function with SciPy's differential evolution optimizer [@virtanen2020]. ActiStruct comes with a shared active learning engine and a growing set of example systems covering metals, semiconductors, oxides, two dimensional materials, molecules, battery related crystals, and surface adsorption models. It is meant for researchers who need to tune one or two structural variables without writing their own optimization code.

# Statement of need

Finding the lowest energy value of a small number of structural parameters is a common step in DFT based research, and it costs a lot of computer time. The usual method, a grid scan, is easy to set up but does not scale well. A scan over two variables at a normal resolution can take dozens of DFT calls, and most of those calls land far from the real minimum. Active learning with a surrogate model [@shahriari2016] can cut this cost a lot, but using it usually means writing custom code to connect a Gaussian process or Bayesian optimization library to a DFT program, handling caching of expensive runs, and working out reasonable pseudopotential and convergence settings for each new material. ActiStruct does this connecting work once. A shared engine runs the active learning loop, caches energies, and handles the acquisition step. Each new material only needs a short script that sets the structure builder, the search variables and their bounds, and the Quantum ESPRESSO settings. This makes it easier to add a new material to a workflow that is reproducible and testable, without rebuilding the active learning part every time.

# State of the field

General purpose Bayesian optimization libraries give you the optimizer itself, but not the connection to ASE or Quantum ESPRESSO, so caching and per-system settings are left to the user. A few existing tools cover related ground. BOSS [@todorovic2019] is built for mapping potential energy surfaces and active learning across many kinds of atomistic problems. AGOX [@christiansen2022], which uses the GOFEE algorithm [@bisbo2020], is built for harder global structure search problems, such as cluster and surface reconstructions, using basin hopping and evolutionary methods inside a flexible framework. ActiStruct is not trying to replace these tools for global search. It covers a smaller, more specific job that sits next to them: tuning one or two structural variables that are already known, with a short script per material, and a multi-domain benchmark that also works as a regression test for the code itself. For the common task of optimizing a lattice constant, bond length, or adsorption height, ActiStruct asks for much less code than AGOX or BOSS style tools, at the cost of being less general.

# Software design

ActiStruct keeps the active learning engine separate from the physics of each system. The shared module builds the ASE Atoms object, attaches the Quantum ESPRESSO calculator, caches each computed energy by system and geometry so a finished calculation is never repeated, fits a Gaussian process with an RBF kernel using scikit-learn [@pedregosa2011], and picks the next geometry by minimizing a lower confidence bound with differential evolution [@virtanen2020] instead of searching a fixed grid of points. Each material is a short wrapper script, usually around forty lines, that sets the structure builder, the search variables and their bounds, and the pseudopotential, cutoff, and k-point settings for that material. Because the engine and the per-material code are kept apart, adding a new material does not touch the optimization logic, and the engine can be tested on its own with a smoke test suite that imports and checks every workflow without running an actual DFT calculation. The engine also catches two mistakes that otherwise cause confusing crashes in Quantum ESPRESSO: mixing pseudopotential types in one run, and writing scratch files to a filesystem that does not support file locking.

# Research impact statement

ActiStruct is new software and does not have outside users yet, so its case for near term impact rests on what it can already show, not on outside use. A benchmark covering many systems across eight material categories runs the full engine end to end and is rerun whenever a new material is added, so it works as an ongoing check rather than a one time demo. For the systems that have a published structure to compare against, the optimized parameter is checked against established PBE benchmarks [@haas2009; @lejaeghere2016] as a sanity check. A fuller, more quantitative validation, including direct comparison against full DFT grids and a test of how much the surrogate actually helps, is written up separately and is being prepared for outside review. That document is kept separate from this one because it is about scientific results, not about the software itself. Planned next steps include adding MXene and MAX phase systems to make the benchmark more varied.

# AI usage disclosure

AI tools were used while building this software. OpenAI Codex was used to write the first draft of each per-material wrapper script, based on a fixed pattern of structure builder, search variables, and Quantum ESPRESSO settings. Every draft was reviewed, corrected, and either accepted or rejected by the author before being added to the project. Anthropic's Claude was used to debug specific problems, such as pseudopotential type mismatches and filesystem locking errors on certain drives, and to review a change in the acquisition search from a fixed grid to differential evolution. The benchmark design, the validation approach, the interpretation of results, and all final code are the author's own responsibility.

# References
