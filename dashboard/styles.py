# ruff: noqa: E501
from __future__ import annotations

APP_CSS = """
<style>
:root {--bg:#050505;--panel:#101010;--border:#2a2a2a;--text:#efefef;--muted:#9b9b9b;}
html, body, [data-testid="stAppViewContainer"] {background:linear-gradient(180deg,#030303,#090909);color:var(--text);}
[data-testid="stHeader"]{background:transparent;} [data-testid="stToolbar"],[data-testid="stDecoration"]{visibility:hidden;height:0;}
.block-container{max-width:1650px;padding-top:1rem;padding-bottom:3rem;}
.brand{display:flex;align-items:center;gap:.8rem;margin-bottom:.9rem}.mark{width:42px;height:42px;border:1px solid #777;transform:rotate(30deg);border-radius:9px;background:linear-gradient(145deg,#eee,#777 48%,#222);box-shadow:inset 0 0 0 6px #080808}.word{font-size:2.35rem;font-weight:500;background:linear-gradient(180deg,#fafafa,#777 58%,#ddd);-webkit-background-clip:text;color:transparent}
[data-testid="stMetric"]{background:linear-gradient(145deg,#151515,#090909);border:1px solid #292929;border-radius:13px;padding:.85rem 1rem}[data-testid="stMetricValue"]{color:#eee}[data-testid="stMetricLabel"]{color:#aaa}
[data-testid="stExpander"]{border:1px solid #2c2c2c;border-radius:11px;background:linear-gradient(180deg,#121212,#0b0b0b)}
.stButton>button,.stDownloadButton>button{border:1px solid #777!important;color:#090909!important;background:linear-gradient(180deg,#eee,#999)!important;font-weight:700;box-shadow:inset 0 1px 0 #fff,0 8px 25px rgba(0,0,0,.25)}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,[data-testid="stNumberInput"] input{background:#090909!important;border-color:#303030!important}
footer{visibility:hidden}
</style>
"""
PLOTLY_LAYOUT = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#d6d6d6"},
    "xaxis": {"gridcolor": "#222"},
    "yaxis": {"gridcolor": "#222"},
    "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
}
