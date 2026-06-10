"""
双方阵营 Top-10 高频词组对比
按照《风格规范.md》赤陶松烟配色体系
"""

import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sklearn.feature_extraction.text import CountVectorizer

# ============================================================
# 风格规范配置
# ============================================================
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

BG = "#F5F3EE"
TEXT_COLOR = "#2F2F2F"
C_ZHANG = "#C07858"
C_WANG = "#5A7A6A"
C_ZHANG_LIGHT = "#D8B0A0"
C_WANG_LIGHT = "#90B0A0"

# ============================================================
# 1. 数据加载 & 阵营划分（按 stance）
# ============================================================
df = pd.read_csv("all_weibo_comments_annotated.csv", encoding="utf-8-sig")
df_z = df[df["stance"] == "support_zhang"]["text_clean"].dropna().copy()
df_w = df[df["stance"] == "support_wang"]["text_clean"].dropna().copy()

# ============================================================
# 2. 文本清洗
# ============================================================
def clean_text(t):
    if pd.isna(t):
        return ""
    t = str(t)
    t = re.sub(r"@\S+", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\[.*?\]", "", t)
    t = re.sub(r"[【】「」]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

df_z = df_z.apply(clean_text)
df_w = df_w.apply(clean_text)

# ============================================================
# 3. Top-10 高频词组提取
# ============================================================
def top_ngrams(texts, n=10):
    vec = CountVectorizer(ngram_range=(2, 3), max_features=n,
                          token_pattern=r"(?u)\b\w+\b")
    X = vec.fit_transform(texts)
    sums = X.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    idx = sums.argsort()[::-1]
    return [(terms[i], int(sums[i])) for i in idx]

zp = top_ngrams(df_z)
wp = top_ngrams(df_w)

z_phrases = [p for p, _ in zp][::-1]
z_counts = [c for _, c in zp][::-1]
w_phrases = [p for p, _ in wp][::-1]
w_counts = [c for _, c in wp][::-1]

# ============================================================
# 4. 绘图
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), facecolor=BG)

# ---- 左侧：女方 ----
ax1.set_facecolor(BG)
bars1 = ax1.barh(range(10), z_counts, color=C_ZHANG, edgecolor="white", linewidth=0.6, height=0.6)
max_z = max(z_counts)
for bar, v in zip(bars1, z_counts):
    ax1.text(bar.get_width() + max_z * 0.03, bar.get_y() + bar.get_height() / 2,
             f"{v}", ha="left", va="center", fontsize=10, color=C_ZHANG, fontweight="bold")
ax1.set_yticks(range(10))
ax1.set_yticklabels(z_phrases, fontsize=10, color=TEXT_COLOR)
ax1.set_xlim(0, max_z * 1.35)
ax1.set_title("支持张碧晨", fontsize=16, fontweight="bold", color=C_ZHANG, pad=10)
ax1.set_xlabel("出现次数 / 次", fontsize=11, color="#666")
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)
ax1.spines["left"].set_color("#DDD")
ax1.spines["bottom"].set_color("#DDD")
ax1.tick_params(axis="x", colors="#888")

# ---- 右侧：男方 ----
ax2.set_facecolor(BG)
bars2 = ax2.barh(range(10), w_counts, color=C_WANG, edgecolor="white", linewidth=0.6, height=0.6)
max_w = max(w_counts)
for bar, v in zip(bars2, w_counts):
    ax2.text(bar.get_width() + max_w * 0.03, bar.get_y() + bar.get_height() / 2,
             f"{v}", ha="left", va="center", fontsize=10, color=C_WANG, fontweight="bold")
ax2.set_yticks(range(10))
ax2.set_yticklabels(w_phrases, fontsize=10, color=TEXT_COLOR)
ax2.set_xlim(0, max_w * 1.35)
ax2.set_title("支持汪苏泷", fontsize=16, fontweight="bold", color=C_WANG, pad=10)
ax2.set_xlabel("出现次数 / 次", fontsize=11, color="#666")
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.spines["left"].set_color("#DDD")
ax2.spines["bottom"].set_color("#DDD")
ax2.tick_params(axis="x", colors="#888")

# ---- 总标题 ----
fig.suptitle("图12 高频词组对比：两套叙事的议题错位",
             fontsize=20, fontweight="bold", color=TEXT_COLOR, y=1.01)

plt.tight_layout()
plt.savefig("fig_10_keyword_top30.png", dpi=300, bbox_inches="tight",
            facecolor=BG, pad_inches=0.3)
plt.close()
print("[OK] 已生成 fig_10_keyword_top30.png")
