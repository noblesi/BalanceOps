from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from balanceops.common.config import get_settings
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.init_db import init_db
from balanceops.tracking.read import get_run_detail, list_runs_summary, get_latest_run_id


st.set_page_config(page_title="BalanceOps Dashboard", layout="wide")

s = get_settings()
init_db(s.db_path)

st.title("BalanceOps Dashboard")

# --- Header ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Current Model")
    info = get_current_model_info()
    st.json(info)

with col2:
    st.subheader("Settings")
    st.code(f"DB: {s.db_path}\nARTIFACTS: {s.artifacts_dir}\nCURRENT_MODEL: {s.current_model_path}")

st.divider()

# --- Load runs (summary) ---
with st.spinner("Loading runs..."):
    items = list_runs_summary(s.db_path, limit=50, offset=0, include_metrics=True)

st.subheader("Recent Runs")

if not items:
    st.info("No runs yet. Try running: scripts/run_once.ps1")
    st.stop()

def _metrics_preview(metrics: dict[str, float], max_items: int = 6) -> str:
    if not metrics:
        return ""
    keys = sorted(metrics.keys())
    parts = []
    for k in keys[:max_items]:
        v = metrics[k]
        parts.append(f"{k}={v:.4g}")
    if len(keys) > max_items:
        parts.append("...")
    return ", ".join(parts)

rows: list[dict[str, Any]] = []
for r in items:
    git = r.get("git") or {}
    metrics = r.get("metrics") or {}
    rows.append(
        {
            "created_at": r.get("created_at"),
            "kind": r.get("kind"),
            "run_id": r.get("run_id"),
            "git_commit": (git.get("commit") or "")[:8],
            "branch": git.get("branch"),
            "dirty": bool(git.get("dirty")),
            "note": r.get("note"),
            "metrics": _metrics_preview(metrics),
        }
    )

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- Drilldown ---
run_ids = [r["run_id"] for r in items]

if "selected_run_id" not in st.session_state:
    st.session_state["selected_run_id"] = run_ids[0]

ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1])

with ctrl1:
    selected = st.selectbox("Select run", options=run_ids, key="selected_run_id")

with ctrl2:
    if st.button("Latest", use_container_width=True):
        latest_id = get_latest_run_id(artifacts_root=s.artifacts_dir, db_path=s.db_path)
        if latest_id is None:
            st.warning("No latest run found.")
        else:
            st.session_state["selected_run_id"] = latest_id
            st.rerun()

with ctrl3:
    if st.button("Refresh", use_container_width=True):
        st.rerun()

detail = get_run_detail(s.db_path, run_id=st.session_state["selected_run_id"], artifacts_root=s.artifacts_dir)
