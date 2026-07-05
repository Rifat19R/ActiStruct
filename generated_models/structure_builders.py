"""Reusable ASE structure builders for the generated 50-system benchmark."""

from __future__ import annotations

import numpy as np
from ase import Atoms
from ase.build import add_adsorbate, bulk, fcc111, make_supercell, molecule


def molecule_box(atoms: Atoms, box: float = 12.0) -> Atoms:
    atoms.set_cell([box, box, box])
    atoms.set_pbc(True)
    atoms.center()
    return atoms


def build_bulk_fcc(symbol: str, a: float) -> Atoms:
    return bulk(symbol, "fcc", a=float(a), cubic=True)


def build_bulk_bcc(symbol: str, a: float) -> Atoms:
    return bulk(symbol, "bcc", a=float(a), cubic=True)


def build_bulk_diamond(symbol: str, a: float) -> Atoms:
    return bulk(symbol, "diamond", a=float(a), cubic=True)


def build_bulk_zincblende(formula: str, a: float) -> Atoms:
    return bulk(formula, "zincblende", a=float(a), cubic=True)


def build_bulk_rocksalt(formula: str, a: float) -> Atoms:
    return bulk(formula, "rocksalt", a=float(a), cubic=True)


def build_zno_wurtzite(a: float, c_over_a: float) -> Atoms:
    return bulk("ZnO", "wurtzite", a=float(a), c=float(c_over_a) * float(a))


def build_tio2_rutile(a: float, c_over_a: float) -> Atoms:
    c = float(c_over_a) * float(a)
    atoms = Atoms("Ti2O4", cell=[a, a, c], pbc=True)
    atoms.set_scaled_positions([
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.5],
        [0.3, 0.3, 0.0],
        [0.7, 0.7, 0.0],
        [0.2, 0.8, 0.5],
        [0.8, 0.2, 0.5],
    ])
    return atoms


def build_al2o3_model(a: float, c_over_a: float) -> Atoms:
    c = float(c_over_a) * float(a)
    atoms = Atoms("Al4O6", cell=[a, a, c], pbc=True)
    atoms.set_scaled_positions([
        [0.35, 0.35, 0.35],
        [0.65, 0.65, 0.65],
        [0.15, 0.15, 0.85],
        [0.85, 0.85, 0.15],
        [0.30, 0.00, 0.25],
        [0.00, 0.30, 0.25],
        [0.70, 0.00, 0.75],
        [0.00, 0.70, 0.75],
        [0.50, 0.50, 0.10],
        [0.50, 0.50, 0.90],
    ])
    return atoms


def build_sio2_model(a: float, c_over_a: float) -> Atoms:
    c = float(c_over_a) * float(a)
    atoms = Atoms("Si3O6", cell=[a, a, c], pbc=True)
    atoms.set_scaled_positions([
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.33],
        [0.25, 0.75, 0.66],
        [0.2, 0.1, 0.15],
        [0.8, 0.9, 0.15],
        [0.4, 0.6, 0.48],
        [0.6, 0.4, 0.48],
        [0.1, 0.8, 0.82],
        [0.9, 0.2, 0.82],
    ])
    return atoms


def build_graphene_like(symbols: str, a: float, vacuum: float = 15.0, buckling: float = 0.0) -> Atoms:
    a1 = np.array([a, 0.0, 0.0])
    a2 = np.array([-0.5 * a, 0.5 * np.sqrt(3.0) * a, 0.0])
    atoms = Atoms(symbols, cell=[a1, a2, [0.0, 0.0, vacuum]], pbc=(True, True, True))
    z1 = 0.5 - buckling / (2.0 * vacuum)
    z2 = 0.5 + buckling / (2.0 * vacuum)
    atoms.set_scaled_positions([[0.0, 0.0, z1], [1.0 / 3.0, 2.0 / 3.0, z2]])
    return make_supercell(atoms, [[2, 0, 0], [0, 2, 0], [0, 0, 1]])


def build_mx2(symbol_m: str, symbol_x: str, a: float, layer_half_thickness: float, vacuum: float = 18.0) -> Atoms:
    atoms = Atoms(
        f"{symbol_m}{symbol_x}2",
        cell=[
            [a, 0.0, 0.0],
            [-0.5 * a, 0.5 * np.sqrt(3.0) * a, 0.0],
            [0.0, 0.0, vacuum],
        ],
        pbc=(True, True, True),
    )
    atoms.set_scaled_positions([
        [0.0, 0.0, 0.5],
        [1.0 / 3.0, 2.0 / 3.0, 0.5 + layer_half_thickness / vacuum],
        [2.0 / 3.0, 1.0 / 3.0, 0.5 - layer_half_thickness / vacuum],
    ])
    return make_supercell(atoms, [[2, 0, 0], [0, 2, 0], [0, 0, 1]])


def build_linear_molecule(symbols: str, bond: float) -> Atoms:
    return molecule_box(Atoms(symbols, positions=[[0.0, 0.0, 0.0], [float(bond), 0.0, 0.0]]))


def build_h2o(bond: float, angle: float) -> Atoms:
    theta = np.radians(float(angle))
    r = float(bond)
    atoms = Atoms("OH2", positions=[[0.0, 0.0, 0.0], [r, 0.0, 0.0], [r * np.cos(theta), r * np.sin(theta), 0.0]])
    return molecule_box(atoms)


def build_scaled_molecule(name: str, bond: float, reference_bond: float) -> Atoms:
    atoms = molecule(name)
    atoms.positions *= float(bond) / float(reference_bond)
    return molecule_box(atoms)


