"""
《年轮》舆论争议项目 —— 支持张碧晨 vs 支持汪苏泷 数据量对比图
===============================================================

生成文件：
  - figures/fig_stance_comparison.html
数据来源：weibo_comments_all_predicted.csv

配色：赤陶 #C07858（张碧晨） vs 松烟 #5A7A6A（汪苏泷）
"""

from pathlib import Path

import pandas as pd

from pyecharts.globals import CurrentConfig
CurrentConfig.ONLINE_HOST = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/"

from pyecharts.charts import Bar
from pyecharts import options as opts
from pyecharts.commons.utils import JsCode


BG_COLOR = "#F5F3EE"
TEXT_COLOR = "#2F2F2F"
FONT = "Microsoft YaHei, Noto Sans SC, sans-serif"

ZHANG_COLOR = "#C07858"
WANG_COLOR = "#5A7A6A"

# Load data
root = Path(__file__).resolve().parent.parent
csv_path = root / "weibo_comments_all_predicted_cleaned.csv"
df = pd.read_csv(csv_path, encoding="utf-8-sig")

total = len(df)
zhang_cnt = int((df["predicted_stance"] == "support_zhang").sum())
wang_cnt = int((df["predicted_stance"] == "support_wang").sum())
zhang_pct = round(zhang_cnt / total * 100, 1)
wang_pct = round(wang_cnt / total * 100, 1)

DATA = [
    ("支持张碧晨", zhang_cnt, zhang_pct, ZHANG_COLOR),
    ("支持汪苏泷", wang_cnt, wang_pct, WANG_COLOR),
]

labels = [d[0] for d in DATA]
values = [d[1] for d in DATA]
pcts = [d[2] for d in DATA]
colors = [d[3] for d in DATA]

diff = values[1] - values[0]
diff_pct = round(pcts[1] - pcts[0], 1)
pct_map_js = str({l: p for l, p in zip(labels, pcts)})

bar = (
    Bar(init_opts=opts.InitOpts(
        bg_color=BG_COLOR,
        width="1000px",
        height="500px",
    ))
    .set_global_opts(
        title_opts=opts.TitleOpts(
            title="支持张碧晨 vs 支持汪苏泷 数据量对比",
            subtitle=f"汪苏泷比张碧晨多 {diff} 条（{diff_pct} 个百分点）",
            pos_left="center",
            pos_top=10,
            title_textstyle_opts=opts.TextStyleOpts(
                font_size=22, font_weight="bold",
                color=TEXT_COLOR, font_family=FONT,
            ),
            subtitle_textstyle_opts=opts.TextStyleOpts(
                font_size=14, color="#666666", font_family=FONT,
            ),
        ),
        legend_opts=opts.LegendOpts(
            pos_top="18%", pos_left="center", orient="horizontal",
            textstyle_opts=opts.TextStyleOpts(
                font_size=12, color=TEXT_COLOR, font_family=FONT,
            ),
        ),
        tooltip_opts=opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="shadow",
            formatter=JsCode(
                "function(p){var m=" + pct_map_js +
                ";return p[0].name+'<br/>数量：'+p[0].value+' 条<br/>占比：'+m[p[0].name]+'%';}"
            ),
        ),
        xaxis_opts=opts.AxisOpts(
            name="数量 / 条",
            name_textstyle_opts=opts.TextStyleOpts(
                font_size=12, color=TEXT_COLOR, font_family=FONT,
            ),
            axislabel_opts=opts.LabelOpts(
                font_size=12, color=TEXT_COLOR, font_family=FONT,
            ),
            splitline_opts=opts.SplitLineOpts(is_show=True),
        ),
        yaxis_opts=opts.AxisOpts(
            name="立场",
            name_textstyle_opts=opts.TextStyleOpts(
                font_size=12, color=TEXT_COLOR, font_family=FONT,
            ),
            axislabel_opts=opts.LabelOpts(
                font_size=13, color=TEXT_COLOR, font_family=FONT, font_weight="bold",
            ),
        ),
    )
    .add_xaxis(labels)
    .add_yaxis(
        series_name="数据量",
        y_axis=values,
        category_gap="60%",
        itemstyle_opts=opts.ItemStyleOpts(
            color=JsCode("function(p){var c=" + str(colors) + ";return c[p.dataIndex];}"),
            border_color=BG_COLOR, border_width=1,

        ),
        label_opts=opts.LabelOpts(
            position="right",
            formatter=JsCode(
                "function(p){var m=" + pct_map_js +
                ";return p.value+' 条（'+m[p.name]+'%）';}"
            ),
            font_size=13, color=TEXT_COLOR, font_family=FONT, font_weight="bold",
        ),
        tooltip_opts=opts.TooltipOpts(
            formatter=JsCode(
                "function(p){var m=" + pct_map_js +
                ";return p.name+'<br/>数量：'+p.value+' 条<br/>占比：'+m[p.name]+'%';}"
            ),
        ),
    )
    .reversal_axis()
)

# 输出
out_dir = root / "figures"
out_dir.mkdir(parents=True, exist_ok=True)
p = out_dir / "fig_stance_comparison.html"
bar.render(str(p))
print(f"[对比图] 已生成：{p}")
print(f"  支持张碧晨: {zhang_cnt} 条 ({zhang_pct}%)")
print(f"  支持汪苏泷: {wang_cnt} 条 ({wang_pct}%)")
print(f"  差值: {diff} 条 ({diff_pct} 个百分点)")
