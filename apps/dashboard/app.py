from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from balanceops.common.config import get_settings
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.init_db import init_db
from balanceops.tracking.read import get_run_detail, list_runs_summary


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

selected = st.selectbox("Select run", options=run_ids, key="selected_run_id")

detail = get_run_detail(s.db_path, run_id=selected, artifacts_root=s.artifacts_dir)

st.subheader("Run Detail")

if detail is None:
    st.error(f"Run not found: {selected}")
    st.stop()

params = detail.get("params") if isinstance(detail.get("params"), dict) else {}
kind = params.get("kind") or "-"

git = detail.get("git") or {}
commit = (git.get("commit") or "")[:8] or "-"
branch = git.get("branch") or "-"
dirty = "dirty" if git.get("dirty") else "clean"

c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
c1.metric("Created", detail.get("created_at") or "-")
c2.metric("Kind", kind)
c3.metric("Git", f"{commit} / {branch}")
c4.metric("Worktree", dirty)

tab_metrics, tab_params, tab_artifacts, tab_manifest = st.tabs(["Metrics", "Params", "Artifacts", "Manifest"])

with tab_metrics:
    m = detail.get("metrics") or {}
    if not m:
        st.info("No metrics for this run.")
    else:
        mdf = pd.DataFrame([{"key": k, "value": v} for k, v in m.items()]).sort_values("key")
        st.dataframe(mdf, use_container_width=True, hide_index=True)

with tab_params:
    if not params:
        st.info("No params_json saved for this run.")
    else:
        st.json(params)

with tab_artifacts:
    artifacts = detail.get("artifacts") or []
    if not artifacts:
        st.info("No artifacts recorded for this run.")
    else:
        adf = pd.DataFrame(artifacts)
        st.dataframe(adf, use_container_width=True, hide_index=True)

with tab_manifest:
    manifest_ptr = detail.get("manifest")
    if not isinstance(manifest_ptr, dict):
        st.info("No manifest pointer found. (artifacts/runs/_by_id/<run_id>.json)")
    else:
        st.json(manifest_ptr)

        mp = manifest_ptr.get("manifest_path")
        if isinstance(mp, str) and mp:
            p = Path(mp)
            st.caption("manifest_path")
            st.code(mp)

            try:
                if p.exists():
                    st.caption("manifest.json (loaded)")
                    st.json(json.loads(p.read_text(encoding="utf-8")))
                else:
                    st.caption("manifest.json not found on filesystem (path mismatch).")
            except Exception as e:
                st.warning(f"Failed to read manifest.json: {e}")
