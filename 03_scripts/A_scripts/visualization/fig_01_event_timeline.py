#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图1 三轨叙事时间线（色块节点版 · 静态）
上轨：原唱叙事 | 中间：媒体事件 | 下轨：版权叙事
左侧 2015 年起源列 + 右侧 2025 年争议时间轴。
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go

from paths import FIG_DIR, ROOT_DIR

NARRATIVE_PATH = ROOT_DIR / "narrative_events.csv"
POSTS_PATH = ROOT_DIR / "weibo_posts_clean.csv"
OUT_HTML = FIG_DIR / "fig_01_event_timeline.html"
OUT_PNG = FIG_DIR / "fig_01_event_timeline.png"

C_ZHANG = "#C07858"
C_ZHANG_LIGHT = "#E8C8B8"
C_ZHANG_DARK = "#9A5A40"
C_WANG = "#5A7A6A"
C_WANG_LIGHT = "#B8D4C4"
C_WANG_DARK = "#3A5A4A"
C_MEDIA = "#8C8C8C"
C_MEDIA_LIGHT = "#ECECEC"
C_SPLIT = "#A05050"
C_BG = "#F5F3EE"
C_TEXT = "#333333"
FONT = "Microsoft YaHei, SimHei, sans-serif"

TITLE = "图1 关键事件时间线：从共同记忆到争议爆发"

Y_TRACK = {"zhang": 2.0, "media": 0.0, "wang": -2.0}
LANE_HALF = 0.52
Y_CLIP = 2.85
TRACK_LABELS = {
    "zhang": "原唱叙事",
    "media": "媒体事件",
    "wang": "版权叙事",
}

ORIGIN_SEGMENT_W = 0.105
_WIDTHS_2025 = [
    ("2025-07-22", 0.088),
    ("2025-07-23", 0.080),
    ("2025-07-25", 0.160),
    ("2025-07-26", 0.080),
    ("2025-07-28", 0.080),
    ("2025-07-29", 0.160),
    ("2025-07-30", 0.080),
    ("2025-07-31", 0.120),
    ("2025-08-04", 0.152),
]


def _build_segments() -> list[tuple[str, float, float]]:
    segs: list[tuple[str, float, float]] = [("2015", 0.0, ORIGIN_SEGMENT_W)]
    cursor = ORIGIN_SEGMENT_W
    scale = 1.0 - ORIGIN_SEGMENT_W
    for key, w in _WIDTHS_2025:
        segs.append((key, cursor, cursor + w * scale))
        cursor += w * scale
    return segs


NARRATIVE_SEGMENTS = _build_segments()
BURST_SEGMENT = next(s for s in NARRATIVE_SEGMENTS if s[0] == "2025-07-25")
SEGMENT_BOUNDS = {k: (lo, hi) for k, lo, hi in NARRATIVE_SEGMENTS}

BLOCK_HALF_H = 0.40
BLOCK_MIN_HALF_W = 0.038
BLOCK_MAX_HALF_W = 0.085
BLOCK_X_PER_CHAR = 0.0042
BLOCK_MIN_GAP = 0.010
SEG_INNER_PAD = 0.006
TEXT_SIZE = 12
MARGIN_LEFT = 100
MARGIN_RIGHT = 55

CN_2025_DATETIME = re.compile(
    r"2025年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})"
)

TRACK_BLOCK = {
    "zhang": (C_ZHANG_LIGHT, C_ZHANG_DARK, C_ZHANG),
    "wang": (C_WANG_LIGHT, C_WANG_DARK, C_WANG),
    "media": (C_MEDIA_LIGHT, "#666666", C_MEDIA),
}

ORIGIN_WRAP = {
    "汪苏泷创作《年轮》词曲 版权归属海蝶": "汪苏泷创作《年轮》词曲<br>版权归属海蝶",
    "张碧晨演唱花千骨OST热播": "张碧晨演唱<br>花千骨OST热播",
}

