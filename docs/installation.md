# Installation

## Core and tests

ActiStruct supports Python 3.10 or newer. CI tests Python 3.11 and 3.12.

```bash
git clone https://github.com/Rifat19R/ActiStruct.git
cd ActiStruct
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -c "import actistruct; print(actistruct.__version__)"
python -m pytest -q
```

PyTorch is a core dependency because the GNN surrogate is part of the
installed package. On systems that need a specific CPU or CUDA wheel, install
PyTorch from its appropriate package index before installing ActiStruct.

## Convenience requirements file

`pyproject.toml` is authoritative. `requirements.txt` is a convenience entry
point for a full local development and dashboard environment:

```bash
python -m pip install -r requirements.txt
```

## Conda environment

`environment.yml` pins the scientific Python base used for reproducibility.
It does not bundle Quantum ESPRESSO or pseudopotential binaries.

```bash
conda env create -f environment.yml
conda activate actistruct
python -m pip install -e ".[test]"
```

## Optional dashboard

```bash
python -m pip install -e ".[dashboard]"
streamlit run actistruct/dashboard/app.py
```

## Live Quantum ESPRESSO workflows

QE is external to the Python package. Live runs require Linux/WSL or a
compatible cluster environment, a reviewed `pw.x` installation, MPI where
appropriate, and the exact pseudopotential family specified by the workflow.

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
which pw.x
```

Read `pseudo/README.md`, `configs/pseudo_manifest_required.yaml`, and
[reproducibility](reproducibility.md) before launching DFT. Normal installation
and tests do not run QE.
