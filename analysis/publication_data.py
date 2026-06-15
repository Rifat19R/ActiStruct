from __future__ import annotations

import ast
import glob
import math
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path("<ACTISTRUCT_ROOT>")
REPORT_DIR = ROOT / "outputs" / "reports"
OUTPUT_DIR = ROOT / "analysis" / "outputs"
RAW_DIR = OUTPUT_DIR / "raw"
TABLE_DIR = OUTPUT_DIR / "tables"
FIGURE_DIR = OUTPUT_DIR / "figures"
SI_FIGURE_DIR = OUTPUT_DIR / "si_figures"


@dataclass(frozen=True)
class Material:
    key: str
    category: str
    material_name: str
    dim: int
    variable: str
    lit_pbe_param1: float | None
    lit_pbe_param2: float | None = None
    exp_param1: float | None = None
    exp_param2: float | None = None
    source: str = ""


MATERIALS: dict[str, Material] = {
    "bulk_al": Material("bulk_al", "FCC metals", "Al (FCC)", 1, "a", 4.042, exp_param1=4.046, source="Haas2009"),
    "bulk_cu": Material("bulk_cu", "FCC metals", "Cu (FCC)", 1, "a", 3.634, exp_param1=3.615, source="Haas2009"),
    "bulk_ni": Material("bulk_ni", "FCC metals", "Ni (FCC)", 1, "a", 3.524, exp_param1=3.524, source="Haas2009"),
    "bulk_ag": Material("bulk_ag", "FCC metals", "Ag (FCC)", 1, "a", 4.154, exp_param1=4.085, source="Haas2009"),
    "bulk_au": Material("bulk_au", "FCC metals", "Au (FCC)", 1, "a", 4.174, exp_param1=4.078, source="Haas2009"),
    "bulk_fe_bcc": Material("bulk_fe_bcc", "BCC metals", "Fe (BCC)", 1, "a", 2.832, exp_param1=2.870, source="Haas2009"),
    "bulk_mo_bcc": Material("bulk_mo_bcc", "BCC metals", "Mo (BCC)", 1, "a", 3.168, exp_param1=3.147, source="Haas2009"),
    "bulk_w_bcc": Material("bulk_w_bcc", "BCC metals", "W (BCC)", 1, "a", 3.185, exp_param1=3.165, source="Haas2009"),
    "bulk_si": Material("bulk_si", "Semiconductors", "Si (diamond)", 1, "a", 5.468, exp_param1=5.431, source="Haas2009"),
    "bulk_ge": Material("bulk_ge", "Semiconductors", "Ge (diamond)", 1, "a", 5.766, exp_param1=5.658, source="Haas2009"),
    "bulk_gaas": Material("bulk_gaas", "Semiconductors", "GaAs", 1, "a", 5.750, exp_param1=5.653, source="Haas2009"),
    "bulk_alas": Material("bulk_alas", "Semiconductors", "AlAs", 1, "a", 5.731, exp_param1=5.660, source="Haas2009"),
    "bulk_inp": Material("bulk_inp", "Semiconductors", "InP", 1, "a", 5.969, exp_param1=5.869, source="Haas2009"),
    "bulk_sic": Material("bulk_sic", "Semiconductors", "SiC", 1, "a", 4.380, exp_param1=4.360, source="Haas2009"),
    "bulk_mgo": Material("bulk_mgo", "Ionic oxides", "MgO", 1, "a", 4.258, exp_param1=4.211, source="Haas2009"),
    "bulk_cao": Material("bulk_cao", "Ionic oxides", "CaO", 1, "a", 4.820, exp_param1=4.811, source="Haas2009"),
    "bulk_zno": Material("bulk_zno", "Ionic oxides", "ZnO", 2, "a,c", 3.282, 5.307, 3.250, 5.207, "Serrano2004"),
    "bulk_tio2_rutile": Material("bulk_tio2_rutile", "Ionic oxides", "TiO2 rutile", 2, "a,c", 4.653, 2.970, 4.594, 2.958, "Labat2007"),
    "bulk_al2o3": Material("bulk_al2o3", "Ionic oxides", "Al2O3", 1, "a", 4.806, exp_param1=4.758, source="Digne2004"),
    "bulk_sio2": Material("bulk_sio2", "Ionic oxides", "SiO2 alpha-quartz", 2, "a,c", 5.025, 5.525, 4.916, 5.406, "Demuth1999"),
    "graphene": Material("graphene", "2D materials", "Graphene", 1, "a", 2.468, exp_param1=2.461, source="Lui2011"),
    "hbn": Material("hbn", "2D materials", "h-BN", 1, "a", 2.512, exp_param1=2.504, source="Pease1950"),
    "silicene": Material("silicene", "2D materials", "Silicene", 1, "a", 3.866, source="Cahangirov2009"),
    "mos2": Material("mos2", "2D materials", "MoS2", 1, "a", 3.190, exp_param1=3.160, source="Mak2010"),
    "ws2": Material("ws2", "2D materials", "WS2", 1, "a", 3.190, exp_param1=3.153, source="Zhao2013"),
    "aln_2d": Material("aln_2d", "2D materials", "2D AlN", 1, "a", 3.126, source="Tsipas2013"),
    "h2": Material("h2", "Molecules", "H2", 1, "bond", 0.750, exp_param1=0.741, source="NIST"),
    "n2": Material("n2", "Molecules", "N2", 1, "bond", 1.101, exp_param1=1.098, source="NIST"),
    "co": Material("co", "Molecules", "CO", 1, "bond", 1.144, exp_param1=1.128, source="NIST"),
    "h2o": Material("h2o", "Molecules", "H2O", 1, "bond", 0.971, exp_param1=0.958, source="NIST"),
    "nh3": Material("nh3", "Molecules", "NH3", 1, "bond", 1.024, exp_param1=1.012, source="NIST"),
    "ch4": Material("ch4", "Molecules", "CH4", 1, "bond", 1.097, exp_param1=1.087, source="NIST"),
    "bulk_licoo2": Material("bulk_licoo2", "Battery materials", "LiCoO2", 2, "a,c", 2.820, 14.10, source="Wolverton1998"),
    "bulk_nacoo2": Material("bulk_nacoo2", "Battery materials", "NaCoO2", 2, "a,c", 2.845, 15.66, source="Meng2004"),
    "bulk_limnpo4": Material("bulk_limnpo4", "Battery materials", "LiMnPO4", 1, "b", 5.985, source="Kim2008"),
    "bulk_limn2o4": Material("bulk_limn2o4", "Battery materials", "LiMn2O4", 1, "a", 8.246, source="Benedek2011"),
    "bulk_litio2": Material("bulk_litio2", "Battery materials", "LiTiO2", 1, "a", 4.148, source="Perez2012"),
    "bulk_srtio3": Material("bulk_srtio3", "Battery materials", "SrTiO3", 1, "a", 3.942, source="Bousquet2010"),
    "bulk_batio3": Material("bulk_batio3", "Battery materials", "BaTiO3", 1, "a", 4.036, source="Bilc2008"),
    "bulk_cspbi3": Material("bulk_cspbi3", "Battery materials", "CsPbI3", 1, "a", 6.296, exp_param1=6.18, source="Brivio2015"),
    "h_on_cu111": Material("h_on_cu111", "Surface adsorption", "H/Cu(111)", 1, "height", 1.00, source="Michaelides2003"),
    "o_on_cu111": Material("o_on_cu111", "Surface adsorption", "O/Cu(111)", 1, "height", 0.85, source="Grabow2010"),
    "co_on_cu111": Material("co_on_cu111", "Surface adsorption", "CO/Cu(111)", 1, "height", 1.90, source="Grabow2010"),
    "h_on_ni111": Material("h_on_ni111", "Surface adsorption", "H/Ni(111)", 1, "height", 1.00, source="Michaelides2003"),
    "o_on_ni111": Material("o_on_ni111", "Surface adsorption", "O/Ni(111)", 1, "height", 1.10, source="Hammer1999"),
    "co_on_ni111": Material("co_on_ni111", "Surface adsorption", "CO/Ni(111)", 1, "height", 1.82, source="Hammer1999"),
    "h_on_pt111": Material("h_on_pt111", "Surface adsorption", "H/Pt(111)", 1, "height", 1.10, source="Michaelides2003"),
    "co_on_pt111": Material("co_on_pt111", "Surface adsorption", "CO/Pt(111)", 1, "height", 1.85, source="Gajdos2004"),
    "bulk_nial": Material("bulk_nial", "Heusler/intermetallic", "NiAl", 1, "a", 2.885, exp_param1=2.887, source="Zou2012"),
    "bulk_co2feal": Material("bulk_co2feal", "Heusler/intermetallic", "Co2FeAl", 1, "a", 5.730, exp_param1=5.730, source="Picozzi2002"),
}