# 单列内微调（不改变日期列宽；默认高度与 BLOCK_HALF_H 一致）
EVENT_BLOCK_TUNING: dict[str, dict] = {
    "5192673235307954": {
        "text_wrapped": "律师：「原唱」<br>并无法律定义",
        "fill_column": True,
    },
    "5192118454714744": {
        "text_wrapped": "张碧晨方声明<br>「无可争议的<br>唯一原唱」",
        "font_size": 10,
    },
    "5192371266390237": {
        "text_wrapped": "张碧晨方：<br>享有永久演唱权<br>不再演唱",
        "font_size": 10,
    },
}

# 同列同轨多事件时间距（07-25 原唱轨两框拉开）
GROUP_GAP_OVERRIDES: dict[tuple[str, str], float] = {
    ("2025-07-25", "zhang"): 0.024,
}

TEXT_WIDTH_PAD = 1.14


def parse_publish_time(raw: str) -> pd.Timestamp:
    m = CN_2025_DATETIME.search(str(raw))
    if not m:
        raise ValueError(f"无法解析时间: {raw}")
    mo, d, h, mi = map(int, m.groups())
    return pd.Timestamp(2025, mo, d, h, mi)


def wrap_summary(text: str) -> str:
    if text in ORIGIN_WRAP:
        return ORIGIN_WRAP[text]
    for sep in ("：", "·"):
        if sep in text:
            head, tail = text.split(sep, 1)
            return f"{head}{sep}<br>{tail}"
    if len(text) <= 11:
        return text
    mid = len(text) // 2
    for i in range(mid, min(mid + 6, len(text))):
        if text[i] in "，。、 ":
            return f"{text[: i + 1].strip()}<br>{text[i + 1 :].strip()}"
    for i in range(mid, max(mid - 6, 0), -1):
        if text[i] in "，。、 ":
            return f"{text[: i + 1].strip()}<br>{text[i + 1 :].strip()}"
    return f"{text[:mid]}<br>{text[mid:]}"


def estimate_half_width(wrapped: str, font_size: int = TEXT_SIZE) -> float:
    lines = wrapped.split("<br>")
    max_len = max(len(line) for line in lines)
    scale = font_size / TEXT_SIZE
    w = max_len * BLOCK_X_PER_CHAR * TEXT_WIDTH_PAD * scale
    return max(BLOCK_MIN_HALF_W, min(BLOCK_MAX_HALF_W, w))


def group_gap(bucket_key: str, kind: str) -> float:
    return GROUP_GAP_OVERRIDES.get((bucket_key, kind), BLOCK_MIN_GAP)


