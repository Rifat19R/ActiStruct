# Pseudopotentials

Do not commit pseudopotential files to this repository.

The QE scripts use SSSP 1.3.0 PBE efficiency pseudopotentials. Point
`ESPRESSO_PSEUDO` at your own local copy (see `docs/qe_setup.md`):

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
```

Required external files:

- `H.pbe-rrkjus_psl.1.0.0.UPF`
- `O.pbe-n-kjpaw_psl.0.1.UPF`
- `Mg.pbe-n-kjpaw_psl.0.3.0.UPF`
- `C.pbe-n-kjpaw_psl.1.0.0.UPF`
- `Cu.paw.z_11.ld1.psl.v1.0.0-low.upf`
- `Si.pbe-n-rrkjus_psl.1.0.0.UPF`
- `pt_pbe_v1.4.uspp.F.UPF`
- `li_pbe_v1.4.uspp.F.UPF`
- `Co_pbe_v1.2.uspp.F.UPF`

This directory may contain local copies for private runs, but `.gitignore`
keeps `*.UPF` and `*.upf` files out of GitHub.
