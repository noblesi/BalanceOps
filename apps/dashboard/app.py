from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from balanceops.common.config import get_settings
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.init_db import init_db
from balanceops.tracking.read import get_latest_run_id, get_run_detail, list_runs_summary

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


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "-"
    if n < 1024:
        return f"{n} B"
    size = float(n)
    for unit in ["KB", "MB", "GB", "TB"]:
        size /= 1024.0
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f} {unit}"
    return f"{size:.2f} TB"


def _resolve_path(artifacts_root: str | Path, p: str) -> Path:
    """Resolve a path stored in DB. Prefer CWD-relative first, fallback to artifacts_root."""
    path = Path(p)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return Path(artifacts_root) / path


_KST = ZoneInfo("Asia/Seoul")


def _iso_to_local(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # created_at은 기본 UTC 저장. UI에서는 KST로 보여주기.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        dt = dt.astimezone(_KST)
        return dt.strftime("%Y-%m-%d %H:%M:%S KST")
    except Exception:
        return ts


@st.cache_data(show_spinner=False)
def _read_file_bytes(path_str: str, mtime_ns: int) -> bytes:
    """Cache file reads; mtime_ns busts cache when file changes."""
    _ = mtime_ns
    return Path(path_str).read_bytes()


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
            "created_at": _iso_to_local(r.get("created_at")),
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
run_meta = {r["run_id"]: r for r in items}
run_ids = list(run_meta.keys())

if "selected_run_id" not in st.session_state:
    st.session_state["selected_run_id"] = run_ids[0]

selected_run_id = str(st.session_state["selected_run_id"])
if selected_run_id not in run_meta:
    run_ids = [selected_run_id] + run_ids


def _run_label(run_id: str) -> str:
    r = run_meta.get(run_id)
    if not r:
        return run_id
    created_at = _iso_to_local(r.get("created_at"))
    kind = r.get("kind") or "-"
    return f"{created_at} | {kind} | {run_id[:8]}…"


ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1])

with ctrl1:
    st.selectbox("Select run", options=run_ids, key="selected_run_id", format_func=_run_label)

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

detail = get_run_detail(
    s.db_path, run_id=st.session_state["selected_run_id"], artifacts_root=s.artifacts_dir
)

st.subheader("Run Detail")

if detail is None:
    st.error("Selected run not found in DB.")
    st.stop()

git = detail.get("git") or {}
params = detail.get("params") or {}
kind = params.get("kind") if isinstance(params, dict) else None

meta1, meta2, meta3, meta4 = st.columns(4)
with meta1:
    st.caption("Run ID")
    st.code(detail.get("run_id") or "")

with meta2:
    st.caption("Created at")
    st.code(_iso_to_local(detail.get("created_at")))

with meta3:
    st.caption("Kind")
    st.code(kind or "-")

with meta4:
    st.caption("Git")
    git_commit = (git.get("commit") or "")[:8]
    git_branch = git.get("branch") or "-"
    git_dirty = bool(git.get("dirty"))
    st.code(f"{git_commit} | {git_branch} | dirty={git_dirty}")

if detail.get("note"):
    st.caption("Note")
    st.write(detail.get("note"))

tab_params, tab_metrics, tab_artifacts, tab_manifest = st.tabs(
    ["Params", "Metrics", "Artifacts", "Manifest"]
)

with tab_params:
    p = detail.get("params")
    if not p:
        st.info("No params recorded for this run.")
    else:
        st.json(p)
        kv_rows = []
        for k, v in sorted(p.items()):
            if isinstance(v, (dict, list)):
                v2 = json.dumps(v, ensure_ascii=False)
            else:
                v2 = v
            kv_rows.append({"key": str(k), "value": v2})
        st.dataframe(pd.DataFrame(kv_rows), use_container_width=True, hide_index=True)

with tab_metrics:
    metrics = detail.get("metrics") or {}
    if not metrics:
        st.info("No metrics recorded for this run.")
    else:
        m_rows = [{"metric": k, "value": float(v)} for k, v in sorted(metrics.items())]
        st.dataframe(pd.DataFrame(m_rows), use_container_width=True, hide_index=True)

with tab_artifacts:
    artifacts = detail.get("artifacts") or []
    if not artifacts:
        st.info("No artifacts logged for this run.")
    else:
        max_download = 50 * 1024 * 1024

        a_rows = []
        grouped: dict[str, list[tuple[str, Path]]] = defaultdict(list)

        for a in artifacts:
            a_kind = a.get("kind") or "-"
            a_path_raw = a.get("path") or ""
            p = _resolve_path(s.artifacts_dir, a_path_raw)
            exists = p.exists()
            is_file = exists and p.is_file()
            size = p.stat().st_size if is_file else None
            a_rows.append(
                {
                    "kind": a_kind,
                    "path": a_path_raw,
                    "exists": bool(exists),
                    "size": _fmt_bytes(size),
                }
            )
            grouped[str(a_kind)].append((str(a_path_raw), p))

        st.dataframe(pd.DataFrame(a_rows), use_container_width=True, hide_index=True)
        st.caption("다운로드는 50MB 이하 파일에만 제공됩니다.")

        for a_kind in sorted(grouped.keys()):
            entries = grouped[a_kind]
            with st.expander(f"{a_kind} ({len(entries)})", expanded=True):
                for i, (raw, p) in enumerate(entries):
                    c1, c2, c3 = st.columns([6, 2, 2])
                    with c1:
                        st.code(raw)
                        if not p.is_absolute() and p.exists():
                            try:
                                st.caption(str(p.resolve()))
                            except Exception:
                                st.caption(str(p))
                        elif p.is_absolute():
                            st.caption(str(p))

                    with c2:
                        if p.exists() and p.is_file():
                            st.caption(_fmt_bytes(p.stat().st_size))
                        else:
                            st.caption("missing")

                    with c3:
                        if p.exists() and p.is_file():
                            size = p.stat().st_size
                            if size <= max_download:
                                mtime_ns = p.stat().st_mtime_ns
                                data = _read_file_bytes(str(p), mtime_ns)
                                st.download_button(
                                    "Download",
                                    data=data,
                                    file_name=p.name,
                                    key=f"dl_{detail['run_id']}_{a_kind}_{i}",
                                    use_container_width=True,
                                )
                            else:
                                st.caption("too large")
                        else:
                            st.caption("-")

with tab_manifest:
    pointer = detail.get("manifest")
    if not pointer:
        st.info("No manifest pointer found. (artifacts/runs/_by_id/<run_id>.json)")
    else:
        st.subheader("Pointer")
        st.json(pointer)

        mp = pointer.get("manifest_path") if isinstance(pointer, dict) else None
        if mp:
            p = _resolve_path(s.artifacts_dir, str(mp))
            if p.exists():
                try:
                    st.subheader("manifest.json")
                    st.json(json.loads(p.read_text(encoding="utf-8")))
                except Exception as e:
                    st.warning(f"Failed to read manifest.json: {e}")
            else:
                st.warning(f"manifest_path not found: {p}")

with st.expander("Raw detail (debug)"):
    st.json(detail)
