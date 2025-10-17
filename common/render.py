import pandas as pd
import streamlit as st
from common.helper import add_bar_labels, category_counts_present, have_cols, make_count_df

# ---- theme-aware text color ----
def get_theme_text_color():
    try:
        return "#FAFAFA" if (st.get_option("theme.base") or "light").lower() == "dark" else "#1D7C48"
    except Exception:
        return "#111827"

def _show_chart(container, title, fig):
    with container:
        st.markdown(
            f"<h5 style='text-align:center;color:{get_theme_text_color()};'>{title}</h5>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig, use_container_width=True)

# ---- single distribution renderer ----
def render_distribution(
    container,
    df_all,
    df_present,
    col,
    title,
    chart_func,
    drop_values=None,
    exclude_values=None,
    custom_counts=None,
    bar_with_labels=False,
    kind="pie",
    warn_text=None,
    info_text=None,
    *,
    sex_col: str | None = None,
    normalize_category=None,
    chart_kwargs: dict | None = None,
):
    chart_kwargs = chart_kwargs or {}

    if df_present.empty or not have_cols(df_all, col):
        with container:
            st.info(info_text or f"No data for column: {col}")
        return

    # Grouped-by-sex path
    if kind == "grouped_sex":
        if not sex_col or not have_cols(df_all, sex_col):
            with container:
                st.info(info_text or f"No data for columns: {col} and/or {sex_col}")
            return

        fig = chart_func(
            df_present,
            col,
            sex_col,
            normalize_category=normalize_category,
            title=title,
            **chart_kwargs,
        )
        _show_chart(container, title, fig)
        return

    # Pie/Bar/vbar paths
    counts = custom_counts(df_all, df_present, col) if callable(custom_counts) else category_counts_present(
        df_all,
        df_present,
        col,
        drop_values=set(drop_values or []),
        exclude_values=set(exclude_values or []),
    )

    df_chart = make_count_df(counts)
    if df_chart.empty or df_chart["Count"].sum() == 0:
        with container:
            st.warning(warn_text or f"No {title.lower()} data available.")
        return

    # Horizontal bar: sort by Count desc (ranked view)
    if kind == "bar":
        df_chart = df_chart.sort_values("Count", ascending=False).reset_index(drop=True)
        df_chart["Category"] = pd.Categorical(df_chart["Category"], categories=df_chart["Category"], ordered=True)
        if bar_with_labels and "Label" not in df_chart:
            df_chart = add_bar_labels(df_chart)
        fig = chart_func(df_chart, "Category", "Count", df_chart.get("Label"), title)
        _show_chart(container, title, fig)
        return

    # Vertical bar (vbar): preserve incoming order (great for months)
    if kind == "vbar":
        # keep original order from counts; ensure categorical to lock axis order
        df_chart = df_chart.reset_index(drop=True)
        cat_order = df_chart["Category"].tolist()
        df_chart["Category"] = pd.Categorical(df_chart["Category"], categories=cat_order, ordered=True)
        # optional bar labels
        label_series = df_chart.get("Label")
        if bar_with_labels and label_series is None:
            # add_bar_labels works fine for vertical too; provides 'Label' column
            df_chart = add_bar_labels(df_chart)
            label_series = df_chart.get("Label")
        # pass category_order via chart_kwargs (builder.vbar supports it)
        ck = {"category_order": cat_order, **chart_kwargs}
        fig = chart_func(df_chart, x="Category", y="Count", text=label_series if label_series is not None else "Count", title=title, **ck)
        _show_chart(container, title, fig)
        return

    # Default: pie
    fig = chart_func(df_chart, "Count", "Category", title)
    _show_chart(container, title, fig)

# ---- render multiple charts ----
def render_many(specs, df_all, df_present):
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
            sex_col=s.get("sex_col"),
            normalize_category=s.get("normalize_category"),
            chart_kwargs=s.get("chart_kwargs"),
        )
