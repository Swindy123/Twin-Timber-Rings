#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_16_platform_narrative_heatmap.py  （在原代码基础上新增HTML导出）
平台叙事差异热力图
新增：运行后同时输出 PNG + 交互式 HTML
鼠标悬停到任意格子 → 显示平台+叙事+数量+占比详情
PNG 部分与原始版本完全一致
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# ---------- Plotly 交互所需 ----------
import plotly.graph_objects as go

# ==================== 路径 ====================
BASE_DIR = Path(__file__).resolve().parent
DATA_PLATFORM = BASE_DIR / "platform_cases_clean.csv"
DATA_WEIBO = BASE_DIR / "all_weibo_texts_clean.csv"
OUTPUT_DIR = BASE_DIR / "figures"
OUTPUT_PNG = OUTPUT_DIR / "fig_16_platform_narrative_heatmap.png"
OUTPUT_HTML = OUTPUT_DIR / "fig_16_platform_narrative_heatmap.html"
OUTPUT_DIR.mkdir(exist_ok=True)

# ==================== 全局样式 ====================
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
FONT = "Microsoft YaHei, SimHei, sans-serif"
C_BG = "#F5F3EE"

# ==================== 平台 & 叙事顺序 ====================
PLATFORM_ORDER = ["B站", "抖音", "知乎", "豆瓣", "微博"]
FRAME_ORDER = [
    "original_singer",
    "copyright_authorization",
    "creator_identity",
    "memory_emotion",
    "legal_discussion",
    "fan_conflict",
    "platform_meta",
    "unclear",
]
FRAME_LABELS = {
    "original_singer": "原唱身份",
    "copyright_authorization": "版权授权",
    "creator_identity": "创作者身份",
    "memory_emotion": "回忆情绪",
    "legal_discussion": "法律解释",
    "fan_conflict": "粉丝冲突",
    "platform_meta": "平台 / 营销号",
    "unclear": "无法判断",
}


