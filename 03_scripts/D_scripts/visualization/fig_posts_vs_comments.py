"""
图X：主帖 vs 评论 vs 转发 — 三个场域的立场分布对比
生成三栏分组柱状图，标注关键落差。改进版：更精准的标注、浅色分区背景。
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import numpy as np

# 中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans SC']
plt.rcParams['axes.unicode_minus'] = False

# ── 配色规范 ──────────────────────────────────────────
C_WANG    = '#5A7A6A'
C_ZHANG   = '#C07858'
C_ANTI    = '#A05050'
C_NEUTRAL = '#8C8C8C'
C_BG      = '#F5F3EE'

# ── 数据 ──────────────────────────────────────────────
categories = ['主帖\n(7,430条)', '评论\n(156,420条)', '转发\n(2,636条)']

data = {
    '支持汪苏泷': [60.1, 34.5, 66.1],
    '支持张碧晨': [14.7, 13.2, 33.9],
    '反感饭圈':   [16.4, 31.6,  0.0],
    '中立':       [ 8.6, 20.7,  0.0],
}
colors = [C_WANG, C_ZHANG, C_ANTI, C_NEUTRAL]

# ── 画布 ──────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(15, 7.5))
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

x = np.arange(len(categories))
bar_width = 0.18

offsets = [-1.5, -0.5, 0.5, 1.5]
offset_scaled = [o * bar_width for o in offsets]

# ── 浅色分区背景 ───────────────────────────────────────
for i in range(3):
    ax.axvspan(i - 0.42, i + 0.42, facecolor='white', edgecolor='none',
               alpha=0.5, zorder=0)

# ── 画柱 ──────────────────────────────────────────────
bar_containers = {}
for idx, (label, values) in enumerate(data.items()):
    bars = ax.bar(
        x + offset_scaled[idx], values, bar_width,
        color=colors[idx], edgecolor='white', linewidth=1.0,
        label=label, zorder=3,
    )
    bar_containers[label] = bars
    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.0,
                f'{val:.1f}%',
                ha='center', va='bottom',
                fontsize=9.5, fontweight='bold', color='#333333',
            )

# ── 坐标轴 ────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=14, fontweight='bold', color='#2A2A2A')
ax.set_ylim(0, 82)
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%d%%'))
ax.tick_params(axis='y', labelsize=11, colors='#666666')
ax.grid(axis='y', color='#E0DCD5', linewidth=0.6, zorder=0)
ax.set_axisbelow(True)
for spine in ax.spines.values():
    spine.set_visible(False)

# ── 图例 ──────────────────────────────────────────────
legend = ax.legend(
    loc='upper center', bbox_to_anchor=(0.5, 1.08),
    fontsize=11.5, frameon=True, facecolor='white',
    edgecolor='#D0CCC5', framealpha=0.95, ncol=4,
    borderpad=0.5, handlelength=1.2, handleheight=1.0,
)
legend.get_frame().set_linewidth(0.5)

# ── 标注①：support_wang 断崖 ──────────────────────────
# 画两条细虚线标记主帖和评论中 support_wang 的高度
posts_wang_bar = bar_containers['支持汪苏泷'][0]
comments_wang_bar = bar_containers['支持汪苏泷'][1]
y1 = posts_wang_bar.get_height()      # 60.1
y2 = comments_wang_bar.get_height()   # 34.5

# 下降箭头
ax.annotate(
    '', xy=(0.73, y2 + 2), xytext=(0.73, y1 + 2),
    arrowprops=dict(arrowstyle='->', color='#CC3333', lw=3.5,
                    connectionstyle='arc3,rad=0'),
)
# 标注文字
ax.text(
    0.97, (y1 + y2) / 2,
    '−25.6pp\n汪方从 60% 跌至 35%\n与反感饭圈几乎持平',
    fontsize=11, color='#CC3333', fontweight='bold', va='center', ha='left',
    bbox=dict(boxstyle='round,pad=0.45', facecolor='white',
              edgecolor='#CC3333', alpha=0.9, linewidth=1.0),
)

# ── 标注②：anti_fanwar 飙升 ──────────────────────────
posts_anti_bar = bar_containers['反感饭圈'][0]
comments_anti_bar = bar_containers['反感饭圈'][1]
y3 = posts_anti_bar.get_height()     # 16.4
y4 = comments_anti_bar.get_height()  # 31.6

# 上升箭头
ax.annotate(
    '', xy=(1.27, y4 + 2), xytext=(1.27, y3 + 2),
    arrowprops=dict(arrowstyle='->', color='#E07820', lw=3.5,
                    connectionstyle='arc3,rad=0'),
)
ax.text(
    1.51, (y3 + y4) / 2,
    '+15.2pp\n评论区更多人\n表达"烦死了别吵了"',
    fontsize=11, color='#E07820', fontweight='bold', va='center', ha='left',
    bbox=dict(boxstyle='round,pad=0.45', facecolor='white',
              edgecolor='#E07820', alpha=0.9, linewidth=1.0),
)

# ── 标注③：转发只站队 ─────────────────────────────────
ax.text(
    2.0, 72,
    '转发行为自带立场筛选\n没有中立，没有反感\n只有站队传播',
    fontsize=9.5, color='#888888', fontstyle='italic',
    va='top', ha='center',
    bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
              edgecolor='#BBBBBB', alpha=0.75, linewidth=0.5),
)

# ── 图内小标签：评论区的关键等号 ──────────────────────
# 在评论组的 support_wang(34.5%) 和 anti_fanwar(31.6%) 之间画个等号标记
ax.annotate(
    '≈ 几乎持平',
    xy=(1.0, 32.5), fontsize=10, color='#666666',
    ha='center', va='bottom', fontstyle='italic',
    bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF8F0',
              edgecolor='#D0C8C0', alpha=0.85, linewidth=0.5),
)

# ── 标题 ──────────────────────────────────────────────
ax.set_title(
    '同一事件，三个场域，三种"气候"',
    fontsize=19, fontweight='bold', color='#2A2A2A',
    pad=28,
)

# 副标题放在标题下方
fig.text(
    0.5, 0.865,
    '主帖中汪方占 60%，版权授权和法律解释框架为主  |  '
    '评论中反感饭圈（32%）与支持汪方（35%）几乎持平  |  '
    '转发中无中立/反感，仅存站队传播',
    fontsize=10.5, color='#666666',
    ha='center', va='top', style='italic',
)

# ── 底部注释 ──────────────────────────────────────────
fig.text(
    0.5, 0.012,
    '数据来源：weibo_posts_clean.csv (7,430条)  |  '
    'weibo_comments_clean.csv (156,420条)  |  '
    'weibo_reposts_clean.csv (2,636条)     '
    '标注方法：规则 + ML + LLM 多轮迭代',
    fontsize=8, color='#AAAAAA',
    ha='center', va='bottom',
)

plt.tight_layout(rect=[0.02, 0.06, 0.98, 0.84])

# ── 保存 ──────────────────────────────────────────────
out_path = 'figures/fig_19_posts_vs_comments_stance.png'
fig.savefig(out_path, dpi=180, bbox_inches='tight', facecolor=C_BG)
print(f'[OK] Saved → {out_path}')
plt.close()
