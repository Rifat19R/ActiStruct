# Quantum ESPRESSO Setup

## WSL Environment

```bash
cd /mnt/d/Rifat_kh/inverse_active
source .venv/bin/activate
which pw.x
```

Scripts also fall back to:

```text
/home/alchemist/q-e/bin/pw.x
```

## Pseudopotentials

QE scripts use SSSP 1.3.0 PBE efficiency pseudopotentials:

```text
/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency
```

| Workflow | Pseudopotential |
| --- | --- |
| H2 QE | `H.pbe-rrkjus_psl.1.0.0.UPF` |
| H2O QE | `H.pbe-rrkjus_psl.1.0.0.UPF`, `O.pbe-n-kjpaw_psl.0.1.UPF` |
| CH4 QE | `C.pbe-n-kjpaw_psl.1.0.0.UPF`, `H.pbe-rrkjus_psl.1.0.0.UPF` |
| Graphene QE | `C.pbe-n-kjpaw_psl.1.0.0.UPF` |
| Bulk Cu QE | `Cu.paw.z_11.ld1.psl.v1.0.0-low.upf` |
| Bulk Si QE | `Si.pbe-n-rrkjus_psl.1.0.0.UPF` |
| Bulk MgO QE | `Mg.pbe-n-kjpaw_psl.0.3.0.UPF`, `O.pbe-n-kjpaw_psl.0.1.UPF` |
| H/Pt(111) QE | `pt_pbe_v1.4.uspp.F.UPF`, `H.pbe-rrkjus_psl.1.0.0.UPF` |
| Bulk LiCoO2 QE | `li_pbe_v1.4.uspp.F.UPF`, `Co_pbe_v1.2.uspp.F.UPF`, `O.pbe-n-kjpaw_psl.0.1.UPF` |
| H/Cu(111) QE | `Cu.paw.z_11.ld1.psl.v1.0.0-low.upf`, `H.pbe-rrkjus_psl.1.0.0.UPF` |

## QE Parameters

### H2 QE

```text
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts = (1, 1, 1)
box = 10 A
```

The isolated H atom reference is spin-polarized.

### H2O QE

```text
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts = (1, 1, 1)
box = 10 A
smearing = gaussian
degauss = 0.01 Ry
```

### CH4 QE

```text
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts = (1, 1, 1)
box = 10 A
smearing = gaussian
degauss = 0.01 Ry
electron_maxstep = 200
spin = unpolarized
```

### Graphene QE

```text
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts = (8, 8, 1)
vacuum = 15 A
smearing = gaussian
degauss = 0.02 Ry
```

### Bulk Cu QE

```text
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts = (12, 12, 12)
smearing = gaussian
degauss = 0.02 Ry
```

### Bulk Si QE

```text
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts = (8, 8, 8)
smearing = gaussian
degauss = 0.01 Ry
```

### Bulk MgO QE

```text
ecutwfc = 60 Ry
ecutrho = 480 Ry
kpts = (8, 8, 8)
smearing = gaussian
degauss = 0.01 Ry
electron_maxstep = 300
```

### H/Pt(111) QE

```text
Pt(111) slab = p(2x2), 3 layers, 12 Pt atoms
adsorbate = 1 H atom
ecutwfc = 60 Ry
ecutrho = 480 Ry
kpts slab = (4, 4, 1)
kpts H atom = (1, 1, 1)
vacuum = 15 A
smearing = mv
degauss = 0.02 Ry
electron_maxstep = 300
```

The clean slab and spin-polarized H atom reference are cached. Adsorbed
structures fix Pt atoms and H x/y while allowing H z to relax by ASE BFGS.

### Bulk LiCoO2 QE

```text
cell = R-3m hexagonal setting, 12 atoms = 3 Li + 3 Co + 6 O
design variables = a, c
oxygen internal z = 0.241
ecutwfc = 60 Ry
ecutrho = 480 Ry
kpts = (4, 4, 2)
smearing = gaussian
degauss = 0.01 Ry
electron_maxstep = 300
spin polarized = yes
Co initial moment = 0.6 mu_B
```

### H/Cu(111) QE

```text
Cu(111) slab = p(2x2), 3 layers, 12 Cu atoms
adsorbate = 1 H atom
ecutwfc = 50 Ry
ecutrho = 400 Ry
kpts slab = (4, 4, 1)
kpts H atom = (1, 1, 1)
vacuum = 15 A
smearing = mv
degauss = 0.02 Ry
electron_maxstep = 300
```

The clean slab and spin-polarized H atom reference are cached. Clean and
adsorbed slabs fix the bottom Cu layer. Adsorbed structures relax H and the
top two Cu layers with ASE BFGS.

## Generated Files

```text
outputs/plots/
outputs/reports/
outputs/qe_runs/
outputs/qe_runs_ch4/
outputs/qe_runs_h2o/
outputs/qe_runs_graphene/
outputs/qe_runs_bulk_cu/
outputs/qe_runs_bulk_si/
outputs/qe_runs_bulk_mgo/
outputs/qe_runs_h_pt111/
outputs/qe_runs_bulk_licoo2/
outputs/qe_runs_h_cu111/
```

These are ignored by git.