def apply_text_tuning(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["font_size"] = TEXT_SIZE
    for idx, row in out.iterrows():
        tune = EVENT_BLOCK_TUNING.get(row["post_id"])
        if not tune:
            continue
        if "text_wrapped" in tune:
            out.at[idx, "text_wrapped"] = tune["text_wrapped"]
        if "font_size" in tune:
            out.at[idx, "font_size"] = tune["font_size"]
    return out


def calendar_bucket_key(dt: pd.Timestamp) -> str:
    if dt.year == 2015:
        return "2015"
    day = dt.strftime("%Y-%m-%d")
    remap = {
        "2025-07-24": "2025-07-23",
        "2025-07-27": "2025-07-26",
    }
    day = remap.get(day, day)
    valid = {k for k, _, _ in NARRATIVE_SEGMENTS}
    if day in valid:
        return day
    if day < "2025-07-22":
        return "2025-07-22"
    if day > "2025-08-04":
        return "2025-08-04"
    for key, _, _ in reversed(NARRATIVE_SEGMENTS):
        if key == "2015":
            continue
        if day >= key:
            return key
    return "2025-07-22"


def segment_tick_label(key: str) -> str:
    if key == "2015":
        return "2015<br>&nbsp;"
    month_day = key[5:]
    return f"2025<br>{month_day}"


def load_events() -> pd.DataFrame:
    narrative = pd.read_csv(NARRATIVE_PATH, encoding="utf-8-sig", dtype={"post_id": str})
    posts = pd.read_csv(POSTS_PATH, encoding="utf-8-sig", dtype={"id": str})
    posts = posts.loc[posts["is_valid"] == 1].copy()

    origin = narrative[narrative["post_id"].str.startswith("origin:", na=False)]
    weibo = narrative[~narrative["post_id"].str.startswith("origin:", na=False)]

    merged = weibo.merge(
        posts,
        left_on="post_id",
        right_on="id",
        how="left",
        validate="many_to_one",
    )
    missing = merged[merged["author_name"].isna()]["post_id"].tolist()
    if missing:
        raise ValueError(f"weibo_posts_clean.csv 中未找到 post_id: {missing}")

    rows = []
    for _, row in origin.iterrows():
        kind = str(row["track"]).strip()
        summary = row["event_summary"]
        wrapped = wrap_summary(summary)
        rows.append(
            {
                "post_id": row["post_id"],
                "event_summary": summary,
                "text_wrapped": wrapped,
                "kind": kind,
                "y": Y_TRACK[kind],
                "dt": pd.Timestamp(2015, 6, 15),
                "block_half_w": estimate_half_width(wrapped),
                "block_half_h": BLOCK_HALF_H,
            }
        )

    for _, row in merged.sort_values("sort_order").iterrows():
        dt = parse_publish_time(row["publish_time"])
        kind = str(row["track"]).strip()
        if kind not in Y_TRACK:
            raise ValueError(f"未知轨道: {kind} (post_id={row['post_id']})")
        summary = row["event_summary"]
        wrapped = wrap_summary(summary)
        rows.append(
            {
                "post_id": row["post_id"],
                "event_summary": summary,
                "text_wrapped": wrapped,
                "kind": kind,
                "y": Y_TRACK[kind],
                "dt": dt,
                "block_half_w": estimate_half_width(wrapped),
                "block_half_h": BLOCK_HALF_H,
            }
        )

    df = pd.DataFrame(rows).sort_values("dt").reset_index(drop=True)
    df["bucket_key"] = df["dt"].apply(calendar_bucket_key)
    df = apply_text_tuning(df)
    df = assign_blocks_in_segments(df)
    return apply_spatial_tuning(df)


def apply_spatial_tuning(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for idx, row in out.iterrows():
        tune = EVENT_BLOCK_TUNING.get(row["post_id"])
        if not tune or not tune.get("fill_column"):
            continue
        lo, hi = SEGMENT_BOUNDS[row["bucket_key"]]
        inner_lo = lo + SEG_INNER_PAD
        inner_hi = hi - SEG_INNER_PAD
        usable = inner_hi - inner_lo
        text_hw = estimate_half_width(
            str(out.at[idx, "text_wrapped"]),
            int(out.at[idx, "font_size"]),
        )
        out.at[idx, "block_half_w"] = min(text_hw, usable / 2 - 0.002)
        out.at[idx, "x_plot"] = (inner_lo + inner_hi) / 2
        out.at[idx, "block_half_h"] = BLOCK_HALF_H
    return out


def assign_blocks_in_segments(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    x_plot: dict[int, float] = {}
    half_w: dict[int, float] = {}

    for bucket_key, bucket_group in out.groupby("bucket_key", sort=False):
        lo, hi = SEGMENT_BOUNDS[bucket_key]
        inner_lo = lo + SEG_INNER_PAD
        inner_hi = hi - SEG_INNER_PAD
        usable = inner_hi - inner_lo

        for kind, kind_group in bucket_group.groupby("kind", sort=False):
            ordered = kind_group.sort_values("dt")
            indices = list(ordered.index)
            n = len(indices)
            if n == 0:
                continue

            gap_step = group_gap(bucket_key, kind)
            widths = [
                estimate_half_width(
                    ordered.loc[idx, "text_wrapped"],
                    int(ordered.loc[idx, "font_size"]),
                )
                for idx in indices
            ]
            gap_total = gap_step * max(0, n - 1)
            total_need = sum(2 * w for w in widths) + gap_total

            if n >= 2:
                slot_hw = (usable - gap_total) / (2 * n)
                widths = [
                    max(
                        estimate_half_width(
                            ordered.loc[idx, "text_wrapped"],
                            int(ordered.loc[idx, "font_size"]),
                        ),
                        slot_hw,
                    )
                    for idx in indices
                ]
                total_need = sum(2 * w for w in widths) + gap_total
                if total_need > usable:
                    scale = usable / total_need
                    widths = [w * scale for w in widths]
            elif total_need > usable:
                scale = usable / total_need
                widths = [max(BLOCK_MIN_HALF_W * 0.8, w * scale) for w in widths]

            for idx, w in zip(indices, widths):
                half_w[idx] = min(w, usable / 2 - 0.001)

            if n == 1:
                x_plot[indices[0]] = (inner_lo + inner_hi) / 2
            else:
                total_need = sum(2 * half_w[idx] for idx in indices) + gap_total
                cursor = inner_lo + max(0.0, (usable - total_need) / 2)
                for i, idx in enumerate(indices):
                    hw = half_w[idx]
                    x_plot[idx] = cursor + hw
                    cursor += 2 * hw + (gap_step if i < n - 1 else 0.0)

            for idx in indices:
                hw = half_w[idx]
                if x_plot[idx] + hw > inner_hi:
                    x_plot[idx] -= x_plot[idx] + hw - inner_hi
                if x_plot[idx] - hw < inner_lo:
                    x_plot[idx] = inner_lo + hw

    out["x_plot"] = [x_plot[i] for i in out.index]
    out["block_half_w"] = [half_w[i] for i in out.index]
    return out


def _hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def add_track_connectors(fig: go.Figure, sub: pd.DataFrame, y: float, line_color: str) -> None:
    ordered = sub.sort_values("x_plot")
    if len(ordered) < 2:
        return
    for i in range(len(ordered) - 1):
        left = ordered.iloc[i]
        right = ordered.iloc[i + 1]
        x0 = left["x_plot"] + left["block_half_w"]
        x1 = right["x_plot"] - right["block_half_w"]
        if x1 <= x0:
            continue
        fig.add_shape(
            type="line",
            x0=x0,
            x1=x1,
            y0=y,
            y1=y,
            line=dict(color=line_color, width=2.2),
            layer="below",
        )


def add_event_blocks(fig: go.Figure, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        kind = row["kind"]
        fill, border, _ = TRACK_BLOCK[kind]
        x, y = row["x_plot"], row["y"]
        hw, hh = row["block_half_w"], row["block_half_h"]
        fig.add_shape(
            type="rect",
            x0=x - hw,
            x1=x + hw,
            y0=y - hh,
            y1=y + hh,
            fillcolor=fill,
            line=dict(color=border, width=2),
            layer="above",
        )
        fig.add_annotation(
            x=x,
            y=y,
            text=row["text_wrapped"],
            showarrow=False,
            xref="x",
            yref="y",
            xanchor="center",
            yanchor="middle",
            font=dict(
                family=FONT,
                size=int(row.get("font_size", TEXT_SIZE)),
                color=C_TEXT,
            ),
            align="center",
        )


def add_legend(fig: go.Figure) -> None:
    items = [
        ("zhang", 0.28),
        ("media", 0.50),
        ("wang", 0.72),
    ]
    for kind, x_paper in items:
        fill, border, _ = TRACK_BLOCK[kind]
        fig.add_shape(
            type="rect",
            xref="paper",
            yref="paper",
            x0=x_paper - 0.012,
            x1=x_paper + 0.012,
            y0=1.03,
            y1=1.055,
            fillcolor=fill,
            line=dict(color=border, width=1.5),
            layer="above",
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=x_paper + 0.018,
            y=1.042,
            text=TRACK_LABELS[kind],
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(family=FONT, size=12, color=C_TEXT),
        )


def build_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    x_min, x_max = 0.0, 1.0

    _, burst_lo, burst_hi = BURST_SEGMENT
    fig.add_shape(
        type="rect",
        x0=burst_lo,
        x1=burst_hi,
        y0=-Y_CLIP,
        y1=Y_CLIP,
        fillcolor=_hex_rgba(C_SPLIT, 0.06),
        line_width=0,
        layer="below",
    )

    lane_bands = [
        (Y_TRACK["zhang"] - LANE_HALF, Y_TRACK["zhang"] + LANE_HALF, C_ZHANG_LIGHT, 0.22),
        (Y_TRACK["media"] - LANE_HALF, Y_TRACK["media"] + LANE_HALF, C_MEDIA_LIGHT, 0.45),
        (Y_TRACK["wang"] - LANE_HALF, Y_TRACK["wang"] + LANE_HALF, C_WANG_LIGHT, 0.22),
    ]
    for y0, y1, color, alpha in lane_bands:
        fig.add_shape(
            type="rect",
            x0=x_min,
            x1=x_max,
            y0=y0,
            y1=y1,
            fillcolor=_hex_rgba(color, alpha),
            line_width=0,
            layer="below",
        )

    for key, lo, _ in NARRATIVE_SEGMENTS[1:]:
        width = 2 if key == "2025-07-22" else 1
        color = "rgba(100,100,100,0.35)" if key == "2025-07-22" else "rgba(140,140,140,0.22)"
        fig.add_shape(
            type="line",
            x0=lo,
            x1=lo,
            y0=-Y_CLIP,
            y1=Y_CLIP,
            line=dict(color=color, width=width),
            layer="below",
        )

    for kind in ("zhang", "media", "wang"):
        sub = df[df["kind"] == kind]
        if sub.empty:
            continue
        _, _, connector = TRACK_BLOCK[kind]
        add_track_connectors(fig, sub, Y_TRACK[kind], connector)

    add_event_blocks(fig, df)
    add_legend(fig)

    for kind, y in Y_TRACK.items():
        color = {"zhang": C_ZHANG, "wang": C_WANG, "media": C_MEDIA}[kind]
        fig.add_annotation(
            xref="paper",
            yref="y",
            x=-0.015,
            y=y,
            text=f"<b>{TRACK_LABELS[kind]}</b>",
            showarrow=False,
            xanchor="right",
            font=dict(family=FONT, size=13, color=color),
        )

    fig.update_layout(
        title=dict(
            text=TITLE,
            font=dict(family=FONT, size=22, color=C_TEXT),
            x=0.5,
            xref="paper",
            xanchor="center",
        ),
        font=dict(family=FONT, size=12, color=C_TEXT),
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        height=760,
        width=2100,
        margin=dict(l=MARGIN_LEFT, r=MARGIN_RIGHT, t=110, b=88),
        showlegend=False,
        xaxis=dict(
            title=dict(text="时间", font=dict(family=FONT, size=14)),
            type="linear",
            tickmode="array",
            tickvals=[(lo + hi) / 2 for _, lo, hi in NARRATIVE_SEGMENTS],
            ticktext=[segment_tick_label(k) for k, _, _ in NARRATIVE_SEGMENTS],
            tickfont=dict(family=FONT, size=12),
            range=[x_min, x_max],
            constrain="domain",
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="#999999",
            mirror=False,
        ),
        yaxis=dict(
            visible=False,
            range=[-Y_CLIP, Y_CLIP],
            fixedrange=True,
            showgrid=False,
            zeroline=False,
            showline=False,
            mirror=False,
        ),
    )
    return fig


def export(fig: go.Figure) -> None:
    static_cfg = {
        "staticPlot": True,
        "displayModeBar": False,
        "scrollZoom": False,
        "doubleClick": False,
    }
    fig.write_html(str(OUT_HTML), include_plotlyjs="cdn", config=static_cfg)
    fig.write_image(str(OUT_PNG), width=2100, height=760, scale=2)
    print(f"已生成: {OUT_HTML}")
    print(f"已生成: {OUT_PNG}")


def main() -> None:
    df = load_events()
    print(f"叙事时间线：{len(df)} 个节点（含 2015 起源 2 个）")
    for kind in ("zhang", "media", "wang"):
        n = (df["kind"] == kind).sum()
        print(f"  {TRACK_LABELS[kind]}: {n}")
    export(build_figure(df))


if __name__ == "__main__":
    main()
