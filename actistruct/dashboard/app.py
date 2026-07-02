"""ActiStruct v2 — Streamlit dashboard.

Launch:
    streamlit run actistruct/dashboard/app.py

Reads from: actistruct/data/run_ledger.jsonl  (Phase 0 ledger)

Tabs
----
1. Campaign Overview  — scorecard, convergence rate, failure breakdown
2. Energy Landscape   — energy vs iteration, best candidate trajectory
3. 3D Structure Viewer — py3Dmol view of any stored structure (via stmol)
4. Run Log            — full sortable/filterable ledger table

Design notes
------------
- Handles empty ledger gracefully (no stack trace, friendly "no data yet" message).
- 3D viewer uses stmol + py3Dmol (the supported Streamlit bridge), NOT the
  private viewer._make_html() call.
- "Uncertainty Evolution" tab is intentionally NOT included here because it
  requires GP predictive std per iteration to be stored in the ledger — that
  data is only available once the surrogate is running live. A clearly marked
  TODO is left instead of showing a chart with a wrong label.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from actistruct.core.ledger import DEFAULT_LEDGER_PATH
from actistruct.dashboard.data_loader import (
    MULTI_LEDGER_ROOT,
    get_summary_stats,
    load_ledger,
    load_multi_ledger,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ActiStruct v2 -- Active Learning Dashboard",
    page_icon=None,
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("ActiStruct v2")

load_mode = st.sidebar.radio(
    "Load mode",
    ["Single ledger", "Multi-system (all campaigns)"],
    help=(
        "Single ledger: point at one JSONL file.\n"
        "Multi-system: globs actistruct_data/*/recovery.jsonl and "
        "actistruct_data/*/campaign.jsonl — aggregates all systems."
    ),
)

if load_mode == "Single ledger":
    ledger_input = st.sidebar.text_input(
        "Ledger path",
        value=str(DEFAULT_LEDGER_PATH),
        help="Path to a single run_ledger.jsonl or campaign.jsonl.",
    )
else:
    ledger_input = st.sidebar.text_input(
        "Campaign root directory",
        value=str(MULTI_LEDGER_ROOT),
        help="Root dir containing <system>/recovery.jsonl and <system>/campaign.jsonl.",
    )

if st.sidebar.button("Refresh"):
    st.cache_data.clear()


@st.cache_data(ttl=30)
def _load_single(path: str) -> pd.DataFrame:
    return load_ledger(Path(path))


@st.cache_data(ttl=30)
def _load_multi(root: str) -> pd.DataFrame:
    return load_multi_ledger(Path(root))


# ── Load data ─────────────────────────────────────────────────────────────────
try:
    if load_mode == "Single ledger":
        df = _load_single(ledger_input)
    else:
        df = _load_multi(ledger_input)
    load_error = None
except ValueError as exc:
    df = pd.DataFrame()
    load_error = str(exc)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_energy, tab_3d, tab_log = st.tabs([
    "📊 Campaign Overview",
    "📈 Energy Landscape",
    "🔬 3D Viewer",
    "📋 Run Log",
])

# ═════════════════════════════════════════════════════════════════════════════
# Tab 1 — Campaign Overview
# ═════════════════════════════════════════════════════════════════════════════
with tab_overview:
    st.header("Campaign Overview")

    if load_error:
        st.error(f"Could not load ledger:\n\n{load_error}")
        st.stop()

    if df.empty:
        st.info(
            "No campaign data yet.\n\n"
            "Run Phase 1 or Phase 2 to generate DFT records, then refresh."
        )
    else:
        stats = get_summary_stats(df)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total runs",        stats["total_runs"])
        col2.metric("Converged",         stats["converged"])
        col3.metric("Failed",            stats["failed"])
        col4.metric("Convergence rate",  f"{stats['convergence_rate_pct']:.1f}%")

        st.subheader("Failure breakdown")
        if stats["failure_types"]:
            fig_pie = px.pie(
                names=list(stats["failure_types"].keys()),
                values=list(stats["failure_types"].values()),
                title="Failure type distribution",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.success("No failures recorded — all runs converged!")

        if stats["systems"]:
            st.subheader("Systems in campaign")
            st.write(", ".join(stats["systems"]))


# ═════════════════════════════════════════════════════════════════════════════
# Tab 2 — Energy Landscape
# ═════════════════════════════════════════════════════════════════════════════
with tab_energy:
    st.header("Energy Landscape")

    if df.empty:
        st.info("No data yet — run Phase 1/2 first.")
    else:
        converged_df = df[df["converged"]].copy()
        if converged_df.empty:
            st.warning("No converged calculations yet.")
        else:
            converged_df = converged_df.sort_values("timestamp").reset_index(drop=True)
            converged_df["run_index"] = range(1, len(converged_df) + 1)
            converged_df["energy_per_atom"] = converged_df["energy"]

            fig_energy = px.scatter(
                converged_df,
                x="run_index",
                y="energy_per_atom",
                color="fidelity",
                hover_data=["system", "candidate_id", "wall_time_s"],
                title="Energy per atom vs run index (converged runs only)",
                labels={"run_index": "Run #", "energy_per_atom": "Energy / atom (eV)"},
                color_discrete_map={"low": "#4CAF50", "high": "#2196F3"},
            )
            st.plotly_chart(fig_energy, use_container_width=True)

            # Best energy trajectory.
            converged_df["best_energy"] = converged_df["energy_per_atom"].cummin()
            fig_best = px.line(
                converged_df,
                x="run_index",
                y="best_energy",
                title="Best energy found so far (running minimum)",
                labels={"run_index": "Run #", "best_energy": "Best energy / atom (eV)"},
            )
            st.plotly_chart(fig_best, use_container_width=True)

        # TODO(Phase 3.1): plot GP predictive std per iteration — not implemented yet.
        # This requires storing surrogate uncertainty at each AL iteration in the ledger.
        # Until that data is available, no "Uncertainty Evolution" chart is shown.
        st.caption(
            "ℹ️ Uncertainty evolution chart: not yet available. "
            "Add GP predictive std to the ledger records in Phase 3.1."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Tab 3 — 3D Structure Viewer
# ═════════════════════════════════════════════════════════════════════════════
with tab_3d:
    st.header("3D Structure Viewer")
    st.caption(
        "Paste or upload an XYZ structure string. "
        "In a live campaign, structures are loaded from the ASE trajectory cache."
    )

    sample_xyz = """\
