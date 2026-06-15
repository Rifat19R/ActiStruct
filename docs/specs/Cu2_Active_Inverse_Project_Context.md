\# Project Context: Combined Active Learning + Inverse Design for Cu₂ Dimer



\## 1. Project Goal

Build a working Python pipeline that demonstrates \*\*combined active learning and inverse design\*\* for a simple atomic system: the Cu₂ dimer (two copper atoms). The system must find the interatomic distance (bond length) that yields a \*\*target total energy\*\* (e.g., -1.5 eV) using as few DFT calculations as possible.



This is a \*\*proof-of-concept (MVP)\*\* to showcase my skills in:

\- Machine Learning for atomic systems

\- Active learning (uncertainty sampling + diversity)

\- Inverse design (Bayesian optimization / acquisition functions)

\- Integration with DFT (mock DFT first, real DFT later)



The final output should be a clean, well-documented Python script that produces plots and convergence reports.



\## 2. My Role \& Expectations from You (ChatGPT)

You are my \*\*coding assistant\*\*. I want you to:

\- Write \*\*correct, runnable Python code\*\* with clear comments.

\- Help me \*\*debug\*\* any errors I encounter.

\- Explain \*\*why\*\* certain design choices are made.

\- Suggest improvements for speed, accuracy, or clarity.

\- When I ask a question, give \*\*concrete answers with code snippets\*\* if relevant.

\- Maintain a \*\*mentor-like tone\*\*: teach me the concepts, not just give code.



\## 3. Technical Constraints \& Preferences

\- \*\*Language\*\*: Python 3.8+

\- \*\*Libraries allowed\*\*: numpy, matplotlib, scikit-learn, ase (Atomic Simulation Environment)

\- \*\*Mock DFT\*\*: Use `ase.calculators.emt.EMT` (Effective Medium Theory) – it's fast and works for Cu₂.

\- \*\*Real DFT (later)\*\*: Should be easily replaceable (e.g., VASP or GPAW) – keep the `dft\_energy` function swappable.

\- \*\*No heavy deep learning frameworks\*\* (PyTorch/TF) for the MVP – Gaussian Process is fine.

\- \*\*The code must be self-contained\*\* – one script that runs from start to finish.



\## 4. Algorithmic Details to Implement

The pipeline must include:



\### 4.1. Forward Model with Uncertainty

\- Use \*\*Gaussian Process Regressor\*\* (from scikit-learn) with RBF + WhiteKernel.

\- Input: bond distance (1D). Output: mean energy and standard deviation (uncertainty).



\### 4.2. Active Learning (Query Strategy)

\- At each iteration, evaluate uncertainty (std) over a dense set of candidate distances.

\- Select \*\*all distances where std > threshold\*\* (e.g., 0.05 eV).

\- From those, pick \*\*top 2 most uncertain\*\* to label with DFT.

\- Label = run `dft\_energy(distance)` and append to training set.

\- Retrain GP model after adding new labels.



\### 4.3. Inverse Design (Proposing Next Best Candidate)

\- Use an \*\*acquisition function\*\* that balances exploitation (near target) and exploration (high uncertainty).

\- Suggested acquisition: `score = -|predicted\_energy - target\_energy| + kappa \* std` (higher is better).

\- Find candidate distance that maximizes this score.

\- (Optional) Evaluate that candidate with DFT if not already in training set.



\### 4.4. Iteration Loop

\- Start with 3 initial DFT points: distances \[2.0, 2.5, 3.0] Å.

\- For up to 12 iterations:

&#x20;   - Active learning step (label high-uncertainty points)

&#x20;   - Inverse design step (propose best candidate, evaluate)

&#x20;   - Retrain GP

&#x20;   - Check convergence: error < 0.03 eV and std < uncertainty\_threshold

\- Stop early if converged.



\### 4.5. Outputs

\- Print progress each iteration (which distances labeled, proposed candidate, errors).

\- Final best distance and energy.

\- Two plots:

&#x20;   1. \*\*Energy vs distance\*\* – shows true DFT curve, GP prediction, uncertainty band, training points, target line.

&#x20;   2. \*\*Convergence plot\*\* – two subplots: (a) best error over iterations, (b) total DFT evaluations over iterations.



\## 5. Example Target

\- Target energy: `-1.5 eV` (choose a value that lies within the EMT energy range for Cu₂ – you can first run a quick scan).

\- If -1.5 eV is not reachable, choose a reachable target (e.g., minimum energy). But explain in comments.



\## 6. Deliverables (What I expect from you)

For each interaction, I may ask for:

\- The complete working code (with no syntax errors).

\- Explanation of a specific part (e.g., acquisition function, uncertainty threshold).

\- Help with debugging (I will paste error messages).

\- Suggestions to extend to 2D or real materials.



\## 7. Future Extensions (Not for MVP)

After this works, I plan to:

\- Replace EMT with real DFT (VASP/Quantum ESPRESSO).

\- Extend to 2D systems (graphene, surfaces) and then to HER catalysts.

\- Add multi-objective optimization (bandgap + ΔG\_H\*).



\## 8. Communication Style

\- Be \*\*precise\*\* and \*\*concise\*\*.

\- Use bullet points and code blocks where helpful.

\- If I ask a vague question, ask me clarifying questions before answering.

\- Don't assume I know advanced concepts – explain briefly.



\## 9. Starting Point

Please begin by providing the \*\*full Python script\*\* as described above. Make sure it runs without errors on a standard machine with `pip install numpy matplotlib scikit-learn ase`. Once I run it and see the output, I will come back with questions or debugging requests.



Thank you – let's build something great.

