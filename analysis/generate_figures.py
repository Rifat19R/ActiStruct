from __future__ import annotations

import csv
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
import numpy as np

from publication_data import FIGURE_DIR, RAW_DIR, choose_report_by_key, ensure_dirs, parse_history

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["font.size"] = 11


def read_csv(name: str) -> list[dict]:
    with (RAW_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def f(row: dict, key: str) -> float | None:
    try:
        return float(row[key]) if row.get(key) not in ("", None, "None") else None
    except ValueError:
        return None


def fig1() -> None:
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.axis("off")
    labels = [
        ("Structure builder", "ASE Atoms object", "#d9d9d9"),
        ("QE single-point SCF", "pw.x via ASE, SSSP PBE", "#9ecae1"),
        ("GP surrogate model", "Scikit-learn RBF kernel", "#a1d99b"),
        ("Acquisition (LCB)", "mean - kappa*std", "#fdae6b"),
        ("Inverse proposal", "differential evolution", "#fb6a4a"),
    ]
    x0, y, w, h, gap = 0.04, 0.60, 0.16, 0.18, 0.025
    centers = []
    for i, (title, sub, color) in enumerate(labels):
        x = x0 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=color, ec="black"))
        ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", weight="bold")
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=9)
        centers.append((x + w / 2, y + h / 2))
    for a, b in zip(centers, centers[1:]):
        ax.add_patch(FancyArrowPatch((a[0] + w / 2, a[1]), (b[0] - w / 2, b[1]), arrowstyle="->", mutation_scale=15))
    dx, dy = 0.48, 0.22
    ax.add_patch(Polygon([[dx, dy + 0.08], [dx + 0.10, dy], [dx, dy - 0.08], [dx - 0.10, dy]], fc="#fff7bc", ec="black"))
    ax.text(dx, dy, "Converged?", ha="center", va="center", weight="bold")
    ax.add_patch(FancyArrowPatch((centers[-1][0], y), (dx + 0.08, dy + 0.03), arrowstyle="->", mutation_scale=15))
    ax.add_patch(FancyArrowPatch((dx - 0.10, dy), (centers[1][0], y), connectionstyle="arc3,rad=-0.35", arrowstyle="->", mutation_scale=15))
    ax.text(0.78, 0.18, "50-workflow benchmark\nmetals, semiconductors, oxides\n2D materials, molecules\nbattery, surfaces, intermetallics", bbox=dict(boxstyle="round", fc="white", ec="gray"))
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig1_pipeline_schematic.png", dpi=300)
    plt.close(fig)


def fig2(rows: list[dict]) -> None:
    reps = ["bulk_cu", "bulk_si", "bulk_mgo", "graphene", "h2", "bulk_licoo2", "h_on_cu111", "bulk_srtio3", "bulk_nial"]
    by_key = {r["key"]: r for r in rows}
    reports = choose_report_by_key()
    fig, axes = plt.subplots(3, 3, figsize=(12, 10))
    for ax, key in zip(axes.ravel(), reps):
        hist = parse_history(reports[key].read_text(errors="ignore")) if key in reports else []
        if hist:
            calls = [h["n_qe"] for h in hist]
            energies = np.minimum.accumulate([h["energy"] for h in hist])
            std = [h["std"] for h in hist]
        else:
            row = by_key.get(key, {})
            calls = [int(f(row, "n_qe_total") or 0)]
            energies = [f(row, "best_energy_eV_per_atom") or np.nan]
            std = [f(row, "gp_uncertainty_eV") or np.nan]
        ax.plot(calls, energies, marker="o", color="tab:blue")
        ax.scatter(calls[-1], energies[-1], marker="*", s=120, color="red")
        ax.set_title(f"{key}\n{calls[-1]} QE calls", fontsize=10)
        ax.set_xlabel("DFT calls")
        ax.set_ylabel("Best energy")
        ax2 = ax.twinx()
        ax2.plot(calls, std, "--", color="tab:orange")
        ax2.set_ylabel("GP std", color="tab:orange")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig2_gp_convergence_panel.png", dpi=300)
    plt.close(fig)