4
CaAlN2 synthetic test structure
Ca   0.000000   0.000000   0.000000
Al   1.575000   1.575000   2.500000
N    0.000000   0.000000   1.875000
N    1.575000   1.575000   4.375000"""

    xyz_input = st.text_area(
        "XYZ structure (paste here)",
        value=sample_xyz,
        height=180,
    )

    if xyz_input.strip():
        try:
            import py3Dmol
            from stmol import showmol

            view = py3Dmol.view(width=700, height=450)
            view.addModel(xyz_input, "xyz")
            view.setStyle({"stick": {"radius": 0.15}, "sphere": {"scale": 0.3}})
            view.addUnitCell()
            view.zoomTo()
            showmol(view, height=500, width=750)
        except Exception as exc:
            st.error(f"3D viewer error: {exc}")
    else:
        st.info("Paste an XYZ string above to view a structure.")


# ═════════════════════════════════════════════════════════════════════════════
# Tab 4 — Run Log
# ═════════════════════════════════════════════════════════════════════════════
with tab_log:
    st.header("Full Run Log")

    if df.empty:
        st.info("No records yet.")
    else:
        # Filters.
        col_sys, col_fid, col_conv = st.columns(3)

        systems_list   = ["All"] + sorted(df["system"].dropna().unique().tolist())
        fidelity_list  = ["All"] + sorted(df["fidelity"].dropna().unique().tolist())
        converged_list = ["All", "Converged", "Failed"]

        sel_sys  = col_sys.selectbox("System",     systems_list)
        sel_fid  = col_fid.selectbox("Fidelity",   fidelity_list)
        sel_conv = col_conv.selectbox("Status",     converged_list)

        filtered = df.copy()
        if sel_sys  != "All":
            filtered = filtered[filtered["system"]   == sel_sys]
        if sel_fid  != "All":
            filtered = filtered[filtered["fidelity"] == sel_fid]
        if sel_conv == "Converged":
            filtered = filtered[filtered["converged"] == True]
        elif sel_conv == "Failed":
            filtered = filtered[filtered["converged"] == False]

        st.write(f"Showing {len(filtered)} / {len(df)} records")
        display_cols = ["timestamp", "system", "fidelity", "converged",
                        "failure_type", "energy", "wall_time_s", "candidate_id"]
        st.dataframe(
            filtered[[c for c in display_cols if c in filtered.columns]],
            use_container_width=True,
        )
