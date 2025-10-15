# common/config.py
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterable, Tuple, Dict, Any, List, Union
import os

import pandas as pd
import streamlit as st


# ==================== Internal: page-scoped state ====================

def _hard_reset_on_page_change(page_key: str, keep: Optional[Iterable[str]] = None) -> None:
    """
    If the current page differs from the last page, clear session_state
    (except a small, explicit whitelist) so filters/widgets don't carry over.

    keep: keys you want to preserve across pages (rarely needed).
    """
    prev = st.session_state.get("_cfg_current_page_key")
    if prev == page_key:
        return

    # Minimal whitelist we keep across pages
    keep_keys = set(keep or [])
    keep_keys.update({
        "_cfg_current_page_key",
        "_cfg_filters_css_injected",
    })

    # Delete everything else
    for k in list(st.session_state.keys()):
        if k not in keep_keys:
            try:
                del st.session_state[k]
            except Exception:
                pass

    st.session_state["_cfg_current_page_key"] = page_key


# ==================== Page setup ====================

def setup_page(
    page_title: str = "📊 Dashboard",
    layout: str = "wide",
    sidebar_state: str = "expanded",
    *,
    page_key: Optional[str] = None,
    keep_state_keys: Optional[Iterable[str]] = None,
) -> None:
    """
    Call at the top of every page.

    - page_key: UNIQUE id per page (e.g., "school_program", "pec").
      If omitted, page_title is used (less ideal if titles repeat).
    - keep_state_keys: optional iterable of session_state keys to keep
      across pages (normally leave empty).
    """
    st.set_page_config(page_title=page_title, layout=layout, initial_sidebar_state=sidebar_state)
    _hard_reset_on_page_change(page_key or page_title, keep=keep_state_keys)


def get_data_path(filename: str, sheet=0):
    """
    Return absolute Path for Excel file.
    If file not found, raises FileNotFoundError.
    """
    DATA_PATH = Path(r"D:\Streamlit_dashboard\pages\data") / filename  # <-- absolute path
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Excel file not found at: {DATA_PATH}")
    return DATA_PATH, sheet


# ==================== Data helpers (common across pages) ====================

def _file_mtime(path: Path | str) -> float:
    """Safe getmtime -> 0.0 on failure (usable as cache-busting version)."""
    try:
        return os.path.getmtime(str(path))
    except Exception:
        return 0.0


def to_datetime_safe(series: pd.Series) -> pd.Series:
    """
    Convert to datetime with errors coerced to NaT.
    Keeps index alignment and returns a Series.
    """
    if series is None or series.empty:
        return pd.to_datetime(pd.Series([], dtype="object"), errors="coerce")
    return pd.to_datetime(series, errors="coerce")


@st.cache_data(show_spinner=False)
def load_excel(path: Path | str, *, sheet: int | str = 0, _v: float | None = None) -> pd.DataFrame:
    """
    Load an Excel sheet with light normalization.
    `_v` is a dummy parameter you should pass `_file_mtime(path)` into,
    so the cache invalidates when the file changes.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    # try openpyxl first, fall back to default
    try:
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    except Exception:
        df = pd.read_excel(path, sheet_name=sheet)

    # normalize: lowercase/trim column names
    df.columns = [str(c).strip().lower() for c in df.columns]

    # strip whitespace in object cols
    obj_cols = df.select_dtypes(include="object").columns
    if len(obj_cols):
        df[obj_cols] = df[obj_cols].apply(lambda s: s.astype(str).str.strip())

    return df


def pick_column(candidates: Iterable[str], columns: set[str]) -> Optional[str]:
    """Return the first candidate that exists in `columns`, else None."""
    return next((c for c in candidates if c in columns), None)


def resolved_cols(df: pd.DataFrame, candidates: Dict[str, Iterable[str]]) -> Dict[str, Optional[str]]:
    """
    Given a DataFrame and a mapping like:
        CANDIDATES = {"date": ["screendate", "date"], "school_name": ["school", "school name"]}
    return a dict mapping each logical name -> the first matching column in df (or None).
    """
    cols = set(df.columns)
    return {key: pick_column(cands, cols) for key, cands in candidates.items()}


def need_cols(df: pd.DataFrame, *names: str) -> bool:
    """True if ALL provided column names are present (non-None and in df)."""
    if df is None or df.empty:
        return False
    return all((n is not None) and (n in df.columns) for n in names)


def have_cols(df: pd.DataFrame, col: Union[str, List[str], Tuple[str, ...]]) -> bool:
    """`col` can be a single name or a tuple/list of names."""
    if isinstance(col, (list, tuple)):
        return need_cols(df, *col)
    return need_cols(df, col)


def load_df_or_stop(
    data_path: Path | str,
    sheet: int | str,
    *,
    candidates: Optional[Dict[str, Iterable[str]]] = None,
    date_key: str = "date",
) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    """
    Unified snippet to use on EVERY page:

        df, RES = config.load_df_or_stop(DATA_PATH, SHEET, candidates=CANDIDATES)

    - Loads Excel (with cache) and stops the app with a friendly error if it fails.
    - Resolves columns using your CANDIDATES mapping (optional).
    - If a resolved date column exists, converts it with to_datetime_safe().
    - Returns (df, RES). If `candidates` is None, RES is {}.
    """
    try:
        df = load_excel(data_path, sheet=sheet, _v=_file_mtime(data_path))
    except Exception as e:
        st.error(f"Could not load Excel file at {data_path}.\n{e}")
        st.stop()

    RES: Dict[str, Optional[str]] = {}
    if candidates:
        RES = resolved_cols(df, candidates)
        date_col = RES.get(date_key)
        if isinstance(date_col, str) and date_col in df.columns:
            df[date_col] = to_datetime_safe(df[date_col])

    return df, RES


# ==================== Active filters (UI chips) ====================

def _ensure_chip_css_once() -> None:
    key = "_cfg_filters_css_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True
    st.markdown(
        """
