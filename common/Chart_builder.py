import hashlib
from typing import Optional, List, Tuple, Callable, Dict, Iterable
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
from streamlit.components.v1 import html

# ---------- Chart Builder ----------
DEFAULT_THEME = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]


class ChartBuilder:
    def __init__(self, color_theme: Optional[List[str]] = None):
        # fall back to default theme if None
        self.color_theme = color_theme or DEFAULT_THEME

    # ------------------------ helpers ------------------------
    @staticmethod
    def _normalize_sex_series(s: pd.Series) -> pd.Series:
        if s is None:
            return pd.Series([], dtype="string")
        z = (
            s.astype("string")
             .str.strip()
             .str.lower()
             .replace({
                 "m": "male", "male": "male", "man": "male", "boy": "male",
                 "f": "female", "female": "female", "woman": "female", "girl": "female",
             })
        )
        return z.map({"male": "Male", "female": "Female"})

    @staticmethod
    def _normalize_newold_series(s: pd.Series) -> pd.Series:
        """Map noisy 'new/old' entries to 'New' / 'Old' (fallback to title-case)."""
        if s is None:
            return pd.Series([], dtype="string")
        raw = s.astype("string").str.strip().str.lower()
        out = raw.where(~raw.str.contains("new", na=False), other="new")
        out = out.where(~out.str.contains("old", na=False), other="old")
        return out.str.title()

    # ------------------------ charts -------------------------
    def pie(
        self,
        df_chart: pd.DataFrame,
        values: str,
        names: str,
        title: str = "",
        legend: bool = True,
        height: int = 420,
        width: int = 420,
        min_slice_percent_for_label: float = 0.7,
    ) -> Figure:
        # Precompute pct for robust custom text
        total = df_chart[values].sum() or 1
        pct = (df_chart[values] / total * 100).round(1)

        fig = px.pie(
            df_chart,
            values=values,
            names=names,
            color=names,
            color_discrete_sequence=self.color_theme,
        )

        fig.update_traces(
            text=df_chart[values].astype(str) + " (" + pct.astype(str) + "%)",
            textinfo="text",
            textposition="outside",
            textfont=dict(size=12),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percent: %{percent}<extra></extra>",
            automargin=True,
            pull=[0.02 if p < min_slice_percent_for_label else 0 for p in pct],
            domain=dict(x=[0, 1], y=[0, 1]),
        )

        showlegend_final = legend or (pct.lt(min_slice_percent_for_label).any())

        fig.update_layout(
            showlegend=showlegend_final,
            legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=60, l=40, r=40),
            height=height,
            width=width,
        )
        return fig

    def bar(
        self,
        df_chart: pd.DataFrame,
        x: str,  # categorical
        y: str,  # numeric
        text: Optional[str] = None,
        title: str = "",
        legend: bool = False,
        height: int = 420,
    ) -> Figure:
        """Horizontal bar chart (categories on Y, values on X)."""
        if text is None:
            text = y

        x_max = df_chart[y].max() or 0
        headroom = max(int(x_max * 0.2), 5)
        x_top = x_max + headroom

        fig = px.bar(
            df_chart,
            x=y,
            y=x,
            text=text,
            color=x,
            orientation="h",
            color_discrete_sequence=self.color_theme,
        )

        fig.update_traces(textposition="outside", cliponaxis=False)

        fig.update_layout(
            xaxis_title="",
            yaxis_title="",
            xaxis=dict(range=[0, x_top], showgrid=False, zeroline=False, automargin=True),
            yaxis=dict(showgrid=False, zeroline=False, automargin=True),
            uniformtext_minsize=10,
            uniformtext_mode="show",
            showlegend=legend,
            margin=dict(t=60, b=60, l=60, r=60),
            height=height,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    # ---------- Reusable grouped bar: Category × Sex ----------
    def grouped_by_category_and_sex(
        self,
        df: pd.DataFrame,
        category_col: str,              # e.g. "no", "wear_glass"
        sex_col: str,                   # e.g. "sex"
        *,
        normalize_category: Optional[Callable[[pd.Series], pd.Series]] = None,
        title: str = "",
        height: int = 420,
        show_grid: bool = False,
        category_order: Optional[List[str]] = None,
        sex_order: Optional[Tuple[str, ...]] = ("Male", "Female"),
    ) -> Figure:
        if df is None or category_col not in df.columns or sex_col not in df.columns:
            return px.bar(pd.DataFrame(columns=["Category", "Sex", "Count"]))

        # Normalize category & sex
        cat = df[category_col]
        if normalize_category:
            cat = normalize_category(cat)
        else:
            cat = cat.astype("string").str.strip().str.title()

        sex = self._normalize_sex_series(df[sex_col])

        g = pd.DataFrame({"Category": cat, "Sex": sex}).dropna()
        if g.empty:
            return px.bar(pd.DataFrame(columns=["Category", "Sex", "Count"]))

        # Aggregate
        tbl = (
            g.groupby(["Category", "Sex"], as_index=False)
             .size()
             .rename(columns={"size": "Count"})
        )

        # Ordering
        if category_order:
            tbl["Category"] = pd.Categorical(tbl["Category"], categories=category_order, ordered=True)
        if sex_order:
            tbl["Sex"] = pd.Categorical(tbl["Sex"], categories=list(sex_order), ordered=True)

        # Stable color map for sex
        cmap: Dict[str, str] = {
            s: self.color_theme[i % len(self.color_theme)]
            for i, s in enumerate(tbl["Sex"].astype(str).unique())
        }

        fig = px.bar(
            tbl,
            x="Category",
            y="Count",
            color="Sex",
            barmode="group",
            category_orders={
                "Category": category_order if category_order else None,
                "Sex": list(sex_order) if sex_order else None,
            },
            color_discrete_map=cmap,
            text=tbl["Count"].astype(int).astype(str),
            title=title,
        )

        fig.update_traces(textposition="outside", cliponaxis=False)

        # Headroom for labels
        y_max = (tbl["Count"].max() or 0)
        headroom = max(int(y_max * 0.2), 5)
        fig.update_yaxes(range=[0, y_max + headroom], title_text="", showgrid=show_grid, zeroline=False)
        fig.update_xaxes(title_text=str(category_col).replace("_", " ").title(), showgrid=show_grid, zeroline=False)

        fig.update_layout(
            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
            margin=dict(t=60, b=60, l=40, r=60),
            height=height,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            uniformtext_minsize=10,
            uniformtext_mode="show",
            bargap=0.2,
            bargroupgap=0.1,
            font=dict(size=12),
        )
        return fig

    # ---------- Build many grouped charts at once ----------
    def grouped_many_by_category_and_sex(
        self,
        df: pd.DataFrame,
        items: Iterable[Dict],
        sex_col: str,
        *,
        height: int = 260,
        show_grid: bool = False,
        default_sex_order: Optional[Tuple[str, ...]] = ("Male", "Female"),
    ) -> List[Tuple[str, Figure]]:
        """
        Build several Category × Sex charts at once.

        items: iterable of dicts, each can contain:
          {
            "category_col": str,                       # REQUIRED
            "title": str,                              # REQUIRED
            "normalize_category": callable | None,     # OPTIONAL
            "category_order": list[str] | None,        # OPTIONAL
            "sex_order": tuple[str, ...] | None        # OPTIONAL
          }

        Returns: list of (title, figure)
        """
        figs: List[Tuple[str, Figure]] = []
        for it in items:
            category_col = it.get("category_col")
            title = it.get("title", category_col or "")
            norm_fn = it.get("normalize_category")
            cat_order = it.get("category_order")
            sex_order = it.get("sex_order", default_sex_order)

            fig = self.grouped_by_category_and_sex(
                df=df,
                category_col=category_col,
                sex_col=sex_col,
                normalize_category=norm_fn,
                title=title,
                height=height,
                show_grid=show_grid,
                category_order=cat_order,
                sex_order=sex_order,
            )
            figs.append((title, fig))
        return figs

    # Convenience wrapper for legacy “New/Old by Sex”
    def grouped_new_old_by_sex(
        self,
        df: pd.DataFrame,
        new_old_col: str,
        sex_col: str,
        *,
        percent: bool = False,   # kept for signature compatibility, ignored
        title: str = "New/Old by Sex",
        height: int = 420,
    ) -> Figure:
        return self.grouped_by_category_and_sex(
            df=df,
           category_col=new_old_col,
            sex_col=sex_col,
            normalize_category=self._normalize_newold_series,
            title=title,
            height=height,
            show_grid=False,
            category_order=["New", "Old"],
            sex_order=("Male", "Female"),
        )

# Instantiate with your theme
builder = ChartBuilder(DEFAULT_THEME)

# ---------- Helpers for Streamlit HTML-embedded Plotly ----------
def _safe_key_from_fig(fig: Figure, prefix: str = "pie") -> str:
    j = fig.to_json().encode("utf-8")
    h = hashlib.md5(j).hexdigest()[:8]
    return f"{prefix}_{h}"

def plotly_pie_click(fig: Figure, key: Optional[str] = None, height: int = 420, width: int = 420):
    """Render a Plotly figure and return the clicked slice payload (or None) via Streamlit component messaging."""
    key = key or _safe_key_from_fig(fig, "pie")
    fig_json = fig.to_json()

    payload = f"""
    <div id="{key}" style="width:100%; max-width:{width}px; height:{height}px;"></div>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
      const mountEl = document.getElementById("{key}");
      const fig = {fig_json};
      function render() {{
        Plotly.newPlot(mountEl, fig.data, fig.layout, {{displayModeBar: false, responsive: true}});
      }}
      render();
      window.addEventListener('resize', () => {{
        Plotly.Plots.resize(mountEl);
      }});
      function sendValue(val) {{
        const msg = {{
          isStreamlitMessage: true,
          type: "streamlit:setComponentValue",
          value: val
        }};
        window.parent.postMessage(msg, "*");
        const legacy = {{
          isStreamlitMessage: true,
          type: "streamlit:componentValue",
          value: val
        }};
        window.parent.postMessage(legacy, "*");
      }}
      mountEl.on('plotly_click', function(evt) {{
        const p = evt?.points?.[0];
        if (!p) return;
        const out = {{
          label: p.label,
          value: p.value,
          percent: p.percent,
          pointNumber: p.pointNumber,
          curveNumber: p.curveNumber
        }};
        sendValue(out);
      }});
    </script>
    """
    return html(payload, height=height)