ALIASES = {
    "bulk_cu_generated": "bulk_cu",
    "bulk_fe": "bulk_fe_bcc",
    "bulk_mo": "bulk_mo_bcc",
    "bulk_w": "bulk_w_bcc",
    "bulk_si_generated": "bulk_si",
    "bulk_mgo_generated": "bulk_mgo",
    "graphene_generated": "graphene",
    "h2_generated": "h2",
    "h2o_generated": "h2o",
    "ch4_generated": "ch4",
    "bulk_licoo2_generated": "bulk_licoo2",
    "bulk_tio2": "bulk_tio2_rutile",
}


VARIABLE_RANGES = {
    "bulk_al": {"dim": 1, "a": (3.8, 4.3)}, "bulk_cu": {"dim": 1, "a": (3.4, 3.8)},
    "bulk_ni": {"dim": 1, "a": (3.3, 3.7)}, "bulk_ag": {"dim": 1, "a": (3.9, 4.3)},
    "bulk_au": {"dim": 1, "a": (3.9, 4.3)}, "bulk_fe_bcc": {"dim": 1, "a": (2.65, 3.05)},
    "bulk_mo_bcc": {"dim": 1, "a": (3.0, 3.3)}, "bulk_w_bcc": {"dim": 1, "a": (3.0, 3.3)},
    "bulk_si": {"dim": 1, "a": (5.2, 5.6)}, "bulk_ge": {"dim": 1, "a": (5.45, 5.85)},
    "bulk_gaas": {"dim": 1, "a": (5.45, 5.85)}, "bulk_alas": {"dim": 1, "a": (5.45, 5.85)},
    "bulk_inp": {"dim": 1, "a": (5.65, 6.05)}, "bulk_sic": {"dim": 1, "a": (4.2, 4.55)},
    "bulk_mgo": {"dim": 1, "a": (4.0, 4.35)}, "bulk_cao": {"dim": 1, "a": (4.65, 5.05)},
    "bulk_zno": {"dim": 2, "a": (3.1, 3.4), "c": (5.0, 5.8)}, "bulk_tio2_rutile": {"dim": 2, "a": (4.45, 4.75), "c": (2.75, 3.15)},
    "bulk_al2o3": {"dim": 1, "a": (4.65, 4.9)}, "bulk_sio2": {"dim": 2, "a": (4.85, 5.15), "c": (5.35, 5.70)},
    "graphene": {"dim": 1, "a": (2.3, 2.7)}, "hbn": {"dim": 1, "a": (2.35, 2.65)},
    "silicene": {"dim": 1, "a": (3.7, 4.05)}, "mos2": {"dim": 1, "a": (3.05, 3.3)},
    "ws2": {"dim": 1, "a": (3.05, 3.3)}, "aln_2d": {"dim": 1, "a": (3.0, 3.25)},
    "h2": {"dim": 1, "a": (0.55, 1.2)}, "n2": {"dim": 1, "a": (0.9, 1.35)},
    "co": {"dim": 1, "a": (0.95, 1.35)}, "h2o": {"dim": 1, "a": (0.85, 1.08)},
    "nh3": {"dim": 1, "a": (0.92, 1.15)}, "ch4": {"dim": 1, "a": (0.95, 1.22)},
    "bulk_licoo2": {"dim": 2, "a": (2.76, 2.88), "c": (13.7, 14.5)}, "bulk_nacoo2": {"dim": 2, "a": (2.78, 2.92), "c": (15.0, 16.3)},
    "bulk_limnpo4": {"dim": 1, "a": (5.9, 6.3)}, "bulk_limn2o4": {"dim": 1, "a": (7.9, 8.4)},
    "bulk_litio2": {"dim": 1, "a": (4.0, 4.3)}, "bulk_srtio3": {"dim": 1, "a": (3.75, 4.05)},
    "bulk_batio3": {"dim": 1, "a": (3.9, 4.15)}, "bulk_cspbi3": {"dim": 1, "a": (6.0, 6.5)},
    "h_on_cu111": {"dim": 1, "a": (0.85, 1.15)}, "o_on_cu111": {"dim": 1, "a": (0.75, 0.95)},
    "co_on_cu111": {"dim": 1, "a": (1.8, 2.0)}, "h_on_ni111": {"dim": 1, "a": (0.85, 1.15)},
    "o_on_ni111": {"dim": 1, "a": (1.0, 1.2)}, "co_on_ni111": {"dim": 1, "a": (1.72, 1.92)},
    "h_on_pt111": {"dim": 1, "a": (0.95, 1.2)}, "co_on_pt111": {"dim": 1, "a": (1.75, 1.95)},
    "bulk_nial": {"dim": 1, "a": (2.75, 3.05)}, "bulk_co2feal": {"dim": 1, "a": (5.5, 5.9)},
}