def build_layered_abo2(a_atom: str, b_atom: str, a: float, c_over_a: float) -> Atoms:
    atoms = Atoms(f"{a_atom}{b_atom}O2", cell=[a, a, float(c_over_a) * a], pbc=True)
    atoms.set_scaled_positions([[0.0, 0.0, 0.0], [0.0, 0.0, 0.5], [1 / 3, 2 / 3, 0.25], [2 / 3, 1 / 3, 0.75]])
    return atoms


def build_rocksalt_litio2(a: float) -> Atoms:
    atoms = Atoms("LiTiO2", cell=[a, a, a], pbc=True)
    atoms.set_scaled_positions([
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
    ])
    return atoms


def build_limn2o4(a: float) -> Atoms:
    atoms = Atoms("Li2Mn4O8", cell=[a, a, a], pbc=True)
    atoms.set_scaled_positions(np.mod(np.arange(14)[:, None] * np.array([[0.211, 0.377, 0.159]]), 1.0))
    return atoms


def build_adsorbate(ads_symbol: str, metal: str, height: float, shift: float) -> Atoms:
    a = {"Cu": 3.61, "Ni": 3.52, "Pt": 3.92}.get(metal, 3.70)
    slab = fcc111(metal, size=(2, 2, 3), a=a, vacuum=12.0, periodic=True)
    position = "ontop"
    if abs(shift - 0.5) < 0.25:
        position = "bridge"
    elif shift > 0.75:
        position = "fcc"
    if ads_symbol == "CO":
        add_adsorbate(slab, Atoms("CO", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.15]]), height, position=position)
    else:
        add_adsorbate(slab, ads_symbol, height, position=position)
    return slab


def build_perovskite(a_atom: str, b_atom: str, x_atom: str, a: float) -> Atoms:
    atoms = Atoms(f"{a_atom}{b_atom}{x_atom}3", cell=[a, a, a], pbc=True)
    atoms.set_scaled_positions([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5], [0.0, 0.5, 0.5]])
    return atoms


def build_nial(a: float) -> Atoms:
    atoms = Atoms("NiAl", cell=[a, a, a], pbc=True)
    atoms.set_scaled_positions([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    return atoms


def build_co2feal(a: float) -> Atoms:
    atoms = Atoms("Co2FeAl", cell=[a, a, a], pbc=True)
    atoms.set_scaled_positions([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [0.25, 0.25, 0.25], [0.75, 0.75, 0.75]])
    return atoms


def build_ti3c2o2_slab(
    a: float = 3.061,
    ti_c_bond: float = 2.164,
    ti_o_bond: float = 2.000,
    vacuum: float = 22.0,
    supercell: tuple[int, int, int] = (2, 2, 1),
) -> Atoms:
    """Ti3C2O2 (double-side O-terminated Ti3C2Tx) MXene slab, hexagonal P-6m2.

    Derived the way these MXenes are physically understood to form: a 5-layer
    Ti-C-Ti-C-Ti core cut from rock-salt TiC along (111) (which naturally gives
    the right edge-sharing-octahedral Ti-C connectivity), plus O termination
    continuing the same ABC-type stacking one layer further out on each face
    (the site vacated by the MAX-phase A-element during etching).

    In-plane hollow-site convention matches build_mx2/build_graphene_like in
    this module: A=(0,0), B=(1/3,2/3), C=(2/3,1/3). Middle Ti sits at A; both
    C layers at B; both outer Ti layers at C (continuing the stacking); both
    terminal O layers back at A (directly over the far Ti layer -- the
    commonly reported low-energy hcp-hollow O site for Ti3C2O2).

    Default a=3.061 A and ti_c_bond=2.164 A correspond to a TiC rock-salt
    lattice constant of 4.328 A (close to bulk TiC's ~4.33 A); ti_o_bond
    defaults to 2.000 A, matching the Ti-O bond length this repo's Ti3C2-O
    oracle script documents. These are literature-typical starting values,
    not final numbers -- the resulting slab is meant to be relaxed via QE/BFGS
    before use as a static reference energy.
    """
    r_hollow = a / np.sqrt(3.0)  # distance from a lattice site to an adjacent 3-fold hollow centroid
    dz_tic = np.sqrt(float(ti_c_bond) ** 2 - r_hollow ** 2)
    dz_tio = np.sqrt(float(ti_o_bond) ** 2 - r_hollow ** 2)

    z_c = dz_tic
    z_ti_outer = z_c + dz_tic
    z_o = z_ti_outer + dz_tio

    symbols = ["O", "Ti", "C", "Ti", "C", "Ti", "O"]
    z_offsets = [-z_o, -z_ti_outer, -z_c, 0.0, z_c, z_ti_outer, z_o]
    xy_sites = [
        (0.0, 0.0),        # O (bottom)  -- site A, over middle Ti
        (2.0 / 3.0, 1.0 / 3.0),  # Ti (bottom, outer) -- site C
        (1.0 / 3.0, 2.0 / 3.0),  # C (bottom) -- site B
        (0.0, 0.0),        # Ti (middle) -- site A
        (1.0 / 3.0, 2.0 / 3.0),  # C (top) -- site B
        (2.0 / 3.0, 1.0 / 3.0),  # Ti (top, outer) -- site C
        (0.0, 0.0),        # O (top) -- site A, over middle Ti
    ]

    atoms = Atoms(
        "".join(symbols),
        cell=[
            [a, 0.0, 0.0],
            [-0.5 * a, 0.5 * np.sqrt(3.0) * a, 0.0],
            [0.0, 0.0, vacuum],
        ],
        pbc=(True, True, True),
    )
    scaled = [[u, v, 0.5 + dz / vacuum] for (u, v), dz in zip(xy_sites, z_offsets)]
    atoms.set_scaled_positions(scaled)

    nx, ny, nz = supercell
    return make_supercell(atoms, [[nx, 0, 0], [0, ny, 0], [0, 0, nz]])
