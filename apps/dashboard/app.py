from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
import streamlit as st

from balanceops.common.config import get_settings
from balanceops.common.version import get_build_info
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.init_db import init_db
from balanceops.tracking.read import get_latest_run_id, get_run_detail, list_runs_summary

st.set_page_config(page_title="BalanceOps Dashboard", layout="wide")

s = get_settings()
init_db(s.db_path)

# ----------------------------
# Time formatting (UTC -> KST)
# ----------------------------
_KST = ZoneInfo("Asia/Seoul")
_UTC = ZoneInfo("UTC")


def _iso_to_kst_dt(ts: str | None) -> datetime | None:
    """ISO timestamp(대개 UTC 저장)을 KST datetime으로 변환(차트/정렬용)."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_UTC)
        return dt.astimezone(_KST)
    except Exception:
        return None


def _iso_to_kst(ts: str | None, *, with_suffix: bool = True) -> str:
    """ISO timestamp(대개 UTC 저장)을 UI에서 KST로 통일 표기."""
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_UTC)
        dt = dt.astimezone(_KST)
        suffix = " KST" if with_suffix else ""
        return dt.strftime("%Y-%m-%d %H:%M:%S") + suffix
    except Exception:
        return str(ts)


def _coerce_str(v: Any) -> str:
    return "" if v is None else str(v)


# ----------------------------
# Helpers
# ----------------------------
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


def _format_current_model_info(raw: dict) -> dict:
    """Current model info의 created_at도 KST로 보여주기."""
    if not raw:
        return {}
    out = dict(raw)
    if "created_at" in out:
        out["created_at"] = _iso_to_kst(_coerce_str(out.get("created_at")))
    return out


def _search_haystack(item: dict[str, Any]) -> str:
    git = item.get("git") or {}
    parts = [
        _coerce_str(item.get("run_dir_name")),
        _coerce_str(item.get("run_id")),
        _coerce_str(item.get("note")),
        _coerce_str(item.get("kind")),
        _coerce_str(git.get("branch")),
        _coerce_str(git.get("commit")),
    ]
    return " ".join(parts).lower()


def _short(v: str | None, n: int = 8) -> str:
    if not v:
        return "-"
    return v[:n]


@st.cache_data(show_spinner=False, ttl=10)
def _fetch_api_version(api_base_url: str) -> tuple[dict[str, Any] | None, str | None]:
    """API /version 호출(실패해도 대시보드가 죽지 않게).

    - 정상: (dict, None)
    - 실패: (None, error_message)
    """
    url = api_base_url.rstrip("/") + "/version"
    try:
        r = httpx.get(url, timeout=2.0)
        r.raise_for_status()

        data = r.json()
        if not isinstance(data, dict):
            return None, "Invalid /version payload (not a JSON object)."
        return data, None

    except httpx.TimeoutException:
        return None, "Timeout while calling /version."

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        return None, f"HTTP {status} from /version."

    except httpx.RequestError as e:
        # DNS/ConnectionError 등 네트워크 계열
        return None, f"Request error: {type(e).__name__}"

    except ValueError:
        # JSON decode error
        return None, "Invalid JSON from /version."

    except Exception as e:
        return None, f"Unexpected error: {type(e).__name__}: {e}"


# ----------------------------
# UI
# ----------------------------
st.title("BalanceOps Dashboard")
st.caption("Timezone: KST (Asia/Seoul)")

# Header
col1, col2, col3 = st.columns([2, 1.4, 1.4])

with col1:
    st.subheader("Current Model")
    info = get_current_model_info()
    st.json(_format_current_model_info(info))

with col2:
    st.subheader("Build (Server)")

    api_url = st.text_input(
        "API URL",
        value=s.api_base_url,
        help="대시보드가 이 주소의 /version 을 호출합니다.",
    )

    # 새로고침 버튼: 캐시 클리어 + rerun
    if st.button("새로고침", key="refresh_api_version", width="stretch"):
        _fetch_api_version.clear()
        st.rerun()

    ver, err = _fetch_api_version(api_url)

    if ver:
        git = ver.get("git") or {}
        pkg = ver.get("package") or {}
        py = ver.get("python") or {}

        st.code(
            "\n".join(
                [
                    f"balanceops: {pkg.get('version') or '-'}",
                    f"git: {git.get('branch') or '-'}@{_short(git.get('commit'))}",
                    f"dirty: {bool(git.get('dirty'))}",
                    f"python: {py.get('version') or '-'}",
                ]
            )
        )

        with st.expander("Raw (/version)", expanded=False):
            st.json(ver)
    else:
        st.warning("API /version 을 가져오지 못했습니다.")
        if err:
            st.caption(f"- 원인: {err}")
        st.caption(r"- 힌트: API 실행 `.\scripts\serve.ps1`")

        # (옵션) 서버가 꺼져있을 때도 로컬 빌드 확인 가능
        with st.expander("Local build (fallback)", expanded=False):
            st.json(get_build_info())

with col3:
    st.subheader("Settings")
    st.code(f"DB: {s.db_path}\nARTIFACTS: {s.artifacts_dir}\nCURRENT_MODEL: {s.current_model_path}")


# ----------------------------
# Recent Runs (summary)
# ----------------------------
st.subheader("Recent Runs")

top1, top2, top3, top4 = st.columns([2.3, 1.1, 1.1, 1.2])

with top1:
    q = st.text_input(
        "Search (run_dir_name / run_id / note / kind / branch / commit)",
        value="",
        placeholder="예) duel, swarm, main, 3ace13f ...",
    )

with top2:
    limit = st.selectbox("Limit", options=[20, 50, 100, 200], index=1)

with top3:
    include_metrics = st.checkbox("Include metrics (load + trend)", value=True)

with top4:
    dirty_filter = st.selectbox("Dirty", options=["All", "Clean", "Dirty"], index=0)

with st.spinner("Loading runs..."):
    items = list_runs_summary(
        # 메트릭 추이/비교 기능을 위해 항상 메트릭을 로드한다.
        # 표에서 보여줄지 여부는 include_metrics 체크박스로 제어.
        s.db_path,
        limit=int(limit),
        offset=0,
        include_metrics=include_metrics,
        artifacts_root=s.artifacts_dir,
        include_run_dir_name=True,
    )

if not items:
    st.info("No runs yet. Try running: scripts/run_once.ps1")
    st.stop()

# kind filter options (loaded after items)
kinds = sorted({str(i.get("kind") or "-") for i in items})
k1, k2 = st.columns([1.2, 3.8])
with k1:
    kind_filter = st.selectbox("Kind", options=["All", *kinds], index=0)
with k2:
    st.caption(f"Loaded: {len(items)} runs")

# Apply filters
q_low = (q or "").strip().lower()
filtered: list[dict[str, Any]] = []
for it in items:
    it_kind = str(it.get("kind") or "-")
    it_git = it.get("git") or {}
    it_dirty = bool(it_git.get("dirty"))

    if kind_filter != "All" and it_kind != kind_filter:
        continue

    if dirty_filter == "Clean" and it_dirty:
        continue
    if dirty_filter == "Dirty" and not it_dirty:
        continue

    if q_low:
        if q_low not in _search_haystack(it):
            continue

    filtered.append(it)

st.caption(f"Showing: {len(filtered)} / {len(items)}")

# Build table rows
rows: list[dict[str, Any]] = []
for r in filtered:
    git = r.get("git") or {}
    metrics = r.get("metrics") or {}

    run_id = _coerce_str(r.get("run_id"))
    run_short = run_id[:8] + "…" if len(run_id) > 9 else run_id

    run_dir_name = _coerce_str(r.get("run_dir_name"))
    run_display = run_dir_name if run_dir_name else run_short

    git_commit = (_coerce_str(git.get("commit"))[:8]) if git.get("commit") else "-"
    git_branch = _coerce_str(git.get("branch")) or "-"
    git_dirty = bool(git.get("dirty"))
    git_view = f"{git_commit} | {git_branch} | dirty={git_dirty}"

    rows.append(
        {
            "created_at": _iso_to_kst(_coerce_str(r.get("created_at"))),
            "kind": _coerce_str(r.get("kind") or "-"),
            "run": run_display,
            "run_id": run_id,
            "git": git_view,
            "note": _coerce_str(r.get("note") or ""),
            "metrics": _metrics_preview(metrics),
        }
    )


df = pd.DataFrame(rows)

# Column order 정리
col_order = ["created_at", "kind", "run", "run_id", "git", "note"]
if include_metrics:
    col_order.append("metrics")

if not df.empty:
    df = df[col_order]

st.dataframe(df, width="stretch", hide_index=True)

# ----------------------------
# Metrics Trend
# ----------------------------
with st.expander("Metrics Trend (최근 run 메트릭 추이)", expanded=include_metrics):
    # ✅ metrics를 로드하지 않는 모드라면 Trend는 안내만
    if not include_metrics:
        st.info("Metrics Trend를 보려면 위에서 'Include metrics'를 켜주세요.")
    else:
        # filtered는 최신순(내림차순)으로 쌓임
        all_metric_keys = sorted({k for it in filtered for k in (it.get("metrics") or {}).keys()})

        if not all_metric_keys:
            st.info(
                "선택된 run들에 기록된 metrics가 없어요. "
                "먼저 scripts/train_dummy.ps1 등을 실행해 metrics를 쌓아주세요."
            )
        else:
            preferred = ["roc_auc", "f1", "bal_acc", "accuracy", "loss"]
            default_metrics = [m for m in preferred if m in all_metric_keys] or [all_metric_keys[0]]

            c1, c2, c3 = st.columns([3, 2, 2])

            with c1:
                picked_metrics = st.multiselect(
                    "Metrics",
                    options=all_metric_keys,
                    default=default_metrics,
                    help="선택한 metric들의 시간(KST) 기준 추이를 그립니다.",
                )

            with c2:
                max_points = len(filtered)
                if max_points < 2:
                    points = max_points
                else:
                    points = st.slider(
                        "Points (latest)",
                        min_value=2,
                        max_value=max_points,
                        value=min(50, max_points),
                        help="필터된 목록에서 최신 N개 run을 사용합니다.",
                    )

            with c3:
                drop_all_nan = st.checkbox(
                    "Drop all-missing rows",
                    value=True,
                    help="선택 메트릭이 전부 없는 run은 차트에서 제외합니다.",
                )

            if not picked_metrics:
                st.info("메트릭을 1개 이상 선택해 주세요.")
            elif points < 2:
                st.info("차트를 그리려면 run이 최소 2개 이상 필요합니다.")
            else:
                recent = filtered[:points]
                trend_rows: list[dict[str, Any]] = []

                # 오래된 → 최신 순으로 쌓기(차트 x축 정렬 안정)
                for it in reversed(recent):
                    dt_kst = _iso_to_kst_dt(_coerce_str(it.get("created_at")))
                    if dt_kst is None:
                        continue

                    metrics = it.get("metrics") or {}
                    row: dict[str, Any] = {
                        "created_at": dt_kst.replace(tzinfo=None),
                        "created_at_text": _iso_to_kst(_coerce_str(it.get("created_at"))),
                        "kind": _coerce_str(it.get("kind") or "-"),
                        "run_id": _coerce_str(it.get("run_id")),
                    }

                    # ✅ run_dir_name 우선, 없으면 run_short fallback
                    run_id = row["run_id"]
                    run_short = run_id[:8] + "…" if len(run_id) > 9 else run_id
                    run_dir_name = _coerce_str(it.get("run_dir_name"))
                    row["run"] = run_dir_name if run_dir_name else run_short

                    for m in picked_metrics:
                        row[m] = metrics.get(m)

                    trend_rows.append(row)

                trend_df = pd.DataFrame(trend_rows)
                if trend_df.empty or len(trend_df) < 2:
                    st.info(
                        "차트에 사용할 유효 run 데이터가 2개 미만입니다. "
                        "(created_at 파싱 실패/필터 영향)"
                    )
                else:
                    trend_df = trend_df.sort_values("created_at")
                    chart_df = trend_df.set_index("created_at")[picked_metrics]
                    chart_df = chart_df.apply(pd.to_numeric, errors="coerce")

                    if drop_all_nan:
                        chart_df = chart_df.dropna(how="all")

                    if chart_df.empty or len(chart_df) < 2:
                        st.info(
                            "차트에 표시할 유효 포인트가 2개 미만입니다. (all-missing 제거 영향)"
                        )
                    else:
                        st.line_chart(chart_df, width="stretch")

                        missing_cells = int(chart_df.isna().sum().sum())
                        total_cells = int(chart_df.size)
                        used_points = int(len(chart_df))

                        start_txt = str(trend_df["created_at_text"].iloc[0])
                        end_txt = str(trend_df["created_at_text"].iloc[-1])

                        st.caption(
                            f"표본: {points} (필터 기준) | 유효 포인트: {used_points} | "
                            f"누락 셀: {missing_cells}/{total_cells} | "
                            f"기간: {start_txt} ~ {end_txt}"
                        )

                        show_table = st.checkbox("Show values table", value=True)
                        if show_table:
                            table_cols = [
                                "created_at_text",
                                "kind",
                                "run",
                                "run_id",
                                *picked_metrics,
                            ]
                            st.dataframe(
                                trend_df[table_cols],
                                width="stretch",
                                hide_index=True,
                            )


# ----------------------------
# Drilldown
# ----------------------------
# 선택 가능한 run 목록은 "필터된 목록"을 기준으로 함.
run_meta = {r["run_id"]: r for r in filtered}
run_ids = list(run_meta.keys())

# 필터 결과가 비어있으면, 상세를 보여줄 수 없으니 안내.
if not run_ids:
    st.info("필터 결과가 비어 있어요. 검색/필터 조건을 완화해 주세요.")
    st.stop()

if "selected_run_id" not in st.session_state:
    st.session_state["selected_run_id"] = run_ids[0]

selected_run_id = str(st.session_state["selected_run_id"])
if selected_run_id not in run_meta:
    # 현재 선택된 run이 필터에서 제외되었더라도, 선택 유지할 수 있게 목록에 포함
    run_ids = [selected_run_id] + run_ids


def _run_label(run_id: str) -> str:
    r = run_meta.get(run_id)
    if not r:
        return run_id
    created_at = _iso_to_kst(_coerce_str(r.get("created_at")), with_suffix=False)
    kind = str(r.get("kind") or "-")

    run_dir_name = _coerce_str(r.get("run_dir_name"))
    tail = run_dir_name if run_dir_name else f"{run_id[:8]}…"

    return f"{created_at} | {kind} | {tail}"


ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1])

with ctrl1:
    st.selectbox("Select run", options=run_ids, key="selected_run_id", format_func=_run_label)

with ctrl2:
    if st.button("Latest", width="stretch"):
        latest_id = get_latest_run_id(artifacts_root=s.artifacts_dir, db_path=s.db_path)
        if latest_id is None:
            st.warning("No latest run found.")
        else:
            st.session_state["selected_run_id"] = latest_id
            st.rerun()

with ctrl3:
    if st.button("Refresh", width="stretch"):
        st.rerun()

detail = get_run_detail(
    s.db_path,
    run_id=st.session_state["selected_run_id"],
    artifacts_root=s.artifacts_dir,
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
    st.code(_coerce_str(detail.get("run_id")))

with meta2:
    st.caption("Created at (KST)")
    st.code(_iso_to_kst(_coerce_str(detail.get("created_at"))))

with meta3:
    st.caption("Kind")
    st.code(_coerce_str(kind or "-"))

with meta4:
    st.caption("Git")
    git_commit = (_coerce_str(git.get("commit"))[:8]) if git.get("commit") else "-"
    git_branch = _coerce_str(git.get("branch") or "-")
    git_dirty = bool(git.get("dirty"))
    st.code(f"{git_commit} | {git_branch} | dirty={git_dirty}")

if detail.get("note"):
    st.caption("Note")
    st.write(_coerce_str(detail.get("note")))

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
            elif isinstance(v, (bytes, bytearray)):
                v2 = v.decode("utf-8", errors="replace")
            else:
                v2 = str(v)  

            kv_rows.append({"key": str(k), "value": v2})

        kv_df = pd.DataFrame(kv_rows).astype(str) 
        st.dataframe(kv_df, width="stretch", hide_index=True)


with tab_metrics:
    metrics = detail.get("metrics") or {}
    if not metrics:
        st.info("No metrics recorded for this run.")
    else:
        m_rows = [{"metric": k, "value": float(v)} for k, v in sorted(metrics.items())]
        st.dataframe(pd.DataFrame(m_rows), width="stretch", hide_index=True)

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
            pth = _resolve_path(s.artifacts_dir, a_path_raw)
            exists = pth.exists()
            is_file = exists and pth.is_file()
            size = pth.stat().st_size if is_file else None

            a_rows.append(
                {
                    "kind": a_kind,
                    "path": a_path_raw,
                    "exists": bool(exists),
                    "size": _fmt_bytes(size),
                }
            )
            grouped[str(a_kind)].append((str(a_path_raw), pth))

        st.dataframe(pd.DataFrame(a_rows), width="stretch", hide_index=True)
        st.caption("다운로드는 50MB 이하 파일에만 제공됩니다.")

        for a_kind in sorted(grouped.keys()):
            entries = grouped[a_kind]
            with st.expander(f"{a_kind} ({len(entries)})", expanded=True):
                for i, (raw, pth) in enumerate(entries):
                    c1, c2, c3 = st.columns([6, 2, 2])

                    with c1:
                        st.code(raw)
                        if not pth.is_absolute() and pth.exists():
                            try:
                                st.caption(str(pth.resolve()))
                            except Exception:
                                st.caption(str(pth))
                        elif pth.is_absolute():
                            st.caption(str(pth))

                    with c2:
                        if pth.exists() and pth.is_file():
                            st.caption(_fmt_bytes(pth.stat().st_size))
                        else:
                            st.caption("missing")

                    with c3:
                        if pth.exists() and pth.is_file():
                            size = pth.stat().st_size
                            if size <= max_download:
                                mtime_ns = pth.stat().st_mtime_ns
                                data = _read_file_bytes(str(pth), mtime_ns)
                                st.download_button(
                                    "Download",
                                    data=data,
                                    file_name=pth.name,
                                    key=f"dl_{detail['run_id']}_{a_kind}_{i}",
                                    width="stretch",
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
        # pointer 안에 created_at이 있는 경우도 KST로 같이 보여주기(있을 때만)
        view_pointer = pointer
        if isinstance(pointer, dict) and "created_at" in pointer:
            view_pointer = dict(pointer)
            view_pointer["created_at"] = _iso_to_kst(_coerce_str(pointer.get("created_at")))
        st.json(view_pointer)
