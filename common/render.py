import pandas as pd
import streamlit as st
from common.helper import add_bar_labels, category_counts_present, have_cols, make_count_df

# ---- helper to detect theme color ----
def get_theme_text_color():
    """Return appropriate text color based on Streamlit theme."""
    try:
        base_theme = (st.get_option("theme.base") or "light").lower()
        return "#FAFAFA" if base_theme == "dark" else "#111827"
    except:
        return "#111827"

# ---- generic renderers ----
def render_distribution(
    container, df_all, df_present, col, title, chart_func,
    drop_values=None, exclude_values=None,
    custom_counts=None,          # callable: (df_all, df_present, col) -> Series
    bar_with_labels=False,
    kind: str = "pie",           # "pie" or "bar"
    warn_text=None, info_text=None
):
    """
    Generic renderer for categorical distributions in a Streamlit column.
    Supports dark and light themes automatically.
    """
    text_color = get_theme_text_color()

    with container:
        # Render title dynamically with theme-aware color
        st.markdown(
            f"""
            <h5 style='text-align:center; color:{text_color} !important; background-color: transparent !important;'>
            {title}
            </h5>
            """,
            unsafe_allow_html=True
        )

        # Validate required columns
        required = col if isinstance(col, (list, tuple)) else [col]
        if not have_cols(df_all, col) or df_present.empty:
            st.info(info_text or f"Column(s) {required} not found or no present records.")
            return

        # Build counts
        if callable(custom_counts):
            counts = custom_counts(df_all, df_present, col)
        else:
            if isinstance(col, (list, tuple)):  # auto-counting only supports single column
                st.info(info_text or f"Column(s) {required} not suitable for automatic counting.")
                return
            counts = category_counts_present(
                df_all, df_present, col,
                drop_values=set(drop_values or []),
                exclude_values=set(exclude_values or [])
            )

        df_chart = make_count_df(counts)
        if df_chart.empty or df_chart["Count"].sum() == 0:
            st.warning(warn_text or f"No {title.lower()} data among present children.")
            return

        # BAR vs PIE (explicit)
        if kind == "bar":
            # 1) Sort by Count desc
            df_chart = df_chart.sort_values("Count", ascending=False).reset_index(drop=True)

            # 2) Freeze category order so Plotly keeps it
            df_chart["Category"] = pd.Categorical(
                df_chart["Category"],
                categories=df_chart["Category"].tolist(),
                ordered=True
            )

            # Labels after sorting
            if bar_with_labels and "Label" not in df_chart:
                df_chart = add_bar_labels(df_chart)

            label_series = df_chart["Label"] if "Label" in df_chart else None
            fig = chart_func(df_chart, "Category", "Count", label_series, title)
        else:
            fig = chart_func(df_chart, "Count", "Category", title)

        st.plotly_chart(fig, use_container_width=True)

# ---- render multiple charts ----
def render_many(specs, df_all, df_present):
    """
    specs: list of dict items with keys:
      container, col, title, chart_func, drop_values, exclude_values,
      custom_counts, bar_with_labels, kind, warn_text, info_text
    """
    for s in specs:
        render_distribution(
            container=s["container"],
            df_all=df_all,
            df_present=df_present,
            col=s["col"],
            title=s["title"],
            chart_func=s["chart_func"],
            drop_values=s.get("drop_values"),
            exclude_values=s.get("exclude_values"),
            custom_counts=s.get("custom_counts"),
            bar_with_labels=s.get("bar_with_labels", False),
            kind=s.get("kind", "pie"),
            warn_text=s.get("warn_text"),
            info_text=s.get("info_text"),
        )
