#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_15_platform_comparison.py  （在原代码基础上新增HTML导出）
平台对比
新增：运行后同时输出 PNG + 交互式 HTML
鼠标悬停到柱子上 → 显示平台+立场+数量+占比详情
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ---------- Plotly 交互所需 ----------
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / 'platform_cases_clean.csv'
WEIBO_DATA_PATH = BASE_DIR / 'all_weibo_texts_clean.csv'
OUTPUT_DIR = BASE_DIR / 'figures'
OUTPUT_PNG = OUTPUT_DIR / 'fig_15_platform_comparison.png'
OUTPUT_HTML = OUTPUT_DIR / 'fig_15_platform_comparison.html'

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
FONT = "Microsoft YaHei, SimHei, sans-serif"
C_BG = "#F5F3EE"

PLATFORM_ORDER = ['B站', '抖音', '知乎', '豆瓣', '微博']
STANCE_ORDER = ['support_zhang', 'support_wang', 'neutral', 'unclear', 'anti_fanwar']
STANCE_LABELS = {
    'support_zhang': '支持张碧晨',
    'support_wang': '支持汪苏泷',
    'neutral': '中立讨论',
    'unclear': '无法判断',
    'anti_fanwar': '反感饭圈争议',
}
STANCE_COLORS = {
    'support_zhang': '#C07858',
    'support_wang': '#5A7A6A',
    'neutral': '#8C8C8C',
    'unclear': '#8C8C8C',
    'anti_fanwar': '#A05050',
}


def load_rows(path: Path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def merge_all_data():
    rows = load_rows(DATA_PATH)
    try:
        weibo_rows = load_rows(WEIBO_DATA_PATH)
    except FileNotFoundError:
        print(f'警告：未找到微博数据文件 {WEIBO_DATA_PATH}，仅使用原有数据。')
        weibo_rows = []
    for row in weibo_rows:
        row['platform'] = '微博'
        if 'stance' not in row or not row['stance'].strip():
            row['stance'] = 'unclear'
        rows.append(row)
    return rows


def summarize_platform_stance(rows):
    counts = defaultdict(Counter)
    totals = Counter()
    for row in rows:
        platform = (row.get('platform') or '').strip()
        if platform not in PLATFORM_ORDER:
            continue
        stance = (row.get('stance') or 'unclear').strip() or 'unclear'
        counts[platform][stance] += 1
        totals[platform] += 1
    return counts, totals


# ============================================================
#  1) Matplotlib PNG（原代码完全保留，仅条件改为用原始计数避免 0.0%）
# ============================================================
def build_png(counts, totals):
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor('#F5F3EE')
    ax.set_facecolor('#F5F3EE')

    x = np.arange(len(PLATFORM_ORDER))
    width = 0.68
    bottom = np.zeros(len(PLATFORM_ORDER), dtype=float)

    for stance in STANCE_ORDER:
        values = np.array([counts[platform].get(stance, 0) for platform in PLATFORM_ORDER], dtype=float)
        totals_array = np.array([totals[platform] if totals[platform] else 1 for platform in PLATFORM_ORDER], dtype=float)
        shares = values / totals_array * 100.0
        bars = ax.bar(
            x, shares, width, bottom=bottom,
            label=STANCE_LABELS[stance],
            color=STANCE_COLORS[stance],
            edgecolor='white', linewidth=0.8, alpha=0.95,
        )
        # 改用原始计数 > 0 来决定是否显示百分比，彻底杜绝“0.0%”
        for i, (rect, share) in enumerate(zip(bars, shares)):
            if values[i] > 0:   # 只有原始数据不为 0 时才显示
                text_color = 'white' if share >= 18 else '#333333'
                ax.text(
                    rect.get_x() + rect.get_width() / 2,
                    rect.get_y() + rect.get_height() / 2,
                    f'{share:.1f}%',
                    ha='center', va='center', fontsize=9.5,
                    color=text_color, fontweight='bold',
                )
        bottom += shares

    for index, platform in enumerate(PLATFORM_ORDER):
        ax.text(index, 103.5, f'n={totals[platform]}',
                ha='center', va='bottom', fontsize=10, color='#5D584F', fontweight='bold')

    ax.set_ylim(0, 110)
    ax.set_ylabel('平台内占比 / %', fontsize=12)
    ax.set_title('图15 平台对比：不同平台的支持结构', fontsize=16, fontweight='bold', pad=14)
    ax.set_xticks(x)
    ax.set_xticklabels(PLATFORM_ORDER, fontsize=12)
    ax.legend(ncol=1, fontsize=10.5, frameon=False, loc='upper left', bbox_to_anchor=(1.02, 1.0))
    ax.grid(axis='y', color='#D8D1C6', linewidth=0.8, alpha=0.7)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#C9C1B5')
    ax.spines['bottom'].set_color('#C9C1B5')

    total_samples = sum(totals.values())
    ax.text(
        0.0, -0.14,
        f'注：按 platform_cases_clean.csv 与 all_weibo_texts_clean.csv 中各平台内部 stance 分布归一化；样本共 {total_samples} 条平台案例。',
        transform=ax.transAxes, ha='left', va='top', fontsize=10, color='#7A746C',
    )

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches='tight', facecolor='#F5F3EE')
    print(f'✅ PNG 已保存: {OUTPUT_PNG}')
    plt.close()


