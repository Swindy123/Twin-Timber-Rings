from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

matplotlib.rcParams["font.family"] = "Microsoft YaHei, Noto Sans SC, sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

BG_COLOR = "#F5F3EE"
TEXT_COLOR = "#2F2F2F"

STAGE_MAP = {
    "outbreak": "争议发酵",
    "response": "双方回应",
    "debate":   "版权争论",
    "cooldown": "冷却期",
}
STAGE_ORDER = ["outbreak", "response", "debate", "cooldown"]

STANCE_CONFIG = [
    {"name": "支持张碧晨",       "key": "support_zhang", "color": "#C07858"},
    {"name": "支持汪苏泷",       "key": "support_wang",  "color": "#5A7A6A"},
    {"name": "反感饭圈争议",     "key": "anti_fanwar",   "color": "#A05050"},
    {"name": "中立讨论/无法判断","key": "neutral_unclear","color": "#8C8C8C"},
]


def main():
    root = Path(__file__).resolve().parent.parent.parent.parent
    csv_path = root / "02_data" / "B_data" / "cleaned" / "weibo_comments_clean.csv"
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    df["stance_group"] = df["stance"].apply(
        lambda x: "neutral_unclear" if x in ("neutral", "unclear") else x
    )

    stage_labels = [STAGE_MAP[s] for s in STAGE_ORDER]
    stage_data = {}
    for s in STAGE_ORDER:
        subset = df[df["event_stage"] == s]
        total = len(subset)
        stage_data[s] = {}
        for sc in STANCE_CONFIG:
            cnt = len(subset[subset["stance_group"] == sc["key"]])
            stage_data[s][sc["key"]] = round(cnt / total * 100, 1) if total else 0.0

    x = np.arange(len(STAGE_ORDER))
    series_data = []
    for sc in STANCE_CONFIG:
        series_data.append([stage_data[s][sc["key"]] for s in STAGE_ORDER])

    colors = [sc["color"] for sc in STANCE_CONFIG]
    labels = [sc["name"] for sc in STANCE_CONFIG]

    fig, ax = plt.subplots(figsize=(12, 7.2))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    ax.stackplot(x, series_data, labels=labels, colors=colors, alpha=0.70, edgecolor="white", linewidth=0.6)

    ax.set_xlim(-0.5, len(STAGE_ORDER) - 0.5)
    ax.set_ylim(0, 100)

    ax.set_xticks(x)
    ax.set_xticklabels(stage_labels, fontsize=11, color=TEXT_COLOR)

    ax.yaxis.set_major_locator(ticker.MultipleLocator(20))
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%d%%"))
    ax.tick_params(axis="y", labelsize=12, colors=TEXT_COLOR)

    ax.set_xlabel("事件演化阶段", fontsize=12, color=TEXT_COLOR, labelpad=10)
    ax.set_ylabel("立场占比 / %", fontsize=12, color=TEXT_COLOR, labelpad=10)

    ax.set_title("图5 立场流变：网民态度的阶段演化", fontsize=22, fontweight="bold", color=TEXT_COLOR, pad=15)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E0DDD6")
    ax.spines["bottom"].set_color("#E0DDD6")

    ax.grid(axis="y", color="#E0DDD6", linestyle="--", linewidth=0.6)
    ax.grid(axis="x", visible=False)

    legend = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=4, fontsize=10, frameon=False, handlelength=1.5, handleheight=1.0)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)

    fig.tight_layout()

    out_dir = root / "04_figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fig_05_stance_over_time.png"
    fig.savefig(out_path, dpi=200, facecolor=BG_COLOR, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    print(f"已生成：{out_path}")

    print("\n各阶段数据量：")
    for s in STAGE_ORDER:
        print(f"  {STAGE_MAP[s]}: {len(df[df['event_stage'] == s])} 条")
    print()
    for sc in STANCE_CONFIG:
        vals = [stage_data[s][sc["key"]] for s in STAGE_ORDER]
        print(f"  {sc['name']}: {vals}")


if __name__ == "__main__":
    main()