def fig3(rows: list[dict]) -> None:
    plot = [r for r in rows if f(r, "best_param1") is not None and f(r, "lit_pbe_param1") is not None]
    fig, ax = plt.subplots(figsize=(8, 8))
    cats = list(dict.fromkeys(r["category"] for r in plot))
    cmap = plt.get_cmap("tab10")
    for i, cat in enumerate(cats):
        sub = [r for r in plot if r["category"] == cat]
        x = [f(r, "lit_pbe_param1") for r in sub]
        y = [f(r, "best_param1") for r in sub]
        sizes = [45 + 1000 * min(abs(f(r, "gp_uncertainty_eV") or 0), 0.05) for r in sub]
        ax.scatter(x, y, s=sizes, label=cat, color=cmap(i % 10), alpha=0.8, edgecolor="black")
        for r, xx, yy in zip(sub, x, y):
            err = f(r, "pct_error_param1")
            if err is not None and err > 3:
                ax.annotate(r["key"], (xx, yy), fontsize=7)
    lo = min(min(f(r, "lit_pbe_param1") for r in plot), min(f(r, "best_param1") for r in plot))
    hi = max(max(f(r, "lit_pbe_param1") for r in plot), max(f(r, "best_param1") for r in plot))
    xs = np.linspace(lo, hi, 200)
    ax.fill_between(xs, xs * 0.98, xs * 1.02, color="lightgray", alpha=0.35)
    ax.fill_between(xs, xs * 0.99, xs * 1.01, color="gray", alpha=0.25)
    ax.plot(xs, xs, "k--")
    ax.set_xlabel("PBE literature parameter")
    ax.set_ylabel("Pipeline prediction")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig3_parity_plot.png", dpi=300)
    plt.close(fig)


def fig4(grid: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, dim, baseline in [(axes[0], 1, 20), (axes[1], 2, 49)]:
        sub = [r for r in grid if int(r["dim"]) == dim and r["n_al_calls"]]
        x = np.arange(len(sub))
        al = [float(r["n_al_calls"]) for r in sub]
        ax.bar(x - 0.2, al, 0.4, label="Active learning")
        ax.bar(x + 0.2, [baseline] * len(sub), 0.4, label="Grid")
        ax.axhline(baseline, ls="--", color="black")
        ax.set_xticks(x)
        ax.set_xticklabels([r["key"] for r in sub], rotation=80, fontsize=7)
        savings = [f(r, "al_savings_pct") for r in sub if f(r, "al_savings_pct") is not None]
        if savings:
            ax.text(0.02, 0.95, f"Mean saving: {np.mean(savings):.1f}%", transform=ax.transAxes, va="top", bbox=dict(fc="white", ec="gray"))
        ax.set_title(f"{dim}D systems")
        ax.set_ylabel("DFT calls")
        ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig4_dft_savings.png", dpi=300)
    plt.close(fig)


def fig5(rows: list[dict]) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    labels, pbe_mean, pbe_std, exp_mean, exp_std = [], [], [], [], []
    for cat, group in grouped.items():
        pbe = [f(r, "pct_error_param1") for r in group if f(r, "pct_error_param1") is not None]
        exp = []
        for r in group:
            best, ref = f(r, "best_param1"), f(r, "exp_param1")
            if best is not None and ref not in (None, 0):
                exp.append(abs(best - ref) / abs(ref) * 100)
        labels.append(cat)
        pbe_mean.append(np.mean(pbe) if pbe else 0)
        pbe_std.append(np.std(pbe) if pbe else 0)
        exp_mean.append(np.mean(exp) if exp else 0)
        exp_std.append(np.std(exp) if exp else 0)
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(y - 0.18, pbe_mean, xerr=pbe_std, height=0.35, label="vs PBE")
    ax.barh(y + 0.18, exp_mean, xerr=exp_std, height=0.35, label="vs exp.")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Mean absolute error (%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig5_category_errors.png", dpi=300)
    plt.close(fig)


def fig6() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 5))
    for ax, name in zip(axes, ["cu", "licoo2", "mos2"]):
        path = RAW_DIR / f"grid_validation_{name}.csv"
        if not path.exists():
            ax.text(0.5, 0.5, "Grid validation\nnot run", ha="center", va="center", transform=ax.transAxes)
        else:
            with path.open(newline="", encoding="utf-8") as handle:
                data = list(csv.DictReader(handle))
            energy = np.minimum.accumulate([float(r["energy_eV_per_atom"]) for r in data])
            ax.plot(range(1, len(energy) + 1), energy, "r--", label="Grid")
        ax.set_title(name)
        ax.set_xlabel("DFT calls")
        ax.set_ylabel("Best energy")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig6_grid_validation.png", dpi=300)
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    rows = read_csv("all_results.csv")
    grid = read_csv("grid_search_comparison.csv")
    fig1(); fig2(rows); fig3(rows); fig4(grid); fig5(rows); fig6()
    print(f"Wrote figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
