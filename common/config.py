# common/config.py
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterable, Tuple, Dict, Any, List, Union
import os

import pandas as pd
import streamlit as st
from common.helper import to_datetime_safe

# ---------------- Page-scoped state ----------------
def _hard_reset_on_page_change(page_key: str, keep: Optional[Iterable[str]] = None) -> None:
    prev = st.session_state.get("_cfg_current_page_key")
    if prev == page_key:
        return
    keep_keys = set(keep or []) | {"_cfg_current_page_key", "_cfg_filters_css_injected"}
    for k in list(st.session_state.keys()):
        if k not in keep_keys:
            st.session_state.pop(k, None)
    st.session_state["_cfg_current_page_key"] = page_key

# ---------------- Page setup ----------------
def setup_page(
    page_title: str = "📊 Dashboard",
    layout: str = "wide",
    sidebar_state: str = "expanded",
    *,
    page_key: Optional[str] = None,
    keep_state_keys: Optional[Iterable[str]] = None,
) -> None:
    st.set_page_config(page_title=page_title, layout=layout, initial_sidebar_state=sidebar_state)
    _hard_reset_on_page_change(page_key or page_title, keep_state_keys)

def get_data_path(filename: str, sheet=0) -> Tuple[Path,int]:
    DATA_PATH = Path(__file__).parent.parent / "pages" / "data" / filename
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Excel file not found at: {DATA_PATH}")
    return DATA_PATH, sheet

# ---------------- Data helpers ----------------
def _file_mtime(path: Path | str) -> float:
    try:
        return os.path.getmtime(str(path))
    except Exception:
        return 0.0

@st.cache_data(show_spinner=False)
def load_excel(path: Path | str, *, sheet: int | str = 0, _v: float | None = None) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    except Exception:
        df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip()
    return df

def pick_column(candidates: Iterable[str], columns: set[str]) -> Optional[str]:
    return next((c for c in candidates if c in columns), None)

def resolved_cols(df: pd.DataFrame, candidates: Dict[str, Iterable[str]]) -> Dict[str, Optional[str]]:
    cols = set(df.columns)
    return {key: pick_column(cands, cols) for key, cands in candidates.items()}

def load_df_or_stop(
    data_path: Path | str,
    sheet: int | str,
    *,
    candidates: Optional[Dict[str, Iterable[str]]] = None,
    date_key: str = "date",
) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    try:
        df = load_excel(data_path, sheet=sheet, _v=_file_mtime(data_path))
    except Exception as e:
        st.error(f"Could not load Excel file at {data_path}.\n{e}")
        st.stop()
    RES: Dict[str, Optional[str]] = resolved_cols(df, candidates) if candidates else {}
    date_col = RES.get(date_key) if RES else None
    if isinstance(date_col, str) and date_col in df.columns:
        df[date_col] = to_datetime_safe(df[date_col])
    return df, RES

# ---------------- Active filters ----------------
def _ensure_chip_css_once() -> None:
    key = "_cfg_filters_css_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True
    st.markdown("""
<style>
.cfg-filters { display:flex; flex-wrap:wrap; gap:.5rem 1rem; align-items:center; }
.cfg-filters .cfg-chip { display:inline-flex; align-items:center; gap:.4rem;
 padding:.25rem .55rem; border-radius:999px; border:1px solid rgba(2,6,23,0.12);
 background:rgba(241,245,249,.6); font-size:.92rem; color:#334155; white-space:nowrap; }
.cfg-filters .cfg-chip b { color:#0f172a; font-weight:700; }
.cfg-filters h4 { margin:0 0 .35rem 0; font-weight:800; color:#334155; }
</style>
""", unsafe_allow_html=True)

def _normalize_filters(active_filters: Union[Dict[str, Any], Iterable[Tuple[str, Any]], None]) -> List[Tuple[str,str]]:
    if not active_filters: return []
    items = active_filters.items() if isinstance(active_filters, dict) else list(active_filters)
    out: List[Tuple[str,str]] = []
    for k,v in items:
        if not v: continue
        if isinstance(v, tuple) and len(v)==2 and all(isinstance(d,(pd.Timestamp,datetime)) for d in v):
            v = f"{v[0].date()} → {v[1].date()}"
        elif isinstance(v,list):
            v = ", ".join(map(str,v))
        else:
            v = str(v)
        out.append((str(k),v))
    return out

def render_active_filters(active_filters: Union[Dict[str, Any], Iterable[Tuple[str, Any]], None],
                          *, heading_text: str="Active filters", show_heading=True,
                          separator_html: str="&nbsp;&nbsp;&nbsp;") -> None:
    pairs = _normalize_filters(active_filters)
    if not pairs: return
    _ensure_chip_css_once()
    parts = [f'<span class="cfg-chip"><b>{k}</b>: {v}</span>' for k,v in pairs]
    interleaved = [p + (separator_html if i<len(parts)-1 else "") for i,p in enumerate(parts)]
    if show_heading:
        st.markdown(f'<div class="cfg-filters"><h4>{heading_text}</h4></div>', unsafe_allow_html=True)
    st.markdown('<div class="cfg-filters">'+"".join(interleaved)+"</div>", unsafe_allow_html=True)

# ---------------- Shared Header ----------------
def render_page_header(title: str, data_path: Path | str, df: Optional[pd.DataFrame]=None,
                       col_spec: list[int]=[3,2,2,3],
                       *, active_filters: Union[Dict[str, Any], Iterable[Tuple[str, Any]], None]=None,
                       show_filters_heading: bool=True) -> Optional[bytes]:
    csv_bytes: Optional[bytes] = None
    with st.container():
        st.title(title)
        c1,c2,c3,c4 = st.columns(col_spec)
        try:
            mtime = os.path.getmtime(str(data_path))
            c1.caption(f"Last updated: **{datetime.fromtimestamp(mtime).strftime('%d-%m-%Y %H:%M')}**")
        except Exception:
            c1.caption("Last updated: —")
        if active_filters:
            render_active_filters(active_filters, heading_text="Active filters", show_heading=show_filters_heading)
        if df is not None and not df.empty:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
    return csv_bytes
