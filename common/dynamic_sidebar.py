# app.py
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Tuple

st.set_page_config(layout="wide")

# ---------------- Helpers ----------------
def _col_present(df: pd.DataFrame, col: Any) -> bool:
    return isinstance(col, str) and df is not None and col in df.columns

def _to_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")

def _init_session_for_filters(df: pd.DataFrame, col_mapping: Dict[str, str], filter_order: List[Dict[str, Any]]) -> None:
    for f in filter_order:
        key = f.get("session_key") or f["col"]
        typ = f.get("type", "multiselect")
        if typ == "date":
            col = col_mapping.get(f["col"])
            dt = _to_datetime(df[col].dropna()) if _col_present(df, col) else pd.Series([], dtype="datetime64[ns]")
            st.session_state.setdefault(key, (dt.min().date() if not dt.empty else None, dt.max().date() if not dt.empty else None))
        else:
            st.session_state.setdefault(key, [])

# ---------------- Filters ----------------
def _apply_date_filter(subset: pd.DataFrame, col: str, key: str, label: str, selections: Dict[str, Any]) -> pd.DataFrame:
    col_dt = _to_datetime(subset[col])
    if not col_dt.notna().any(): return subset
    mn, mx = col_dt.min().date(), col_dt.max().date()
    default_start, default_end = st.session_state.setdefault(key, (mn, mx))

    with st.sidebar.expander(label, expanded=False):
        c1, c2 = st.columns(2)
        start = c1.date_input("Start", value=st.session_state.get(f"{key}_start", default_start), min_value=mn, max_value=mx, key=f"{key}_start")
        end   = c2.date_input("End", value=st.session_state.get(f"{key}_end", default_end), min_value=mn, max_value=mx, key=f"{key}_end")

    if start > end: start, end = end, start
    st.session_state[key] = (start, end)
    selections[key] = f"{start.isoformat()} → {end.isoformat()}"

    start_dt = pd.Timestamp(start).normalize()
    end_dt   = pd.Timestamp(end).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return subset[(col_dt >= start_dt) & (col_dt <= end_dt)].copy()

def _apply_multiselect_filter(subset: pd.DataFrame, col: str, key: str, label: str, selections: Dict[str, Any]) -> pd.DataFrame:
    with st.sidebar.expander(label, expanded=False):
        s = subset[col].fillna("unknown")
        options = list(s.value_counts().sort_index().index)
        current = [v for v in st.session_state.setdefault(key, []) if v in options]
        sel = st.multiselect("Choose", options=options, default=current, key=key,
                             format_func=lambda v: f"{v} ({int(s.value_counts().get(v,0))})")
    selections[key] = ", ".join(map(str, sel)) if sel else ""
    return subset[s.isin(sel)].copy() if sel else subset

# ---------------- Main ----------------
def dynamic_sidebar_filters(df: pd.DataFrame, col_mapping: Dict[str, str], filter_order: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    subset = df.copy()
    selections: Dict[str, Any] = {}

    def clear_filters():
        for f in filter_order:
            base = f.get("session_key") or f["col"]
            for k in (base, f"{base}_start", f"{base}_end"):
                st.session_state.pop(k, None)
        _init_session_for_filters(df, col_mapping, filter_order)

    with st.sidebar:
        st.markdown("### 🔍 Filters")
        st.button("🧹 Clear", type="secondary", on_click=clear_filters)

    if any((f.get("session_key") or f["col"]) not in st.session_state for f in filter_order):
        _init_session_for_filters(df, col_mapping, filter_order)

    for f in filter_order:
        key = f.get("session_key") or f["col"]
        col = col_mapping.get(f["col"])
        if not _col_present(subset, col): continue
        if f.get("type", "multiselect") == "date":
            subset = _apply_date_filter(subset, col, key, f.get("label", key), selections)
        else:
            subset = _apply_multiselect_filter(subset, col, key, f.get("label", key), selections)

    return subset, selections
