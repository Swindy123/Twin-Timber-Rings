#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_14_twin_rings.py  （PNG + 交互式 HTML）
双生年轮主视觉 - 基于真实数据的同心圆环年轮
运行后同时输出 PNG 与交互式 HTML，视觉严格对齐原始 PNG（无多余背景方块）
"""

import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.patches import Circle

import plotly.graph_objects as go

# ==================== 路径配置 ====================
BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "all_weibo_texts_clean.csv"
OUTPUT_DIR = BASE_DIR / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PNG = OUTPUT_DIR / "fig_14_twin_rings.png"
OUTPUT_HTML = OUTPUT_DIR / "fig_14_twin_rings.html"

# ==================== 字体设置 ====================
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["patch.antialiased"] = True
plt.rcParams["text.antialiased"] = True

# ==================== 配色规范 ====================
BG_COLOR = "#F5F3EE"
ZHANG_MAIN = "#C07858"
ZHANG_DEEP = "#9A5A40"
ZHANG_LIGHT = "#D8B0A0"
WANG_MAIN = "#5A7A6A"
WANG_DEEP = "#3A5A4A"
WANG_LIGHT = "#90B0A0"
OVERLAP = "#9A8A7A"
CRACK = "#A05050"
FONT = "Microsoft YaHei, SimHei, sans-serif"

STAGE_ORDER = ["pre_event", "outbreak", "response", "debate", "cooldown"]
STAGE_LABELS = {
    "pre_event": "爆发前",
    "outbreak": "爆发期",
    "response": "回应期",
    "debate": "争论期",
    "cooldown": "冷却期",
}
ZHANG_CENTER = (-1.9, 0.0)
WANG_CENTER = (1.9, 0.0)
RADII = [0.7, 1.1, 1.5, 1.9, 2.3]
LEFT_ANGLES_DEG = [135, 165, 195, 225, 255]
RIGHT_ANGLES_DEG = [-75, -45, -15, 15, 45]


def load_rows(path: Path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_stage_counts(rows, stance):
    counts = Counter()
    for row in rows:
        if row.get("is_valid") != "1":
            continue
        if row.get("stance") != stance:
            continue
        stage = row.get("event_stage") or "cooldown"
        if stage not in STAGE_ORDER:
            stage = "cooldown"
        counts[stage] += 1
    return counts


# ============================================================
#  1) Matplotlib PNG
# ============================================================
def draw_twin_ring_beautiful(ax, center, main_color, deep_color, light_color, counts, total, side="left"):
    if total == 0:
        return
    min_lw, max_lw = 2.0, 12.0
    min_alpha_fill, max_alpha_fill = 0.25, 0.40
    stage_props = []
    for stage in STAGE_ORDER:
        cnt = counts.get(stage, 0)
        prop = cnt / total if total > 0 else 0
        stage_props.append(prop)
    colors = []
    for prop in stage_props:
        if prop > 0.6:
            colors.append(deep_color)
        elif prop < 0.2:
            colors.append(light_color)
        else:
            colors.append(main_color)
    for idx, (stage, radius, prop, color) in enumerate(zip(STAGE_ORDER, RADII, stage_props, colors)):
        cnt = counts.get(stage, 0)
        linewidth = min_lw + prop * (max_lw - min_lw)
        fill_alpha = min_alpha_fill + prop * (max_alpha_fill - min_alpha_fill)
        ax.add_patch(Circle(center, radius, facecolor=color, edgecolor="none", alpha=fill_alpha, zorder=1))
        ax.add_patch(Circle(center, radius, fill=False, edgecolor=color, linewidth=linewidth, alpha=0.85, zorder=3))
        if side == "left":
            angle_deg = LEFT_ANGLES_DEG[idx]
        else:
            angle_deg = RIGHT_ANGLES_DEG[idx]
        angle_rad = np.deg2rad(angle_deg)
        label_radius = radius + 0.25
        label_x = center[0] + label_radius * np.cos(angle_rad)
        label_y = center[1] + label_radius * np.sin(angle_rad)
        rotation = angle_deg + 90 if side == "left" else angle_deg - 90
        ax.text(label_x, label_y, f"{STAGE_LABELS[stage]}\n{cnt} 条",
                ha="center", va="center", fontsize=9, color=deep_color, fontweight="bold",
                rotation=rotation, rotation_mode="anchor",
                path_effects=[pe.withStroke(linewidth=2, foreground=BG_COLOR, alpha=0.7)], zorder=10)
    ax.add_patch(Circle(center, 0.42, facecolor=BG_COLOR, edgecolor=deep_color, linewidth=1.5, alpha=0.98, zorder=8))
    letter = "张" if center[0] < 0 else "汪"
    ax.text(center[0], center[1], letter, ha="center", va="center", fontsize=24, color="white",
            fontweight="bold", path_effects=[pe.withStroke(linewidth=4, foreground=deep_color)], zorder=12)
    ax.text(center[0], center[1] - 2.4, f"n={total}", ha="center", va="center", fontsize=11,
            color=deep_color, fontweight="bold", path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)], zorder=12)


def build_png():
    rows = load_rows(DATA_PATH)
    left_counts = build_stage_counts(rows, "support_zhang")
    right_counts = build_stage_counts(rows, "support_wang")
    total_left = sum(left_counts.values())
    total_right = sum(right_counts.values())

    fig, ax = plt.subplots(figsize=(14, 12))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(-4.5, 4.5)
    ax.set_ylim(-4.2, 4.2)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.add_patch(Circle((0, 0), 1.0, facecolor=OVERLAP, edgecolor="none", alpha=0.25, zorder=0))
    ax.text(0, 0.55, "同一首歌", ha="center", va="center", fontsize=16, color="#3D3A35", fontweight="bold", zorder=20,
            path_effects=[pe.withStroke(linewidth=2.5, foreground=BG_COLOR)])
    ax.text(0, 0.15, "两套叙事", ha="center", va="center", fontsize=16, color="#3D3A35", fontweight="bold", zorder=20,
            path_effects=[pe.withStroke(linewidth=2.5, foreground=BG_COLOR)])
    ax.text(0, -0.35, "共同记忆 / 双生分裂", ha="center", va="center", fontsize=11, color="#4A4035", fontweight="bold", zorder=20,
            path_effects=[pe.withStroke(linewidth=1.8, foreground=BG_COLOR)])

    draw_twin_ring_beautiful(ax, ZHANG_CENTER, ZHANG_MAIN, ZHANG_DEEP, ZHANG_LIGHT, left_counts, total_left, side="left")
    draw_twin_ring_beautiful(ax, WANG_CENTER, WANG_MAIN, WANG_DEEP, WANG_LIGHT, right_counts, total_right, side="right")

    crack_coords = [([-0.5, 0.5], [0.8, -0.4]), ([-0.3, 0.3], [-0.9, 0.6]), ([0.1, 0.4], [0.3, 0.7]),
                    ([-0.5, -0.2], [-0.4, -0.9])]
    for (x_vals, y_vals) in crack_coords:
        ax.plot(x_vals, y_vals, color=CRACK, linewidth=3.5, alpha=0.85, solid_capstyle="round", zorder=15)
    ax.plot([0.15, 0.5], [0.2, 0.6], color=CRACK, linewidth=2, alpha=0.6, solid_capstyle="round", zorder=15)
    ax.plot([-0.4, -0.1], [-0.6, -1.0], color=CRACK, linewidth=2, alpha=0.6, solid_capstyle="round", zorder=15)

    ax.text(0, 3.4, "图14 双生年轮：同一首歌在微博上生长出的两套真实叙事",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#3D3A35")
    ax.text(0, 3.05, "数据来源：all_weibo_texts_clean.csv | 仅统计 is_valid=1 的微博 | 年轮厚度 ∝ 阶段讨论量",
            ha="center", va="center", fontsize=10, color="#7A746C")

    legend_y = -3.4
    ax.add_patch(Circle((-3.2, legend_y), 0.14, facecolor=ZHANG_MAIN, edgecolor="none", alpha=0.8))
    ax.text(-2.92, legend_y, "张碧晨叙事", ha="left", va="center", fontsize=10, color=ZHANG_DEEP, fontweight="bold")
    ax.add_patch(Circle((-1.2, legend_y), 0.14, facecolor=WANG_MAIN, edgecolor="none", alpha=0.8))
    ax.text(-0.92, legend_y, "汪苏泷叙事", ha="left", va="center", fontsize=10, color=WANG_DEEP, fontweight="bold")
    ax.add_patch(Circle((0.8, legend_y), 0.14, facecolor=CRACK, edgecolor="none", alpha=0.8))
    ax.text(1.08, legend_y, "争议裂纹", ha="left", va="center", fontsize=10, color=CRACK, fontweight="bold")
    ax.add_patch(Circle((2.4, legend_y), 0.14, facecolor=OVERLAP, edgecolor="none", alpha=0.8))
    ax.text(2.68, legend_y, "共同记忆区", ha="left", va="center", fontsize=10, color=OVERLAP, fontweight="bold")

    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight", facecolor=BG_COLOR)
    print(f"✅ PNG 已保存: {OUTPUT_PNG}")
    plt.close()
    return rows, left_counts, right_counts, total_left, total_right


# ============================================================
#  2) Plotly 交互式 HTML
# ============================================================
def hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def build_html(rows, left_counts, right_counts, total_left, total_right):
    fig = go.Figure()

    # 共同记忆区
    theta = np.linspace(0, 2 * np.pi, 300)
    fig.add_trace(go.Scatter(
        x=1.0 * np.cos(theta), y=1.0 * np.sin(theta),
        fill="toself", fillcolor=hex_to_rgba(OVERLAP, 0.25),
        line=dict(width=0), hoverinfo="skip", showlegend=False, mode="lines",
    ))

    fig.add_annotation(x=0, y=0.55, text="<b>同一首歌</b>", showarrow=False,
                       font=dict(family=FONT, size=16, color="#3D3A35"))
    fig.add_annotation(x=0, y=0.15, text="<b>两套叙事</b>", showarrow=False,
                       font=dict(family=FONT, size=16, color="#3D3A35"))
    fig.add_annotation(x=0, y=-0.35, text="<b>共同记忆 / 双生分裂</b>", showarrow=False,
                       font=dict(family=FONT, size=11, color="#4A4035"))

    def add_rings(center, main_c, deep_c, light_c, counts, total, side):
        cx, cy = center
        stance_name = "张碧晨叙事" if side == "left" else "汪苏泷叙事"
        letter = "张" if side == "left" else "汪"

        stage_data = []
        for stage in STAGE_ORDER:
            cnt = counts.get(stage, 0)
            prop = cnt / total if total > 0 else 0
            if prop > 0.6:
                color = deep_c
            elif prop < 0.2:
                color = light_c
            else:
                color = main_c
            min_lw, max_lw = 2.0, 12.0
            linewidth = min_lw + prop * (max_lw - min_lw)
            min_a, max_a = 0.25, 0.40
            fill_alpha = min_a + prop * (max_a - min_a)
            stage_data.append({
                'stage': stage, 'cnt': cnt, 'prop': prop,
                'color': color, 'lw': linewidth, 'fa': fill_alpha,
                'label': STAGE_LABELS[stage]
            })

        for idx, d in enumerate(stage_data):
            radius = RADII[idx]
            t = np.linspace(0, 2 * np.pi, 300)
            fig.add_trace(go.Scatter(
                x=cx + radius * np.cos(t), y=cy + radius * np.sin(t),
                fill="toself",
                fillcolor=hex_to_rgba(d['color'], d['fa']),
                line=dict(width=0),
                hoverinfo="skip", showlegend=False, mode="lines",
            ))
            fig.add_trace(go.Scatter(
                x=cx + radius * np.cos(t), y=cy + radius * np.sin(t),
                mode="lines",
                line=dict(color=d['color'], width=d['lw']),
                opacity=0.85,
                hoverinfo="skip", showlegend=False,
            ))

        for idx, d in enumerate(stage_data):
            radius = RADII[idx]
            n_hover = 20
            hover_t = np.linspace(0, 2 * np.pi, n_hover, endpoint=False)
            hover_x = cx + radius * np.cos(hover_t)
            hover_y = cy + radius * np.sin(hover_t)

            if side == "left":
                angle_deg = LEFT_ANGLES_DEG[idx]
            else:
                angle_deg = RIGHT_ANGLES_DEG[idx]
            angle_rad = np.deg2rad(angle_deg)
            label_r = radius + 0.25
            label_x = cx + label_r * np.cos(angle_rad)
            label_y = cy + label_r * np.sin(angle_rad)
            rotation = angle_deg + 90 if side == "left" else angle_deg - 90

            fig.add_trace(go.Scatter(
                x=hover_x, y=hover_y,
                mode="markers",
                marker=dict(size=22, color="rgba(0,0,0,0.001)", line=dict(width=0)),
                customdata=[[d['stage'], d['label'], d['cnt'], total, d['prop'] * 100, stance_name, d['color']]] * n_hover,
                hovertemplate=(
                    "<b>%{customdata[5]}</b><br>"
                    "阶段：%{customdata[1]}<br>"
                    "微博数：%{customdata[2]} 条<br>"
                    "占比：%{customdata[4]:.1f}%<br>"
                    "该立场总计：%{customdata[3]} 条<extra></extra>"
                ),
                showlegend=False,
                hoverlabel=dict(
                    font=dict(family=FONT, size=12),
                    bgcolor="#FFFFFF",
                    bordercolor=d['color'],
                ),
            ))

            fig.add_annotation(
                x=label_x, y=label_y,
                text=f"<b>{d['label']}</b><br>{d['cnt']} 条",
                showarrow=False,
                font=dict(family=FONT, size=9, color=deep_c),
                textangle=rotation,
            )

        # 中心圆底（米白色，深色边框）
        ct = np.linspace(0, 2 * np.pi, 100)
        fig.add_trace(go.Scatter(
            x=cx + 0.42 * np.cos(ct), y=cy + 0.42 * np.sin(ct),
            fill="toself", fillcolor=BG_COLOR,
            line=dict(color=deep_c, width=1.5),
            hoverinfo="skip", showlegend=False, mode="lines",
        ))

        # 中心字母：直接使用深色文字（张用深褐，汪用深绿），无背景
        fig.add_annotation(x=cx, y=cy, text=f"<b>{letter}</b>", showarrow=False,
                           font=dict(family=FONT, size=24, color=deep_c))

        # 底部样本量
        fig.add_annotation(x=cx, y=cy - 2.4, text=f"<b>n={total}</b>", showarrow=False,
                           font=dict(family=FONT, size=11, color=deep_c))

    add_rings(ZHANG_CENTER, ZHANG_MAIN, ZHANG_DEEP, ZHANG_LIGHT, left_counts, total_left, "left")
    add_rings(WANG_CENTER, WANG_MAIN, WANG_DEEP, WANG_LIGHT, right_counts, total_right, "right")

    # 争议裂纹
    crack_lines = [
        ([-0.5, 0.5], [0.8, -0.4], 3.5, 0.85),
        ([-0.3, 0.3], [-0.9, 0.6], 3.5, 0.85),
        ([0.1, 0.4], [0.3, 0.7], 3.5, 0.85),
        ([-0.5, -0.2], [-0.4, -0.9], 3.5, 0.85),
        ([0.15, 0.5], [0.2, 0.6], 2.0, 0.60),
        ([-0.4, -0.1], [-0.6, -1.0], 2.0, 0.60),
    ]
    for xv, yv, lw, alpha in crack_lines:
        fig.add_trace(go.Scatter(
            x=xv, y=yv, mode="lines",
            line=dict(color=CRACK, width=lw),
            opacity=alpha,
            hoverinfo="skip", showlegend=False,
        ))

    # 底部图例
    legend_items = [
        (-3.2, "张碧晨叙事", ZHANG_MAIN, ZHANG_DEEP),
        (-1.2, "汪苏泷叙事", WANG_MAIN, WANG_DEEP),
        (0.8, "争议裂纹", CRACK, CRACK),
        (2.4, "共同记忆区", OVERLAP, OVERLAP),
    ]
    for lx, label, fill_c, text_c in legend_items:
        lt = np.linspace(0, 2 * np.pi, 40)
        fig.add_trace(go.Scatter(
            x=lx + 0.14 * np.cos(lt), y=-3.4 + 0.14 * np.sin(lt),
            fill="toself", fillcolor=fill_c, line=dict(width=0),
            opacity=0.8, hoverinfo="skip", showlegend=False, mode="lines",
        ))
        fig.add_annotation(x=lx + 0.28, y=-3.4, text=f"<b>{label}</b>",
                           showarrow=False, xanchor="left",
                           font=dict(family=FONT, size=10, color=text_c))

    # 标题
    fig.add_annotation(x=0, y=3.4, text="<b>图14 双生年轮：同一首歌在微博上生长出的两套真实叙事</b>",
                       showarrow=False, font=dict(family=FONT, size=18, color="#3D3A35"))
    fig.add_annotation(x=0, y=3.05, text="数据来源：all_weibo_texts_clean.csv | 仅统计 is_valid=1 的微博 | 悬停圆环查看阶段详情",
                       showarrow=False, font=dict(family=FONT, size=10, color="#7A746C"))

    fig.update_layout(
        font=dict(family=FONT, size=12, color="#333333"),
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        height=840,
        width=980,
        margin=dict(l=20, r=20, t=60, b=60),
        xaxis=dict(visible=False, range=[-4.5, 4.5], fixedrange=True),
        yaxis=dict(visible=False, range=[-4.2, 4.2], fixedrange=True,
                   scaleanchor="x", scaleratio=1),
        hoverlabel=dict(font=dict(family=FONT, size=12), bgcolor="#FFFFFF", bordercolor="#999999"),
        hovermode="closest",
        showlegend=False,
    )

    cfg = {"displayModeBar": True, "scrollZoom": True}
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn", config=cfg)
    print(f"✅ 交互式 HTML 已保存: {OUTPUT_HTML}")


def main():
    rows, left_counts, right_counts, total_left, total_right = build_png()
    build_html(rows, left_counts, right_counts, total_left, total_right)


if __name__ == "__main__":
    main()