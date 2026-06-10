"""
《年轮》舆论争议项目 —— Fig 03 + Fig 04 绘制脚本
==================================================

归属成员：B —— 立场与情绪分析
负责问题：微博网友支持谁？他们在讲事实、讲版权，还是在表达情绪？

图表清单：
  - Fig 03：立场分布环形图（fig_03_stance_distribution.png）

配色方案：赤陶松烟（风格规范.md）
  - 赤陶 #C07858 …… 张碧晨叙事（支持张碧晨 / 原唱身份）
  - 松烟 #5A7A6A …… 汪苏泷叙事（支持汪苏泷 / 创作者 / 版权）
  - 灰色 #8C8C8C …… 中立 / 无法判断
  - 深绯 #A05050 …… 反感饭圈 / 愤怒 / 冲突

数据说明：
  - 优先使用内存中的 data_copilot_cleaned DataFrame
  - 回退策略：weibo_comments_all_predicted_cleaned.csv
  - 关键字段：stance（立场）

运行方式：
  python scripts/plot_fig03_fig04.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# ============================================================
# 一、全局样式：统一项目视觉规范
# ============================================================

# 画布底色 —— 亚麻白（风格规范.md 规定）
BACKGROUND_COLOR = "#F5F3EE"
# 正文文字色 —— 深灰，保证在浅底色上清晰可读
TEXT_COLOR = "#2F2F2F"
# 网格线色 —— 浅灰，辅助阅读但不抢眼
GRID_COLOR = "#CFC8BF"

# 字体优先级：Windows / macOS / Linux 均能正确显示中文
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "Noto Sans SC",
    "SimHei",
    "Arial Unicode MS",
    "sans-serif",
]
plt.rcParams["axes.unicode_minus"] = False


# ============================================================
# 二、配色与标签映射（严格遵循 风格规范.md）
# ============================================================

# ---------- 2.1 立场标签与颜色 ----------
STANCE_LABELS: dict[str, str] = {
    "support_zhang": "支持张碧晨",       # 赤陶
    "support_wang": "支持汪苏泷",         # 松烟
    "anti_fanwar": "反感饭圈争议",        # 深绯
    "neutral_unclear": "中立讨论/无法判断",  # 灰色（neutral + unclear 合并）
    "other": "其他立场",                  # 灰色兜底
}

STANCE_COLORS: dict[str, str] = {
    "support_zhang": "#C07858",
    "support_wang": "#5A7A6A",
    "anti_fanwar": "#A05050",
    "neutral_unclear": "#8C8C8C",
    "other": "#8C8C8C",
}

# 构建标签 → 颜色的反向查找表，方便在绘图中直接使用
_LABEL_TO_STANCE_COLOR: dict[str, str] = {
    v: STANCE_COLORS[k] for k, v in STANCE_LABELS.items()
}




# ============================================================
# 三、数据加载与校验
# ============================================================

def get_project_root() -> Path:
    """
    定位项目根目录（Homework3 目录）。
    """
    if "__file__" in globals():
        return Path(__file__).resolve().parent.parent.parent.parent
    return Path.cwd().resolve()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一列名，兼容不同数据文件的字段名差异。
    """
    df = df.copy()

    # 映射 predicted_stance → stance
    if "stance" not in df.columns and "predicted_stance" in df.columns:
        df.rename(columns={"predicted_stance": "stance"}, inplace=True)

    # 映射 comment_text / text → text_raw
    if "text_raw" not in df.columns:
        if "comment_text" in df.columns:
            df.rename(columns={"comment_text": "text_raw"}, inplace=True)
        elif "text" in df.columns:
            df.rename(columns={"text": "text_raw"}, inplace=True)

    return df


def load_dataframe() -> pd.DataFrame:
    """
    加载清洗后的数据，优先级如下：
       1. 当前全局作用域中的 data_copilot_cleaned 变量（Notebook 场景）
       2. 项目根目录下的 weibo_comments_all_predicted.csv
    """
    # 场景一：交互式环境中已存在变量
    if "data_copilot_cleaned" in globals():
        df = globals()["data_copilot_cleaned"]
        if isinstance(df, pd.DataFrame):
            return _normalize_columns(df)

    # 场景二：从 CSV 文件读取
    root = get_project_root()
    candidates = [
        root / "02_data" / "B_data" / "cleaned" / "weibo_comments_clean.csv",
        root / "02_data" / "B_data" / "cleaned" / "all_weibo_texts_clean.csv",
        root / "02_data" / "B_data" / "cleaned" / "weibo_posts_clean.csv",
    ]

    for path in candidates:
        if path.exists():
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding="gbk")
            return _normalize_columns(df)

    raise FileNotFoundError(
        "未找到数据文件。"
    )


def validate_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    """确保 DataFrame 包含所有必要字段，缺失时提前报错。"""
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"数据缺少必要字段：{missing}")


