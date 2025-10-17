import hashlib
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
from typing import Optional, List, Tuple, Callable, Iterable, Dict
from streamlit.components.v1 import html

# ---------------- Default Theme ----------------
DEFAULT_THEME = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

# ==============================================================
#                         CHART BUILDER
# ==============================================================

class ChartBuilder:
    def __init__(self, color_theme: Optional[List[str]] = None):
        self.color_theme = color_theme or DEFAULT_THEME

    # ---------------- Helpers ----------------
    @staticmethod
    def _normalize_sex_series(s: pd.Series) -> pd.Series:
        if s is None:
            return pd.Series([], dtype="string")
        z = (
            s.astype(str)
            .str.strip()
            .str.lower()
            .replace({
                "m": "male",
                "male": "male",
                "man": "male",
                "boy": "male",
                "f": "female",
                "female": "female",
                "woman": "female",
                "girl": "female",
            })
        )
        return z.map({"male": "Male", "female": "Female"})

    @staticmethod
    def _normalize_newold_series(s: pd.Series) -> pd.Series:
        if s is None:
            return pd.Series([], dtype="string")
        raw = s.astype(str).str.strip().str.lower()
        out = raw.where(~raw.str.contains("new", na=False), other="new")
        out = out.where(~out.str.contains("old", na=False), other="old")
        return out.str.title()

    # ==============================================================
    #                           PIE CHART
    # ==============================================================

    def pie(
        self,
        df: pd.DataFrame,
        values: str,
        names: str,
        title: str = "",
        legend: bool = True,
        min_slice_percent_for_label: float = 0.7,
        *,
        auto_rotate: bool = True,            # NEW: rotate to center largest slice at 12 o'clock
        direction: str = "counterclockwise", # or "clockwise"
    ) -> Figure:
        total = float(df[values].sum() or 0)
        if total <= 0:
            return px.pie(
                pd.DataFrame({names: [], values: []}),
                values=values, names=names,
                color=names,
                color_discrete_sequence=self.color_theme,
            )

        # Sort so largest is first (deterministic rotation/legend order)
        df_sorted = df.sort_values(values, ascending=False).reset_index(drop=True)
        pct = (df_sorted[values] / total * 100).round(1)

        fig = px.pie(
            df_sorted,
            values=values,
            names=names,
            color=names,
            color_discrete_sequence=self.color_theme,
        )

        # Compute rotation so largest slice is centered at 12 o'clock
        rotation = 0
        if auto_rotate and len(df_sorted):
            largest = float(df_sorted.loc[0, values])
            ang = 360.0 * (largest / total)
            rotation = -ang / 2.0  # shift so its center hits 12 o'clock

        fig.update_traces(
            sort=False,                      # keep our sorted order
            direction=direction,
            rotation=rotation,
            text=df_sorted[values].astype(str) + " (" + pct.astype(str) + "%)",
            textinfo="text",
            textposition="auto",             # auto-switch inside/outside
            textfont=dict(size=14),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percent: %{percent}<extra></extra>",
            pull=[0.02 if p < min_slice_percent_for_label else 0 for p in pct],
            insidetextorientation="auto",
            marker=dict(line=dict(color="rgba(0,0,0,0)", width=0)),
            domain=dict(x=[0, 1], y=[0, 0.95]),  # fill more vertical space
        )

        fig.update_layout(
            autosize=True,
            height=420,
            width=None,
            showlegend=bool(legend or pct.lt(min_slice_percent_for_label).any()),
            legend=dict(
                orientation="h",
                y=-0.25,
                x=0.5,
                xanchor="center",
                font=dict(size=13),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=60, b=60, l=40, r=40),
        )

        return fig

    # ==============================================================
    #                           BAR CHART
    # ==============================================================

    def bar(self, df: pd.DataFrame, x: str, y: str, text: Optional[str] = None,
            title: str = "", legend=False, height=420) -> Figure:
        if text is None:
            text = y
        x_max = df[y].max() or 0
        headroom = max(int(x_max * 0.2), 5)
        fig = px.bar(
            df,
            x=y,
            y=x,
            text=text,
            color=x,
            orientation="h",
            color_discrete_sequence=self.color_theme
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(
            xaxis=dict(range=[0, x_max + headroom], showgrid=False, zeroline=False, automargin=True),
            yaxis=dict(showgrid=False, zeroline=False, automargin=True),
            showlegend=legend,
            margin=dict(t=60, b=60, l=60, r=60),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=height
        )
        return fig

    # ==============================================================
    #           GROUPED BY CATEGORY & SEX BAR CHART
    # ==============================================================

    def grouped_by_category_and_sex(
        self, df: pd.DataFrame, category_col: str, sex_col: str,
        normalize_category: Optional[Callable[[pd.Series], pd.Series]] = None,
        title: str = "", height=420, show_grid=False,
        category_order: Optional[List[str]] = None,
        sex_order: Optional[Tuple[str, ...]] = ("Male", "Female")
    ) -> Figure:
        if df is None or category_col not in df.columns or sex_col not in df.columns:
            return px.bar(pd.DataFrame(columns=["Category", "Sex", "Count"]))

        cat = normalize_category(df[category_col]) if normalize_category else df[category_col].astype(str).str.strip().str.title()
        sex = self._normalize_sex_series(df[sex_col])
        g = pd.DataFrame({"Category": cat, "Sex": sex}).dropna()
        if g.empty:
            return px.bar(pd.DataFrame(columns=["Category", "Sex", "Count"]))

        tbl = g.groupby(["Category", "Sex"], as_index=False).size().rename(columns={"size": "Count"})
        if category_order:
            tbl["Category"] = pd.Categorical(tbl["Category"], categories=category_order, ordered=True)
        if sex_order:
            tbl["Sex"] = pd.Categorical(tbl["Sex"], categories=list(sex_order), ordered=True)

        cmap = {s: self.color_theme[i % len(self.color_theme)] for i, s in enumerate(tbl["Sex"].astype(str).unique())}

        fig = px.bar(
            tbl, x="Category", y="Count", color="Sex", barmode="group",
            category_orders={"Category": category_order, "Sex": list(sex_order) if sex_order else None},
            color_discrete_map=cmap,
            text=tbl["Count"].astype(int).astype(str),
        )

        fig.update_traces(textposition="outside", cliponaxis=False)
        y_max = tbl["Count"].max() or 0
        fig.update_yaxes(range=[0, y_max + max(int(y_max * 0.2), 5)], showgrid=show_grid, zeroline=False)
        fig.update_xaxes(title_text=category_col.replace("_", " ").title(), showgrid=show_grid, zeroline=False)

        return fig

# ==============================================================
#                       UTILITIES
# ==============================================================

def _safe_key_from_fig(fig: Figure, prefix: str = "pie") -> str:
    j = fig.to_json().encode("utf-8")
    return f"{prefix}_{hashlib.md5(j).hexdigest()[:8]}"

def plotly_pie_click(fig: Figure, key: Optional[str] = None, height=420, width=420):
    key = key or _safe_key_from_fig(fig, "pie")
    fig_json = fig.to_json()
    payload = f"""
    <div id="{key}" style="width:100%; max-width:{width}px; height:{height}px;"></div>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
      const mountEl = document.getElementById("{key}");
      const fig = {fig_json};
      Plotly.newPlot(mountEl, fig.data, fig.layout, {{displayModeBar:false, responsive:true}});
      mountEl.on('plotly_click', function(evt){{
        const p = evt?.points?.[0]; if(!p) return;
        const out = {{label:p.label, value:p.value, percent:p.percent, pointNumber:p.pointNumber, curveNumber:p.curveNumber}};
        window.parent.postMessage({{isStreamlitMessage:true, type:"streamlit:setComponentValue", value:out}}, "*");
      }});
      window.addEventListener('resize',()=>Plotly.Plots.resize(mountEl));
    </script>
    """
    return html(payload, height=height)

# ==============================================================
#                       INSTANCE
# ==============================================================

builder = ChartBuilder(DEFAULT_THEME)
