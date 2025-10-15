import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Tuple

def _col_present(df: pd.DataFrame, col: Any) -> bool:
    return isinstance(col, str) and (df is not None) and (col in df.columns)

def _to_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")

def _init_session_for_filters(df: pd.DataFrame, col_mapping: Dict[str, str], filter_order: List[Dict[str, Any]]) -> None:
    """Ensure every filter key exists in session with a sensible default (only used by Reset)."""
    for f in filter_order:
        key = f.get("session_key") or f["col"]
        typ = f.get("type", "multiselect")
        if typ == "date":
            col = col_mapping.get(f["col"])
            if _col_present(df, col):
                dt = _to_datetime(df[col].dropna())
                st.session_state[key] = (dt.min().date(), dt.max().date()) if not dt.empty else (None, None)
            else:
                st.session_state[key] = (None, None)
        else:
            st.session_state[key] = []

def _apply_date_filter(subset: pd.DataFrame, col: str, key: str, label: str, selections: Dict[str, Any]) -> pd.DataFrame:
    col_dt = _to_datetime(subset[col])
    if not col_dt.notna().any():
        return subset

    mn, mx = col_dt.min().date(), col_dt.max().date()
    cur = st.session_state.get(key)
    if not (isinstance(cur, tuple) and len(cur) == 2):
        st.session_state[key] = (mn, mx)

    with st.sidebar.expander(label, expanded=False):
        c1, c2 = st.columns(2)
        start = c1.date_input("Start", value=st.session_state[key][0] or mn, min_value=mn, max_value=mx, key=f"{key}_start")
        end   = c2.date_input("End",   value=st.session_state[key][1] or mx, min_value=mn, max_value=mx, key=f"{key}_end")

    if start > end:
        start, end = end, start
    st.session_state[key] = (start, end)
    selections[key] = f"{start.isoformat()} → {end.isoformat()}"

    start_dt = pd.Timestamp(start).normalize()  # 00:00:00
    end_dt   = pd.Timestamp(end).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    mask = (col_dt >= start_dt) & (col_dt <= end_dt)
    return subset[mask].copy()

def _apply_multiselect_filter(subset: pd.DataFrame, col: str, key: str, label: str, selections: Dict[str, Any]) -> pd.DataFrame:
    with st.sidebar.expander(label, expanded=False):
        s = subset[col].fillna("unknown")
        counts = s.value_counts().sort_index()
        options = list(counts.index)
        st.session_state.setdefault(key, [])
        current = [v for v in st.session_state[key] if v in options]
        sel = st.multiselect(
            "Choose", options=options, default=current, key=key,
            format_func=lambda v: f"{v} ({int(counts.get(v,0))})"
        )
    selections[key] = ", ".join(map(str, sel)) if sel else ""
    return subset[s.fillna("unknown").isin(sel)].copy() if sel else subset

def dynamic_sidebar_filters(
    df: pd.DataFrame,
    col_mapping: Dict[str, str],
    filter_order: List[Dict[str, Any]]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply cascading sidebar filters (date + multiselect). Returns (filtered_df, selections_summary)."""
    st.sidebar.header("🔍 Filters")
    subset = df.copy()
    selections: Dict[str, Any] = {}

    # Controls
    with st.sidebar:
        c1, c2 = st.columns(2)
        if c1.button("🧹 Clear", type="secondary"):
            _init_session_for_filters(df, col_mapping, filter_order)
            st.rerun()
        c2.button("🔄 Refresh", type="secondary", on_click=lambda: st.cache_data.clear())
    # Apply filters in sequence
    for f in filter_order:
        logic_col = f["col"]
        typ = f.get("type", "multiselect")
        label = f.get("label", logic_col)
        key = f.get("session_key") or logic_col
        resolved = col_mapping.get(logic_col)

        if not _col_present(subset, resolved):
            continue

        if typ == "date":
            subset = _apply_date_filter(subset, resolved, key, label, selections)
        else:
            subset = _apply_multiselect_filter(subset, resolved, key, label, selections)

    return subset, selections
