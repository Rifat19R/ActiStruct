from __future__ import annotations

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from publication_data import RAW_DIR, SI_FIGURE_DIR, choose_report_by_key, ensure_dirs, parse_history


def main() -> None:
    ensure_dirs()
    with (RAW_DIR / "all_results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    reports = choose_report_by_key()
    for idx, row in enumerate(rows, start=1):
        fig, ax = plt.subplots(figsize=(8, 5))
        hist = parse_history(reports[row["key"]].read_text(errors="ignore")) if row["key"] in reports else []
        if hist:
            calls = [h["n_qe"] for h in hist]
            energy = np.minimum.accumulate([h["energy"] for h in hist])
            ax.plot(calls, energy, "k-o", label="Best observed")
        else:
            ax.text(0.5, 0.5, "No convergence history parsed", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{row['key']}: parameter={row['best_param1'] or '--'}, DFT calls={row['n_qe_total'] or '--'}")
        ax.set_xlabel("DFT calls")
        ax.set_ylabel("Best energy")
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(SI_FIGURE_DIR / f"SI_figure_{idx:02d}_{row['key']}.png", dpi=300)
        plt.close(fig)
    print(f"Wrote SI figures to {SI_FIGURE_DIR}")


if __name__ == "__main__":
    main()