def ensure_dirs() -> None:
    for path in (RAW_DIR, TABLE_DIR, FIGURE_DIR, SI_FIGURE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def normalize_key(raw: str) -> str | None:
    key = raw.strip()
    for suffix in (
        "_qe_active_inverse_report", "_active_inverse_report", "_qe_run_report",
        "_run_report", "_report", "_energy_curve", "_convergence",
    ):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    key = key.replace("_4_qe", "").replace("_8_qe", "")
    key = ALIASES.get(key, key)
    return key if key in MATERIALS else None


def report_files() -> list[Path]:
    patterns = [
        str(REPORT_DIR / "*_report.txt"),
        str(REPORT_DIR / "*_active_inverse_report.txt"),
        str(REPORT_DIR / "*report*.txt"),
    ]
    seen: dict[Path, None] = {}
    for pattern in patterns:
        for item in glob.glob(pattern):
            seen[Path(item)] = None
    return sorted(seen)


def choose_report_by_key() -> dict[str, Path]:
    selected: dict[str, Path] = {}
    scores: dict[str, tuple[int, float]] = {}
    for path in report_files():
        text = path.read_text(errors="ignore")
        key_match = re.search(r"^Key:\s*([A-Za-z0-9_]+)", text, re.MULTILINE)
        raw_key = key_match.group(1) if key_match else path.stem
        key = normalize_key(raw_key) or normalize_key(path.stem)
        if key is None:
            continue
        score = 0
        if "Computed quantity:" in text:
            score += 10
        if path.name.endswith("_report.txt"):
            score += 2
        if "FINAL RESULT" in text:
            score += 2
        score_tuple = (score, path.stat().st_mtime)
        if key not in selected or score_tuple > scores[key]:
            selected[key] = path
            scores[key] = score_tuple
    return selected


def parse_variables(text: str) -> dict[str, tuple[float, float]]:
    match = re.search(r"^Variables:\s*(\{.*\})", text, re.MULTILINE)
    if not match:
        return {}
    try:
        return ast.literal_eval(match.group(1))
    except Exception:
        return {}


def parse_best_params(text: str) -> dict[str, float]:
    patterns = [
        r"Best parameters\s*:\s*([^\n]+)",
        r"Best:\s*([A-Za-z_][^\n]*?)\s+E=",
        r"Best observed:\s*([^,\n]+(?:,\s*[^,\n]+)*)",
    ]
    params: dict[str, float] = {}
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        chunk = match.group(1)
        for name, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([-+]?\d+(?:\.\d+)?)", chunk):
            params[name] = float(value)
        if params:
            return params
    # Old final-line fallbacks.
    for label, name in [("Best lattice constant", "a"), ("Best distance", "bond")]:
        match = re.search(label + r"[:\s]+([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if match:
            params[name] = float(match.group(1))
    return params


def params_to_material_values(key: str, params: dict[str, float]) -> tuple[float | None, float | None]:
    meta = MATERIALS[key]
    p1 = None
    p2 = None
    if "a" in params:
        p1 = params["a"]
    elif "b" in params:
        p1 = params["b"]
    elif "bond" in params:
        p1 = params["bond"]
    elif "height" in params:
        p1 = params["height"]
    elif "distance" in params:
        p1 = params["distance"]

    if meta.dim == 2:
        if "c" in params:
            p2 = params["c"]
        elif "c_over_a" in params and p1 is not None:
            p2 = p1 * params["c_over_a"]
        elif "layer_half_thickness" in params:
            p2 = params["layer_half_thickness"]
    return p1, p2


def parse_energy(text: str) -> float | None:
    patterns = [
        r"Best .*?objective:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV",
        r"Best QE energy per atom[:\s]+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV",
        r"Best .*?E=([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return float(matches[-1])
    return None


def parse_gp_std(text: str) -> float | None:
    patterns = [
        r"GP uncertainty\s*:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV",
        r"GP std=([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        r"GP uncertainty at best[^:]*:[:\s]+([\d.eE+-]+)\s*eV",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return float(matches[-1])
    return None


def parse_n_qe(text: str) -> int | None:
    patterns = [
        r"Total QE calls\s*:\s*(\d+)",
        r"Successful QE evaluations[:\s]+(\d+)",
        r"QE labels=(\d+)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return int(matches[-1])
    return None


def parse_iterations(text: str) -> int:
    matches = re.findall(r"^Iteration\s+(\d+)\s*$", text, flags=re.MULTILINE)
    return max([int(x) for x in matches], default=0)


def parse_converged(text: str) -> bool:
    return bool(re.search(r"Converged|Converged\.|\xe2\x9c\x93 Converged", text, re.IGNORECASE))


def parse_history(text: str) -> list[dict[str, float]]:
    rows = []
    for match in re.finditer(
        r"Best:\s*(.*?)\s+E=([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV\s+GP std=([\d.eE+-]+)\s*eV\s+QE labels=(\d+)",
        text,
    ):
        rows.append({
            "params": match.group(1),
            "energy": float(match.group(2)),
            "std": float(match.group(3)),
            "n_qe": int(match.group(4)),
        })
    return rows


def parse_labeled_points(text: str) -> tuple[list[list[float]], list[float]]:
    x_rows: list[list[float]] = []
    y_rows: list[float] = []
    for match in re.finditer(
        r"Added (?:AL|ID|inverse)[:\s]+(.*?)\s*->\s*E(?:/atom)?=([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV",
        text,
    ):
        params = [float(v) for _, v in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([-+]?\d+(?:\.\d+)?)", match.group(1))]
        if params:
            x_rows.append(params)
            y_rows.append(float(match.group(2)))
    return x_rows, y_rows


def pct_error(pred: float | None, ref: float | None) -> float | None:
    if pred is None or ref in (None, 0):
        return None
    return abs(pred - ref) / abs(ref) * 100.0
