\# Task: Write Python code for Active Learning + Inverse Design of H₂ dimer using Quantum ESPRESSO (via ASE)



You are an expert Python programmer and computational chemist. Your task is to write a complete, production‑ready Python script that implements \*\*combined active learning and inverse design\*\* for the H₂ molecule. The “oracle” is \*\*Quantum ESPRESSO (QE)\*\* called through the ASE (Atomic Simulation Environment) interface.



The script must follow the architecture you have already provided for Cu₂ (with EMT) and H₂ (with Lennard‑Jones), but now the energy evaluation is done by QE. You must include proper error handling, caching, and parallel evaluation of multiple distances.



\## 1. Inputs (to be defined in the script as constants)

\- Bond distance search range: `0.5` to `2.0` Å.

\- Initial distances: `\[0.62, 0.9, 1.3]` Å.

\- Target property: \*\*binding energy\*\* (not total energy).  

&#x20; Binding energy = `E\_H2(r) - 2 \* E\_H(atom)`.

&#x20; Target binding energy = `-4.5` eV (the minimum).

\- Uncertainty threshold for active learning: `0.05` eV (standard deviation).

\- Acquisition function parameter `kappa = 1.0`.

\- Convergence criteria:  

&#x20; - Absolute error of best candidate < `0.03` eV \*\*and\*\*  

&#x20; - Uncertainty of best candidate < `0.05` eV.

\- Maximum iterations: `12`.



\## 2. Required functionality



\### 2.1. Quantum ESPRESSO setup (via ASE)

\- Write a function `make\_h2(r, box\_size=10.0)` that returns an `ase.Atoms` object for H₂ with bond distance `r` (in Å) inside a cubic box of side `box\_size` Å (pbc=True).

\- Define QE input parameters as a dictionary (use `ecutwfc = 60.0` Ry, `ecutrho = 480.0` Ry, `conv\_thr = 1e-8`, smearing `degauss=0.01`, `kpts=(1,1,1)`). Use norm‑conserving pseudopotentials – the user will provide the path and file name. For the script, define a variable `pseudo\_dir = './pseudo'` and `pseudopotentials = {'H': 'H\_ONCV\_PBE-1.2.upf'}`.

\- Write a function `get\_qe\_calculator()` that returns an `Espresso` calculator instance configured with the above parameters and the command `mpirun -np 2 pw.x -in PREFIX.pwi > PREFIX.pwo` (the number of MPI processes can be a constant, e.g., `N\_PROCS = 2`).

\- Write a function `get\_h\_atom\_energy()` that creates a single H atom in the same box and runs QE to get its total energy. This should be called once and cached.



\### 2.2. Energy evaluation with caching and error handling

\- Use a dictionary cache stored via `pickle` to avoid recomputing the same bond distance. The cache file name: `h2\_energy\_cache.pkl`.

\- Write a function `compute\_binding\_energy(r, retries=2)` that:

&#x20; - Checks cache; returns cached value if present.

&#x20; - Creates the H₂ atoms, attaches the QE calculator, runs the calculation.

&#x20; - Computes binding energy = `total\_energy - 2 \* h\_atom\_energy`.

&#x20; - Stores result in cache and saves cache to disk.

&#x20; - If QE fails (exception, non‑convergence, etc.), retry up to `retries` times, waiting 5 seconds between attempts.

&#x20; - If all retries fail, return `None` (do not add to training set, but log a warning).

\- In the main loop, when a distance returns `None`, skip adding it and continue.



\### 2.3. Gaussian Process model (same as before)

\- Use `sklearn.gaussian\_process.GaussianProcessRegressor` with kernel: `RBF(length\_scale=0.2) + WhiteKernel(noise\_level=0.02)`.

\- Provide a class `GPModel` with `train(X, y)` and `predict(X)` methods.



\### 2.4. Active learning query

\- Input: current GP model, a dense array of candidate distances (e.g., 100 points from min to max), uncertainty threshold.

\- Return a list of distances where predicted standard deviation > threshold.

\- From those, select the top `K` (e.g., 2) with the highest uncertainty. If fewer than `K` exist, take all.

\- Evaluate these distances using `compute\_binding\_energy` (in parallel if possible – see section 3).



\### 2.5. Inverse design acquisition

\- Use acquisition function: `score = -|pred\_energy - target| + kappa \* std`.

\- Evaluate over the candidate distances and return the distance that maximises the score.

\- If that distance is not already in the training set, evaluate it with QE and add it.



\### 2.6. Main loop

\- Compute `h\_atom\_energy` once.

\- Initialise training set with the three initial distances (evaluate each with `compute\_binding\_energy` – if any fails, replace with nearby distance).

\- Train GP model.

\- For each iteration up to `max\_iterations`:

&#x20; - \*\*Active learning step:\*\* get high‑uncertainty distances, label them (QE), add to training set, retrain GP.

&#x20; - \*\*Inverse design step:\*\* propose best distance, if new, label it, add to training set, retrain GP.

&#x20; - \*\*Convergence check:\*\* Find best observed distance (closest to target in training set). If its error < tolerance and its uncertainty (from GP at that distance) < threshold, break.

&#x20; - Print iteration summary.



\### 2.7. Output

\- Console print of each iteration (distances labeled, proposed candidate, errors).

\- Final best distance, binding energy, total number of QE evaluations.

\- Generate two plots (using `matplotlib`):

&#x20; 1. Energy vs distance: true QE points (from training set), GP predicted curve with uncertainty band, target line.

&#x20; 2. Convergence plot: two subplots – (a) best error per iteration, (b) total QE evaluations per iteration.

\- Save plots as PNG files.

\- Save a text report with all run details.



\## 3. Parallel evaluation of multiple distances (optional but strongly recommended)

\- Because QE is slow, the active learning step may need to evaluate 2–5 distances. Use `multiprocessing.Pool` to run them in parallel.

\- Write a helper function `evaluate\_distance(r)` that calls `compute\_binding\_energy` and returns `(r, energy)`.

\- Example:

&#x20; ```python

&#x20; with Pool(processes=2) as pool:

&#x20;     results = pool.map(evaluate\_distance, distances\_to\_label)