def _recover_stance_from_unclear(df: pd.DataFrame) -> pd.DataFrame:
    """
    从 unclear 中通过关键词规则恢复部分立场标签。

    规则说明：
      - 匹配支持张碧晨 / 支持汪苏泷 / 反感饭圈 / 中立讨论的关键词
      - 被匹配为 support_zhang 但实际文本含负面信号（批评张碧晨本人），
        则退回重判为 neutral，避免将"骂张"误标为"挺张"
    """
    df = df.copy()
    unclear_mask = df["stance"] == "unclear"
    if not unclear_mask.any():
        return df

    # 拼接可用的文本字段：优先 text_raw（保留完整回复内容）
    texts = df.loc[unclear_mask, "text_raw"].fillna("").astype(str)
    texts = texts.replace("nan", "")
    texts = texts.str.strip()

    # ----- 关键词规则 -----
    def _keyword_stance(t: str) -> str | None:
        if not t:
            return None

        # 支持张碧晨
        if any(kw in t for kw in [
            "张碧晨唱", "张碧晨好", "喜欢张碧晨", "支持张碧晨",
            "碧晨", "张碧晨的歌", "张碧晨版本",
            "她唱", "她唱得", "支持她", "她值得", "她太", "她真",
            "碧晨唱",
        ]):
            return "support_zhang"

        # 支持汪苏泷
        if any(kw in t for kw in [
            "汪苏泷唱", "汪苏泷好", "喜欢汪苏泷", "支持汪苏泷",
            "苏泷", "汪苏泷的歌", "汪苏泷版本",
            "他唱", "他唱得", "支持他", "他值得", "他太", "他真",
            "苏泷唱",
        ]):
            return "support_wang"

        # 反感饭圈争议
        if any(kw in t for kw in ["饭圈", "吵架", "别吵", "撕", "引战", "粉丝互", "骂来骂去"]):
            return "anti_fanwar"

        # 中立讨论（提到事件但不站队）
        if any(kw in t for kw in ["年轮", "原唱", "版权", "授权", "OST", "主题曲", "这首歌"]):
            return "neutral"

        return None

    # ----- 负面信号过滤（针对 support_zhang）-----
    # 如果文本匹配了 support_zhang，但正文在批评/嘲讽张碧晨本人，退回 neutral
    _ZHANG_NEGATIVE = [
        "疯", "怕", "无语", "恶心", "有病", "烦", "脑残",
        "笑死", "呵呵", "搞笑", "有毒", "受不了", "太可怕",
        "不喜欢", "无感", "讨厌", "恶心", "什么玩意",
        "私生饭", "未婚怀孕", "不喜",
    ]

    def _has_negative_to_zhang(t: str) -> bool:
        """检查文本是否对张碧晨本人有负面倾向。"""
        return any(kw in t for kw in _ZHANG_NEGATIVE)

    # 逐行判断
    for idx in unclear_mask.index[unclear_mask]:
        t = texts.loc[idx]
        pred = _keyword_stance(t)
        if pred is None:
            continue
        # 命中 support_zhang 但含负面信号 → neutral
        if pred == "support_zhang" and _has_negative_to_zhang(t):
            pred = "neutral"
        df.at[idx, "stance"] = pred

    return df


# ============================================================
# 四、Fig 03 — 立场分布环形图
# ============================================================

def clean_stance(value: object) -> str:
    """
    将原始的 stance 英文值映射为中文展示标签。

    合并规则：
      - 'neutral' 与 'unclear' → "中立讨论/无法判断"
      - 其余未预期的值 → "其他立场"（防静默丢失）
    """
    if pd.isna(value):
        return STANCE_LABELS["other"]
    v = str(value).strip()

    if v == "support_zhang":
        return STANCE_LABELS["support_zhang"]
    if v == "support_wang":
        return STANCE_LABELS["support_wang"]
    if v == "anti_fanwar":
        return STANCE_LABELS["anti_fanwar"]
    if v in ("neutral", "unclear"):
        return STANCE_LABELS["neutral_unclear"]

    return STANCE_LABELS["other"]


