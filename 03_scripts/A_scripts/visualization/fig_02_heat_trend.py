#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 heat_trend_real.csv 生成三联分面折线图（主帖互动指标）。"""

import csv
import math
import subprocess
import sys
from dataclasses import dataclass

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from paths import FIG_DIR, ROOT_DIR

CSV_PATH = ROOT_DIR / "heat_trend_real.csv"
OUT_HTML = FIG_DIR / "fig_02_heat_trend.html"
OUT_PNG = FIG_DIR / "fig_02_heat_trend.png"

FIG_WIDTH = 1100
FIG_HEIGHT = 900
EXPORT_SCALE = 300 / 96  # kaleido 默认按 96dpi，scale≈3.125 → ≥300dpi

C_POST = "#C07858"
C_COMMENT = "#5A7A6A"
C_REPOST = "#8C8C8C"
C_PEAK = "#A05050"
C_BG = "#F5F3EE"  # 风格规范 · 亚麻白画布
FONT = "Microsoft YaHei, SimHei, sans-serif"

TITLE = "图2 《年轮》争议事件微博传播热度演化趋势"
SUBTITLE = "微博互动指标汇总（2025-07-22 ~ 2025-08-10）"
Y_TITLE = "互动量（次）"
Y_GRID_INTERVALS = 5  # 各子图主网格约 5 个区间（6 条刻度含 0）


@dataclass(frozen=True)
class EventMarker:
    """子图事件标注：date 竖线仅画在 row 对应面板。"""

    date: str
    note: str
    row: int  # 1=发帖 2=评论 3=转发
    ax: int = 70
    ay: int = -50


EVENT_MARKERS: tuple[EventMarker, ...] = (
    EventMarker(
        "2025-07-25",
        "汪苏泷收回版权<br>张碧晨Studio声明、媒体集中报道、争议爆发",
        row=2,
        ax=70,
        ay=-50,
    ),
    EventMarker(
        "2025-07-31",
        "合肥演唱会演唱《年轮》，发帖量峰值",
        row=1,
        ax=-95,
        ay=-42,
    ),
    EventMarker(
        "2025-08-04",
        "粉丝不限圈澄清抽奖，转发次峰",
        row=3,
        ax=-95,
        ay=-48,
    ),
)


@dataclass(frozen=True)
class Fig02Config:
    title: str
    subtitle: str
    y_title: str
    markers: tuple[EventMarker, ...]
    hover_post: str
    hover_comment: str
    hover_repost: str


DEFAULT_CONFIG = Fig02Config(
    title=TITLE,
    subtitle=SUBTITLE,
    y_title=Y_TITLE,
    markers=EVENT_MARKERS,
    hover_post="发帖量：%{y} 条<br>日期：%{x}<extra></extra>",
    hover_comment="评论互动：%{y:,} 次<br>日期：%{x}<extra></extra>",
    hover_repost="转发互动：%{y:,} 次<br>日期：%{x}<extra></extra>",
)

# 三子图共用 Y 轴网格样式（避免第三行被 x 轴默认网格覆盖视觉）
YAXIS_GRID_STYLE = dict(
    showgrid=True,
    gridwidth=1,
    gridcolor="rgba(140,140,140,0.2)",
    zeroline=True,
    zerolinewidth=1,
    zerolinecolor="rgba(140,140,140,0.2)",
)
XAXIS_GRID_STYLE = dict(
    showgrid=False,
    gridwidth=1,
    gridcolor="rgba(140,140,140,0.2)",
    zeroline=False,
)
PANEL_DIVIDER_COLOR = "rgba(150,150,150,0.45)"
PANEL_DIVIDER_WIDTH = 1
PANEL_DIVIDER_SHIFT = 0.012  # 分隔线略下移（paper 坐标）
SUBTITLE_GAP_HTML = "<br>"  # 主标题与副标题之间一行间距
SUBTITLE_STYLE = "font-size:14px;color:#555;display:block;margin-top:5px"


def _nice_step(raw_step: float) -> float:
    """将步长取为 1/2/5×10^n，便于阅读。"""
    if raw_step <= 0:
        return 1.0
    exp = math.floor(math.log10(raw_step))
    frac = raw_step / 10**exp
    if frac <= 1:
        nice = 1
    elif frac <= 2:
        nice = 2
    elif frac <= 5:
        nice = 5
    else:
        nice = 10
    return nice * 10**exp


def y_axis_ticks(values: list[int], n_intervals: int = Y_GRID_INTERVALS) -> tuple[float, float]:
    """按数据最大值计算独立 Y 轴上限与 dtick，保持约 n_intervals 个区间。"""
    ymax_data = max(max(values), 1)
    step = _nice_step(ymax_data / n_intervals)
    ymax = step * n_intervals
    if ymax < ymax_data:
        ymax = step * math.ceil(ymax_data / step)
    return ymax, step


def load_csv() -> dict[str, list]:
    data: dict[str, list] = {
        "date": [],
        "post_count": [],
        "comment_count": [],
        "repost_count": [],
    }
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            data["date"].append(row["date"])
            data["post_count"].append(int(row["post_count"]))
            data["comment_count"].append(int(row["comment_count"]))
            data["repost_count"].append(int(row["repost_count"]))
    return data


def add_panel_dividers(fig: go.Figure) -> None:
    """在相邻子图间距中央绘制浅色水平分隔线。"""
    x_dom = fig.layout.xaxis.domain
    if not x_dom:
        return
    x0, x1 = float(x_dom[0]), float(x_dom[1])
    # make_subplots 自上而下：row1→yaxis，row2→yaxis2，row3→yaxis3
    pairs = [
        (fig.layout.yaxis, fig.layout.yaxis2),
        (fig.layout.yaxis2, fig.layout.yaxis3),
    ]
    for upper, lower in pairs:
        if not upper or not lower or not upper.domain or not lower.domain:
            continue
        y = (float(upper.domain[0]) + float(lower.domain[1])) / 2 - PANEL_DIVIDER_SHIFT
        fig.add_shape(
            type="line",
            xref="paper",
            yref="paper",
            x0=x0,
            x1=x1,
            y0=y,
            y1=y,
            line=dict(color=PANEL_DIVIDER_COLOR, width=PANEL_DIVIDER_WIDTH),
            layer="above",
        )


