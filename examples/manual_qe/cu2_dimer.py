"""
Combined active learning + inverse design for a Cu2 dimer.

Goal:
    Find a Cu-Cu bond distance whose EMT total energy is close to a target.

Notes:
    - EMT is used as a fast mock DFT oracle.
    - Replace dft_energy(distance) later with VASP, GPAW, QE, etc.
    - Script is self-contained and writes plots/reports under outputs/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from ase import Atoms
from ase.calculators.emt import EMT
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from scipy.optimize import differential_evolution

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


ROOT = Path(__file__).resolve().parents[2]
PLOT_DIR = ROOT / "outputs" / "plots"
REPORT_DIR = ROOT / "outputs" / "reports"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    requested_target_energy: float = -1.5
    distance_min: float = 1.8
    distance_max: float = 3.5
    n_candidates: int = 250
    n_truth_grid: int = 400
    initial_distances: tuple[float, ...] = (2.0, 2.5, 3.0)
    max_iterations: int = 12
    uncertainty_threshold: float = 0.05
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_error: float = 0.03
    duplicate_tol: float = 1e-6
    random_state: int = 7


def dft_energy(distance: float) -> float:
    """Mock DFT oracle: return Cu2 EMT potential energy in eV."""
    atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [float(distance), 0.0, 0.0]])
    atoms.calc = EMT()
    return float(atoms.get_potential_energy())


class GPModel:
    """Gaussian-process forward model: distance -> energy mean/std."""

    def __init__(self, random_state: int) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=0.35, length_scale_bounds=(1e-2, 10.0))
            + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-8, 1e-1))
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=8,
            random_state=random_state,
        )

    def train(self, distances: list[float], energies: list[float]) -> None:
        x_train = np.asarray(distances, dtype=float).reshape(-1, 1)
        y_train = np.asarray(energies, dtype=float)
        self.gp.fit(x_train, y_train)

    def predict(self, distances: np.ndarray | list[float]) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(distances, dtype=float).reshape(-1, 1)
        mean, std = self.gp.predict(x, return_std=True)
        return mean, std


def choose_reachable_target(config: Config, truth_distances: np.ndarray, truth_energies: np.ndarray) -> float:
    """Use requested target if reachable; otherwise use minimum EMT energy."""
    e_min = float(np.min(truth_energies))
    e_max = float(np.max(truth_energies))
    target = config.requested_target_energy

    if e_min <= target <= e_max:
        return target

    min_idx = int(np.argmin(truth_energies))
    adjusted = float(truth_energies[min_idx])
    print(
        f"Requested target {target:.4f} eV is outside EMT range "
        f"[{e_min:.4f}, {e_max:.4f}] eV."
    )
    print(
        f"Using reachable target = minimum EMT energy {adjusted:.4f} eV "
        f"near R = {truth_distances[min_idx]:.4f} A."
    )
    return adjusted


def is_new_distance(distance: float, labeled_distances: list[float], tol: float) -> bool:
    return not np.any(np.isclose(float(distance), np.asarray(labeled_distances), atol=tol, rtol=0.0))


def add_label(distance: float, distances: list[float], energies: list[float], tol: float) -> tuple[bool, float]:
    """Evaluate dft_energy(distance) once if not already labeled."""
    distance = float(distance)
    if not is_new_distance(distance, distances, tol):
        idx = int(np.argmin(np.abs(np.asarray(distances) - distance)))
        return False, float(energies[idx])

    energy = dft_energy(distance)
    distances.append(distance)
    energies.append(energy)
    return True, energy


def acquisition_score(mean: np.ndarray, std: np.ndarray, target_energy: float, kappa: float) -> np.ndarray:
    """Higher score means closer to target while still rewarding uncertainty."""
    return -np.abs(mean - target_energy) + kappa * std


def top_uncertain_points(
    model: GPModel,
    candidate_distances: np.ndarray,
    labeled_distances: list[float],
    threshold: float,
    max_points: int,
    tol: float,
) -> list[float]:
    """Select up to max_points unlabeled candidates with std > threshold."""
    _, std = model.predict(candidate_distances)
    order = np.argsort(std)[::-1]

    selected: list[float] = []
    for idx in order:
        distance = float(candidate_distances[idx])
        if std[idx] <= threshold:
            break
        if is_new_distance(distance, labeled_distances + selected, tol):
            selected.append(distance)
        if len(selected) == max_points:
            break
    return selected


def best_observed(distances: list[float], energies: list[float], target_energy: float) -> tuple[float, float, float]:
    errors = np.abs(np.asarray(energies) - target_energy)
    idx = int(np.argmin(errors))
    return float(distances[idx]), float(energies[idx]), float(errors[idx])


def plot_energy_curve(
    truth_distances: np.ndarray,
    truth_energies: np.ndarray,
    model: GPModel,
    labeled_distances: list[float],
    labeled_energies: list[float],
    target_energy: float,
) -> Path:
    mean, std = model.predict(truth_distances)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(truth_distances, truth_energies, color="black", lw=2, label="True EMT curve")
    ax.plot(truth_distances, mean, color="tab:red", ls="--", lw=2, label="GP prediction")
    ax.fill_between(
        truth_distances,
        mean - std,
        mean + std,
        color="tab:red",
        alpha=0.22,
        label="GP uncertainty (+/- 1 std)",
    )
    ax.scatter(labeled_distances, labeled_energies, s=55, color="tab:blue", zorder=5, label="Labeled DFT points")
    ax.axhline(target_energy, color="tab:green", ls=":", lw=2, label="Target energy")
    ax.set_xlabel("Cu-Cu distance (A)")
    ax.set_ylabel("Total energy (eV)")
    ax.set_title("Cu2 Dimer: Active Learning + Inverse Design")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "cu2_energy_curve.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_convergence(history: dict[str, list[float]]) -> Path:
    fig, (ax_error, ax_dft) = plt.subplots(1, 2, figsize=(12, 4.5))

    ax_error.plot(history["iteration"], history["best_error"], marker="o", color="tab:orange")
    ax_error.set_xlabel("Iteration")
    ax_error.set_ylabel("Best observed error (eV)")
    ax_error.set_title("Convergence")
    ax_error.grid(alpha=0.25)

    ax_dft.plot(history["iteration"], history["n_dft"], marker="s", color="tab:purple")
    ax_dft.set_xlabel("Iteration")
    ax_dft.set_ylabel("Total DFT evaluations")
    ax_dft.set_title("Data efficiency")
    ax_dft.grid(alpha=0.25)

    fig.tight_layout()
    path = PLOT_DIR / "cu2_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    path = REPORT_DIR / "cu2_run_report.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    config = Config()
    candidate_distances = np.linspace(config.distance_min, config.distance_max, config.n_candidates)
    truth_distances = np.linspace(config.distance_min, config.distance_max, config.n_truth_grid)
    truth_energies = np.asarray([dft_energy(d) for d in truth_distances])
    target_energy = choose_reachable_target(config, truth_distances, truth_energies)

    labeled_distances = list(config.initial_distances)
    labeled_energies = [dft_energy(d) for d in labeled_distances]

    model = GPModel(random_state=config.random_state)
    model.train(labeled_distances, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_distance": [],
        "best_energy": [],
        "best_error": [],
        "n_dft": [],
    }
    report: list[str] = []

    header = [
        "=" * 72,
        "Cu2 active learning + inverse design",
        f"Target energy: {target_energy:.6f} eV",
        f"Initial distances: {list(config.initial_distances)} A",
        "=" * 72,
    ]
    print("\n".join(header))
    report.extend(header)

    for iteration in range(1, config.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        query_distances = top_uncertain_points(
            model,
            candidate_distances,
            labeled_distances,
            config.uncertainty_threshold,
            config.active_labels_per_iter,
            config.duplicate_tol,
        )

        if query_distances:
            print(f"  Active learning labels: {[round(d, 4) for d in query_distances]} A")
            report.append(f"  Active learning labels: {[round(d, 4) for d in query_distances]} A")
            for distance in query_distances:
                _, energy = add_label(distance, labeled_distances, labeled_energies, config.duplicate_tol)
                print(f"    R={distance:.4f} A -> E={energy:.6f} eV")
                report.append(f"    R={distance:.4f} A -> E={energy:.6f} eV")
            model.train(labeled_distances, labeled_energies)
        else:
            print("  Active learning labels: none above uncertainty threshold")
            report.append("  Active learning labels: none above uncertainty threshold")

        # --- Fix 2: DE-based acquisition optimisation (replaces grid argmax) ---
        def _neg_acq_cu2(x: np.ndarray) -> float:
            m, s = model.predict(x.reshape(1, -1))
            return float(abs(m[0] - target_energy) - config.kappa * s[0])
        _de_result = differential_evolution(
            _neg_acq_cu2,
            [(config.distance_min, config.distance_max)],
            seed=config.random_state,
            maxiter=500, tol=1e-7, polish=True,
            mutation=(0.5, 1.5), recombination=0.9,
        )
        proposal_distance = float(_de_result.x[0])
        _m_at, _s_at = model.predict([[proposal_distance]])
        proposal_mean = float(_m_at[0])
        proposal_std = float(_s_at[0])
        proposal_pred_error = abs(proposal_mean - target_energy)

        print(
            f"  Inverse proposal: R={proposal_distance:.4f} A, "
            f"GP E={proposal_mean:.6f} +/- {proposal_std:.6f} eV, "
            f"pred error={proposal_pred_error:.6f} eV"
        )
        report.append(
            f"  Inverse proposal: R={proposal_distance:.4f} A, "
            f"GP E={proposal_mean:.6f} +/- {proposal_std:.6f} eV, "
            f"pred error={proposal_pred_error:.6f} eV"
        )

        added, true_energy = add_label(proposal_distance, labeled_distances, labeled_energies, config.duplicate_tol)
        if added:
            model.train(labeled_distances, labeled_energies)
            true_error = abs(true_energy - target_energy)
            print(f"    DFT check: E={true_energy:.6f} eV, true error={true_error:.6f} eV")
            report.append(f"    DFT check: E={true_energy:.6f} eV, true error={true_error:.6f} eV")
        else:
            print(f"    Already labeled: E={true_energy:.6f} eV")
            report.append(f"    Already labeled: E={true_energy:.6f} eV")

        best_r, best_e, best_err = best_observed(labeled_distances, labeled_energies, target_energy)
        history["iteration"].append(iteration)
        history["best_distance"].append(best_r)
        history["best_energy"].append(best_e)
        history["best_error"].append(best_err)
        history["n_dft"].append(len(labeled_distances))

        print(f"  Best observed: R={best_r:.4f} A, E={best_e:.6f} eV, error={best_err:.6f} eV")
        report.append(f"  Best observed: R={best_r:.4f} A, E={best_e:.6f} eV, error={best_err:.6f} eV")

        if best_err < config.convergence_error and proposal_std < config.uncertainty_threshold:
            print("  Converged: error and uncertainty thresholds met")
            report.append("  Converged: error and uncertainty thresholds met")
            break

    best_r, best_e, best_err = best_observed(labeled_distances, labeled_energies, target_energy)
    energy_plot = plot_energy_curve(
        truth_distances,
        truth_energies,
        model,
        labeled_distances,
        labeled_energies,
        target_energy,
    )
    convergence_plot = plot_convergence(history)

    final_lines = [
        "",
        "=" * 72,
        "Final result",
        f"Best distance: {best_r:.6f} A",
        f"Best EMT energy: {best_e:.6f} eV",
        f"Target energy: {target_energy:.6f} eV",
        f"Absolute error: {best_err:.6f} eV",
        f"DFT evaluations used by loop: {len(labeled_distances)}",
        f"Energy plot: {energy_plot}",
        f"Convergence plot: {convergence_plot}",
    ]
    print("\n".join(final_lines))
    report.extend(final_lines)
    report_path = write_report(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