def build_stance_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    生成立场分布汇总表。

    输出列：立场 / 数量 / 占比（%）
    排序：按数量降序，同数量时按预定义顺序（张→汪→反感→中立→其他）。
    """
    # 映射为中文标签
    mapped = df["stance"].apply(clean_stance)
    summary = mapped.value_counts().rename_axis("立场").reset_index(name="数量")

    # 加入自定义排序权重，保证图例顺序稳定
    order = [
        STANCE_LABELS["support_zhang"],
        STANCE_LABELS["support_wang"],
        STANCE_LABELS["anti_fanwar"],
        STANCE_LABELS["neutral_unclear"],
        STANCE_LABELS["other"],
    ]
    priority = {label: i for i, label in enumerate(order)}
    summary["_sort"] = summary["立场"].map(priority).fillna(99)
    summary = summary.sort_values(["数量", "_sort"], ascending=[False, True])
    summary = summary.drop(columns="_sort")

    total = summary["数量"].sum()
    summary["占比"] = round(summary["数量"] / total * 100, 1)
    return summary


def make_autopct(values: list[int]):
    """
    饼图标签工厂：同时显示「数量」和「占比 %」。

    返回的函数会被 matplotlib 的 autopct 调用，
    pct 是 matplotlib 自动计算的百分比（0~100）。
    """
    total = sum(values)

    def _autopct(pct: float) -> str:
        count = int(round(pct * total / 100.0))
        return f"{count} 条\n{pct:.1f}%"

    return _autopct


def plot_fig03_stance_distribution(df: pd.DataFrame, output_path: Path) -> None:
    """
    绘制 Fig 03：立场分布环形图（Donut Chart）。

    设计要点：
      - 环形 width=0.38，中心留白区域标注"立场分布"与说明文字
      - 图例放在右侧，同时展示数量与占比
      - 配色严格使用赤陶松烟方案
    """
    validate_columns(df, ["stance"])
    summary = build_stance_summary(df)

    labels = summary["立场"].tolist()
    values = summary["数量"].tolist()
    percentages = summary["占比"].tolist()
    colors = [_LABEL_TO_STANCE_COLOR.get(l, STANCE_COLORS["other"]) for l in labels]

    # 创建画布
    fig, ax = plt.subplots(figsize=(12.5, 8), facecolor=BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    # ---------- 绘制环形图 ----------
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        startangle=90,           # 从 12 点钟方向开始
        counterclock=False,      # 顺时针排列
        wedgeprops={
            "width": 0.38,            # 环形宽度，越小环越细
            "edgecolor": BACKGROUND_COLOR,
            "linewidth": 1.5,
        },
        autopct=make_autopct(values),
        pctdistance=0.78,        # 百分比文字与圆心的距离
        labeldistance=1.08,      # 类别标签与圆心的距离
        textprops={"fontsize": 12, "color": TEXT_COLOR},
    )

    # 加粗百分比文字
    for t in autotexts:
        t.set_fontsize(11)
        t.set_color(TEXT_COLOR)
        t.set_weight("bold")

    # ---------- 中心留白区域：标注"立场分布" ----------
    center_circle = plt.Circle(
        (0, 0), 0.43,
        color=BACKGROUND_COLOR,
        ec=BACKGROUND_COLOR,
    )
    ax.add_artist(center_circle)

    ax.text(0, 0.03, "立场\n分布",
            ha="center", va="center",
            fontsize=16, fontweight="bold", color=TEXT_COLOR)
    ax.text(0, -0.22, "合并中立与无法判断",
            ha="center", va="center",
            fontsize=10.5, color="#666666")

    # ---------- 图例（右侧，展示数量+占比） ----------
    legend_handles = [
        Patch(facecolor=c, edgecolor="none",
              label=f"{l}：{n} 条，占比 {p:.1f}%")
        for l, n, p, c in zip(labels, values, percentages, colors)
    ]
    ax.legend(
        handles=legend_handles,
        title="立场类别",
        loc="center left",
        bbox_to_anchor=(1.15, 0.5),
        frameon=False,
        fontsize=11,
        title_fontsize=12,
        handletextpad=1.5,
    )

    # ---------- 标题 ----------
    ax.set_title(
        "图3 立场分布：原唱与版权叙事的分化",
        fontsize=20, fontweight="bold", color=TEXT_COLOR, pad=18,
    )
    ax.set(aspect="equal")

    # 为右侧图例留出空间
    plt.tight_layout(rect=[0, 0, 0.80, 1])

    # ---------- 输出 ----------
    fig.savefig(output_path, dpi=300, bbox_inches="tight",
                facecolor=BACKGROUND_COLOR)
    plt.close(fig)
    print(f"[Fig 03] 已生成：{output_path}")


# ============================================================
# 五、主入口
# ============================================================

def main() -> None:
    """统一入口：加载数据 → 生成 Fig 03。"""
    print("=" * 50)
    print("《年轮》舆论争议项目 —— 立场分析图表生成")
    print("=" * 50)

    # ---------- 1. 加载数据 ----------
    print("\n[Info] 正在加载数据...")
    df = load_dataframe()
    print(f"[Info] 数据加载完成，共 {len(df)} 行")
    # ---------- 2. 从 unclear 中恢复立场标签 ----------
    before = df["stance"].value_counts().to_dict()
    df = _recover_stance_from_unclear(df)
    after = df["stance"].value_counts().to_dict()
    print(f"\n[Info] stance 分布（恢复前后对比）：")
    for label in sorted(set(list(before.keys()) + list(after.keys()))):
        b = before.get(label, 0)
        a = after.get(label, 0)
        if b != a:
            print(f"    {label}: {b} → {a} (Δ{a-b:+.0f})")
        else:
            print(f"    {label}: {b}")

    # ---------- 3. 生成图片 ----------
    root = get_project_root()
    figures_dir = root / "04_figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    fig03_path = figures_dir / "fig_03_stance_distribution.png"

    print("\n[Info] 正在生成 Fig 03 立场分布环形图...")
    plot_fig03_stance_distribution(df, fig03_path)

    print("\n" + "=" * 50)
    print("全部图表生成完毕！")
    print(f"  - {fig03_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
