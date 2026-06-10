"""
同质化内容分布图：重复文本 × 发布者身份
按照《风格规范.md》赤陶松烟配色体系
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

BG = "#F5F3EE"
TEXT_COLOR = "#2F2F2F"
C_ZHANG_FAN = "#D8B0A0"
C_ZHANG_ARMY = "#C07858"
C_WANG_FAN = "#90B0A0"
C_WANG_ARMY = "#5A7A6A"
C_OTHER = "#9A8A7A"

# ============================================================
# 数据（来自用户整理的统计数据）
# ============================================================
data_zhang = [
    {
        "label": "「#张碧晨爱的史诗交响演唱会#」",
        "segments": [
            ("张碧晨粉丝", 69, C_ZHANG_FAN),
            ("张方水军", 18, C_ZHANG_ARMY),
        ],
        "total": 89,
    },
    {
        "label": "「#专家称张碧晨唯一原唱证据不足#」",
        "segments": [
            ("张碧晨粉丝", 38, C_ZHANG_FAN),
            ("张方水军", 3, C_ZHANG_ARMY),
        ],
        "total": 41,
    },
    {
        "label": "「没关系，梦幻诛仙我只听\n140w收藏+那版……」",
        "segments": [
            ("张方水军", 18, C_ZHANG_ARMY),
            ("张碧晨粉丝", 13, C_ZHANG_FAN),
        ],
        "total": 32,
    },
    {
        "label": "「#专业人士不认同年轮抄袭#」",
        "segments": [
            ("张碧晨粉丝", 6, C_ZHANG_FAN),
        ],
        "total": 6,
    },
]

data_wang = [
    {
        "label": "「汪苏泷方及粉丝自始至终\n坚持双原唱……」",
        "segments": [
            ("汪方水军", 742, C_WANG_ARMY),
            ("汪苏泷粉丝", 191, C_WANG_FAN),
        ],
        "total": 964,
    },
    {
        "label": "「同上（截断版①）」",
        "segments": [
            ("汪方水军", 394, C_WANG_ARMY),
            ("汪苏泷粉丝", 80, C_WANG_FAN),
        ],
        "total": 490,
    },
    {
        "label": "「同上（截断版②）」",
        "segments": [
            ("汪方水军", 51, C_WANG_ARMY),
        ],
        "total": 59,
    },
    {
        "label": "「The flower will wither…\n花会枯萎爱意永不凋零」",
        "segments": [
            ("汪方水军", 32, C_WANG_ARMY),
        ],
        "total": 32,
    },
    {
        "label": "「汪苏泷作为词曲作者…\n民法典第1023条…」",
        "segments": [
            ("汪方水军", 24, C_WANG_ARMY),
            ("汪苏泷粉丝", 6, C_WANG_FAN),
        ],
        "total": 31,
    },
]

# ============================================================
# 绘图
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8), facecolor=BG)

def draw_side(ax, data, title, title_color):
    ax.set_facecolor(BG)
    y_pos = range(len(data))
    # 先画最长的bar作为底
    for i, d in enumerate(data):
        ax.barh(i, d["total"], color=BG, edgecolor="none", height=0.55)
    # 再画分段
    for i, d in enumerate(data):
        left = 0
        for seg_name, seg_val, seg_c in d["segments"]:
            ax.barh(i, seg_val, left=left, color=seg_c, edgecolor="white",
                    linewidth=0.4, height=0.55)
            left += seg_val
    # 总数标注
    max_t = max(d["total"] for d in data)
    for i, d in enumerate(data):
        ax.text(d["total"] + max_t * 0.02, i, f"{d['total']}次",
                ha="left", va="center", fontsize=11, color=TEXT_COLOR, fontweight="bold")
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels([d["label"] for d in data], fontsize=10, color=TEXT_COLOR)
    ax.set_xlim(0, max_t * 1.28)
    ax.set_title(title, fontsize=16, fontweight="bold", color=title_color, pad=12)
    ax.set_xlabel("出现次数 / 次", fontsize=11, color="#666")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDD")
    ax.spines["bottom"].set_color("#DDD")
    ax.tick_params(axis="x", colors="#888")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x)}"))

draw_side(ax1, data_zhang, "支持张碧晨 — 同质化内容（11.6%）", C_ZHANG_ARMY)
draw_side(ax2, data_wang, "支持汪苏泷 — 同质化内容（15.5%）", C_WANG_ARMY)

# ---- 通用图例 ----
legend_patches = [
    mpatches.Patch(color=C_ZHANG_FAN, label="张碧晨粉丝"),
    mpatches.Patch(color=C_ZHANG_ARMY, label="张方水军"),
    mpatches.Patch(color=C_WANG_FAN, label="汪苏泷粉丝"),
    mpatches.Patch(color=C_WANG_ARMY, label="汪方水军"),
]
fig.legend(handles=legend_patches, loc="lower center", ncol=4,
           fontsize=12, frameon=False, bbox_to_anchor=(0.5, -0.05))

fig.suptitle("图13 同质化内容分布：重复文本与发布者身份统计",
             fontsize=20, fontweight="bold", color=TEXT_COLOR, y=1.01)

plt.tight_layout(rect=[0, 0.06, 1, 1])
plt.savefig("fig_13_duplicate_content_distribution.png", dpi=300,
            bbox_inches="tight", facecolor=BG, pad_inches=0.3)
plt.close()
print("[OK] 已生成 fig_13_duplicate_content_distribution.png")