# ============================================================
#  2) Plotly 交互式 HTML（完全未动）
# ============================================================
def build_html(counts, totals):
    fig = go.Figure()
    x = np.arange(len(PLATFORM_ORDER))
    bottom = np.zeros(len(PLATFORM_ORDER), dtype=float)

    for stance in STANCE_ORDER:
        values = np.array([counts[platform].get(stance, 0) for platform in PLATFORM_ORDER], dtype=float)
        totals_array = np.array([totals[platform] if totals[platform] else 1 for platform in PLATFORM_ORDER], dtype=float)
        shares = values / totals_array * 100.0

        hover_texts = []
        for i, platform in enumerate(PLATFORM_ORDER):
            cnt = int(values[i])
            total = totals[platform]
            share = shares[i]
            hover_texts.append(
                f"<b>{platform}</b><br>"
                f"立场：{STANCE_LABELS[stance]}<br>"
                f"数量：{cnt} 条<br>"
                f"平台内占比：{share:.1f}%<br>"
                f"该平台总计：{total} 条<extra></extra>"
            )

        fig.add_trace(go.Bar(
            x=PLATFORM_ORDER,
            y=shares,
            name=STANCE_LABELS[stance],
            marker=dict(color=STANCE_COLORS[stance], line=dict(color='white', width=0.8)),
            opacity=0.95,
            base=bottom,
            text=[f'{s:.1f}%' if s > 0 else '' for s in shares],
            textposition='inside',
            textfont=dict(family=FONT, size=9.5, color=['white' if s >= 18 else '#333333' for s in shares]),
            hovertemplate='%{customdata}',
            customdata=hover_texts,
            hoverlabel=dict(
                font=dict(family=FONT, size=12),
                bgcolor="#FFFFFF",
                bordercolor=STANCE_COLORS[stance],
            ),
        ))
        bottom += shares

    sample_annotations = []
    for i, platform in enumerate(PLATFORM_ORDER):
        sample_annotations.append(dict(
            x=platform, y=103.5,
            text=f"<b>n={totals[platform]}</b>",
            showarrow=False,
            font=dict(family=FONT, size=10, color="#5D584F"),
        ))

    total_samples = sum(totals.values())

    fig.update_layout(
        title=dict(
            text="<b>图15 平台对比：不同平台的支持结构</b>",
            font=dict(family=FONT, size=16, color="#333333"),
            x=0.5, xref="paper", xanchor="center",
        ),
        font=dict(family=FONT, size=12, color="#333333"),
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        height=560,
        width=960,
        margin=dict(l=70, r=160, t=80, b=80),
        barmode='stack',
        legend=dict(
            orientation="v", yanchor="top", y=1.0,
            xanchor="left", x=1.02,
            font=dict(family=FONT, size=10.5),
            bgcolor="rgba(245,243,238,0.9)",
        ),
        xaxis=dict(
            tickfont=dict(family=FONT, size=12),
            showgrid=False, zeroline=False,
            showline=True, linecolor="#C9C1B5",
        ),
        yaxis=dict(
            title=dict(text="平台内占比 / %", font=dict(family=FONT, size=12)),
            range=[0, 110],
            tickfont=dict(family=FONT, size=11),
            gridcolor="#D8D1C6", gridwidth=0.8,
            showgrid=True, zeroline=False,
            showline=True, linecolor="#C9C1B5",
        ),
        hovermode="closest",
        annotations=sample_annotations + [
            dict(
                x=0.0, y=-0.14, xref="paper", yref="paper",
                text=f"注：按 platform_cases_clean.csv 与 all_weibo_texts_clean.csv 中各平台内部 stance 分布归一化；样本共 {total_samples} 条平台案例。",
                showarrow=False,
                font=dict(family=FONT, size=10, color="#7A746C"),
                xanchor="left",
            )
        ],
    )

    cfg = {"displayModeBar": True, "scrollZoom": True}
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn", config=cfg)
    print(f"✅ 交互式 HTML 已保存: {OUTPUT_HTML}")


def main():
    rows = merge_all_data()
    counts, totals = summarize_platform_stance(rows)
    build_png(counts, totals)
    build_html(counts, totals)


if __name__ == '__main__':
    main()