def load_rows(path: Path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def count_frames_per_platform(rows):
    frame_counts = defaultdict(Counter)
    totals = Counter()
    for row in rows:
        platform = (row.get("platform") or "").strip()
        if platform not in PLATFORM_ORDER:
            continue
        frame = (row.get("frame") or "unclear").strip() or "unclear"
        if frame not in FRAME_ORDER:
            frame = "unclear"
        frame_counts[platform][frame] += 1
        totals[platform] += 1
    return frame_counts, totals


# ============================================================
#  1) Matplotlib PNG（与原代码完全一致）
# ============================================================
def build_png(all_rows, frame_counts, totals):
    data = np.zeros((len(FRAME_ORDER), len(PLATFORM_ORDER)), dtype=float)
    counts = np.zeros((len(FRAME_ORDER), len(PLATFORM_ORDER)), dtype=int)

    for i, frame in enumerate(FRAME_ORDER):
        for j, platform in enumerate(PLATFORM_ORDER):
            cnt = frame_counts[platform].get(frame, 0)
            counts[i, j] = cnt
            total = totals[platform] if totals[platform] else 1
            data[i, j] = cnt / total * 100.0

    colors = ["#D8B0A0", "#C07858", "#9A8A7A", "#5A7A6A", "#3A5A4A"]
    cmap = LinearSegmentedColormap.from_list("twin_rings_wood", colors, N=256)

    fig, ax = plt.subplots(figsize=(12.5, 8.5))
    fig.patch.set_facecolor("#F5F3EE")
    ax.set_facecolor("#F5F3EE")

    im = ax.imshow(data, cmap=cmap, aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(len(PLATFORM_ORDER)))
    ax.set_xticklabels(PLATFORM_ORDER, fontsize=12)
    ax.set_yticks(range(len(FRAME_ORDER)))
    ax.set_yticklabels([FRAME_LABELS[f] for f in FRAME_ORDER], fontsize=11)
    ax.set_title("图16 平台叙事差异：不同平台在讲什么故事", fontsize=16, fontweight="bold", pad=14)

    ax.set_xticks(np.arange(-0.5, len(PLATFORM_ORDER), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(FRAME_ORDER), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    threshold = max(12.0, data.max() * 0.55)
    for i in range(len(FRAME_ORDER)):
        for j in range(len(PLATFORM_ORDER)):
            pct = data[i, j]
            cnt = counts[i, j]
            # 恢复为两行显示，与原版相同
            text = "0" if cnt == 0 else f"{pct:.1f}%\n({cnt})"
            color = "white" if pct >= threshold else "#2F2B27"
            ax.text(j, i, text, ha="center", va="center", fontsize=9.5,
                    color=color, fontweight="bold")

    cbar = plt.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
    cbar.set_label("平台内占比 / %", fontsize=11)

    total_samples = sum(totals.values())
    # 底部注释与原版完全一致（数字从数据中动态获取，结果相同）
    ax.text(
        0.0, -0.13,
        f"注：每一列按平台内部占比归一化；样本来自 platform_cases_clean.csv 与 all_weibo_texts_clean.csv，共 {total_samples} 条案例。\n"
        f"B站/抖音样本量较小（分别为{totals.get('B站', 0)}/{totals.get('抖音', 0)}），占比仅供参考。",
        transform=ax.transAxes, ha="left", va="top",
        fontsize=10, color="#7A746C"
    )

    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight", facecolor="#F5F3EE")
    plt.close()
    print(f"✅ PNG 已保存: {OUTPUT_PNG}")
    return data, counts, totals


# ============================================================
#  2) Plotly 交互式 HTML（视觉严格对齐 PNG）
# ============================================================
def build_html(data, counts, totals):
    total_samples = sum(totals.values())

    # 构建 hover text
    hover_texts = []
    for i, frame in enumerate(FRAME_ORDER):
        row_texts = []
        for j, platform in enumerate(PLATFORM_ORDER):
            pct = data[i, j]
            cnt = counts[i, j]
            total = totals[platform]
            row_texts.append(
                f"<b>{platform}</b><br>"
                f"叙事：{FRAME_LABELS[frame]}<br>"
                f"数量：{cnt} 条<br>"
                f"平台内占比：{pct:.1f}%<br>"
                f"该平台总计：{total} 条<extra></extra>"
            )
        hover_texts.append(row_texts)

    # 构建显示文字（两行，与 PNG 一致）
    display_texts = []
    for i in range(len(FRAME_ORDER)):
        row_texts = []
        for j in range(len(PLATFORM_ORDER)):
            pct = data[i, j]
            cnt = counts[i, j]
            row_texts.append("0" if cnt == 0 else f"{pct:.1f}%<br>({cnt})")
        display_texts.append(row_texts)

    # 文字颜色（与 PNG 阈值逻辑一致）
    threshold = max(12.0, data.max() * 0.55)
    text_colors = [
        ["white" if data[i][j] >= threshold else "#2F2B27"
         for j in range(len(PLATFORM_ORDER))]
        for i in range(len(FRAME_ORDER))
    ]

    # 颜色映射（与原始 cmap 一致）
    colors = ["#D8B0A0", "#C07858", "#9A8A7A", "#5A7A6A", "#3A5A4A"]
    n_colors = len(colors)
    colorscale = []
    for idx, c in enumerate(colors):
        colorscale.append([idx / (n_colors - 1), c])

    # 先创建空白热力图（只负责颜色和悬停）
    fig = go.Figure(data=go.Heatmap(
        z=data,
        x=PLATFORM_ORDER,
        y=[FRAME_LABELS[f] for f in FRAME_ORDER],
        colorscale=colorscale,
        zmin=0,
        zmax=100,
        text=[["" for _ in PLATFORM_ORDER] for _ in FRAME_ORDER],  # 隐藏默认文字
        hovertemplate='%{customdata}',
        customdata=hover_texts,
        colorbar=dict(
            title=dict(text="平台内占比 / %", font=dict(family=FONT, size=11)),
            tickfont=dict(family=FONT, size=10),
            thickness=20,
            len=0.82,
            x=1.02,
        ),
        hoverlabel=dict(
            font=dict(family=FONT, size=12),
            bgcolor="#FFFFFF",
            bordercolor="#999999",
        ),
    ))

    # 用 annotation 添加文字，支持按格子变色
    annotations = []
    for i, frame in enumerate(FRAME_ORDER):
        for j, platform in enumerate(PLATFORM_ORDER):
            pct = data[i, j]
            cnt = counts[i, j]
            text = "0" if cnt == 0 else f"{pct:.1f}%<br>({cnt})"
            color = text_colors[i][j]
            annotations.append(dict(
                x=platform,
                y=FRAME_LABELS[frame],
                text=text,
                showarrow=False,
                font=dict(family=FONT, size=9.5, color=color),
            ))

    # 底部注释
    annotations.append(
        dict(
            x=0.0, y=-0.14, xref="paper", yref="paper",
            text=f"注：每一列按平台内部占比归一化；样本来自 platform_cases_clean.csv 与 all_weibo_texts_clean.csv，共 {total_samples} 条案例。<br>"
                 f"B站/抖音样本量较小（分别为{totals.get('B站', 0)}/{totals.get('抖音', 0)}），占比仅供参考。",
            showarrow=False,
            font=dict(family=FONT, size=10, color="#7A746C"),
            xanchor="left",
            align="left",
        )
    )

    fig.update_layout(
        title=dict(
            text="<b>图16 平台叙事差异：不同平台在讲什么故事</b>",
            font=dict(family=FONT, size=16, color="#333333"),
            x=0.5, xref="paper", xanchor="center",
        ),
        font=dict(family=FONT, size=12, color="#333333"),
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        height=680,
        width=1000,
        margin=dict(l=110, r=100, t=80, b=100),
        xaxis=dict(
            tickfont=dict(family=FONT, size=12),
            showgrid=False,
            zeroline=False,
            side="top",  # x轴上方，与imshow默认一致
        ),
        yaxis=dict(
            tickfont=dict(family=FONT, size=11),
            showgrid=False,
            zeroline=False,
            autorange="reversed",  # y轴反转，使第一行在顶部
        ),
        hovermode="closest",
        annotations=annotations,
    )

    cfg = {"displayModeBar": True, "scrollZoom": True}
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn", config=cfg)
    print(f"✅ 交互式 HTML 已保存: {OUTPUT_HTML}")


def main():
    # 加载数据
    rows_platform = load_rows(DATA_PLATFORM)
    rows_weibo = load_rows(DATA_WEIBO)

    all_rows = []
    for row in rows_platform:
        row["platform"] = (row.get("platform") or "").strip()
        row["frame"] = (row.get("frame") or "unclear").strip() or "unclear"
        all_rows.append(row)
    for row in rows_weibo:
        row["platform"] = "微博"
        row["frame"] = (row.get("frame") or "unclear").strip() or "unclear"
        all_rows.append(row)

    frame_counts, totals = count_frames_per_platform(all_rows)
    data, counts, totals = build_png(all_rows, frame_counts, totals)
    build_html(data, counts, totals)


if __name__ == "__main__":
    main()