"""
《年轮》舆论争议项目 —— Fig 03 Pyecharts 交互式图表
=====================================================

功能特色：
  - 环形图
  - 鼠标悬停时展示真实高赞热评（从 weibo_comments_all_predicted.csv 提取）
  - 赤陶松烟配色

生成文件：
  - figures/fig_03_stance_distribution.html
"""

from pathlib import Path
import json
import pandas as pd

from pyecharts.globals import CurrentConfig
CurrentConfig.ONLINE_HOST = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/"

from pyecharts.charts import Pie
from pyecharts import options as opts
from pyecharts.commons.utils import JsCode

BG_COLOR = "#F5F3EE"
TEXT_COLOR = "#2F2F2F"
FONT = "Microsoft YaHei, Noto Sans SC, sans-serif"

STANCE_COLORS = {
    "支持张碧晨": "#C07858",
    "支持汪苏泷": "#5A7A6A",
    "反感饭圈争议": "#A05050",
    "中立讨论": "#8C8C8C",
    "无法判断": "#8C8C8C",
}

RAW_STANCE_MAP = {
    "support_zhang": "支持张碧晨",
    "support_wang": "支持汪苏泷",
    "neutral": "中立讨论",
    "anti_fanwar": "反感饭圈争议",
    "unclear": "无法判断",
}

STANCE_ORDER = ["支持张碧晨", "支持汪苏泷", "反感饭圈争议", "中立讨论", "无法判断"]

def _fmt_like(n: int) -> str:
    if n >= 10000:
        return f"{n/1000:.1f}k"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)

def _load_data() -> tuple[list[tuple], dict]:
    root = Path(__file__).resolve().parent.parent
    csv_path = root / "weibo_comments_all_predicted_cleaned.csv"
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    stance_counts = df["predicted_stance"].value_counts()
    total = len(df)
    stance_data = []
    for raw in ["support_wang", "support_zhang", "anti_fanwar", "neutral", "unclear"]:
        name = RAW_STANCE_MAP[raw]
        cnt = int(stance_counts.get(raw, 0))
        pct = round(cnt / total * 100, 1)
        stance_data.append((name, cnt, pct))

    stance_comments: dict[str, list[str]] = {}
    for raw_stance, display_name in RAW_STANCE_MAP.items():
        subset = df[df["predicted_stance"] == raw_stance].copy()
        subset = subset.sort_values("like_count", ascending=False)
        seen: set[str] = set()
        top3: list[str] = []
        for _, row in subset.iterrows():
            text = str(row.get("comment_text", "")).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            like = int(row["like_count"]) if pd.notna(row["like_count"]) else 0
            top3.append(f"[点赞 {_fmt_like(like)}] {text}")
            if len(top3) >= 3:
                break
        stance_comments[display_name] = top3

    return stance_data, stance_comments

def _color_js(colors: list) -> JsCode:
    return JsCode(f"function(p){{var c={colors};return c[p.dataIndex];}}")

def _build_tooltip_js(comment_dict: dict) -> str:
    comments_js = json.dumps(comment_dict, ensure_ascii=False)
    comments_js = comments_js.replace('"', "'")

    return (
        "function(p) {"
        "  var name = p.name || p[0].name;"
        "  var value = p.value !== undefined ? p.value : p[0].value;"
        "  var percent = p.percent !== undefined ? p.percent : '';"
        "  var html = '<div style=\"max-width:420px;line-height:1.6;word-break:break-all;white-space:normal\">';"
        "  html += '<b style=\"font-size:14px\">' + name + '</b><br/>';"
        "  html += '<span style=\"color:#666\">数量：' + value + ' 条' + "
        "    (percent ? ' | 占比：' + percent + '%' : '') + '</span>';"
        "  var comments = " + comments_js + ";"
        "  var list = comments[name] || [];"
        "  if (list.length > 0) {"
        "    html += '<hr style=\"margin:6px 0;border:0;border-top:1px solid #ddd\"/>';"
        "    html += '<span style=\"font-size:12px;color:#888\">▎热评</span><br/>';"
        "    for (var i = 0; i < list.length; i++) {"
        "      html += '<span style=\"font-size:12px;word-break:break-all;white-space:normal\">' + list[i] + '</span><br/>';"
        "    }"
        "  }"
        "  html += '</div>';"
        "  return html;"
        "}"
    )

def make_fig03(stance_data: list[tuple], stance_comments: dict) -> Pie:
    names = [n for n, _, _ in stance_data]
    values = [v for _, v, _ in stance_data]
    colors = [STANCE_COLORS[n] for n in names]

    pie = (
        Pie(init_opts=opts.InitOpts(
            bg_color=BG_COLOR, width="1200px", height="800px",
        ))
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="图3 立场分布：原唱与版权叙事的分化",
                pos_left="center", pos_top=10,
                title_textstyle_opts=opts.TextStyleOpts(
                    font_size=22, font_weight="bold",
                    color=TEXT_COLOR, font_family=FONT,
                ),
            ),
            legend_opts=opts.LegendOpts(
                type_="scroll", pos_left="80%", pos_top="middle",
                orient="vertical", item_gap=15,
                textstyle_opts=opts.TextStyleOpts(
                    font_size=12, color=TEXT_COLOR, font_family=FONT,
                ),
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="item",
                formatter=JsCode(_build_tooltip_js(stance_comments)),
            ),
        )
        .add(
            series_name="立场分布",
            data_pair=list(zip(names, values)),
            radius=["38%", "62%"],
            center=["35%", "55%"],
            label_opts=opts.LabelOpts(
                position="outside",
                formatter=JsCode("function(p){return p.name+'\\n'+p.percent+'%';}"),
                font_size=12, color=TEXT_COLOR, font_family=FONT,
            ),
            itemstyle_opts=opts.ItemStyleOpts(
                color=_color_js(colors),
                border_color=BG_COLOR, border_width=2,
            ),
        )
    )
    return pie

def main() -> None:
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("正在从 weibo_comments_all_predicted.csv 提取真实高赞热评…")
    stance_data, stance_comments = _load_data()
    for cat, comments in stance_comments.items():
        print(f"  [{cat}] 取到 {len(comments)} 条")

    p03 = out_dir / "fig_03_stance_distribution.html"
    make_fig03(stance_data, stance_comments).render(str(p03))
    print(f"\n[Fig 03] 已生成：{p03}")

    print("\n全部交互式图表生成完毕！热评数据来自 weibo_comments_all_predicted.csv。")

if __name__ == "__main__":
    main()
