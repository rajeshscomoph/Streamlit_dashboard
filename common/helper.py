import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, Set

# -------------------- Date utils --------------------
def to_datetime_safe(series: pd.Series) -> pd.Series:
    """
    Convert to datetime with errors coerced to NaT.
    Keeps index alignment and returns a Series.
    """
    if series is None or series.empty:
        return pd.to_datetime(pd.Series([], dtype="object"), errors="coerce")
    return pd.to_datetime(series, errors="coerce")


# -------------------- Column presence helpers --------------------
def need_cols(df: pd.DataFrame, *names: str) -> bool:
    """Return True if ALL provided column names are present (non-None and in df)."""
    if df is None or df.empty:
        return False
    return all((n is not None) and (n in df.columns) for n in names)

def have_cols(df: pd.DataFrame, col) -> bool:
    """col can be a single name or a tuple/list of names."""
    if isinstance(col, (list, tuple)):
        return need_cols(df, *col)
    return need_cols(df, col)


# -------------------- Series accessors --------------------
def safe_series(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    """
    Return a Series from df[col] if present; else an empty Series (object dtype).
    Assumes df is already normalized case-wise by the caller.
    """
    if df is None or col is None or col not in df.columns:
        return pd.Series(dtype="object")
    return df[col]


# -------------------- Cleaning / counts --------------------
def clean_referrals(s: pd.Series) -> pd.Series:
    """
    Remove blanks, the literal 'nan' (case-insensitive), and real NaNs.
    Preserves index of the remaining values.
    """
    if s is None or s.empty:
        return s
    s2 = s.astype("string")  # pandas NA-friendly string dtype
    s2 = s2.str.strip()
    s2 = s2.mask(s2.str.lower() == "nan", pd.NA).dropna()
    return s2[s2 != ""]


def make_count_df(counts: pd.Series) -> pd.DataFrame:
    """
    Build a tidy count+percentage dataframe from a counts Series.
    - Keeps the order of counts.index as-is (caller can pre-order).
    - Returns empty schema when counts empty or total==0.
    """
    if counts is None or len(counts) == 0:
        return pd.DataFrame(columns=["Category", "Count", "Percentage"])

    vals = pd.to_numeric(pd.Series(counts.values), errors="coerce").fillna(0)
    total = int(vals.sum())
    if total == 0:
        return pd.DataFrame(columns=["Category", "Count", "Percentage"])

    pct = (vals / total * 100).round(1)
    out = pd.DataFrame(
        {
            "Category": counts.index,
            "Count": vals.astype(int).values,
            "Percentage": pct.values,
        }
    )
    out["Category"] = out["Category"].astype("string")
    return out


# -------------------- UI helpers --------------------
def metric_card(
    title: str,
    value: str,
    help_text: Optional[str] = None,
    icon: str = "",
    color: str = "#2563eb",
    container=None,
):
    """
    Render a simple metric card. If `container` is None or lacks markdown(),
    it falls back to a lightweight shim (print-style).
    """
    html = f"""
<div style="
  border:1px solid rgba(2,6,23,0.08);
  border-radius:14px;
  padding:12px 14px;
  background:#fff;
  box-shadow:0 1px 1.5px rgba(2,6,23,.06), 0 8px 18px rgba(2,6,23,.04);
  ">
  <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
    <span style="font-size:1.05rem">{icon}</span>
    <span style="font-weight:700; color:#334155;">{title}</span>
  </div>
  <div style="font-size:1.25rem; font-weight:800; color:{color};">{value}</div>
  {f'<div style="margin-top:4px; font-size:.9rem; color:#64748b;">{help_text}</div>' if help_text else ''}
</div>
""".strip()
    try:
        if container is not None and hasattr(container, "markdown"):
            container.markdown(html, unsafe_allow_html=True)
        else:
            import streamlit as st  # local import to avoid hard dep at module import time
            st.markdown(html, unsafe_allow_html=True)
    except Exception:
        print(f"[metric_card] {title}: {value}" + (f" ({help_text})" if help_text else ""))


# -------------------- “present” subset counts --------------------
def category_counts_present(
    df_all: pd.DataFrame,
    df_present: pd.DataFrame,
    col: Optional[str],
    drop_values: Optional[Set[str]] = None,
    exclude_values: Optional[Set[str]] = None,
) -> pd.Series:
    """
    Build counts for a column restricted to 'present' subset.
      - drop_values: values to treat as NA and drop (e.g., {"", "nan"})
      - exclude_values: values to exclude from BOTH global ordering and present counts
    Returns a Series with the full category order derived from df_all (sorted).
    """
    if col is None:
        return pd.Series(dtype="int")

    s_all = safe_series(df_all, col)
    s_pre = safe_series(df_present, col)
    if s_all.empty or s_pre.empty:
        return pd.Series(dtype="int")

    s_all = s_all.astype("string")
    s_pre = s_pre.astype("string")

    if drop_values:
        s_all = s_all.mask(s_all.isin(drop_values), pd.NA)
        s_pre = s_pre.mask(s_pre.isin(drop_values), pd.NA)

    s_all = s_all.dropna()
    s_pre = s_pre.dropna()

    if exclude_values:
        s_all = s_all[~s_all.isin(exclude_values)]
        s_pre = s_pre[~s_pre.isin(exclude_values)]

    if s_all.empty:
        return pd.Series(dtype="int")

    all_order = pd.Index(sorted(s_all.unique().tolist()))
    counts = s_pre.value_counts().reindex(all_order, fill_value=0)

    if counts.dtype != "int":
        counts = counts.astype(int)
    return counts


# -------------------- Label helpers --------------------
def add_bar_labels(df_chart: pd.DataFrame) -> pd.DataFrame:
    """
    Append a 'Label' column like '123 (45.6%)'.
    Expects 'Count' and 'Percentage' columns (numeric). Returns a copy.
    """
    if df_chart is None or df_chart.empty:
        return df_chart

    df_out = df_chart.copy()

    df_out["Count"] = (
        pd.to_numeric(
            df_out.get("Count", pd.Series([np.nan] * len(df_out))),
            errors="coerce"
        ).fillna(0).astype(int)
    )

    df_out["Percentage"] = pd.to_numeric(
        df_out.get("Percentage", pd.Series([np.nan] * len(df_out))),
        errors="coerce"
    ).fillna(0.0)

    df_out["Label"] = df_out.apply(
        lambda r: f"{int(r['Count'])} ({round(float(r['Percentage']), 1)}%)", axis=1
    )
    return df_out


# -------------------- Global dataframe CSS (inject once) --------------------
_DATAFRAME_CSS = """
<style>
/* first st.dataframe on the page */
div[data-testid="stDataFrame"]:nth-of-type(1) [data-testid="stElementToolbar"] { display:none !important; }

/* hide column menu and header actions everywhere */
div[data-testid="stDataFrameColumnMenu"] { display:none !important; }
span[data-testid="stHeaderActionElements"] { display:none !important; }
</style>
"""

def inject_global_dataframe_css(state_key: str = "_global_df_css_injected") -> None:
    """
    Injects the shared st.dataframe CSS once per user session.
    Call this at the top of every page.
    """
    try:
        import streamlit as st
        if st.session_state.get(state_key):
            return
        st.session_state[state_key] = True
        st.markdown(_DATAFRAME_CSS, unsafe_allow_html=True)
    except Exception:
        # In non-Streamlit contexts, quietly do nothing.
        pass
