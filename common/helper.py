from datetime import date
import pandas as pd
import numpy as np
from typing import Optional, Set
import streamlit as st

# -------------------- Date utils --------------------
def to_datetime_safe(series) -> pd.Series:
    """Convert input to datetime safely."""
    return pd.to_datetime(pd.Series(series), errors="coerce") if series is not None else pd.Series([], dtype="datetime64[ns]")

# -------------------- Column helpers --------------------
def have_cols(df: pd.DataFrame, cols) -> bool:
    """Check if df has all specified columns."""
    if df is None or df.empty:
        return False
    if isinstance(cols, (list, tuple)):
        return all(c in df.columns for c in cols)
    return cols in df.columns

def safe_series(df: Optional[pd.DataFrame], col: Optional[str]) -> pd.Series:
    """Return df[col] if exists, else empty Series."""
    if df is None or col is None or col not in df.columns:
        return pd.Series([], dtype="object")
    s = df[col]
    return pd.Series(s) if isinstance(s, (list, np.ndarray)) else s

# -------------------- Cleaning / counts --------------------
def clean_referrals(s) -> pd.Series:
    """Remove blanks, 'nan', NaN."""
    if s is None:
        return pd.Series([], dtype="object")
    s = pd.Series(s).astype("string").str.strip()
    s = s.mask(s.str.lower() == "nan", pd.NA).dropna()
    return s[s != ""]

def make_count_df(counts) -> pd.DataFrame:
    """Build count+percentage dataframe."""
    counts = pd.Series(counts) if counts is not None and not isinstance(counts, pd.Series) else counts
    if counts is None or counts.empty:
        return pd.DataFrame(columns=["Category","Count","Percentage"])
    vals = np.nan_to_num(pd.to_numeric(counts.values, errors="coerce")).astype(int)
    total = vals.sum()
    if total == 0:
        return pd.DataFrame(columns=["Category","Count","Percentage"])
    pct = np.round(vals / total * 100, 1)
    index = counts.index if hasattr(counts, "index") else range(len(vals))
    return pd.DataFrame({"Category": pd.Series(index, dtype="string"), "Count": vals, "Percentage": pct})

def category_counts_present(df_all, df_present, col: Optional[str], drop_values: Optional[Set[str]] = None, exclude_values: Optional[Set[str]] = None) -> pd.Series:
    """Counts for a column restricted to a subset, preserving all categories."""
    s_all = safe_series(df_all, col).astype("string")
    s_pre = safe_series(df_present, col).astype("string")
    if s_all.empty or s_pre.empty:
        return pd.Series(dtype="int")
    if drop_values:
        s_all = s_all[~s_all.isin(drop_values)]
        s_pre = s_pre[~s_pre.isin(drop_values)]
    if exclude_values:
        s_all = s_all[~s_all.isin(exclude_values)]
        s_pre = s_pre[~s_pre.isin(exclude_values)]
    return s_pre.value_counts().reindex(sorted(s_all.unique()), fill_value=0).astype(int)

# -------------------- Label helpers --------------------
def add_bar_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'Label' column like '123 (45.6%)'."""
    if df is None or df.empty:
        return df
    df_out = df.copy()
    df_out["Count"] = pd.to_numeric(df_out.get("Count",0), errors="coerce").fillna(0).astype(int)
    df_out["Percentage"] = pd.to_numeric(df_out.get("Percentage",0.0), errors="coerce").fillna(0.0)
    df_out["Label"] = df_out.apply(lambda r: f"{int(r['Count'])} ({round(r['Percentage'],1)}%)", axis=1)
    return df_out

# -------------------- UI helpers --------------------
def metric_card(title: str, value: str, help_text: Optional[str] = None, icon: str = "", color: str = "#2563eb", container=None):
    """Render simple metric card (Streamlit or HTML)."""
    html = f"""
<div style="border:1px solid rgba(2,6,23,0.08);border-radius:14px;padding:12px 14px;background:#fff;
box-shadow:0 1px 1.5px rgba(2,6,23,.06),0 8px 18px rgba(2,6,23,.04);">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <span style="font-size:1.05rem">{icon}</span>
    <span style="font-weight:700;color:#334155;">{title}</span>
  </div>
  <div style="font-size:1.25rem;font-weight:800;color:{color};">{value}</div>
  {f'<div style="margin-top:4px;font-size:.9rem;color:#64748b;">{help_text}</div>' if help_text else ''}
</div>
"""
    try:
        if container and hasattr(container, "markdown"):
            container.markdown(html, unsafe_allow_html=True)
        else:
            st.markdown(html, unsafe_allow_html=True)
    except Exception:
        pass

# Helpers
def is_done(val):
    if pd.isna(val): return False
    if isinstance(val, (bool, int, float,date)): return bool(val)
    return str(val).strip().lower() in {"yes","y","true","1"}

def render_metric_cards(
    metrics: dict[str, tuple[str, str | None]],
    df: pd.DataFrame,
    res: dict,
    *,
    is_done_fn=is_done,
    metric_card_fn=metric_card,
    columns=None
) -> None:
    """
    Render metric cards from a spec dict:
      metrics = { "Title": (col_name, base_col_or_None), ... }

    - Shows total count per metric.
    - If base_col is provided, shows 'count (pct%)' where pct = count/base*100.
    - If a sex column exists, adds help_text 'M:x | F:y'.
    """
    sex_col = res.get("sex")
    # Optional: use provided columns layout, else auto-create
    cols = columns or st.columns(len(metrics))

    def _count_done(col: str) -> int:
        return df[col].apply(is_done_fn).sum() if col in df.columns else 0

    for col_block, (title, (col_name, base_col)) in zip(cols, metrics.items()):
        with col_block:
            # main value
            val = _count_done(col_name)
            # gender breakdown
            help_txt = ""
            if sex_col and sex_col in df.columns and col_name in df.columns:
                done_data = df[df[col_name].apply(is_done_fn)]
                if not done_data.empty:
                    s = done_data[sex_col].astype(str).str.strip().str.lower()
                    m = int(s.isin({"male","m","man","boy"}).sum())
                    w = int(s.isin({"female","f","woman","girl"}).sum())
                    help_txt = f"M:{m} | F:{w}"

            # percentage vs base (if provided)
            display_val = val
            if base_col:
                base_val = _count_done(base_col)
                pct = (val / base_val * 100.0) if base_val else 0.0
                display_val = f"{val} ({pct:.1f}%)"

            metric_card_fn(title, display_val, help_text=help_txt)

# -------------------- Global dataframe CSS --------------------
_DATAFRAME_CSS = """
<style>
div[data-testid="stDataFrame"]:nth-of-type(1) [data-testid="stElementToolbar"] { display:none !important; }
div[data-testid="stDataFrameColumnMenu"] { display:none !important; }
span[data-testid="stHeaderActionElements"] { display:none !important; }
</style>
"""

def inject_global_dataframe_css(state_key: str="_global_df_css_injected"):
    """Inject shared st.dataframe CSS once per session."""
    try:
        import streamlit as st
        if not st.session_state.get(state_key):
            st.session_state[state_key] = True
            st.markdown(_DATAFRAME_CSS, unsafe_allow_html=True)
    except Exception:
        pass
