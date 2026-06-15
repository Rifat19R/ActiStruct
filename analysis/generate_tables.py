from __future__ import annotations

import csv

from publication_data import RAW_DIR, TABLE_DIR, ensure_dirs


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def esc(text: str) -> str:
    return str(text).replace("_", "\\_")


def f(value: str) -> float | None:
    try:
        return float(value) if value not in ("", "None") else None
    except ValueError:
        return None


def table1(rows: list[dict]) -> str:
    lines = ["\\begin{tabular}{llllrrrl}", "\\toprule", "System & Category & Dim & Pred. & PBE Lit. & $|\\Delta|$ (\\%) & Exp. & DFT calls \\\\", "\\midrule"]
    last = None
    for row in sorted(rows, key=lambda r: (r["category"], r["key"])):
        if last is not None and row["category"] != last:
            lines.append("\\midrule")
        pred = "--" if f(row["best_param1"]) is None else f"{f(row['best_param1']):.4f}"
        lit = "--" if f(row["lit_pbe_param1"]) is None else f"{f(row['lit_pbe_param1']):.4f}"
        exp = "--" if f(row["exp_param1"]) is None else f"{f(row['exp_param1']):.4f}"
        err = "--" if f(row["pct_error_param1"]) is None else f"{f(row['pct_error_param1']):.2f}"
        calls = row["n_qe_total"] or "--"
        line = f"{esc(row['key'])} & {esc(row['category'])} & {row['dim']} & {pred} & {lit} & {err} & {exp} & {calls} \\\\"
        if f(row["pct_error_param1"]) is not None and f(row["pct_error_param1"]) > 3:
            line = "\\textbf{" + line[:-2] + "} \\\\"
        lines.append(line)
        last = row["category"]
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines)


def table2(rows: list[dict]) -> str:
    counts = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    defaults = {
        "FCC metals": ("50-70", "400-560", "12x12x12", "mv"),
        "BCC metals": ("70", "560", "14x14x14", "mv"),
        "Semiconductors": ("50-60", "400-480", "8x8x8", "gaussian"),
        "Ionic oxides": ("70", "560", "6-10", "gaussian"),
        "2D materials": ("50-70", "400-560", "6-8x6-8x1", "gaussian"),
        "Molecules": ("50-60", "400-480", "1x1x1", "gaussian"),
        "Battery materials": ("50-70", "400-560", "2-6", "gaussian/mv"),
        "Surface adsorption": ("70", "560", "4x4x1", "mv"),
        "Heusler/intermetallic": ("70", "560", "8-10", "mv"),
    }
    lines = ["\\begin{tabular}{lrrrrl}", "\\toprule", "Category & N & ecutwfc & ecutrho & k-mesh & Smearing \\\\", "\\midrule"]
    for cat, count in counts.items():
        e1, e2, kmesh, smear = defaults.get(cat, ("--", "--", "--", "--"))
        lines.append(f"{esc(cat)} & {count} & {e1} & {e2} & {kmesh} & {smear} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines)


def table3(rows: list[dict]) -> str:
    lines = ["\\begin{tabular}{lrrrrr}", "\\toprule", "Category & N & MAE PBE (\\%) & MAE Exp. (\\%) & Mean DFT calls & Converged (\\%) \\\\", "\\midrule"]
    for row in rows:
        if row["category"].startswith("Overall") and row["category"] != "Overall":
            continue
        lines.append(f"{esc(row['category'])} & {row['n_systems']} & {float(row['mean_abs_error_pbe'] or 0):.2f} & {float(row['mean_abs_error_exp'] or 0):.2f} & {float(row['mean_n_qe'] or 0):.1f} & {float(row['pct_converged'] or 0):.1f} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    results = read_csv(RAW_DIR / "all_results.csv")
    stats = read_csv(TABLE_DIR / "statistics_summary.csv")
    (TABLE_DIR / "table1_results.tex").write_text(table1(results), encoding="utf-8")
    (TABLE_DIR / "table2_settings.tex").write_text(table2(results), encoding="utf-8")
    (TABLE_DIR / "table3_statistics.tex").write_text(table3(stats), encoding="utf-8")
    print(f"Wrote tables to {TABLE_DIR}")


if __name__ == "__main__":
    main()