<style>
.cfg-filters { display:flex; flex-wrap:wrap; gap:.5rem 1rem; align-items:center; }
.cfg-filters .cfg-chip {
  display:inline-flex; align-items:center; gap:.4rem;
  padding:.25rem .55rem; border-radius:999px;
  border:1px solid rgba(2,6,23,0.12); background:rgba(241,245,249,.6);
  font-size:.92rem; color:#334155; white-space:nowrap;
}
.cfg-filters .cfg-chip b { color:#0f172a; font-weight:700; }
.cfg-filters h4 { margin:0 0 .35rem 0; font-weight:800; color:#334155; }
</style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_filters(
    active_filters: Union[Dict[str, Any], Iterable[Tuple[str, Any]], None]
) -> List[Tuple[str, str]]:
    """
    Accepts dict {name: value} or iterable of (name, value).
    Returns list[(name, pretty_value)], dropping empty values.
    """
    if not active_filters:
        return []

    items = active_filters.items() if isinstance(active_filters, dict) else list(active_filters)

    def _pretty(v: Any) -> str:
        from datetime import datetime as _dt
        if isinstance(v, tuple) and len(v) == 2 and all(isinstance(d, (pd.Timestamp, _dt)) for d in v):
            left = v[0].date()
            right = v[1].date()
            return f"{left} → {right}"
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    out: List[Tuple[str, str]] = []
    for k, v in items:
        if v:
            out.append((str(k), _pretty(v)))
    return out


def render_active_filters(
    active_filters: Union[Dict[str, Any], Iterable[Tuple[str, Any]], None],
    *,
    heading_text: str = "Active filters",
    show_heading: bool = True,
    separator_html: str = "&nbsp;&nbsp;&nbsp;",  # explicit spacing between chips
) -> None:
    """
    Render compact 'chips' for current filters.
    """
    pairs = _normalize_filters(active_filters)
    if not pairs:
        return

    _ensure_chip_css_once()

    parts = [f'<span class="cfg-chip"><b>{k}</b>: {v}</span>' for k, v in pairs]

    # Interleave explicit separators so spacing works even if CSS gap isn't honored
    interleaved: List[str] = []
    for i, p in enumerate(parts):
        interleaved.append(p)
        if i < len(parts) - 1:
            interleaved.append(separator_html)

    chips_html = '<div class="cfg-filters">' + "".join(interleaved) + "</div>"

    if show_heading:
        st.markdown(f'<div class="cfg-filters"><h4>{heading_text}</h4></div>', unsafe_allow_html=True)

    st.markdown(chips_html, unsafe_allow_html=True)


# ==================== Shared Header ====================

def render_page_header(
    title: str,
    data_path: Path | str,
    df: Optional[pd.DataFrame] = None,
    col_spec: list[int] = [3, 2, 2, 3],
    *,
    active_filters: Union[Dict[str, Any], Iterable[Tuple[str, Any]], None] = None,
    show_filters_heading: bool = True,
) -> Optional[bytes]:
    """
    Standard page header used across pages:
      - Title
      - 'Last updated' (from file mtime of data_path)
      - Optional Active Filters row (chips)
      - Returns CSV bytes if df is provided and non-empty
    """
    csv_bytes: Optional[bytes] = None
    with st.container():
        st.title(title)
        c1, c2, c3, c4 = st.columns(col_spec)
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
