from pathlib import Path
import pandas as pd
from pyecharts.globals import CurrentConfig
CurrentConfig.ONLINE_HOST = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/"
from pyecharts.charts import Line
from pyecharts import options as opts

BG_COLOR = "#F5F3EE"
TEXT_COLOR = "#2F2F2F"
FONT = "Microsoft YaHei, Noto Sans SC, sans-serif"

STAGE_MAP = {
    "outbreak": "争议发酵",
    "response": "双方回应",
    "debate": "版权争论",
    "cooldown": "冷却期",
}
STAGE_ORDER = ["outbreak", "response", "debate", "cooldown"]

STANCE_CONFIG = [
    {"name": "支持张碧晨", "key": "support_zhang", "color": "#C07858"},
    {"name": "支持汪苏泷", "key": "support_wang", "color": "#5A7A6A"},
    {"name": "反感饭圈争议", "key": "anti_fanwar", "color": "#A05050"},
    {"name": "中立讨论/无法判断", "key": "neutral_unclear", "color": "#8C8C8C"},
]

def main():
    root = Path(__file__).resolve().parent.parent.parent.parent
    csv_path = root / "02_data" / "B_data" / "cleaned" / "weibo_comments_clean.csv"
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    df["stance_group"] = df["stance"].apply(
        lambda x: "neutral_unclear" if x in ("neutral", "unclear") else x
    )

    stage_labels = [STAGE_MAP[s] for s in STAGE_ORDER]
    series_data = []
    for sc in STANCE_CONFIG:
        vals = []
        for s in STAGE_ORDER:
            subset = df[df["event_stage"] == s]
            total = len(subset)
            cnt = len(subset[subset["stance_group"] == sc["key"]])
            vals.append(round(cnt / total * 100, 1) if total else 0.0)
        series_data.append({"name": sc["name"], "key": sc["key"], "color": sc["color"], "data": vals})

    line = Line(
        init_opts=opts.InitOpts(
            bg_color=BG_COLOR, width="1200px", height="720px",
        )
    )

    line.add_xaxis(stage_labels)

    for sd in reversed(series_data):
        line.add_yaxis(
            series_name=sd["name"],
            y_axis=sd["data"],
            stack="total",
            areastyle_opts=opts.AreaStyleOpts(
                opacity=0.7,
                color=sd["color"],
            ),
            linestyle_opts=opts.LineStyleOpts(
                color=sd["color"],
                width=1,
            ),
            label_opts=opts.LabelOpts(
                font_family=FONT, font_size=11, color=TEXT_COLOR,
                formatter="{c}%",
            ),
        )

    line.set_global_opts(
        title_opts=opts.TitleOpts(
            title="图5 立场流变：网民态度的阶段演化",
            pos_left="center",
            title_textstyle_opts=opts.TextStyleOpts(
                font_size=22, font_weight="bold",
                color=TEXT_COLOR, font_family=FONT,
            ),
        ),
        tooltip_opts=opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="cross",
            formatter="{b}<br/>" + "<br/>".join(
                ["{a0}: {c0}%", "{a1}: {c1}%", "{a2}: {c2}%", "{a3}: {c3}%"]
            ),
        ),
        legend_opts=opts.LegendOpts(
            pos_bottom="5%",
            item_gap=20,
            textstyle_opts=opts.TextStyleOpts(
                font_size=12, color=TEXT_COLOR, font_family=FONT,
            ),
        ),
        xaxis_opts=opts.AxisOpts(
            type_="category",
            boundary_gap=False,
            axislabel_opts=opts.LabelOpts(
                font_size=11, color=TEXT_COLOR, font_family=FONT,
            ),
            axisline_opts=opts.AxisLineOpts(
                linestyle_opts=opts.LineStyleOpts(color="#E0DDD6"),
            ),
            splitline_opts=opts.SplitLineOpts(is_show=False),
        ),
        yaxis_opts=opts.AxisOpts(
            type_="value",
            max_=100,
            axislabel_opts=opts.LabelOpts(
                font_size=12, color=TEXT_COLOR, font_family=FONT,
                formatter="{value}%",
            ),
            axisline_opts=opts.AxisLineOpts(
                linestyle_opts=opts.LineStyleOpts(color="#E0DDD6"),
            ),
            splitline_opts=opts.SplitLineOpts(
                is_show=True,
                linestyle_opts=opts.LineStyleOpts(
                    color="#E0DDD6", type_="dashed", width=0.6,
                ),
            ),
        ),
    )

    out_dir = root / "04_figures" / "B_figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fig_05_stance_over_time.html"
    line.render(str(out_path))
    print(f"已生成：{out_path}")

    print("\n各阶段数据量：")
    for s in STAGE_ORDER:
        print(f"  {STAGE_MAP[s]}: {len(df[df['event_stage'] == s])} 条")
    print()
    for sd in series_data:
        print(f"  {sd['name']}: {sd['data']}")

if __name__ == "__main__":
    main()
