#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_17_platform_role_matrix.py
平台传播角色矩阵
输出：PNG（完全保持原样） + 交互式 HTML（悬停卡片突出显示）
"""

import csv
import base64
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / 'platform_cases_clean.csv'
OUTPUT_DIR = BASE_DIR / 'figures'
OUTPUT_PNG = OUTPUT_DIR / 'fig_17_platform_role_matrix.png'
OUTPUT_HTML = OUTPUT_DIR / 'fig_17_platform_role_matrix.html'

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

PLATFORM_ORDER = ['B站', '抖音', '知乎', '豆瓣']
STANCE_LABELS = {
    'support_zhang': '支持张碧晨',
    'support_wang': '支持汪苏泷',
    'neutral': '中立讨论',
    'unclear': '无法判断',
    'anti_fanwar': '反感争议',
}
FRAME_LABELS = {
    'original_singer': '原唱身份',
    'copyright_authorization': '版权授权',
    'creator_identity': '创作者身份',
    'memory_emotion': '回忆情绪',
    'legal_discussion': '法律解释',
    'fan_conflict': '粉丝冲突',
    'platform_meta': '平台 / 营销号',
    'unclear': '无法判断',
}
VIDEO_TYPE_LABELS = {
    '事件梳理': '事件梳理',
    '法律科普': '法律科普',
    '粉丝混剪': '粉丝混剪',
    '评论': '评论',
}
ROLE_COLORS = {
    'support_zhang': '#C07858',
    'support_wang': '#5A7A6A',
    'neutral': '#8C8C8C',
    'unclear': '#8C8C8C',
    'anti_fanwar': '#A05050',
}


def load_rows(path: Path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def aggregate_platform(rows):
    grouped = defaultdict(list)
    for row in rows:
        platform = (row.get('platform') or '').strip()
        if platform in PLATFORM_ORDER:
            grouped[platform].append(row)
    return grouped


def human_label(key, mapping):
    return mapping.get(key, key)


def role_from_summary(summary):
    if summary['top_frame_key'] == 'copyright_authorization' and summary['top_stance_key'] == 'support_wang':
        return '版权解释场'
    if summary['top_frame_key'] == 'original_singer' and summary['top_stance_key'] == 'support_zhang':
        return '原唱共鸣场'
    if summary['frame_unclear_share'] >= 40 and summary['stance_unclear_share'] >= 25:
        return '长评争论场'
    if summary['top_video_type_key'] == '事件梳理':
        return '热点扩散场'
    return '争议讨论场'


def summarize_platform(rows):
    stance_counts = Counter((row.get('stance') or 'unclear').strip() or 'unclear' for row in rows)
    frame_counts = Counter(((row.get('frame') or 'unclear').strip() or 'unclear') if ((row.get('frame') or 'unclear').strip() or 'unclear') in FRAME_LABELS else 'unclear' for row in rows)
    video_type_counts = Counter(((row.get('video_type') or '评论').strip() or '评论') if ((row.get('video_type') or '评论').strip() or '评论') in VIDEO_TYPE_LABELS else '评论' for row in rows)

    total = len(rows) if rows else 1
    top_stance_key, top_stance_count = stance_counts.most_common(1)[0]
    top_frame_key, top_frame_count = frame_counts.most_common(1)[0]
    top_video_type_key, top_video_type_count = video_type_counts.most_common(1)[0]

    summary = {
        'total': total,
        'stance_counts': stance_counts,
        'frame_counts': frame_counts,
        'video_type_counts': video_type_counts,
        'top_stance_key': top_stance_key,
        'top_stance_count': top_stance_count,
        'top_frame_key': top_frame_key,
        'top_frame_count': top_frame_count,
        'top_video_type_key': top_video_type_key,
        'top_video_type_count': top_video_type_count,
        'stance_unclear_share': stance_counts.get('unclear', 0) / total * 100.0,
        'frame_unclear_share': frame_counts.get('unclear', 0) / total * 100.0,
    }
    summary['role'] = role_from_summary(summary)
    return summary


def build_summaries(rows):
    grouped = aggregate_platform(rows)
    return {platform: summarize_platform(grouped[platform]) for platform in PLATFORM_ORDER}


def choose_accent(summary):
    role = summary['role']
    if role == '版权解释场':
        return '#5A7A6A'
    if role == '原唱共鸣场':
        return '#C07858'
    if role == '长评争论场':
        return '#8C8C8C'
    if role == '热点扩散场':
        return '#9A8A7A'
    return ROLE_COLORS.get(summary['top_stance_key'], '#8C8C8C')


def draw_card(ax, platform, summary):
    """绘制单个卡片（与原代码完全一致）"""
    accent = choose_accent(summary)
    total = summary['total']
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_facecolor('#F5F3EE')

    ax.add_patch(FancyBboxPatch((0.35, 0.35), 9.3, 9.3, boxstyle='round,pad=0.30,rounding_size=0.35',
                                facecolor='#F8F6F1', edgecolor=accent, linewidth=2.3, alpha=0.98))
    ax.add_patch(FancyBboxPatch((0.35, 8.45), 9.3, 1.25, boxstyle='round,pad=0.25,rounding_size=0.35',
                                facecolor=accent, edgecolor='none', alpha=0.97))
    ax.text(0.78, 9.0, platform, ha='left', va='center', fontsize=18, fontweight='bold', color='white')
    ax.text(9.1, 9.0, summary['role'], ha='right', va='center', fontsize=14, fontweight='bold', color='white')

    lines = [
        f'样本量：{total} 条',
        f'主导立场：{human_label(summary["top_stance_key"], STANCE_LABELS)} {summary["top_stance_count"] / total * 100.0:.1f}%（{summary["top_stance_count"]}/{total}）',
        f'主导叙事：{human_label(summary["top_frame_key"], FRAME_LABELS)} {summary["top_frame_count"] / total * 100.0:.1f}%（{summary["top_frame_count"]}/{total}）',
        f'主导内容：{human_label(summary["top_video_type_key"], VIDEO_TYPE_LABELS)} {summary["top_video_type_count"] / total * 100.0:.1f}%（{summary["top_video_type_count"]}/{total}）',
    ]
    y = 7.45
    for line in lines:
        ax.text(0.8, y, line, ha='left', va='center', fontsize=11.5, color='#3E3A35')
        y -= 1.05

    secondary_frames = summary['frame_counts'].most_common(3)
    if len(secondary_frames) > 1:
        secondary_text = '；'.join(f'{human_label(frame_key, FRAME_LABELS)} {count} 条'
                                   for frame_key, count in secondary_frames[1:] if count > 0)
        if secondary_text:
            ax.text(0.8, 2.95, f'次级叙事：{secondary_text}', ha='left', va='center', fontsize=10.3, color='#6B655E')

    stance_order = ['support_zhang', 'support_wang', 'neutral', 'unclear', 'anti_fanwar']
    bar_x = 0.8
    bar_y = 1.05
    bar_w = 8.4
    ax.text(bar_x, 1.95, '立场构成', ha='left', va='center', fontsize=10.5, color='#6B655E')
    current_x = bar_x
    for key in stance_order:
        count = summary['stance_counts'].get(key, 0)
        share = count / total if total else 0
        segment_w = bar_w * share
        if segment_w <= 0:
            continue
        ax.add_patch(FancyBboxPatch((current_x, bar_y), segment_w, 0.34,
                                    boxstyle='round,pad=0.01,rounding_size=0.12',
                                    facecolor=ROLE_COLORS.get(key, '#8C8C8C'),
                                    edgecolor='white', linewidth=0.8, alpha=0.95))
        if segment_w > 1.1:
            ax.text(current_x + segment_w / 2, bar_y + 0.17, f'{share * 100:.1f}%',
                    ha='center', va='center', fontsize=8.5, color='white', fontweight='bold')
        current_x += segment_w


def build_png(summaries):
    """生成 PNG（完全保持原样），并返回图片的 base64 编码"""
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    fig.patch.set_facecolor('#F5F3EE')

    for ax, platform in zip(axes.flat, PLATFORM_ORDER):
        draw_card(ax, platform, summaries[platform])

    plt.suptitle('图17 平台传播角色矩阵：不同平台如何分配争议的传播功能',
                 fontsize=17, fontweight='bold', y=0.98, color='#3D3A35')
    plt.figtext(0.5, 0.015, '注：角色名称根据 platform_cases_clean.csv 中的主导立场、主导叙事与内容类型自动归纳。',
                ha='center', va='bottom', fontsize=10, color='#7A746C')
    plt.tight_layout(rect=[0.02, 0.03, 1, 0.955])

    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches='tight', facecolor='#F5F3EE')
    plt.close()
    print(f'✅ PNG 已保存: {OUTPUT_PNG}')

    # 读取 PNG 并转为 base64，供 HTML 内嵌使用
    with open(OUTPUT_PNG, 'rb') as f:
        png_bytes = f.read()
    return base64.b64encode(png_bytes).decode('utf-8')


def build_html(summaries, png_base64):
    """
    生成交互式 HTML：
    - 显示与 PNG 完全相同的图片
    - 在四个卡片位置覆盖透明层
    - 鼠标悬停时，对应卡片出现彩色发光突出效果
    """
    accent_colors = {p: choose_accent(summaries[p]) for p in PLATFORM_ORDER}

    # 卡片区域位置（百分比，可微调）
    card_positions = {
        'B站':  {'left': 4, 'top': 10, 'width': 44, 'height': 40},
        '抖音': {'left': 52, 'top': 10, 'width': 44, 'height': 40},
        '知乎': {'left': 4, 'top': 54, 'width': 44, 'height': 40},
        '豆瓣': {'left': 52, 'top': 54, 'width': 44, 'height': 40},
    }

    overlay_divs = ""
    for plat, pos in card_positions.items():
        accent = accent_colors[plat]
        overlay_divs += f"""
        <div class="card-overlay" style="
            left: {pos['left']}%; top: {pos['top']}%;
            width: {pos['width']}%; height: {pos['height']}%;
            --accent-color: {accent};
        " data-platform="{plat}"></div>"""

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>平台传播角色矩阵</title>
<style>
    body {{
        margin: 0; padding: 20px;
        background: #F5F3EE;
        display: flex; justify-content: center; align-items: center;
        min-height: 100vh;
    }}
    .figure-container {{
        position: relative;
        display: inline-block;
        line-height: 0;
    }}
    .figure-container img {{
        display: block;
        max-width: 100%;
        height: auto;
    }}
    .card-overlay {{
        position: absolute;
        border: 2px solid transparent;
        border-radius: 12px;
        box-sizing: border-box;
        cursor: pointer;
        transition: all 0.25s ease;
        background: transparent;
        z-index: 1;
    }}
    .card-overlay:hover {{
        border-color: var(--accent-color) !important;
        box-shadow: 0 0 18px 4px var(--accent-color);
        transform: scale(1.03);
        z-index: 10;
    }}
</style>
</head>
<body>
<div class="figure-container">
    <img src="data:image/png;base64,{png_base64}" alt="平台传播角色矩阵">
    {overlay_divs}
</div>
</body>
</html>"""

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'✅ 交互式 HTML 已保存: {OUTPUT_HTML}')

def main():
    rows = load_rows(DATA_PATH)
    summaries = build_summaries(rows)
    png_base64 = build_png(summaries)
    build_html(summaries, png_base64)


if __name__ == '__main__':
    main()