"""Quantum ESPRESSO reliability metadata parser.

The parser is intentionally text-based and dependency-free. It is designed for
completed and failed QE ``pw.x`` outputs, with optional QE input text used to
recover settings that are not always repeated in the output.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

RY_TO_EV = 13.605693122994


@dataclass(frozen=True)
class QEReliabilityRecord:
    """Structured metadata for one QE calculation."""

    material_id: str | None
    qe_input_path: str | None
    qe_output_path: str | None
    converged: bool
    job_done: bool
    scf_iterations: int | None
    final_energy_ry: float | None
    energy_ev: float | None
    max_force: float | None
    pressure_kbar: float | None
    wall_time: str | None
    failure_reason: str | None
    ecutwfc: float | None
    ecutrho: float | None
    kpoints: str | None
    smearing: str | None
    mixing_beta: float | None
    pseudo_family: str | None
    pseudopotentials: dict[str, str] = field(default_factory=dict)
    calculation_hash: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_qe_output_file(
    output_path: str | Path,
    input_path: str | Path | None = None,
    material_id: str | None = None,
) -> QEReliabilityRecord:
    """Parse QE output from disk, with optional matching input file."""

    output = Path(output_path)
    input_text = None
    if input_path is not None:
        input_text = Path(input_path).read_text(encoding="utf-8", errors="replace")
    return parse_qe_output_text(
        output.read_text(encoding="utf-8", errors="replace"),
        input_text=input_text,
        material_id=material_id,
        qe_output_path=str(output),
        qe_input_path=str(input_path) if input_path is not None else None,
    )


def parse_qe_output_text(
    output_text: str,
    input_text: str | None = None,
    material_id: str | None = None,
    qe_output_path: str | None = None,
    qe_input_path: str | None = None,
) -> QEReliabilityRecord:
    """Parse QE output text into reliability metadata."""

    settings_text = "\n".join(part for part in (input_text, output_text) if part)
    final_energy_ry = _last_float(
        output_text,
        r"!\s+total energy\s+=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+Ry",
    )
    if final_energy_ry is None:
        final_energy_ry = _last_float(
            output_text,
            r"\btotal energy\s+=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+Ry",
        )

    job_done = "JOB DONE" in output_text
    converged = job_done and "convergence NOT achieved" not in output_text
    scf_iterations = _parse_scf_iterations(output_text)
    max_force = _last_float(
        output_text,
        r"Total force\s+=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)",
    )
    pressure_kbar = _last_float(
        output_text,
        r"P=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)",
    )
    failure_reason = _failure_reason(output_text, job_done, converged)
    ecutwfc = _setting_float(settings_text, "ecutwfc")
    ecutrho = _setting_float(settings_text, "ecutrho")
    mixing_beta = _setting_float(settings_text, "mixing_beta")
    pseudopotentials = _parse_pseudopotentials(settings_text)

    return QEReliabilityRecord(
        material_id=material_id,
        qe_input_path=qe_input_path,
        qe_output_path=qe_output_path,
        converged=converged,
        job_done=job_done,
        scf_iterations=scf_iterations,
        final_energy_ry=final_energy_ry,
        energy_ev=final_energy_ry * RY_TO_EV if final_energy_ry is not None else None,
        max_force=max_force,
        pressure_kbar=pressure_kbar,
        wall_time=_parse_wall_time(output_text),
        failure_reason=failure_reason,
        ecutwfc=ecutwfc,
        ecutrho=ecutrho,
        kpoints=_parse_kpoints(settings_text),
        smearing=_setting_string(settings_text, "smearing"),
        mixing_beta=mixing_beta,
        pseudo_family=_pseudo_family(pseudopotentials),
        pseudopotentials=pseudopotentials,
        calculation_hash=_calculation_hash(output_text, input_text),
    )


def _last_float(text: str, pattern: str) -> float | None:
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    return float(matches[-1]) if matches else None


def _setting_float(text: str, name: str) -> float | None:
    return _last_float(
        text,
        rf"\b{name}\s*=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)",
    )


def _setting_string(text: str, name: str) -> str | None:
    matches = re.findall(
        rf"\b{name}\s*=\s*['\"]?([A-Za-z0-9_.+-]+)['\"]?",
        text,
        flags=re.IGNORECASE,
    )
    return matches[-1] if matches else None


def _parse_scf_iterations(text: str) -> int | None:
    matches = re.findall(
        r"convergence has been achieved in\s+(\d+)\s+iterations",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        return int(matches[-1])
    iteration_numbers = re.findall(r"iteration\s+#\s*(\d+)", text, flags=re.IGNORECASE)
    if iteration_numbers:
        return max(int(item) for item in iteration_numbers)
    return None


def _parse_wall_time(text: str) -> str | None:
    matches = re.findall(
        r"PWSCF\s*:\s*.*?CPU\s+([^\n]+?WALL)",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        return " ".join(matches[-1].split())
    return None


def _failure_reason(text: str, job_done: bool, converged: bool) -> str | None:
    if converged:
        return None
    if "convergence NOT achieved" in text:
        return "scf_not_converged"
    if "could not find namelist" in text:
        return "invalid_input_namelist"
    if "Error in routine" in text or "from " in text and "error #" in text:
        return "qe_error"
    if not job_done:
        return "job_not_completed"
    return "unknown_failure"


def _parse_pseudopotentials(text: str) -> dict[str, str]:
    pseudos: dict[str, str] = {}
    in_species = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        upper = line.upper()
        if upper.startswith("ATOMIC_SPECIES"):
            in_species = True
            continue
        if in_species and (not line or upper.startswith(("ATOMIC_POSITIONS", "K_POINTS", "CELL_PARAMETERS"))):
            in_species = False
            continue
        if in_species:
            parts = line.split()
            if len(parts) >= 3:
                pseudos[parts[0]] = parts[2]
    if pseudos:
        return pseudos

    for symbol, pseudo in re.findall(
        r"PseudoPot\.\s+#\s*\d+\s+for\s+([A-Za-z][a-z]?)\s+read from file:\s+(\S+)",
        text,
    ):
        pseudos[symbol] = Path(pseudo).name
    return pseudos


def _parse_kpoints(text: str) -> str | None:
    match = re.search(
        r"K_POINTS\s+automatic\s*\n\s*([0-9]+\s+[0-9]+\s+[0-9]+(?:\s+[0-9]+\s+[0-9]+\s+[0-9]+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return " ".join(match.group(1).split())

    match = re.search(
        r"number of k points=\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)} k-points"
    return None


def _pseudo_family(pseudos: dict[str, str]) -> str | None:
    if not pseudos:
        return None
    names = " ".join(pseudos.values()).lower()
    if "sssp" in names:
        return "SSSP"
    if "psl" in names:
        return "PSLibrary"
    if "oncv" in names:
        return "ONCV"
    if "paw" in names:
        return "PAW"
    if "uspp" in names or "rrkjus" in names:
        return "USPP"
    return "mixed_or_unknown"


def _calculation_hash(output_text: str, input_text: str | None) -> str:
    hasher = hashlib.sha256()
    if input_text:
        hasher.update(input_text.encode("utf-8", errors="replace"))
    hasher.update(output_text.encode("utf-8", errors="replace"))
    return hasher.hexdigest()