def build_figure(data: dict[str, list], config: Fig02Config = DEFAULT_CONFIG) -> go.Figure:
    dates = data["date"]
    y_series = {
        1: data["post_count"],
        2: data["comment_count"],
        3: data["repost_count"],
    }

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.11,
        subplot_titles=("发帖量", "评论量", "转发量"),
        row_heights=[0.32, 0.36, 0.32],
    )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=data["post_count"],
            mode="lines+markers",
            name="发帖量",
            line=dict(color=C_POST, width=2.5),
            marker=dict(size=6, color=C_POST),
            hovertemplate=config.hover_post,
            legendgroup="post",
            showlegend=True,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=data["comment_count"],
            mode="lines+markers",
            name="评论量",
            line=dict(color=C_COMMENT, width=2.5),
            marker=dict(size=6, color=C_COMMENT),
            hovertemplate=config.hover_comment,
            legendgroup="comment",
            showlegend=True,
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=data["repost_count"],
            mode="lines+markers",
            name="转发量",
            line=dict(color=C_REPOST, width=2.5),
            marker=dict(size=6, color=C_REPOST),
            hovertemplate=config.hover_repost,
            legendgroup="repost",
            showlegend=True,
        ),
        row=3,
        col=1,
    )

    for marker in config.markers:
        idx = dates.index(marker.date)
        y_val = y_series[marker.row][idx]
        fig.add_vline(
            x=marker.date,
            line_width=2,
            line_dash="dot",
            line_color=C_PEAK,
            opacity=0.75,
            row=marker.row,
            col=1,
        )
        fig.add_annotation(
            x=marker.date,
            y=y_val,
            text=f"<b>{marker.date}</b><br>{marker.note}",
            showarrow=True,
            arrowhead=2,
            arrowwidth=1.5,
            arrowcolor=C_PEAK,
            ax=marker.ax,
            ay=marker.ay,
            font=dict(family=FONT, size=10, color=C_PEAK),
            bgcolor="rgba(245,243,238,0.95)",
            bordercolor=C_PEAK,
            borderwidth=1.5,
            align="left" if marker.ax > 0 else "right",
            row=marker.row,
            col=1,
        )
    for row in (1, 2, 3):
        ymax, dtick = y_axis_ticks(y_series[row])
        fig.update_yaxes(
            **YAXIS_GRID_STYLE,
            title_text=config.y_title if row == 2 else "",
            title_font=dict(family=FONT, size=12),
            tickfont=dict(family=FONT, size=10),
            linecolor="#999999",
            range=[0, ymax],
            dtick=dtick,
            tickmode="linear",
            row=row,
            col=1,
        )

    for row in (1, 2, 3):
        fig.update_xaxes(
            **XAXIS_GRID_STYLE,
            tickfont=dict(family=FONT, size=9 if row < 3 else 10),
            linecolor="#999999",
            type="category",
            showticklabels=True,
            tickangle=-35,
            row=row,
            col=1,
        )
    fig.update_xaxes(
        title_text="日期",
        title_font=dict(family=FONT, size=13),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=dict(
            text=(
                f"{config.title}{SUBTITLE_GAP_HTML}"
                f"<span style='{SUBTITLE_STYLE}'>{config.subtitle}</span>"
            ),
            font=dict(family=FONT, size=20, color="#333333"),
            x=0.5,
            xanchor="center",
            pad=dict(t=4, b=8),
        ),
        font=dict(family=FONT, size=12, color="#333333"),
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        height=FIG_HEIGHT,
        width=FIG_WIDTH,
        margin=dict(l=75, r=55, t=128, b=90),
        hovermode="x unified",
        hoverlabel=dict(font=dict(family=FONT, size=12)),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(family=FONT, size=11),
            bgcolor="rgba(245,243,238,0.9)",
            bordercolor="#CCCCCC",
            borderwidth=1,
        ),
    )

    for ann in fig.layout.annotations:
        if getattr(ann, "text", None) in ("发帖量", "评论量", "转发量"):
            ann.font = dict(family=FONT, size=13, color="#333333")

    add_panel_dividers(fig)
    return fig


def ensure_kaleido() -> None:
    try:
        import kaleido  # noqa: F401
    except ImportError:
        print("正在安装 kaleido …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "kaleido", "-q"])


def export_png(fig: go.Figure) -> None:
    ensure_kaleido()
    kwargs = dict(
        width=FIG_WIDTH,
        height=FIG_HEIGHT,
        scale=EXPORT_SCALE,
    )
    fig.write_image(str(OUT_PNG), **kwargs)
    px_w = int(FIG_WIDTH * EXPORT_SCALE)
    px_h = int(FIG_HEIGHT * EXPORT_SCALE)
    print(f"已生成: {OUT_PNG}（约 {px_w}×{px_h} px，≥300 dpi）")


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"请先运行 heat_trend_real.py 生成 {CSV_PATH.name}")

    data = load_csv()
    fig = build_figure(data)
    fig.write_html(
        str(OUT_HTML),
        include_plotlyjs="cdn",
        config={"displayModeBar": True, "responsive": True},
    )
    print(f"已生成: {OUT_HTML}（三联分面折线图 · 主帖互动指标）")
    export_png(fig)


if __name__ == "__main__":
    main()
