from __future__ import annotations

import pandas as pd
import streamlit as st

from balanceops.common.config import get_settings
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.db import connect
from balanceops.tracking.init_db import init_db


st.set_page_config(page_title="BalanceOps Dashboard", layout="wide")

s = get_settings()
init_db(s.db_path)

st.title("BalanceOps Dashboard")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Current Model")
    info = get_current_model_info()
    st.json(info)

with col2:
    st.subheader("DB")
    st.code(s.db_path)

con = connect(s.db_path)

runs = pd.read_sql_query(
    "SELECT run_id, created_at, git_commit, git_branch, git_dirty, note FROM runs ORDER BY created_at DESC LIMIT 20",
    con,
)
metrics = pd.read_sql_query(
    "SELECT run_id, key, value FROM metrics",
    con,
)
con.close()

st.subheader("Recent Runs")
st.dataframe(runs, use_container_width=True)

st.subheader("Metrics (pivot)")
if len(metrics) == 0:
    st.info("No metrics yet. Try running demo_run.")
else:
    pivot = metrics.pivot_table(index="run_id", columns="key", values="value", aggfunc="max").reset_index()
    st.dataframe(pivot, use_container_width=True)
