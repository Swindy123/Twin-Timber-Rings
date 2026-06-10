from __future__ import annotations

"""
C 组：传播链 / 网络分析（《年轮》争议微博）

数据源：
  - 网络边/节点：output_recrawl（multihop 优先）
  - 核心源：output/top_source_posts.csv
"""

import argparse
import html as html_lib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(r"D:\nl")
OUTPUT_DIR = BASE_DIR / "output"
RECRAWL_DIR = BASE_DIR / "output_recrawl"
E_DATA_DIR = BASE_DIR / "E_data"
FINAL_DIR = Path(__file__).resolve().parent
FIG_DIR = FINAL_DIR / "figures"
SOURCE_PATH = OUTPUT_DIR / "top_source_posts.csv"

# 传播网络（API 重爬真实转发链）
# 多层边表优先（若已跑 recrawl_weibo_reposts_multihop.py）；否则回退一层 api
EDGES_MULTIHOP_PATH = RECRAWL_DIR / "repost_edges_multihop.csv"
NODES_MULTIHOP_PATH = RECRAWL_DIR / "repost_nodes_multihop.csv"
CLEAN_MULTIHOP_PATH = RECRAWL_DIR / "weibo_reposts_api_clean_multihop.csv"
LABELED_MULTIHOP_PATH = RECRAWL_DIR / "weibo_reposts_api_clean_multihop_labeled.csv"

EDGE_PATH = EDGES_MULTIHOP_PATH if EDGES_MULTIHOP_PATH.exists() else RECRAWL_DIR / "repost_edges_api.csv"
NODE_PATH = NODES_MULTIHOP_PATH if NODES_MULTIHOP_PATH.exists() else RECRAWL_DIR / "repost_nodes_api.csv"
REPOST_CLEAN_PATH = (
    LABELED_MULTIHOP_PATH
    if LABELED_MULTIHOP_PATH.exists()
    else CLEAN_MULTIHOP_PATH
    if CLEAN_MULTIHOP_PATH.exists()
    else RECRAWL_DIR / "weibo_reposts_api_clean.csv"
)
RAW_PATH = RECRAWL_DIR / "weibo_reposts_api_raw.csv"
TIME_WINDOW_PATH = RECRAWL_DIR / "recrawl_time_window_summary.csv"

CHAIN_SUMMARY_PATH = OUTPUT_DIR / "repost_chain_summary.md"
EDATA_REPOST_PATH = E_DATA_DIR / "weibo_reposts_clean.csv"
OUTPUT_REPOST_PATH = OUTPUT_DIR / "weibo_reposts_clean.csv"

REPORT_PATH = FINAL_DIR / "repost_network_analysis.md"
DATA_CHECK_PATH = FINAL_DIR / "data_check_repost_network.md"


# 方案七 · 赤陶松烟（见 风格规范.md）
PALETTE = {
    "zhang": "#C07858",
    "zhang_dark": "#9A5A40",
    "zhang_light": "#D8B0A0",
    "wang": "#5A7A6A",
    "wang_dark": "#3A5A4A",
    "wang_light": "#90B0A0",
    "mixed": "#9A8A7A",
    "neutral": "#8C8C8C",
    "conflict": "#A05050",
    "memory": "#D4B898",
    "legal": "#6F7F9D",
    "mocking": "#B08070",
    "background": "#F5F3EE",
    "text": "#2B2926",
    "panel": "#FFFDF8",
    "muted": "#666666",
    "grid": "#D7CFC4",
}

STANCE_COLORS = {
    "support_zhang": PALETTE["zhang"],
    "support_wang": PALETTE["wang"],
    "neutral": PALETTE["neutral"],
    "unclear": PALETTE["neutral"],
    "anti_fanwar": PALETTE["conflict"],
    "legal_discussion": PALETTE["legal"],
}

STANCE_LABELS_CN = {
    "support_zhang": "支持张碧晨",
    "support_wang": "支持汪苏泷",
    "neutral": "中立讨论",
    "unclear": "无法判断",
    "anti_fanwar": "反感饭圈争议",
    "legal_discussion": "版权法律讨论",
}

BUCKET_LABELS = {
    "hot_repost": "热门转发",
    "source_day": "源帖当天",
    "plus_1_day": "+1 天补足",
    "plus_3_day": "+3 天补足",
    "plus_7_day": "+7 天补足",
    "unknown": "未标注",
}

# 采样窗口边色：在赤陶/松烟体系内区分时间层，不与立场色混淆
BUCKET_COLORS = {
    "hot_repost": PALETTE["conflict"],
    "source_day": PALETTE["zhang"],
    "plus_1_day": PALETTE["wang"],
    "plus_3_day": PALETTE["legal"],
    "plus_7_day": PALETTE["memory"],
    "unknown": PALETTE["neutral"],
}

# multihop 爬取层级边色（与采样窗口色区分，用于网络图）
HOP_COLORS = {1: PALETTE["zhang"], 2: PALETTE["wang"], 3: PALETTE["memory"]}
HOP_LABELS_CN = {
    1: "一层·核心源→直接转发",
    2: "二层·热门种子→转发",
    3: "三层·高互动帖→转发",
}

TYPE_LABELS = {
    "media": "媒体号",
    "fan_account": "粉丝号",
    "marketing_account": "营销号",
    "marketing": "营销号",
    "music_account": "音乐相关号",
    "legal_account": "法律相关号",
    "ordinary_user": "普通用户",
    "unknown": "未识别",
}

TYPE_COLORS = {
    "media": PALETTE["neutral"],
    "fan_account": PALETTE["zhang"],
    "marketing_account": PALETTE["conflict"],
    "marketing": PALETTE["conflict"],
    "music_account": PALETTE["wang"],
    "legal_account": PALETTE["legal"],
    "ordinary_user": PALETTE["mixed"],
    "unknown": PALETTE["neutral"],
}


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def read_csv_auto(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str).fillna("")
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str).fillna("")


def clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def to_num(value: Any) -> float:
    return float(pd.to_numeric(value, errors="coerce") or 0)


def setup_matplotlib():
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    preferred = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "Arial Unicode MS"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for font in preferred:
        if font in installed:
            plt.rcParams["font.sans-serif"] = [font]
            break
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def classify_user(name: str, text: str = "") -> str:
    blob = f"{name} {text}"
    if re.search(r"新闻|娱乐|日报|观察|财经|视频|传媒|新浪|梨视频|晚报|快报|后浪|热点", blob):
        return "media"
    if re.search(r"工作室|后援会|粉丝|超话|站子|个站|应援|Diamond|泷", blob):
        return "fan_account"
    if re.search(r"吃瓜|爆料|八卦|娱记|扒皮|饭圈|营销|明星娱乐|企划", blob):
        return "marketing_account"
    if re.search(r"律师|法律|著作权|版权|合约", blob):
        return "legal_account"
    if re.search(r"音乐|歌手|Radio|Studio", blob):
        return "music_account"
    return "ordinary_user"


def label_stance(text: str, user_name: str = "") -> dict[str, str | float]:
    """立场与话语框架；仅提及姓名不直接判支持。"""
    blob = f"{user_name} {text}".strip()
    matched: list[str] = []

    def hit(pattern: str) -> bool:
        if re.search(pattern, blob, flags=re.I):
            matched.append(pattern)
            return True
        return False

    anti = any(hit(p) for p in [r"别吵", r"饭圈真烦", r"双输", r"别互撕", r"别引战", r"乌烟瘴气"])
    zhang_support = sum(
        1
        for p in [r"唯一原唱", r"年轮唯一原唱", r"支持张碧晨", r"张碧晨.*原唱", r"张碧晨女士"]
        if hit(p)
    )
    wang_support = sum(
        1
        for p in [r"支持汪苏泷", r"汪苏泷.*创作", r"词曲作者", r"收回.*授权", r"汪苏泷Studio", r"尊重创作者"]
        if hit(p)
    )
    legal_only = any(hit(p) for p in [r"版权", r"授权", r"著作权", r"合约", r"法律", r"权利"]) and not zhang_support and not wang_support
    zhang_mention = bool(re.search(r"张碧晨", blob)) and zhang_support == 0
    wang_mention = bool(re.search(r"汪苏泷", blob)) and wang_support == 0

    frame = "platform_meta"
    if anti:
        frame = "fan_conflict"
    elif legal_only:
        frame = "legal_discussion"
    elif zhang_support or wang_support:
        frame = "original_singer" if re.search(r"原唱", blob) else "creator_identity"
    elif any(hit(p) for p in [r"回忆", r"青春", r"感动", r"情怀", r"十年"]):
        frame = "memory_emotion"

    stance = "unclear"
    confidence = 0.35
    if anti:
        stance = "anti_fanwar"
        confidence = 0.82
    elif legal_only:
        stance = "neutral"
        frame = "legal_discussion"
        confidence = 0.75
    elif zhang_support > 0 and wang_support > 0:
        stance = "unclear"
        frame = "fan_conflict"
        confidence = 0.55
    elif zhang_support >= 1 and zhang_support > wang_support:
        stance = "support_zhang"
        confidence = min(0.95, 0.55 + 0.15 * zhang_support)
    elif wang_support >= 1 and wang_support > zhang_support:
        stance = "support_wang"
        confidence = min(0.95, 0.55 + 0.15 * wang_support)
    elif zhang_mention or wang_mention:
        stance = "unclear"
        confidence = 0.4
    else:
        stance = "neutral"
        confidence = 0.5

    return {
        "stance": stance,
        "frame": frame,
        "stance_confidence": round(confidence, 3),
        "matched_keywords": "|".join(matched[:8]),
    }


def infer_stance(name: str, text: str = "") -> str:
    return label_stance(text, name)["stance"]


def infer_narrative(name: str, text: str = "") -> str:
    lab = label_stance(text, name)
    stance = lab["stance"]
    if lab.get("frame") == "legal_discussion":
        return "legal"
    if stance == "support_zhang":
        return "zhang"
    if stance == "support_wang":
        return "wang"
    if stance == "anti_fanwar":
        return "conflict"
    return "mixed"


def stance_node_color(stance: str, frame: str = "") -> str:
    if frame == "legal_discussion" and stance in ("neutral", "unclear"):
        return STANCE_COLORS["legal_discussion"]
    if stance in ("neutral", "unclear"):
        return STANCE_COLORS["neutral"]
    return STANCE_COLORS.get(stance, PALETTE["neutral"])


def stance_label_cn(stance: str, frame: str = "") -> str:
    base = STANCE_LABELS_CN.get(stance, stance)
    if frame == "legal_discussion" and stance in ("neutral", "unclear"):
        return f"{base}（版权法律讨论）"
    return base


def dominant_bucket_for_user(edges_df: pd.DataFrame, user: str, role: str = "target") -> str:
    key = "_target" if role == "target" else "_source"
    sub = edges_df[edges_df[key] == user]
    if sub.empty:
        return "unknown"
    return sub["_bucket"].value_counts().index[0]


def stance_color(stance: str, frame: str = "") -> str:
    if frame == "legal_discussion" and stance in ("neutral", "unclear"):
        return STANCE_COLORS["legal_discussion"]
    return STANCE_COLORS.get(stance, PALETTE["neutral"])


def narrative_color(value: str, dark: bool = False) -> str:
    if value == "zhang":
        return PALETTE["zhang_dark"] if dark else PALETTE["zhang"]
    if value == "wang":
        return PALETTE["wang_dark"] if dark else PALETTE["wang"]
    if value == "legal":
        return PALETTE["legal"]
    if value == "conflict":
        return PALETTE["conflict"]
    return PALETTE["mixed"]


def narrative_label(value: str) -> str:
    return {
        "zhang": "张碧晨/原唱叙事",
        "wang": "汪苏泷/版权叙事",
        "legal": "版权法律讨论",
        "conflict": "冲突/营销扩散",
        "mixed": "混合/中立传播",
    }.get(value, "混合/中立传播")


def account_type_label(value: str) -> str:
    return TYPE_LABELS.get(str(value), str(value) if value else "未识别")


def account_type_color(value: str) -> str:
    return TYPE_COLORS.get(str(value), PALETTE["neutral"])


def bucket_color(bucket: str) -> str:
    return BUCKET_COLORS.get(bucket or "unknown", BUCKET_COLORS["unknown"])


def top_items(metric: dict[str, float], n: int = 10) -> list[tuple[str, float]]:
    return sorted(metric.items(), key=lambda x: (-x[1], x[0]))[:n]


def load_supplemental_reposts() -> pd.DataFrame:
    """优先 E_data 清洗转发表，用于补充用户文本（不参与构网）。"""
    for path in (EDATA_REPOST_PATH, OUTPUT_REPOST_PATH):
        if path.exists():
            return read_csv_auto(path)
    return pd.DataFrame()


def inspect_data(data: dict[str, Any]) -> dict[str, Any]:
    """数据读取与检查（任务一）。"""
    import networkx as nx

    edges = data["edges"]
    nodes = data["nodes"]
    sources = data["sources"]
    graph: nx.DiGraph = data["graph"]

    edge_dup = 0
    if not edges.empty:
        edge_dup = int(edges.duplicated(subset=["_source", "_target", "_post_id"]).sum())
    node_dup = 0
    user_col = pick_col(nodes, ["user_name", "node_id", "user_id"])
    if user_col and not nodes.empty:
        node_dup = int(nodes[user_col].map(clean).duplicated().sum())

    null_edges = int(edges[["_source", "_target"]].eq("").any(axis=1).sum()) if not edges.empty else 0
    n_components = len(list(nx.weakly_connected_components(graph))) if graph.number_of_nodes() else 0
    suitable = graph.number_of_nodes() > 0 and graph.number_of_edges() > 0

    files_meta = []
    loaded = {
        "repost_edges_api": data["edges"],
        "repost_nodes_api": data["nodes"],
        "weibo_reposts_api_clean": data["reposts"],
        "top_source_posts": data["sources"],
        "recrawl_time_window_summary": data["time_summary"],
    }
    for label, path in [
        ("repost_edges_api", EDGE_PATH),
        ("repost_nodes_api", NODE_PATH),
        ("weibo_reposts_api_clean", REPOST_CLEAN_PATH),
        ("top_source_posts", SOURCE_PATH),
        ("recrawl_time_window_summary", TIME_WINDOW_PATH),
        ("weibo_reposts_api_raw", RAW_PATH),
    ]:
        if not path.exists():
            continue
        if label == "weibo_reposts_api_raw":
            files_meta.append(
                {
                    "label": label,
                    "path": str(path),
                    "rows": data.get("raw_count", 0),
                    "columns": ["raw_json 等"],
                    "missing_cells": 0,
                }
            )
            continue
        df = loaded.get(label)
        if df is None:
            df = read_csv_auto(path)
        files_meta.append(
            {
                "label": label,
                "path": str(path),
                "rows": len(df),
                "columns": list(df.columns),
                "missing_cells": int(df.isna().sum().sum()) if not df.empty else 0,
            }
        )
    sup = load_supplemental_reposts()
    if not sup.empty:
        files_meta.append(
            {
                "label": "weibo_reposts_clean_supplement",
                "path": str(EDATA_REPOST_PATH if EDATA_REPOST_PATH.exists() else OUTPUT_REPOST_PATH),
                "rows": len(sup),
                "columns": list(sup.columns),
                "missing_cells": int(sup.isna().sum().sum()),
            }
        )

    return {
        "files": files_meta,
        "edge_dup": edge_dup,
        "node_dup": node_dup,
        "null_edge_rows": null_edges,
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "n_sources": len(sources),
        "n_components": n_components,
        "suitable_for_network": suitable,
        "largest_component": max((len(c) for c in nx.weakly_connected_components(graph)), default=0) if suitable else 0,
        "original_edge_rows": data.get("original_edge_rows", len(edges)),
        "outside_event_window_rows": data.get("outside_event_window_rows", 0),
        "event_window": data.get("event_window", ""),
    }


def print_data_check(check: dict[str, Any]) -> None:
    print("\n=== 数据检查结果 ===")
    for f in check["files"]:
        print(f"- {f['label']}: {f['rows']} 行, {len(f['columns'])} 列")
        print(f"  路径: {f['path']}")
    print(f"- 网络节点: {check['n_nodes']}, 边: {check['n_edges']}, 核心源: {check['n_sources']}")
    if check.get("outside_event_window_rows"):
        print(f"- 后续长尾转发: {check.get('event_window')} 窗口外边 {check['outside_event_window_rows']} / {check.get('original_edge_rows')}；当前保留参与分析")
    print(f"- 重复边(同源同目标同帖): {check['edge_dup']}, 重复节点名: {check['node_dup']}")
    print(f"- 弱连通分量: {check['n_components']}, 最大分量: {check['largest_component']}")
    print(f"- 适合画网络图: {'是' if check['suitable_for_network'] else '否'}\n")


def write_data_check_md(check: dict[str, Any]) -> None:
    lines = ["# 传播链数据检查\n"]
    lines.append("|文件|行数|列数|路径|\n|---|---:|---:|---|\n")
    for f in check["files"]:
        lines.append(f"|{f['label']}|{f['rows']}|{len(f['columns'])}|`{f['path']}`|\n")
    lines.append(
        f"\n- 网络节点 **{check['n_nodes']}**，边 **{check['n_edges']}**，核心源 **{check['n_sources']}**\n"
        f"- 事件窗口：**{check.get('event_window', '')}**；窗口外边：**{check.get('outside_event_window_rows', 0)} / {check.get('original_edge_rows', check['n_edges'])}**（作为后续长尾转发保留参与分析）\n"
        f"- 重复边 {check['edge_dup']}，重复节点 {check['node_dup']}\n"
        f"- 弱连通分量 {check['n_components']}，最大分量 {check['largest_component']}\n"
        f"- 适合网络可视化：**{'是' if check['suitable_for_network'] else '否'}**\n"
    )
    DATA_CHECK_PATH.write_text("".join(lines), encoding="utf-8")


def md_table(rows: list[dict[str, Any]], columns: list[str], max_rows: int = 10) -> str:
    if not rows:
        return "无可用数据。"
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows[:max_rows]:
        lines.append("|" + "|".join(clean(row.get(c, "")) for c in columns) + "|")
    return "\n".join(lines)


def prepare_data():
    import networkx as nx

    edges = read_csv_auto(EDGE_PATH)
    nodes = read_csv_auto(NODE_PATH)
    reposts = read_csv_auto(REPOST_CLEAN_PATH)
    sources = read_csv_auto(SOURCE_PATH)
    time_summary = read_csv_auto(TIME_WINDOW_PATH) if TIME_WINDOW_PATH.exists() else pd.DataFrame()
    raw_count = sum(1 for _ in RAW_PATH.open("r", encoding="utf-8-sig", errors="ignore")) - 1 if RAW_PATH.exists() else 0

    required = ["source_user", "target_user", "source_post_id", "repost_time", "sampling_bucket"]
    for col in required:
        if col not in edges.columns:
            edges[col] = ""

    edges["_source"] = edges["source_user"].map(clean)
    edges["_target"] = edges["target_user"].map(clean)
    edges["_post_id"] = edges["source_post_id"].map(clean)
    if {"repost_id", "source_author", "repost_user_name"}.issubset(reposts.columns):
        chain_cols = ["repost_id", "source_author", "repost_user_name"]
        chain_map = reposts[chain_cols].drop_duplicates("repost_id").copy()
        chain_map["_chain_source"] = chain_map["source_author"].map(clean)
        chain_map["_chain_target"] = chain_map["repost_user_name"].map(clean)
        edges = edges.merge(
            chain_map[["repost_id", "_chain_source", "_chain_target"]],
            on="repost_id",
            how="left",
        )
        chain_source_ok = edges["_chain_source"].fillna("").ne("")
        chain_target_ok = edges["_chain_target"].fillna("").ne("")
        edges.loc[chain_source_ok, "_source"] = edges.loc[chain_source_ok, "_chain_source"]
        edges.loc[chain_target_ok, "_target"] = edges.loc[chain_target_ok, "_chain_target"]
        edges["_chain_edge_mode"] = "source_author_to_repost_user"
    else:
        edges["_chain_edge_mode"] = "edge_csv_source_to_target"
    if "sampling_bucket" in edges.columns:
        edges["_bucket"] = edges["sampling_bucket"].map(clean).replace("", "unknown")
    else:
        edges["_bucket"] = "unknown"
    edges["_event_time"] = pd.to_datetime(edges["repost_time"], errors="coerce")
    original_edge_rows = len(edges)
    event_window_start = pd.Timestamp("2025-07-20 00:00:00")
    event_window_end = pd.Timestamp("2025-07-31 23:59:59")
    in_event_window = edges["_event_time"].between(event_window_start, event_window_end, inclusive="both")
    outside_event_window_rows = int((~in_event_window).sum())
    edges["_in_event_window"] = in_event_window
    if "crawl_hop" in edges.columns:
        edges["_hop"] = edges["crawl_hop"].map(clean)
    else:
        edges["_hop"] = "1"
    edges = edges[(edges["_source"] != "") & (edges["_target"] != "")].copy()

    if "sampling_bucket" not in reposts.columns:
        reposts["sampling_bucket"] = "unknown"
    text_by_user: dict[str, str] = {}
    user_type: dict[str, str] = {}
    label_by_user: dict[str, dict[str, Any]] = {}

    def absorb_repost_rows(frame: pd.DataFrame) -> None:
        name_col = pick_col(frame, ["repost_user_name", "repost_user", "target_user", "user_name"])
        text_col = pick_col(frame, ["repost_text_clean", "repost_text", "text"])
        stance_col = pick_col(frame, ["stance_llm", "predicted_stance", "stance_b2_rule", "stance", "new_stance"])
        frame_col = pick_col(frame, ["frame_b2_rule", "frame"])
        conf_col = pick_col(frame, ["stance_llm_confidence", "rule_confidence", "stance_confidence", "confidence"])
        if not name_col:
            return
        for _, row in frame.iterrows():
            name = clean(row.get(name_col, ""))
            text = clean(row.get(text_col, "")) if text_col else ""
            if name and text and (name not in text_by_user or len(text) > len(text_by_user.get(name, ""))):
                text_by_user[name] = text
            if name:
                user_type.setdefault(name, classify_user(name, text))
                stance_value = clean(row.get(stance_col, "")) if stance_col else ""
                frame_value = clean(row.get(frame_col, "")) if frame_col else ""
                if stance_value in STANCE_LABELS_CN:
                    label_by_user.setdefault(
                        name,
                        {
                            "stance": stance_value,
                            "frame": frame_value or "platform_meta",
                            "stance_confidence": to_num(row.get(conf_col, 0)) if conf_col else 0,
                            "matched_keywords": clean(row.get("matched_rule_groups", row.get("matched_keywords", ""))),
                        },
                    )

    absorb_repost_rows(reposts)
    supplemental = load_supplemental_reposts()
    if not supplemental.empty:
        absorb_repost_rows(supplemental)

    type_col = pick_col(nodes, ["author_type", "node_type", "user_type", "verified_type"])
    for _, row in nodes.iterrows():
        name = clean(row.get("user_name", row.get("node_id", "")))
        if not name:
            continue
        if type_col and clean(row.get(type_col, "")):
            user_type.setdefault(name, clean(row[type_col]))
        else:
            user_type.setdefault(name, classify_user(name, text_by_user.get(name, "")))

    for _, row in sources.iterrows():
        name = clean(row.get("source_author", row.get("author_name", "")))
        if name:
            user_type.setdefault(name, classify_user(name))

    graph = nx.DiGraph()
    for _, row in edges.iterrows():
        u, v = row["_source"], row["_target"]
        graph.add_node(u)
        graph.add_node(v)
        user_type.setdefault(u, classify_user(u, text_by_user.get(u, "")))
        user_type.setdefault(v, classify_user(v, text_by_user.get(v, "")))
        if graph.has_edge(u, v):
            graph[u][v]["weight"] += 1
        else:
            graph.add_edge(u, v, weight=1)

    n_nodes = graph.number_of_nodes()
    pagerank = nx.pagerank(graph, weight="weight") if n_nodes else {}
    degree = dict(graph.degree(weight="weight"))
    indegree = dict(graph.in_degree(weight="weight"))
    outdegree = dict(graph.out_degree(weight="weight"))
    degree_centrality = nx.degree_centrality(graph) if n_nodes > 1 else {n: 0 for n in graph.nodes}

    source_stats = build_source_stats(sources, edges)
    betweenness: dict[str, float] = {}
    if 0 < n_nodes <= 800:
        betweenness = nx.betweenness_centrality(graph, weight="weight")

    chain_summary_excerpt = ""
    if CHAIN_SUMMARY_PATH.exists():
        chain_summary_excerpt = CHAIN_SUMMARY_PATH.read_text(encoding="utf-8", errors="ignore")[:500]

    return {
        "edges": edges,
        "nodes": nodes,
        "reposts": reposts,
        "sources": sources,
        "time_summary": time_summary,
        "raw_count": raw_count,
        "original_edge_rows": original_edge_rows,
        "outside_event_window_rows": outside_event_window_rows,
        "event_window": f"{event_window_start:%Y-%m-%d} 至 {event_window_end:%Y-%m-%d}",
        "graph": graph,
        "pagerank": pagerank,
        "degree": degree,
        "indegree": indegree,
        "outdegree": outdegree,
        "degree_centrality": degree_centrality,
        "betweenness": betweenness,
        "user_type": user_type,
        "text_by_user": text_by_user,
        "label_by_user": label_by_user,
        "source_stats": source_stats,
        "chain_summary_excerpt": chain_summary_excerpt,
    }


def build_source_stats(sources: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in sources.iterrows():
        post_id = clean(row.get("source_post_id", row.get("post_id", "")))
        source_edges = edges[edges["_post_id"] == post_id] if post_id else edges.iloc[0:0]
        involved = set(source_edges["_source"]) | set(source_edges["_target"])
        author = clean(row.get("source_author", row.get("author_name", "")))
        if author:
            involved.add(author)
        repost_count = int(to_num(row.get("repost_count", 0)))
        comment_count = int(to_num(row.get("comment_count", 0)))
        like_count = int(to_num(row.get("like_count", 0)))
        rows.append(
            {
                "source_post_id": post_id,
                "source_author": author,
                "publish_time": clean(row.get("publish_time", "")),
                "direct_reposts_in_edges": int(len(source_edges)),
                "involved_nodes": int(len(involved)),
                "estimated_depth": 1,
                "repost_count": repost_count,
                "comment_count": comment_count,
                "like_count": like_count,
                "interaction_total": repost_count + comment_count + like_count,
                "text": clean(row.get("text", ""))[:90],
            }
        )
    return pd.DataFrame(rows).sort_values(["direct_reposts_in_edges", "interaction_total"], ascending=False)


def style_axes(ax, title: str, xlabel: str | None = None, ylabel: str | None = None):
    ax.set_title(title, fontsize=15, fontweight="bold", color=PALETTE["text"], pad=14)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11, color=PALETTE["text"])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11, color=PALETTE["text"])
    ax.set_facecolor(PALETTE["background"])
    ax.grid(True, color="#D8D1C8", linestyle="--", linewidth=0.7, alpha=0.55)
    ax.tick_params(colors=PALETTE["text"], labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#CFC7BD")
        spine.set_linewidth(0.8)


def add_note(fig, note: str):
    fig.text(0.012, 0.012, note, ha="left", va="bottom", fontsize=8.5, color="#666666")


def write_top_nodes_barh(path: Path, df: pd.DataFrame):
    """任务版图：横向柱状 Top15（PageRank）。"""
    plt = setup_matplotlib()
    plot_df = df.head(15).iloc[::-1].copy()
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=180)
    fig.patch.set_facecolor(PALETTE["background"])
    colors = [account_type_color(t) for t in plot_df["user_type"]]
    ax.barh(range(len(plot_df)), plot_df["pagerank"], color=colors, alpha=0.9, height=0.72)
    ax.set_yticks(range(len(plot_df)))
    ax.set_yticklabels([str(x)[:22] for x in plot_df["node"]])
    style_axes(ax, "图 06 关键传播节点：PageRank Top15", "PageRank", "微博账号")
    for i, (_, row) in enumerate(plot_df.iterrows()):
        ax.text(row["pagerank"], i, f"  度{int(row['degree'])}", va="center", fontsize=8, color=PALETTE["text"])
    add_note(fig, "注：完整网络指标基于全部节点与边；本图展示 Top15。颜色=账号类型（规则推断）。")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def write_source_posts_bars(path: Path, source_stats: pd.DataFrame):
    """任务版图：核心源微博采集边数与平台互动量对比。"""
    import numpy as np

    plt = setup_matplotlib()
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=180)
    fig.patch.set_facecolor(PALETTE["background"])
    if source_stats.empty:
        style_axes(ax, "图 07 核心源微博：传播规模与互动量", "指标", "核心源")
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return
    plot_df = source_stats.head(12).iloc[::-1].copy()
    y = np.arange(len(plot_df))
    h = 0.36
    ax.barh(y - h / 2, plot_df["direct_reposts_in_edges"], height=h, color=PALETTE["wang"], alpha=0.85, label="采集转发边数")
    max_inter = plot_df["interaction_total"].max() or 1
    scale = (plot_df["direct_reposts_in_edges"].max() or 1) / max_inter * 0.85
    scaled = plot_df["interaction_total"] * scale
    ax.barh(y + h / 2, scaled, height=h, color=PALETTE["zhang"], alpha=0.75, label="转评赞总量（缩放对比）")
    ax.set_yticks(y)
    ax.set_yticklabels([str(a)[:14] for a in plot_df["source_author"]])
    style_axes(ax, "图 07 核心源微博：传播规模与互动量", "数值（橙=互动量缩放，绿=采集边）", "核心源作者")
    ax.legend(loc="lower right", fontsize=9, frameon=True, facecolor="white")
    add_note(fig, "注：纵轴为 top_source_posts 核心源；橙条为平台转评赞总量按采集边最大值缩放，便于同图对比。")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def write_lollipop_top_nodes(path: Path, df: pd.DataFrame):
    from matplotlib.lines import Line2D

    plt = setup_matplotlib()
    plot_df = df.head(15).iloc[::-1].copy()
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=180)
    fig.patch.set_facecolor(PALETTE["background"])
    y = range(len(plot_df))
    colors = [account_type_color(x) for x in plot_df["user_type"]]
    ax.hlines(y, 0, plot_df["pagerank"], color=colors, alpha=0.45, linewidth=3)
    ax.scatter(plot_df["pagerank"], y, s=90 + plot_df["degree"].astype(float) * 16, c=colors, edgecolors="white", linewidths=1.2, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels([str(x)[:22] for x in plot_df["node"]])
    style_axes(ax, "图 08 关键转发节点：PageRank 与连接规模", "PageRank（节点重要性）", "微博账号 / 节点")
    for yi, (_, row) in zip(y, plot_df.iterrows()):
        ax.text(row["pagerank"] * 1.01, yi, f" 度={int(row['degree'])}｜{account_type_label(row['user_type'])}", va="center", fontsize=8.5, color=PALETTE["text"])
    legend_items = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=account_type_color(typ), label=account_type_label(typ), markersize=8)
        for typ in plot_df["user_type"].drop_duplicates()
    ]
    ax.legend(handles=legend_items, loc="lower right", fontsize=9, frameon=True, facecolor="white")
    add_note(fig, "注：圆点大小表示总度数；颜色表示账号类型。数据来源：repost_edges_api.csv、repost_nodes_api.csv。")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def write_source_bubble(path: Path, source_stats: pd.DataFrame):
    import numpy as np
    from matplotlib.lines import Line2D

    plt = setup_matplotlib()
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=180)
    fig.patch.set_facecolor(PALETTE["background"])
    if source_stats.empty:
        style_axes(ax, "图 07 核心源微博：传播规模与互动量", "采集转发边数 / 条", "互动量 / 次")
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return
    plot_df = source_stats.copy().head(20)
    plot_df["narrative"] = plot_df.apply(lambda r: infer_narrative(r.get("source_author", ""), r.get("text", "")), axis=1)
    sizes = 150 + np.sqrt(plot_df["involved_nodes"].astype(float).clip(lower=1)) * 85
    colors = [narrative_color(x) for x in plot_df["narrative"]]
    ax.scatter(plot_df["direct_reposts_in_edges"], plot_df["interaction_total"], s=sizes, c=colors, edgecolors="white", linewidths=1.2, alpha=0.86)
    label_df = plot_df.sort_values(["interaction_total", "direct_reposts_in_edges"], ascending=False).head(8)
    right_offsets = [-18, 0, 18, 36, -36, 54, -54]
    left_offsets = [8, 22, -12, 36, -26]
    r_i = l_i = 0
    for _, row in label_df.iterrows():
        name = str(row["source_author"])[:12]
        if row["direct_reposts_in_edges"] > plot_df["direct_reposts_in_edges"].max() * 0.72:
            offset = (-62, right_offsets[r_i % len(right_offsets)])
            ha = "right"
            r_i += 1
        else:
            offset = (8, left_offsets[l_i % len(left_offsets)])
            ha = "left"
            l_i += 1
        ax.annotate(name, (row["direct_reposts_in_edges"], row["interaction_total"]), xytext=offset, textcoords="offset points", fontsize=8.2, ha=ha, arrowprops=dict(arrowstyle="-", color="#8C8C8C", lw=0.6, alpha=0.7))
    ax.set_xlim(left=-5, right=plot_df["direct_reposts_in_edges"].max() * 1.08)
    style_axes(ax, "图 07 核心源微博：传播规模与互动量", "采集转发边数 / 条", "转评赞互动总量 / 次")
    legend_items = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE["zhang"], label="张碧晨/原唱叙事", markersize=9),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE["wang"], label="汪苏泷/版权叙事", markersize=9),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE["legal"], label="版权法律讨论", markersize=9),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE["mixed"], label="混合/中立传播", markersize=9),
    ]
    ax.legend(handles=legend_items, loc="upper right", fontsize=9, frameon=True, facecolor="white")
    add_note(fig, "注：气泡大小表示涉及节点数；横轴为本次采集到的转发边，不等同于微博平台全量转发。")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def write_account_type_distribution(path: Path, type_node_counts: Counter, type_edge_out: Counter, type_edge_in: Counter):
    import numpy as np

    plt = setup_matplotlib()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6.75), dpi=180, gridspec_kw={"width_ratios": [1, 1.25]})
    fig.patch.set_facecolor(PALETTE["background"])
    labels = list(type_node_counts.keys())
    node_values = [type_node_counts[k] for k in labels]
    colors = [account_type_color(k) for k in labels]
    display_labels = [account_type_label(k) for k in labels]
    wedges, _ = ax1.pie(node_values, colors=colors, startangle=90, wedgeprops=dict(width=0.38, edgecolor="white"))
    ax1.set_title("账号类型节点占比", fontsize=13, fontweight="bold", color=PALETTE["text"])
    ax1.text(0, 0, f"{sum(node_values)}\n节点", ha="center", va="center", fontsize=14, fontweight="bold", color=PALETTE["text"])
    ax1.legend(wedges, display_labels, loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=8, frameon=False)
    x = np.arange(2)
    bottom = np.zeros(2)
    for label, key, color in zip(display_labels, labels, colors):
        vals = np.array([type_edge_out[key], type_edge_in[key]], dtype=float)
        ax2.bar(x, vals, bottom=bottom, color=color, alpha=0.9, label=label)
        bottom += vals
    style_axes(ax2, "图 09 账号类型网络：节点构成与边贡献", "传播贡献类型", "边数量 / 条")
    ax2.set_xticks(x)
    ax2.set_xticklabels(["发出边", "接收边"])
    ax2.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
    add_note(fig, "注：账号类型优先使用清洗数据字段，缺失时按用户名关键词弱规则推断。")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def write_source_type_heatmap(path: Path, heat_df: pd.DataFrame, *, fig_num: str = "10"):
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    plt = setup_matplotlib()
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=180)
    fig.patch.set_facecolor(PALETTE["background"])
    title = f"图 {fig_num} 传播结构：核心源微博与账号类型扩散矩阵"
    if heat_df.empty:
        style_axes(ax, title, "账号类型", "核心源微博")
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return
    plot_df = heat_df.copy()
    values = plot_df.values.astype(float)
    cmap = LinearSegmentedColormap.from_list(
        "twin_ring_heat",
        [PALETTE["background"], PALETTE["memory"], PALETTE["zhang"], PALETTE["zhang_dark"]],
    )
    im = ax.imshow(values, cmap=cmap, aspect="auto")
    ax.set_xticks(np.arange(plot_df.shape[1]))
    ax.set_xticklabels([account_type_label(c) for c in plot_df.columns], rotation=25, ha="right")
    ax.set_yticks(np.arange(plot_df.shape[0]))
    ax.set_yticklabels([str(x)[:18] for x in plot_df.index])
    ax.set_facecolor(PALETTE["background"])
    ax.set_title(title, fontsize=15, fontweight="bold", color=PALETTE["text"], pad=14)
    ax.set_xlabel("转发目标账号类型")
    ax.set_ylabel("核心源微博作者")
    for i in range(plot_df.shape[0]):
        for j in range(plot_df.shape[1]):
            if values[i, j] > 0:
                ax.text(j, i, str(int(values[i, j])), ha="center", va="center", fontsize=8, color="#2B2926")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("转发边数 / 条")
    add_note(fig, "注：该图替代层级深度图，展示每条核心源微博向不同账号类型扩散的二层结构。")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _json_for_html(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _write_interactive_html(path: Path, title: str, subtitle: str, body: str, script: str) -> None:
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_lib.escape(title)}</title>
  <style>
    :root {{
      --bg: {PALETTE["background"]};
      --panel: {PALETTE["panel"]};
      --text: {PALETTE["text"]};
      --muted: {PALETTE["muted"]};
      --grid: {PALETTE["grid"]};
      --accent: {PALETTE["zhang"]};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    header {{ display: flex; justify-content: space-between; gap: 16px; align-items: end; margin-bottom: 16px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; line-height: 1.25; letter-spacing: 0; }}
    .subtitle {{ margin: 0; color: var(--muted); font-size: 13px; line-height: 1.7; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    button {{
      border: 1px solid #cfc7bd;
      background: #fffdf8;
      color: var(--text);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
      font-size: 13px;
    }}
    button.active, button:hover {{ border-color: var(--accent); color: #7a422e; }}
    .chart-wrap {{
      position: relative;
      background: rgba(255, 253, 248, 0.62);
      border: 1px solid #ded7ce;
      border-radius: 8px;
      padding: 14px;
      min-height: 560px;
    }}
    svg {{ width: 100%; height: 620px; display: block; overflow: visible; }}
    .axis text, .legend text {{ fill: var(--text); font-size: 12px; }}
    .grid-line {{ stroke: var(--grid); stroke-dasharray: 4 4; stroke-width: 1; opacity: .72; }}
    .axis-line {{ stroke: #bdb4aa; stroke-width: 1; }}
    .mark {{ cursor: pointer; transition: opacity .16s ease, transform .16s ease, filter .16s ease; }}
    .mark.dimmed {{ opacity: .16; }}
    .mark:hover {{ opacity: 1; filter: drop-shadow(0 4px 7px rgba(43, 41, 38, .16)); }}
    .label {{ fill: var(--text); font-size: 12px; paint-order: stroke; stroke: var(--bg); stroke-width: 3px; }}
    .cell-number {{ fill: #2B2926; font-size: 12px; font-weight: 600; stroke: none; paint-order: normal; pointer-events: none; }}
    #tooltip {{
      position: fixed;
      pointer-events: none;
      z-index: 10;
      max-width: 320px;
      padding: 10px 12px;
      border: 1px solid #cfc7bd;
      border-radius: 6px;
      background: rgba(255, 253, 248, .96);
      box-shadow: 0 10px 24px rgba(43, 41, 38, .16);
      color: var(--text);
      font-size: 12px;
      line-height: 1.55;
      display: none;
    }}
    #detail {{
      margin-top: 12px;
      min-height: 44px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.7;
    }}
    @media (max-width: 720px) {{
      main {{ padding: 14px; }}
      header {{ display: block; }}
      .toolbar {{ justify-content: flex-start; margin-top: 10px; }}
      .chart-wrap {{ min-height: 520px; padding: 8px; }}
      svg {{ height: 560px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{html_lib.escape(title)}</h1>
        <p class="subtitle">{html_lib.escape(subtitle)}</p>
      </div>
      <div class="toolbar" id="toolbar"></div>
    </header>
    <section class="chart-wrap">
      {body}
      <div id="tooltip"></div>
    </section>
    <div id="detail">Hover for details. Click an item to pin it here.</div>
  </main>
  <script>
{script}
  </script>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")


def write_source_bubble_html(path: Path, source_stats: pd.DataFrame) -> None:
    rows = []
    if not source_stats.empty:
        for _, row in source_stats.head(20).iterrows():
            narrative = infer_narrative(row.get("source_author", ""), row.get("text", ""))
            rows.append(
                {
                    "name": clean(row.get("source_author", "")),
                    "x": int(to_num(row.get("direct_reposts_in_edges", 0))),
                    "y": int(to_num(row.get("interaction_total", 0))),
                    "size": int(to_num(row.get("involved_nodes", 0))),
                    "narrative": narrative_label(narrative),
                    "color": narrative_color(narrative),
                    "text": clean(row.get("text", "")),
                }
            )
    script = f"""
const rows = {_json_for_html(rows)};
const svg = document.getElementById("chart");
const tooltip = document.getElementById("tooltip");
const detail = document.getElementById("detail");
const W = 1080, H = 620, m = {{l: 86, r: 34, t: 34, b: 74}};
const maxX = Math.max(1, ...rows.map(d => d.x));
const maxY = Math.max(1, ...rows.map(d => d.y));
const maxSize = Math.max(1, ...rows.map(d => d.size));
const sx = x => m.l + x / maxX * (W - m.l - m.r);
const sy = y => H - m.b - y / maxY * (H - m.t - m.b);
const sr = s => 9 + Math.sqrt(s / maxSize) * 28;
function el(name, attrs, parent = svg) {{
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  parent.appendChild(node);
  return node;
}}
function fmt(n) {{ return Number(n || 0).toLocaleString("zh-CN"); }}
function tip(d) {{
  return `<b>${{d.name}}</b><br>采集转发边：${{fmt(d.x)}}<br>转评赞总量：${{fmt(d.y)}}<br>涉及节点：${{fmt(d.size)}}<br>叙事：${{d.narrative}}`;
}}
for (let i = 0; i <= 5; i++) {{
  const x = m.l + i * (W - m.l - m.r) / 5;
  const y = H - m.b - i * (H - m.t - m.b) / 5;
  el("line", {{x1: x, y1: m.t, x2: x, y2: H - m.b, class: "grid-line"}});
  el("line", {{x1: m.l, y1: y, x2: W - m.r, y2: y, class: "grid-line"}});
  el("text", {{x, y: H - m.b + 24, "text-anchor": "middle", class: "label"}}).textContent = fmt(maxX * i / 5);
  el("text", {{x: m.l - 12, y: y + 4, "text-anchor": "end", class: "label"}}).textContent = fmt(maxY * i / 5);
}}
el("line", {{x1: m.l, y1: H - m.b, x2: W - m.r, y2: H - m.b, class: "axis-line"}});
el("line", {{x1: m.l, y1: m.t, x2: m.l, y2: H - m.b, class: "axis-line"}});
el("text", {{x: W / 2, y: H - 24, "text-anchor": "middle", class: "label"}}).textContent = "采集转发边数";
el("text", {{x: 18, y: H / 2, transform: `rotate(-90 18 ${{H / 2}})`, "text-anchor": "middle", class: "label"}}).textContent = "转评赞互动总量";
rows.forEach((d, i) => {{
  const c = el("circle", {{cx: sx(d.x), cy: sy(d.y), r: sr(d.size), fill: d.color, stroke: "white", "stroke-width": 1.4, opacity: .86, class: "mark", "data-kind": d.narrative}});
  c.addEventListener("mousemove", e => {{ tooltip.innerHTML = tip(d); tooltip.style.display = "block"; tooltip.style.left = e.clientX + 14 + "px"; tooltip.style.top = e.clientY + 14 + "px"; }});
  c.addEventListener("mouseleave", () => tooltip.style.display = "none");
  c.addEventListener("click", () => detail.innerHTML = tip(d) + (d.text ? `<br>文本：${{d.text}}` : ""));
  if (i < 8) el("text", {{x: sx(d.x) + sr(d.size) + 4, y: sy(d.y) + 4, class: "label"}}).textContent = d.name.slice(0, 12);
}});
const kinds = [...new Set(rows.map(d => d.narrative))];
const toolbar = document.getElementById("toolbar");
["全部", ...kinds].forEach(k => {{
  const b = document.createElement("button");
  b.textContent = k;
  b.onclick = () => {{
    document.querySelectorAll("button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".mark").forEach(x => x.classList.toggle("dimmed", k !== "全部" && x.dataset.kind !== k));
  }};
  toolbar.appendChild(b);
}});
toolbar.firstChild.classList.add("active");
"""
    _write_interactive_html(path, "图 07 核心源微博：传播规模与互动量", "气泡大小表示涉及节点数，颜色表示叙事类型。", '<svg id="chart" viewBox="0 0 1080 620" role="img"></svg>', script)


def write_lollipop_top_nodes_html(path: Path, df: pd.DataFrame) -> None:
    rows = [
        {
            "name": clean(row.get("node", "")),
            "pagerank": float(to_num(row.get("pagerank", 0))),
            "degree": int(to_num(row.get("degree", 0))),
            "type": account_type_label(clean(row.get("user_type", ""))),
            "color": account_type_color(clean(row.get("user_type", ""))),
        }
        for _, row in df.head(15).iloc[::-1].iterrows()
    ]
    script = f"""
const rows = {_json_for_html(rows)};
const svg = document.getElementById("chart"), tooltip = document.getElementById("tooltip"), detail = document.getElementById("detail");
const W = 1080, H = 620, m = {{l: 220, r: 170, t: 34, b: 58}};
const maxX = Math.max(0.000001, ...rows.map(d => d.pagerank));
const maxD = Math.max(1, ...rows.map(d => d.degree));
const sx = x => m.l + x / maxX * (W - m.l - m.r);
const sy = i => m.t + i * ((H - m.t - m.b) / Math.max(1, rows.length - 1));
function el(name, attrs, parent = svg) {{ const node = document.createElementNS("http://www.w3.org/2000/svg", name); Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v)); parent.appendChild(node); return node; }}
function tip(d) {{ return `<b>${{d.name}}</b><br>PageRank：${{d.pagerank.toFixed(6)}}<br>总度数：${{d.degree}}<br>账号类型：${{d.type}}`; }}
for (let i = 0; i <= 5; i++) {{
  const x = m.l + i * (W - m.l - m.r) / 5;
  el("line", {{x1:x, y1:m.t, x2:x, y2:H-m.b, class:"grid-line"}});
  el("text", {{x, y:H-m.b+24, "text-anchor":"middle", class:"label"}}).textContent = (maxX*i/5).toFixed(4);
}}
el("line", {{x1:m.l, y1:H-m.b, x2:W-m.r, y2:H-m.b, class:"axis-line"}});
rows.forEach((d, i) => {{
  const y = sy(i), x = sx(d.pagerank);
  el("text", {{x:m.l-12, y:y+4, "text-anchor":"end", class:"label"}}).textContent = d.name.slice(0, 22);
  el("line", {{x1:m.l, y1:y, x2:x, y2:y, stroke:d.color, "stroke-width":3, opacity:.46, class:"mark", "data-kind":d.type}});
  const c = el("circle", {{cx:x, cy:y, r:7 + Math.sqrt(d.degree/maxD)*18, fill:d.color, stroke:"white", "stroke-width":1.3, class:"mark", "data-kind":d.type}});
  el("text", {{x:x+12, y:y+4, class:"label"}}).textContent = `度 ${{d.degree}}`;
  c.addEventListener("mousemove", e => {{ tooltip.innerHTML = tip(d); tooltip.style.display = "block"; tooltip.style.left = e.clientX+14+"px"; tooltip.style.top = e.clientY+14+"px"; }});
  c.addEventListener("mouseleave", () => tooltip.style.display = "none");
  c.addEventListener("click", () => detail.innerHTML = tip(d));
}});
const types = [...new Set(rows.map(d => d.type))], toolbar = document.getElementById("toolbar");
["全部", ...types].forEach(k => {{ const b=document.createElement("button"); b.textContent=k; b.onclick=()=>{{ document.querySelectorAll("button").forEach(x=>x.classList.remove("active")); b.classList.add("active"); document.querySelectorAll(".mark").forEach(x=>x.classList.toggle("dimmed", k!=="全部" && x.dataset.kind!==k)); }}; toolbar.appendChild(b); }});
toolbar.firstChild.classList.add("active");
"""
    _write_interactive_html(path, "图 08 关键转发节点：PageRank 与连接规模", "横向位置表示 PageRank，圆点大小表示总度数，颜色表示账号类型。", '<svg id="chart" viewBox="0 0 1080 620" role="img"></svg>', script)


def write_account_type_distribution_html(path: Path, type_node_counts: Counter, type_edge_out: Counter, type_edge_in: Counter) -> None:
    rows = []
    for key, count in type_node_counts.most_common():
        rows.append(
            {
                "key": key,
                "label": account_type_label(key),
                "nodes": int(count),
                "out": int(type_edge_out[key]),
                "in": int(type_edge_in[key]),
                "color": account_type_color(key),
            }
        )
    script = f"""
const rows = {_json_for_html(rows)};
const svg = document.getElementById("chart"), tooltip = document.getElementById("tooltip"), detail = document.getElementById("detail");
const W = 1080, H = 620, cx = 245, cy = 275, r = 160, inner = 92;
function el(name, attrs, parent = svg) {{ const node = document.createElementNS("http://www.w3.org/2000/svg", name); Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v)); parent.appendChild(node); return node; }}
function polar(a, radius) {{ return [cx + Math.cos(a) * radius, cy + Math.sin(a) * radius]; }}
let activeKind = "全部";
function arc(start, end, color, d) {{
  const [x1,y1]=polar(start,r), [x2,y2]=polar(end,r), [x3,y3]=polar(end,inner), [x4,y4]=polar(start,inner);
  const large = end-start > Math.PI ? 1 : 0;
  const p = `M ${{x1}} ${{y1}} A ${{r}} ${{r}} 0 ${{large}} 1 ${{x2}} ${{y2}} L ${{x3}} ${{y3}} A ${{inner}} ${{inner}} 0 ${{large}} 0 ${{x4}} ${{y4}} Z`;
  const node = el("path", {{d:p, fill:color, stroke:"white", "stroke-width":1.2, class:"mark", "data-kind":d.label}});
  const mid = (start + end) / 2;
  const dx = Math.cos(mid) * 7;
  const dy = Math.sin(mid) * 7;
  node.addEventListener("mousemove", e => {{ tooltip.innerHTML=tip(d); tooltip.style.display="block"; tooltip.style.left=e.clientX+14+"px"; tooltip.style.top=e.clientY+14+"px"; }});
  node.addEventListener("mouseenter",()=>{{ node.style.transform = `translate(${{dx}}px, ${{dy}}px)`; }});
  node.addEventListener("mouseleave",()=>{{ tooltip.style.display="none"; node.style.transform = ""; }});
  node.addEventListener("click",()=>toggleKind(d.label, tip(d)));
}}
function tip(d) {{ return `<b>${{d.label}}</b><br>节点：${{d.nodes}}<br>发出边：${{d.out}}<br>接收边：${{d.in}}`; }}
function selectKind(kind, html) {{
  activeKind = kind;
  document.querySelectorAll("button").forEach(x => x.classList.toggle("active", x.textContent === kind));
  document.querySelectorAll(".mark").forEach(x => {{
    const hit = x.dataset.kind === kind;
    x.classList.toggle("dimmed", !hit);
  }});
  detail.innerHTML = html;
}}
function toggleKind(kind, html) {{
  if (activeKind === kind) {{
    clearSelection();
  }} else {{
    selectKind(kind, html);
  }}
}}
function clearSelection() {{
  activeKind = "全部";
  document.querySelectorAll("button").forEach(x => x.classList.toggle("active", x.textContent === "全部"));
  document.querySelectorAll(".mark").forEach(x => {{
    x.classList.remove("dimmed");
  }});
}}
const total = rows.reduce((s,d)=>s+d.nodes,0) || 1;
let a = -Math.PI/2;
rows.forEach(d => {{ const next = a + d.nodes / total * Math.PI * 2; arc(a, next, d.color, d); a = next; }});
el("text", {{x:cx, y:cy-4, "text-anchor":"middle", class:"label", "font-size":24}}).textContent = total;
el("text", {{x:cx, y:cy+22, "text-anchor":"middle", class:"label"}}).textContent = "节点";
const barX = 610, barW = 96, gap = 126, base = 500, maxTotal = Math.max(1, rows.reduce((s,d)=>s+d.out,0), rows.reduce((s,d)=>s+d.in,0));
["发出边", "接收边"].forEach((name, idx) => el("text", {{x:barX+idx*gap+barW/2, y:base+28, "text-anchor":"middle", class:"label"}}).textContent=name);
["out", "in"].forEach((field, idx) => {{
  let y = base;
  rows.forEach(d => {{
    const h = d[field] / maxTotal * 360;
    y -= h;
    const rect = el("rect", {{x:barX+idx*gap, y, width:barW, height:h, fill:d.color, class:"mark", "data-kind":d.label}});
    rect.addEventListener("mousemove", e => {{ tooltip.innerHTML=tip(d); tooltip.style.display="block"; tooltip.style.left=e.clientX+14+"px"; tooltip.style.top=e.clientY+14+"px"; }});
    rect.addEventListener("mouseenter",()=>{{ rect.setAttribute("x", barX+idx*gap-4); rect.setAttribute("width", barW+8); }});
    rect.addEventListener("mouseleave",()=>{{ tooltip.style.display="none"; rect.setAttribute("x", barX+idx*gap); rect.setAttribute("width", barW); }});
    rect.addEventListener("click",()=>toggleKind(d.label, tip(d)));
  }});
}});
rows.forEach((d, i) => {{
  const y = 110 + i * 28;
  const item = el("rect", {{x:880, y:y-12, width:14, height:14, fill:d.color, class:"mark", "data-kind":d.label}});
  item.addEventListener("click",()=>toggleKind(d.label, tip(d)));
  el("text", {{x:902, y, class:"label"}}).textContent = `${{d.label}}  节点 ${{d.nodes}}`;
}});
const toolbar = document.getElementById("toolbar");
["全部", ...rows.map(d=>d.label)].forEach(k => {{ const b=document.createElement("button"); b.textContent=k; b.onclick=()=>{{ if (k==="全部") {{ clearSelection(); return; }} const d = rows.find(x => x.label === k); toggleKind(k, tip(d)); }}; toolbar.appendChild(b); }});
toolbar.firstChild.classList.add("active");
"""
    _write_interactive_html(path, "图 09 账号类型网络：节点构成与边贡献", "左侧为账号类型节点占比，右侧为发出边与接收边堆叠。", '<svg id="chart" viewBox="0 0 1080 620" role="img"></svg>', script)


def write_source_type_heatmap_html(path: Path, heat_df: pd.DataFrame) -> None:
    rows = []
    if not heat_df.empty:
        for source in heat_df.index:
            for typ in heat_df.columns:
                rows.append({"source": clean(source), "type": account_type_label(typ), "value": int(to_num(heat_df.loc[source, typ]))})
    script = f"""
const cells = {_json_for_html(rows)};
const sources = [...new Set(cells.map(d => d.source))];
const types = [...new Set(cells.map(d => d.type))];
const svg = document.getElementById("chart"), tooltip = document.getElementById("tooltip"), detail = document.getElementById("detail");
const W = 1080, H = 620, m = {{l: 230, r: 104, t: 50, b: 86}};
const cellW = (W - m.l - m.r) / Math.max(1, types.length);
const cellH = (H - m.t - m.b) / Math.max(1, sources.length);
const maxV = Math.max(1, ...cells.map(d => d.value));
function el(name, attrs, parent = svg) {{ const node = document.createElementNS("http://www.w3.org/2000/svg", name); Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v)); parent.appendChild(node); return node; }}
function color(v) {{
  const t = Math.sqrt(v / maxV);
  const a = [245,243,238], b = [192,120,88];
  return `rgb(${{Math.round(a[0]+(b[0]-a[0])*t)}},${{Math.round(a[1]+(b[1]-a[1])*t)}},${{Math.round(a[2]+(b[2]-a[2])*t)}})`;
}}
function tip(d) {{ return `<b>${{d.source}}</b><br>目标账号类型：${{d.type}}<br>转发边数：${{d.value}}`; }}
const defs = el("defs", {{}});
const grad = el("linearGradient", {{id:"heatLegend", x1:"0", y1:"1", x2:"0", y2:"0"}}, defs);
[0, .25, .5, .75, 1].forEach(t => {{
  el("stop", {{offset:`${{t * 100}}%`, "stop-color":color(maxV * t * t)}}, grad);
}});
sources.forEach((s, i) => el("text", {{x:m.l-12, y:m.t+i*cellH+cellH/2+4, "text-anchor":"end", class:"label"}}).textContent = s.slice(0, 18));
types.forEach((t, j) => el("text", {{x:m.l+j*cellW+cellW/2, y:H-m.b+28, transform:`rotate(25 ${{m.l+j*cellW+cellW/2}} ${{H-m.b+28}})`, "text-anchor":"start", class:"label"}}).textContent = t);
cells.forEach(d => {{
  const i = sources.indexOf(d.source), j = types.indexOf(d.type);
  const rect = el("rect", {{x:m.l+j*cellW, y:m.t+i*cellH, width:Math.max(1,cellW-2), height:Math.max(1,cellH-2), fill:color(d.value), stroke:"#fffdf8", class:"mark", "data-kind":d.type}});
  if (d.value > 0) el("text", {{x:m.l+j*cellW+cellW/2, y:m.t+i*cellH+cellH/2+4, "text-anchor":"middle", class:"cell-number"}}).textContent = d.value;
  rect.addEventListener("mousemove", e => {{ tooltip.innerHTML=tip(d); tooltip.style.display="block"; tooltip.style.left=e.clientX+14+"px"; tooltip.style.top=e.clientY+14+"px"; }});
  rect.addEventListener("mouseleave",()=>tooltip.style.display="none");
  rect.addEventListener("click",()=>detail.innerHTML=tip(d));
}});
const legendX = W - 72, legendY = m.t, legendH = H - m.t - m.b, legendW = 14;
el("rect", {{x:legendX, y:legendY, width:legendW, height:legendH, fill:"url(#heatLegend)", stroke:"#cfc7bd", "stroke-width":1}});
el("text", {{x:legendX + legendW / 2, y:legendY - 12, "text-anchor":"middle", class:"label"}}).textContent = "边数";
[0, .5, 1].forEach(t => {{
  const y = legendY + legendH * (1 - t);
  el("line", {{x1:legendX + legendW, y1:y, x2:legendX + legendW + 6, y2:y, stroke:"#8C8C8C", "stroke-width":1}});
  el("text", {{x:legendX + legendW + 10, y:y + 4, class:"label"}}).textContent = Math.round(maxV * t);
}});
const toolbar = document.getElementById("toolbar");
["全部", ...types].forEach(k => {{ const b=document.createElement("button"); b.textContent=k; b.onclick=()=>{{ document.querySelectorAll("button").forEach(x=>x.classList.remove("active")); b.classList.add("active"); document.querySelectorAll(".mark").forEach(x=>x.classList.toggle("dimmed", k!=="全部" && x.dataset.kind!==k)); }}; toolbar.appendChild(b); }});
toolbar.firstChild.classList.add("active");
"""
    _write_interactive_html(path, "图 10 传播结构：核心源微博与账号类型扩散矩阵", "颜色越深表示该核心源微博流向对应账号类型的转发边越多。", '<svg id="chart" viewBox="0 0 1080 620" role="img"></svg>', script)


def patch_vis_network_html(html_path: Path) -> None:
    """修复 PyVis/vis-network CDN 与 loading 条不消失。"""
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    html = html.replace("/dist/dist/", "/dist/")
    html = re.sub(
        r'<link rel="stylesheet" href="https://cdnjs\.cloudflare\.com/ajax/libs/vis-network/[^"]+"[^>]*/>',
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/vis-network@9.1.2/styles/vis-network.min.css" />',
        html,
    )
    html = re.sub(
        r'<script src="https://cdnjs\.cloudflare\.com/ajax/libs/vis-network/[^"]+"[^>]*></script>',
        '<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.2/standalone/umd/vis-network.min.js"></script>',
        html,
    )
    if "forceHideLoadingBar" not in html:
        inject = """
                      function forceHideLoadingBar() {
                        var bar = document.getElementById('loadingBar');
                        if (bar) { bar.style.opacity = 0; bar.style.display = 'none'; }
                      }
                      network.once("init", forceHideLoadingBar);
                      network.once("stabilizationIterationsDone", forceHideLoadingBar);
                      setTimeout(forceHideLoadingBar, 2500);
"""
        needle = "network = new vis.Network(container, data, options);"
        if needle in html:
            html = html.replace(needle, needle + inject, 1)
    html_path.write_text(html, encoding="utf-8")


def select_network_subgraph(
    graph,
    edges_df: pd.DataFrame,
    pagerank: dict[str, float],
    *,
    max_nodes: int = 300,
) -> tuple[Any, pd.DataFrame, str]:
    """展示子图：先取最大弱连通分量，再按 PageRank 截断至 max_nodes。"""
    import networkx as nx

    full_n = graph.number_of_nodes()
    full_e = graph.number_of_edges()
    if full_n == 0:
        return graph, edges_df.iloc[0:0], "网络为空"

    wccs = list(nx.weakly_connected_components(graph))
    largest_nodes = max(wccs, key=len)
    sub = graph.subgraph(largest_nodes).copy()
    note = (
        f"全量网络 {full_n} 节点 / {full_e} 边；"
        f"展示图取最大弱连通分量（{sub.number_of_nodes()} 节点 / {sub.number_of_edges()} 边）"
    )

    if sub.number_of_nodes() > max_nodes:
        hop_num = pd.to_numeric(edges_df.get("_hop", 1), errors="coerce").fillna(1).astype(int)
        root_sources = set(edges_df.loc[hop_num == 1, "_source"].value_counts().head(30).index)
        amplifiers = set(edges_df["_source"].value_counts().head(45).index)
        keep = set((root_sources | amplifiers) & set(sub.nodes))
        keep |= {n for n, _ in top_items({n: pagerank.get(n, 0) for n in sub.nodes}, max_nodes)}
        sub = sub.subgraph(keep).copy()
        note += f"，并按 PageRank 保留 Top {max_nodes} 重要节点（含核心源与二层放大种子）"

    node_set = set(sub.nodes)
    view_edges = edges_df[(edges_df["_source"].isin(node_set)) & (edges_df["_target"].isin(node_set))].copy()
    return sub, view_edges, note


def write_pyvis_temporal_network(path: Path, data: dict[str, Any]) -> str:
    """
    vis-network 传播图：打开自动按时间展开；点击节点显示结构化详情面板。
    节点填充=立场，外圈=账号类型；大小=度数+PageRank；边色=采样窗口。
    """
    import networkx as nx

    graph = data["graph"]
    edges_df = data["edges"]
    pagerank = data["pagerank"]
    degree = data["degree"]
    user_type = data["user_type"]
    text_by_user = data["text_by_user"]
    label_by_user = data.get("label_by_user", {})

    sub, view_edges, filter_note = select_network_subgraph(graph, edges_df, pagerank, max_nodes=200)
    if sub.number_of_nodes() == 0:
        path.write_text("<html><meta charset='utf-8'><body><p>无可展示网络</p></body></html>", encoding="utf-8")
        return filter_note

    net_w, net_h = 1100, 620
    view_hop_num = pd.to_numeric(view_edges.get("_hop", 1), errors="coerce").fillna(1).astype(int)
    top_sources_list = view_edges.loc[view_hop_num == 1, "_source"].value_counts().head(20).index.tolist()
    if not top_sources_list:
        top_sources_list = view_edges["_source"].value_counts().head(20).index.tolist()
    top_sources = set(top_sources_list)
    label_nodes = top_sources | {n for n, _ in top_items(pagerank, 40)}

    timeline = view_edges.copy()
    timeline["_show_time"] = pd.to_datetime(timeline["_event_time"], errors="coerce")
    if timeline["_show_time"].isna().all() and "crawl_time" in timeline.columns:
        timeline["_show_time"] = pd.to_datetime(timeline["crawl_time"], errors="coerce")
    timeline["_hop_num"] = pd.to_numeric(timeline.get("_hop", 1), errors="coerce").fillna(1).astype(int)
    timeline = timeline.sort_values(["_hop_num", "_show_time"], na_position="last")

    # 层级扩散布局：核心源在左，直接转发/二跳/三跳从左到右展开。
    # 比 spring_layout 的星爆形态更适合解释“传播过程”。
    cx, cy = net_w / 2, net_h / 2
    usable_top, usable_bottom = 92, net_h - 82
    usable_h = usable_bottom - usable_top
    root_y: dict[str, float] = {}
    if top_sources_list:
        for idx, node in enumerate(top_sources_list):
            root_y[node] = usable_top + (idx + 0.5) * usable_h / max(1, len(top_sources_list))
    root_for: dict[str, str] = {node: node for node in top_sources_list}
    hop_for: dict[str, int] = {node: 0 for node in top_sources_list}
    for _, row in timeline.iterrows():
        u, v = row["_source"], row["_target"]
        hop_n = int(row.get("_hop_num", 1) or 1)
        if u in root_for:
            root = root_for[u]
        elif u in top_sources:
            root = u
        else:
            root = top_sources_list[0] if top_sources_list else u
        root_for.setdefault(u, root)
        root_for.setdefault(v, root)
        hop_for.setdefault(u, max(0, hop_n - 1))
        hop_for[v] = max(hop_for.get(v, 0), min(3, hop_n))

    grouped_nodes: dict[tuple[str, int], list[str]] = defaultdict(list)
    for node in sub.nodes:
        root = root_for.get(node, top_sources_list[0] if top_sources_list else node)
        hop_n = hop_for.get(node, 1 if node not in top_sources else 0)
        grouped_nodes[(root, hop_n)].append(node)

    x_by_hop = {0: 145, 1: 405, 2: 685, 3: 955}
    pos: dict[str, tuple[float, float]] = {}
    for (root, hop_n), items in grouped_nodes.items():
        items = sorted(items, key=lambda n: (-degree.get(n, 0), n))
        center_y = root_y.get(root, net_h / 2)
        layer = min(max(hop_n, 0), 3)
        x_center = x_by_hop.get(layer, 955)
        band_h = max(42, min(112, usable_h / max(3, len(top_sources_list)) * 1.65))
        cols = 1 if len(items) <= 12 else 2 if len(items) <= 34 else 3
        rows = max(1, math.ceil(len(items) / cols))
        row_gap = min(19, max(7, band_h / max(1, rows - 1)))
        col_gap = 34
        for idx, node in enumerate(items):
            col = idx % cols
            row_i = idx // cols
            x_jitter = (col - (cols - 1) / 2) * col_gap + ((idx % 5) - 2) * 2.2
            y_offset = (row_i - (rows - 1) / 2) * row_gap + ((idx % 3) - 1) * 2.5
            if layer == 0:
                x_jitter = ((idx % 3) - 1) * 7
                y_offset = ((idx % 5) - 2) * 5
            x = x_center + x_jitter
            y = center_y + y_offset
            pos[node] = (max(74, min(net_w - 74, x)), max(72, min(net_h - 72, y)))

    nodes_js: list[dict[str, Any]] = []
    node_meta: dict[str, dict[str, str]] = {}
    is_source = top_sources

    for node in sub.nodes:
        typ = user_type.get(node, "ordinary_user")
        pr = float(pagerank.get(node, 0))
        deg = int(degree.get(node, 0))
        lab = label_by_user.get(node) or label_stance(text_by_user.get(node, ""), node)
        fill = stance_node_color(lab.get("stance", "unclear"), lab.get("frame", ""))
        border = account_type_color(typ)
        x, y = pos[node]
        size = max(4, min(10, 4 + math.sqrt(max(deg, 0)) * 0.65 + pr * 90))
        if node in is_source:
            size = min(14, size + 3)
        show_label = node in label_nodes
        bucket_cn = BUCKET_LABELS.get(dominant_bucket_for_user(view_edges, node), "未标注")
        node_meta[node] = {
            "name": node,
            "account_type": account_type_label(typ),
            "stance": stance_label_cn(lab.get("stance", "unclear"), lab.get("frame", "")),
            "degree": str(deg),
            "pagerank": f"{pr:.6f}",
            "bucket": bucket_cn,
            "fill": fill,
            "border": border,
        }
        active_color = {
            "background": fill,
            "border": border,
            "highlight": {"background": fill, "border": PALETTE["text"]},
        }
        label_font = {
            "size": 10 if node in is_source else 9,
            "color": PALETTE["text"],
            "face": "Microsoft YaHei, SimHei, sans-serif",
            "strokeWidth": 2,
            "strokeColor": "#FFFDF8",
        }
        nodes_js.append(
            {
                "id": node,
                "label": str(node)[:14] if show_label else "",
                "showLabel": show_label,
                "x": float(x),
                "y": float(y),
                "size": size,
                "activeColor": active_color,
                "activeFont": label_font,
                "borderWidth": 1.5 if node in is_source else 1,
                "shadow": False,
            }
        )

    if nodes_js:
        xs = [n["x"] for n in nodes_js]
        ys = [n["y"] for n in nodes_js]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)
        left_pad = 58
        right_pad = 140
        y_pad = 82
        for n in nodes_js:
            n["x"] = left_pad + (n["x"] - min_x) / span_x * (net_w - left_pad - right_pad)
            n["y"] = y_pad + (n["y"] - min_y) / span_y * (net_h - 2 * y_pad)

    edges_js = []
    for i, (_, row) in enumerate(timeline.iterrows()):
        u, v = row["_source"], row["_target"]
        if u not in sub or v not in sub:
            continue
        bucket = clean(row.get("_bucket", "")) or "unknown"
        t = row["_show_time"]
        time_str = "" if pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d %H:%M")
        hop_n = int(row.get("_hop_num", 1) or 1)
        hop_n = hop_n if hop_n in HOP_COLORS else 1
        edges_js.append(
            {
                "id": f"e{i}",
                "from": u,
                "to": v,
                "hop": hop_n,
                "hopLabel": HOP_LABELS_CN.get(hop_n, "一层"),
                "color": {"color": HOP_COLORS.get(hop_n, PALETTE["neutral"]), "opacity": 0.38},
                "width": max(0.45, min(1.2, 0.35 + int(sub[u][v].get("weight", 1)) * 0.25)),
                "time": time_str,
                "bucket": BUCKET_LABELS.get(bucket, bucket),
            }
        )

    n_edges = len(edges_js)
    n_hop1 = sum(1 for e in edges_js if e.get("hop") == 1)
    n_hop2 = sum(1 for e in edges_js if e.get("hop") == 2)
    n_hop3 = sum(1 for e in edges_js if e.get("hop") == 3)
    source_ids_view = [n for n in sub.nodes if n in top_sources]
    total_frames = 115
    phase0_end = 6
    phase1_end = 72
    phase2_end = 98
    frame_ms = 52

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>图 06 微博转发传播网络</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/vis-network@9.1.2/styles/vis-network.min.css" />
  <script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.2/standalone/umd/vis-network.min.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(165deg, {PALETTE['background']} 0%, #EDE9E2 45%, {PALETTE['background']} 100%);
      font-family: "Microsoft YaHei", "Noto Sans SC", SimHei, sans-serif;
      color: {PALETTE['text']};
    }}
    .nl-shell {{ max-width: 1320px; margin: 0 auto; padding: 16px 20px 24px; }}
    .nl-card {{
      background: rgba(255,253,248,0.92);
      border: 1px solid {PALETTE['grid']};
      border-radius: 14px;
      box-shadow: 0 8px 32px rgba(42,41,38,0.06);
      overflow: visible;
    }}
    .nl-head {{ padding: 18px 22px 12px; border-bottom: 1px solid #E8E2D8; }}
    .nl-head h1 {{ margin: 0 0 6px; font-size: 21px; font-weight: 700; letter-spacing: 0.02em; }}
    .nl-head .sub {{ margin: 0; font-size: 13px; color: #666; line-height: 1.6; }}
    .nl-head .note {{ margin: 6px 0 0; font-size: 11.5px; color: #999; }}
    .nl-controls {{
      display: flex; align-items: center; gap: 14px; padding: 12px 22px;
      flex-wrap: wrap; background: #FAF8F4;
    }}
    #animStatus {{ font-size: 13px; font-weight: 600; min-width: 220px; color: {PALETTE['text']}; }}
    .nl-progress {{
      flex: 1; min-width: 120px; height: 6px; background: #E5DFD6; border-radius: 99px; overflow: hidden;
    }}
    #progressBar {{
      height: 100%; width: 0%; background: linear-gradient(90deg, {PALETTE['wang']}, {PALETTE['zhang']});
      border-radius: 99px; transition: width 0.12s ease-out;
    }}
    #timeSlider {{ flex: 1; min-width: 160px; max-width: 360px; accent-color: {PALETTE['zhang']}; }}
    .nl-btn {{
      border: 1px solid #CFC7BD; background: #fff; color: {PALETTE['text']};
      padding: 7px 16px; border-radius: 8px; cursor: pointer; font-size: 13px;
      transition: background 0.15s, box-shadow 0.15s;
    }}
    .nl-btn:hover {{ background: #F5F1EA; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .nl-legend {{
      display: flex; flex-wrap: wrap; gap: 14px; padding: 8px 22px 14px;
      font-size: 11.5px; color: #666; border-bottom: 1px solid #E8E2D8;
    }}
    .nl-legend i {{
      display: inline-block; width: 10px; height: 10px; border-radius: 50%;
      margin-right: 4px; vertical-align: -1px;
    }}
    .nl-network-wrap {{
      width: 100%; height: {net_h}px; min-height: {net_h}px; max-height: {net_h}px;
      position: relative; background: {PALETTE['panel']};
      border-top: 1px solid #E8E2D8;
    }}
    .nl-main {{ display: block; position: relative; width: 100%; height: {net_h}px; }}
    #mynetwork {{
      width: 100%; height: {net_h}px; min-height: {net_h}px; max-height: {net_h}px;
      background: {PALETTE['panel']};
    }}
    #mynetwork canvas {{ outline: none; }}
    #nl-detail {{
      position: absolute; right: 16px; top: 16px; width: 280px;
      background: rgba(255,255,255,0.96); border: 1px solid #E0D8CE;
      border-radius: 12px; padding: 16px 18px; box-shadow: 0 12px 40px rgba(42,41,38,0.12);
      font-size: 13px; line-height: 1.65; display: none; z-index: 10;
      backdrop-filter: blur(8px);
    }}
    #nl-detail.show {{ display: block; animation: nlIn 0.22s ease-out; }}
    @keyframes nlIn {{ from {{ opacity: 0; transform: translateY(-6px); }} to {{ opacity: 1; transform: none; }} }}
    #nl-detail h3 {{ margin: 0 0 10px; font-size: 15px; word-break: break-all; }}
    #nl-detail dl {{ margin: 0; display: grid; grid-template-columns: 72px 1fr; gap: 6px 10px; }}
    #nl-detail dt {{ color: #888; font-weight: 500; }}
    #nl-detail dd {{ margin: 0; color: {PALETTE['text']}; }}
    #nl-detail .swatch {{
      display: inline-block; width: 12px; height: 12px; border-radius: 50%;
      border: 2px solid; vertical-align: -2px; margin-right: 6px;
    }}
    #nl-detail .hint {{ margin-top: 12px; font-size: 11px; color: #aaa; border-top: 1px solid #EEE; padding-top: 8px; }}
  </style>
</head>
<body>
  <div class="nl-shell">
    <div class="nl-card">
      <div class="nl-head">
        <h1>图 06 微博转发传播网络</h1>
        <p class="sub">神经网络式传播布局：核心源、直接转发、二层扩散、三层扩散分层排列；播放完成后启用真实物理引擎，约 4 秒后只居中一次。悬停看名称，点击节点看详情。</p>
        <p class="note">{html_lib.escape(filter_note)}</p>
      </div>
      <div class="nl-controls">
        <span id="animStatus">正在初始化…</span>
        <div class="nl-progress"><div id="progressBar"></div></div>
        <input id="timeSlider" type="range" min="0" max="{total_frames}" value="0" step="1" />
        <button type="button" class="nl-btn" id="pauseBtn">暂停</button>
        <button type="button" class="nl-btn" id="replayBtn">重播</button>
        <button type="button" class="nl-btn" id="fullBtn">一次显示全部</button>
        <button type="button" class="nl-btn" id="resetViewBtn">重置视图</button>
      </div>
      <div class="nl-legend">
        <span><b>立场</b></span>
        <span><i style="background:{STANCE_COLORS['support_zhang']}"></i>支持张碧晨</span>
        <span><i style="background:{STANCE_COLORS['support_wang']}"></i>支持汪苏泷</span>
        <span><i style="background:{STANCE_COLORS['neutral']}"></i>中立</span>
        <span><i style="background:{STANCE_COLORS['anti_fanwar']}"></i>反饭圈</span>
        <span><i style="background:{STANCE_COLORS['legal_discussion']}"></i>版权法律</span>
        <span style="margin-left:8px"><b>爬取层</b></span>
        <span><i style="background:{PALETTE['zhang']};border-radius:2px"></i>一层 {n_hop1}</span>
        <span><i style="background:{PALETTE['wang']};border-radius:2px"></i>二层 {n_hop2}</span>
        <span><i style="background:{PALETTE['memory']};border-radius:2px"></i>三层 {n_hop3}</span>
      </div>
      <div class="nl-network-wrap nl-main">
        <div id="mynetwork"></div>
        <div id="nl-detail">
          <h3 id="detailName">—</h3>
          <dl>
            <dt>账号类型</dt><dd id="detailType">—</dd>
            <dt>立场</dt><dd id="detailStance">—</dd>
            <dt>总度数</dt><dd id="detailDeg">—</dd>
            <dt>PageRank</dt><dd id="detailPr">—</dd>
            <dt>采样窗口</dt><dd id="detailBucket">—</dd>
          </dl>
          <p class="hint">点击空白处关闭 · 悬停边可查看转发时间</p>
        </div>
      </div>
    </div>
  </div>
<script>
(function() {{
  const ALL_NODES = {json.dumps(nodes_js, ensure_ascii=False)};
  const ALL_EDGES = {json.dumps(edges_js, ensure_ascii=False)};
  const NODE_META = {json.dumps(node_meta, ensure_ascii=False)};
  const TOTAL_FRAMES = {total_frames};
  const PHASE0_END = {phase0_end};
  const PHASE1_END = {phase1_end};
  const PHASE2_END = {phase2_end};
  const SOURCE_IDS = {json.dumps(source_ids_view, ensure_ascii=False)};
  const NET_W = {net_w};
  const NET_H = {net_h};
  const FRAME_MS = {frame_ms};
  const HOP1 = ALL_EDGES.filter(e => (e.hop || 1) === 1);
  const HOP2 = ALL_EDGES.filter(e => e.hop === 2);
  const HOP3 = ALL_EDGES.filter(e => e.hop === 3);
  const N1 = HOP1.length, N2 = HOP2.length, N3 = HOP3.length;
  const nodeBase = Object.fromEntries(ALL_NODES.map(n => [n.id, n]));

  let network = null, visNodes = null, visEdges = null;
  let frame = 0, edgeUpto = 0, rafId = null, paused = false, lastTs = 0, didFit = false, floating = false, floatRaf = null, floatFitTimer = null;

  const statusEl = document.getElementById('animStatus');
  const progressBar = document.getElementById('progressBar');
  const slider = document.getElementById('timeSlider');
  const pauseBtn = document.getElementById('pauseBtn');
  const replayBtn = document.getElementById('replayBtn');
  const fullBtn = document.getElementById('fullBtn');
  const resetViewBtn = document.getElementById('resetViewBtn');
  const detail = document.getElementById('nl-detail');

  function resizeNetwork() {{
    const el = document.getElementById('mynetwork');
    if (!network || !el) return;
    const w = el.clientWidth || NET_W;
    network.setSize(w + 'px', NET_H + 'px');
    network.redraw();
  }}

  function safeFit() {{
    if (!network || edgeUpto < 1) return;
    resizeNetwork();
    try {{
      network.fit({{
        animation: false,
        padding: 48,
        minZoomLevel: 0.2,
        maxZoomLevel: 1.5
      }});
    }} catch (e) {{}}
  }}

  function fitFullLayout() {{
    if (!network || !visNodes) return;
    const existingNodes = visNodes.get();
    const existingEdges = visEdges ? visEdges.get() : [];
    try {{
      visEdges.clear();
      visNodes.clear();
      visNodes.add(ALL_NODES.map(n => nodePayload(n.id)).filter(Boolean));
      network.fit({{
        nodes: ALL_NODES.map(n => n.id),
        animation: false,
        padding: 34,
        minZoomLevel: 0.2,
        maxZoomLevel: 1.5
      }});
      visNodes.clear();
      if (existingNodes.length) visNodes.add(existingNodes);
      if (visEdges && existingEdges.length) visEdges.add(existingEdges);
    }} catch (e) {{
      try {{
        visNodes.clear();
        if (existingNodes.length) visNodes.add(existingNodes);
        if (visEdges && existingEdges.length) visEdges.add(existingEdges);
      }} catch (_e) {{}}
    }}
  }}

  function disableFloating() {{
    floating = false;
    if (floatRaf) cancelAnimationFrame(floatRaf);
    floatRaf = null;
    if (floatFitTimer) clearTimeout(floatFitTimer);
    floatFitTimer = null;
    if (!network || !visNodes) return;
    try {{
      network.setOptions({{ physics: {{ enabled: false }}, nodes: {{ fixed: true }} }});
      const updates = visNodes.getIds().map(id => {{
        const b = nodeBase[id];
        return b ? {{ id: id, x: b.x, y: b.y, fixed: {{ x: true, y: true }} }} : {{ id: id, fixed: {{ x: true, y: true }} }};
      }});
      if (updates.length) visNodes.update(updates);
    }} catch (e) {{}}
  }}

  function enableFloating() {{
    if (floating || !network || !visNodes || edgeUpto < ALL_EDGES.length) return;
    floating = true;
    try {{
      if (floatFitTimer) clearTimeout(floatFitTimer);
      const updates = visNodes.getIds().map(id => {{ return {{ id: id, fixed: {{ x: false, y: false }} }}; }});
      if (updates.length) visNodes.update(updates);
      network.setOptions({{
        physics: {{
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {{
            gravitationalConstant: -22,
            centralGravity: 0.028,
            springLength: 86,
            springConstant: 0.021,
            damping: 0.88,
            avoidOverlap: 0.35
          }},
          minVelocity: 0.05,
          maxVelocity: 5,
          stabilization: false,
          timestep: 0.32,
          adaptiveTimestep: true
        }},
        nodes: {{ fixed: false }}
      }});
      floatFitTimer = setTimeout(function() {{
        if (!floating || !network) return;
        safeFit();
        floatFitTimer = null;
      }}, 4000);
    }} catch (e) {{}}
  }}

  function targetEdgeCount(f) {{
    if (f <= PHASE0_END) return 0;
    if (f <= PHASE1_END) {{
      const t = (f - PHASE0_END) / Math.max(1, PHASE1_END - PHASE0_END);
      return Math.max(0, Math.round(t * N1));
    }}
    if (f <= PHASE2_END) {{
      const t = (f - PHASE1_END) / Math.max(1, PHASE2_END - PHASE1_END);
      return N1 + Math.max(0, Math.round(t * N2));
    }}
    const t = (f - PHASE2_END) / Math.max(1, TOTAL_FRAMES - PHASE2_END);
    return N1 + N2 + Math.max(0, Math.round(t * N3));
  }}

  function showSourcesOnly() {{
    visEdges.clear();
    edgeUpto = 0;
    visNodes.clear();
    SOURCE_IDS.forEach(id => {{
      const p = nodePayload(id);
      if (p) visNodes.add(p);
    }});
  }}

  function statusText(f, upto, done) {{
    if (done) return '三层传播已全部显示 · 真实物理引擎运行中 · 约 4 秒后居中一次';
    if (f <= PHASE0_END) return '第 0 步：核心源节点（' + SOURCE_IDS.length + ' 个）· 尚未连边';
    if (upto <= N1) return '第 1 层：核心源→直接转发 ' + upto + ' / ' + N1 + ' 条';
    if (upto <= N1 + N2) return '第 2 层：热门种子→转发 ' + (upto - N1) + ' / ' + N2 + ' 条';
    return '第 3 层：高互动帖→转发 ' + (upto - N1 - N2) + ' / ' + N3 + ' 条';
  }}

  function nodePayload(id) {{
    const base = nodeBase[id];
    if (!base) return null;
    return {{
      id: base.id,
      x: base.x,
      y: base.y,
      size: base.size,
      color: base.activeColor,
      font: base.activeFont,
      label: base.showLabel ? (base.label || String(id).slice(0, 14)) : '',
      borderWidth: base.borderWidth,
      shadow: base.shadow,
      fixed: {{ x: true, y: true }}
    }};
  }}

  function syncNodesFromEdges(edgeList) {{
    const need = new Set(SOURCE_IDS);
    edgeList.forEach(e => {{ need.add(e.from); need.add(e.to); }});
    const ids = visNodes.getIds();
    ids.forEach(id => {{ if (!need.has(id)) visNodes.remove(id); }});
    need.forEach(id => {{
      if (!visNodes.get(id)) {{
        const p = nodePayload(id);
        if (p) visNodes.add(p);
      }}
    }});
  }}

  function rebuildEdges(target) {{
    const slice = ALL_EDGES.slice(0, target);
    if (target < edgeUpto) {{
      visEdges.clear();
      visNodes.clear();
      edgeUpto = 0;
    }}
    if (slice.length > edgeUpto) {{
      visEdges.add(slice.slice(edgeUpto));
      syncNodesFromEdges(slice);
    }} else if (target === 0) {{
      visEdges.clear();
      visNodes.clear();
    }}
    edgeUpto = target;
    if (edgeUpto > 0 && !didFit) didFit = true;
  }}

  function setFrame(f) {{
    frame = Math.max(0, Math.min(f, TOTAL_FRAMES));
    if (slider) slider.value = frame;
    if (progressBar) progressBar.style.width = (TOTAL_FRAMES ? (frame / TOTAL_FRAMES * 100) : 0) + '%';
    if (frame <= PHASE0_END) {{
      showSourcesOnly();
    }} else {{
      rebuildEdges(targetEdgeCount(frame));
    }}
    const done = frame >= TOTAL_FRAMES;
    if (statusEl) statusEl.textContent = statusText(frame, edgeUpto, done);
    if (done && network) {{
      setTimeout(enableFloating, 450);
    }}
  }}

  function showDetail(nodeId) {{
    const m = NODE_META[nodeId];
    if (!m || !detail) return;
    document.getElementById('detailName').textContent = m.name;
    document.getElementById('detailType').innerHTML =
      '<span class="swatch" style="background:' + m.fill + ';border-color:' + m.border + '"></span>' + m.account_type;
    document.getElementById('detailStance').textContent = m.stance;
    document.getElementById('detailDeg').textContent = m.degree;
    document.getElementById('detailPr').textContent = m.pagerank;
    document.getElementById('detailBucket').textContent = m.bucket;
    detail.classList.add('show');
  }}

  function loop(ts) {{
    rafId = requestAnimationFrame(loop);
    if (paused || frame >= TOTAL_FRAMES) return;
    if (ts - lastTs < FRAME_MS) return;
    lastTs = ts;
    frame++;
    setFrame(frame);
  }}

  function startAutoplay() {{
    paused = false;
    disableFloating();
    if (pauseBtn) pauseBtn.textContent = '暂停';
    didFit = false;
    frame = 0;
    if (slider) slider.value = 0;
    if (progressBar) progressBar.style.width = '0%';
    fitFullLayout();
    setFrame(0);
    lastTs = 0;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(loop);
  }}

  function initNetwork() {{
    const container = document.getElementById('mynetwork');
    if (!container || typeof vis === 'undefined') {{
      if (statusEl) statusEl.textContent = 'vis-network 未加载，请检查网络/CDN';
      return;
    }}
    visNodes = new vis.DataSet([]);
    visEdges = new vis.DataSet([]);
    network = new vis.Network(container, {{ nodes: visNodes, edges: visEdges }}, {{
      physics: {{ enabled: false }},
      layout: {{ improvedLayout: false }},
      interaction: {{
        hover: true, dragNodes: true, dragView: true, zoomView: true,
        navigationButtons: true, tooltipDelay: 80, hideEdgesOnDrag: false
      }},
      nodes: {{
        shape: 'dot',
        fixed: true,
        borderWidth: 1,
        borderWidthSelected: 2,
        font: {{ size: 9, face: 'Microsoft YaHei, SimHei, sans-serif' }}
      }},
      edges: {{
        arrows: {{ to: {{ enabled: true, scaleFactor: 0.28 }} }},
        smooth: {{ enabled: true, type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.42 }},
        color: {{ inherit: false }},
        chosen: {{ edge: function(values) {{ values.width = values.width * 1.4; values.opacity = 0.85; }} }}
      }}
    }});
    network.on('hoverNode', function(p) {{
      if (!p.node || !nodeBase[p.node]) return;
      const b = nodeBase[p.node];
      visNodes.update({{
        id: p.node,
        label: b.label || String(p.node).slice(0, 14),
        font: {{ size: 10, color: '{PALETTE["text"]}', face: 'Microsoft YaHei, SimHei, sans-serif', strokeWidth: 2, strokeColor: '#FFFDF8' }}
      }});
    }});
    network.on('blurNode', function(p) {{
      if (!p.node || !nodeBase[p.node]) return;
      const b = nodeBase[p.node];
      if (!b.showLabel) visNodes.update({{ id: p.node, label: '' }});
    }});
    network.on('click', function(p) {{
      if (p.nodes.length) showDetail(p.nodes[0]);
      else if (detail) detail.classList.remove('show');
    }});
    network.on('hoverEdge', function(p) {{
      if (!p.edge) return;
      const e = visEdges.get(p.edge);
      if (e) container.title = (e.hopLabel || '') + ' · ' + (e.time || '') + ' · ' + e.from + ' → ' + e.to;
    }});
    network.on('blurEdge', function() {{ container.title = ''; }});
    resizeNetwork();
    window.addEventListener('resize', function() {{ resizeNetwork(); safeFit(); }});
    if (typeof ResizeObserver !== 'undefined') {{
      new ResizeObserver(function() {{ resizeNetwork(); safeFit(); }}).observe(container);
    }}
    var booted = false;
    function readyPlay() {{
      if (booted || !network) return;
      booted = true;
      resizeNetwork();
      startAutoplay();
    }}
    network.once('init', readyPlay);
    setTimeout(readyPlay, 80);
    setTimeout(function() {{ resizeNetwork(); fitFullLayout(); }}, 400);
  }}

  if (slider) slider.addEventListener('input', function() {{
    paused = true;
    if (pauseBtn) pauseBtn.textContent = '继续';
    if (rafId) cancelAnimationFrame(rafId);
    setFrame(+slider.value);
  }});
  if (pauseBtn) pauseBtn.addEventListener('click', function() {{
    paused = !paused;
    pauseBtn.textContent = paused ? '继续' : '暂停';
    if (!paused && frame < TOTAL_FRAMES) {{
      lastTs = 0;
      rafId = requestAnimationFrame(loop);
    }}
  }});
  if (replayBtn) replayBtn.addEventListener('click', startAutoplay);
  if (fullBtn) fullBtn.addEventListener('click', function() {{
    paused = true;
    if (pauseBtn) pauseBtn.textContent = '继续';
    if (rafId) cancelAnimationFrame(rafId);
    frame = TOTAL_FRAMES;
    if (slider) slider.value = TOTAL_FRAMES;
    setFrame(TOTAL_FRAMES);
    safeFit();
  }});
  if (resetViewBtn) resetViewBtn.addEventListener('click', safeFit);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initNetwork);
  else setTimeout(initNetwork, 50);
}})();
</script>
</body>
</html>"""

    path.write_text(html_body, encoding="utf-8")
    return filter_note


def write_network_html(path: Path, data: dict[str, Any]) -> str:
    """生成 fig_06 传播网络 HTML，返回子图筛选说明。"""
    return write_pyvis_temporal_network(path, data)


def analyze_repost_chain_depth(data: dict[str, Any]) -> dict[str, Any]:
    """核对 multihop 边表层级（crawl_hop 1/2/3）。"""
    edges = data["edges"]
    reposts = data["reposts"]
    author_col = pick_col(reposts, ["source_author", "root_source_user_name"])
    parent_col = pick_col(reposts, ["parent_user_name", "parent_user"])
    multihop = 0
    if author_col and parent_col and not reposts.empty:
        a = reposts[author_col].map(clean)
        p = reposts[parent_col].map(clean)
        multihop = int(((p != "") & (a != "") & (p != a)).sum())
    hot = int((edges["_bucket"] == "hot_repost").sum()) if "_bucket" in edges.columns else 0
    hop_s = edges["_hop"].map(clean) if "_hop" in edges.columns else pd.Series(dtype=str)
    n1 = int((hop_s == "1").sum())
    n2 = int((hop_s == "2").sum())
    n3 = int((hop_s == "3").sum())
    using_multihop = EDGES_MULTIHOP_PATH.exists() and EDGE_PATH.resolve() == EDGES_MULTIHOP_PATH.resolve()
    structure = (
        f"三层爬取边：一层核心源→直接转发 {n1} 条；二层热门种子帖→转发 {n2} 条；三层高互动帖→转发 {n3} 条"
        if using_multihop and (n2 or n3)
        else "一层：核心源作者 → 直接转发用户（星形）"
    )
    crawler_note = (
        "multihop 爬虫：对 top20 源帖爬一层；每源 Top10 互动种子再爬二层；二层中 reposts_count≥50 的帖再爬三层。"
        "边语义均为「被转发帖作者 source_user → 转发者 target_user」，故图上为多层星形，而非一条 A→B→C 折线；"
        "二层/三层边在 clean 中 parent_user 常不等于争议源作者。"
    )
    return {
        "total_edges": len(edges),
        "multihop_rows": multihop,
        "hop1_edges": n1,
        "hop2_edges": n2,
        "hop3_edges": n3,
        "hot_repost_edges": hot,
        "structure": structure,
        "crawler_note": crawler_note,
    }


def metric_rank_rows(metric: dict[str, float], user_type: dict[str, str], n: int = 10) -> list[dict[str, Any]]:
    rows = []
    for node, val in top_items(metric, n):
        rows.append({"节点": node, "值": f"{val:.6f}" if isinstance(val, float) and val < 1 else f"{val:.0f}", "账号类型": account_type_label(user_type.get(node, "ordinary_user"))})
    return rows


def node_role_notes(node_rank_df: pd.DataFrame, source_stats: pd.DataFrame, betweenness: dict[str, float]) -> str:
    source_authors = {clean(a) for a in source_stats.get("source_author", []) if clean(a)}
    top_pr = set(node_rank_df.head(8)["node"])
    top_between = {n for n, _ in top_items(betweenness, 6)} if betweenness else set()
    lines = ["|节点|角色|说明|", "|---|---|---|"]
    for _, row in node_rank_df.head(10).iterrows():
        n = row["node"]
        roles = []
        if n in source_authors:
            roles.append("源头节点")
        if n in top_pr:
            roles.append("放大节点")
        if n in top_between:
            roles.append("桥接节点")
        if not roles:
            roles.append("参与节点")
        lines.append(f"|{n}|{'、'.join(roles)}|PageRank={row['pagerank']:.6f}，度={int(row['degree'])}|")
    return "\n".join(lines)


def summarize_propagation_mode(
    source_stats: pd.DataFrame,
    node_rank_df: pd.DataFrame,
    type_counts: Counter,
    n_components: int,
    top3_ratio: float,
) -> str:
    type_str = ", ".join(f"{account_type_label(k)}{v}个" for k, v in type_counts.most_common(4))
    multi_center = top3_ratio < 0.75 and len(source_stats) >= 3
    headline = (
        "微博传播呈现**多中心扩散**：少数高互动主帖作为核心源，再经由普通用户、粉丝号、营销号与媒体号共同参与放大。"
        if multi_center
        else "微博传播呈现**头部源帖主导**特征，但仍有多条核心源微博分别吸纳转发，并非严格单点扩散。"
    )
    return (
        f"{headline}\n\n"
        f"- 前 3 个核心源约占采集边的 {top3_ratio:.1%}，说明存在头部集中但不等于唯一源头。\n"
        f"- 弱连通分量 {n_components} 个，反映多簇并行扩散。\n"
        f"- PageRank 前列节点包含 {', '.join(node_rank_df.head(5)['node'].astype(str).tolist())} 等账号。\n"
        f"- 节点类型构成（规则推断）：{type_str}。\n"
        f"- 当前 API 边表为「核心源→直接转发者」二层星形结构（见下文「传播层级」），不含转发的转发第三跳。"
    )


def write_report(data: dict[str, Any], check: dict[str, Any], node_rank_df: pd.DataFrame, heat_df: pd.DataFrame):
    import networkx as nx

    graph = data["graph"]
    edges = data["edges"]
    sources = data["sources"]
    source_stats = data["source_stats"]
    time_summary = data["time_summary"]
    user_type = data["user_type"]
    betweenness = data.get("betweenness", {})
    weak_components = list(nx.weakly_connected_components(graph)) if graph.number_of_nodes() else []
    largest_component = max((len(c) for c in weak_components), default=0)
    density = nx.density(graph) if graph.number_of_nodes() > 1 else 0
    avg_degree = sum(dict(graph.degree()).values()) / graph.number_of_nodes() if graph.number_of_nodes() else 0
    bucket_counts = Counter(edges["_bucket"])
    type_counts = Counter(user_type.get(n, "ordinary_user") for n in graph.nodes)
    top3 = int(source_stats.head(3)["direct_reposts_in_edges"].sum()) if not source_stats.empty else 0
    total = int(source_stats["direct_reposts_in_edges"].sum()) if not source_stats.empty else 0
    top3_ratio = top3 / total if total else 0

    file_lines = "\n".join(f"|{f['label']}|{f['rows']}|{len(f['columns'])}|`{f['path']}`|" for f in check["files"])

    top_nodes = node_rank_df.head(10).copy()
    top_nodes["PageRank"] = top_nodes["pagerank"].map(lambda x: f"{x:.6f}")
    top_nodes["账号类型"] = top_nodes["user_type"].map(account_type_label)
    top_nodes["节点"] = top_nodes["node"]
    top_nodes["总度"] = top_nodes["degree"].astype(int).astype(str)

    mode_text = summarize_propagation_mode(source_stats, node_rank_df, type_counts, len(weak_components), top3_ratio)

    report = f"""# 微博转发传播链分析报告

## 1. 数据概况

本报告为《年轮》争议微博**传播链 / 网络分析（C 组）**。传播网络边与节点来自 **`output_recrawl`** API 重爬结果；核心源微博清单与平台互动量来自 **`output/top_source_posts.csv`**（仅元数据，不混用旧 `repost_edges.csv`）。转发文本优先用 `output_recrawl/weibo_reposts_api_clean.csv`，并可用 **`E_data/weibo_reposts_clean.csv`** 补充用户文本。

|数据文件|行数|主要字段数|路径|
|---|---:|---:|---|
{file_lines}

**检查结果：**

- 重复边（同 source/target/post）：{check['edge_dup']} 条
- 重复节点名：{check['node_dup']} 个
- 网络节点 {check['n_nodes']}、边 {check['n_edges']}、核心源 {check['n_sources']} 条
- 弱连通分量 {check['n_components']} 个，最大分量 {check['largest_component']} 节点
- 是否适合画网络图：{'是' if check['suitable_for_network'] else '否'}
- 采样窗口：{", ".join(f"{BUCKET_LABELS.get(k,k)}={v}" for k, v in bucket_counts.most_common())}
- 时间范围说明：{check.get('event_window', '')} 为争议爆发窗口；窗口外边 {check.get('outside_event_window_rows', 0)} / {check.get('original_edge_rows', check['n_edges'])} 条作为后续长尾转发保留，用于观察议题延续传播。

参考 `repost_chain_summary.md` 摘要（前 500 字，不替代本报告计算）：{data.get('chain_summary_excerpt', '（文件不存在）')[:200]}…

## 2. 网络整体结构

|指标|数值|
|---|---:|
|节点数|{graph.number_of_nodes()}|
|边数|{graph.number_of_edges()}|
|弱连通分量|{len(weak_components)}|
|最大连通分量|{largest_component}|
|平均度|{avg_degree:.3f}|
|网络密度|{density:.8f}|

### 入度 Top10

{md_table(metric_rank_rows(data['indegree'], user_type), ["节点", "值", "账号类型"])}

### 出度 Top10

{md_table(metric_rank_rows(data['outdegree'], user_type), ["节点", "值", "账号类型"])}

### PageRank Top10

{md_table(metric_rank_rows(data['pagerank'], user_type), ["节点", "值", "账号类型"])}

### 度中心性 Top10

{md_table(metric_rank_rows(data['degree_centrality'], user_type), ["节点", "值", "账号类型"])}

交互式网络图筛选规则：{data.get('network_filter_note', '见 data_check')}。**完整网络的上述指标仍基于全部节点与边计算**；图中按时间自动展开，节点填充=立场、外圈=账号类型，点击节点在侧栏显示详情（非原生 tooltip，避免换行符乱码）。

## 3. 核心传播节点

{md_table(top_nodes.to_dict("records"), ["节点", "PageRank", "总度", "账号类型"], 10)}

### 节点角色（规则 + 结构推断）

{node_role_notes(node_rank_df, source_stats, betweenness)}

- **源头节点**：出现在 `top_source_posts.csv` 的作者，或其主帖被大量转发。
- **放大节点**：PageRank / 总度靠前，在多条转发关系中处于中心。
- **桥接节点**：介数中心性靠前（仅在小规模网络上计算），可能连接不同传播簇。

当前边表为二层 `source_user → target_user`，无法还原完整多跳父子链，桥接判断仅供参考。

## 4. 核心源微博分析

|作者|采集边|涉及节点|深度替代|转发|评论|点赞|
|---|---:|---:|---:|---:|---:|---:|
"""
    for _, row in source_stats.head(12).iterrows():
        report += (
            f"|{row['source_author']}|{row['direct_reposts_in_edges']}|{row['involved_nodes']}|"
            f"{row['estimated_depth']}|{row['repost_count']}|{row['comment_count']}|{row['like_count']}|\n"
        )
    report += f"""
**说明：** 无多跳层级字段时，以「直接转发边数」和「涉及节点数」替代传播深度。

前 3 个核心源占采集边 **{top3_ratio:.1%}**（{top3}/{total}）。{'存在少数头部源帖，同时多条核心源各自形成传播簇，更接近多中心扩散。' if top3_ratio < 0.8 else '头部源帖占比较高，但仍有多条核心源并存。'}

## 5. 账号类型与传播角色

账号类型优先读取节点表字段；缺失时按用户名/文本关键词弱规则推断（媒体/粉丝/营销/普通用户等），**不等于平台认证身份**。

节点构成：{", ".join(f"{account_type_label(k)}={v}" for k, v in type_counts.most_common())}。

不同类型在传播中可能承担：媒体号放大公共讨论、粉丝号圈层扩散、营销号二次搬运、普通用户情绪与立场表达。具体占比见 `fig_08` / `fig_09`。

## 6. 传播模式总结

{mode_text}

## 7. 可视化说明

正式出图采用 `风格规范.md` 中 C 模块命名与版式（赤陶松烟配色）：

|文件|内容|
|---|---|
|`fig_06_repost_network.html`|vis-network 交互图：**核心源→直接转发者**二层星形；节点填充=立场、外圈=账号类型；打开后自动按时间展开；点击节点看侧栏详情|
|`fig_07_top_source_posts.png`|核心源气泡图：横轴采集转发边，纵轴转评赞总量，大小=涉及节点，颜色=叙事|
|`fig_08_top_repost_nodes.png`|关键转发节点棒棒糖图：PageRank + 度数，颜色=账号类型|
|`fig_09_account_type_network.png`|账号类型甜甜圈 + 发出/接收边堆叠柱|
|`fig_10_source_type_spread_matrix.png`|核心源 × 目标账号类型扩散热力图（二层结构替代深度图）|

旧版柱状/简化命名图已归档至 `figures/past/`。

## 8. 传播层级说明（为何图上只有「一层转发」）

{data.get('chain_depth', {}).get('crawler_note', '')}

|项目|数值/说明|
|---|---|
|边表总条数|{data.get('chain_depth', {}).get('total_edges', len(edges))}|
|parent_user ≠ 源作者（多跳）|{data.get('chain_depth', {}).get('multihop_rows', 0)} 条|
|热门转发采样边|{data.get('chain_depth', {}).get('hot_repost_edges', 0)} 条|
|网络形态|{data.get('chain_depth', {}).get('structure', '二层星形')}|

爬虫里的「热门」= **采样优先级**（第一页前排 + 优先入库），不是「再爬一层转发列表」。若图上要 A→B→C，需在现有爬虫之外对中间帖 `repost_mblogid` 再调 `repostTimeline`（当前代码未包含该循环）。

## 9. 局限性

1. **非全量数据**：仅为 API 可见范围内的采样转发，非微博全站转发链。
2. **仅二层边**：不含「转发的转发」，多跳传播需二次爬取中间节点。
3. **账号类型误判**：规则推断不能替代真实身份，存在媒体/粉丝/营销误判。
4. **平台可见性**：删除、权限、反爬导致边与节点不完整。
5. **时间窗口补足**：部分源帖依赖 +1/+3/+7 天补采，各源采样窗口不均衡（见 `recrawl_time_window_summary.csv`）。

---
*由 `analyze_repost_network.py` 自动生成。*
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> int:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    data = prepare_data()
    check = inspect_data(data)
    print_data_check(check)
    write_data_check_md(check)
    graph = data["graph"]
    pagerank = data["pagerank"]
    degree = data["degree"]
    indegree = data["indegree"]
    outdegree = data["outdegree"]
    degree_centrality = data["degree_centrality"]
    user_type = data["user_type"]
    edges = data["edges"]

    node_rank_df = pd.DataFrame(
        [
            {
                "node": n,
                "user_type": user_type.get(n, "ordinary_user"),
                "in_degree": indegree.get(n, 0),
                "out_degree": outdegree.get(n, 0),
                "degree": degree.get(n, 0),
                "pagerank": pagerank.get(n, 0),
                "degree_centrality": degree_centrality.get(n, 0),
            }
            for n in graph.nodes
        ]
    ).sort_values(["pagerank", "degree"], ascending=False)

    type_node_counts = Counter(user_type.get(n, "ordinary_user") for n in graph.nodes)
    type_edge_out = Counter()
    type_edge_in = Counter()
    for u, v, d in graph.edges(data=True):
        w = d.get("weight", 1)
        type_edge_out[user_type.get(u, "ordinary_user")] += w
        type_edge_in[user_type.get(v, "ordinary_user")] += w

    sources = data["sources"]
    source_author_by_post = {}
    for _, row in sources.iterrows():
        pid = clean(row.get("source_post_id", row.get("post_id", "")))
        author = clean(row.get("source_author", row.get("author_name", "")))
        if pid:
            source_author_by_post[pid] = author

    heat_rows = []
    for _, row in edges.iterrows():
        post_id = row["_post_id"]
        source_author = source_author_by_post.get(post_id, row["_source"])
        heat_rows.append({"source_author": source_author, "target_type": user_type.get(row["_target"], "ordinary_user")})
    heat_df = pd.DataFrame(heat_rows)
    if not heat_df.empty:
        heat_df = heat_df.groupby(["source_author", "target_type"]).size().unstack(fill_value=0)
        row_order = heat_df.sum(axis=1).sort_values(ascending=False).head(12).index
        heat_df = heat_df.loc[row_order]

    # 传播网络（PyVis/vis-network，打开自动按时间展开）
    data["chain_depth"] = analyze_repost_chain_depth(data)
    network_note = write_network_html(FIG_DIR / "fig_06_repost_network.html", data)
    data["network_filter_note"] = network_note

    # 正式图表（风格规范：气泡 / 棒棒糖 / 甜甜圈+堆叠柱 / 热力图）
    write_source_bubble(FIG_DIR / "fig_07_top_source_posts.png", data["source_stats"])
    write_lollipop_top_nodes(FIG_DIR / "fig_08_top_repost_nodes.png", node_rank_df)
    write_account_type_distribution(FIG_DIR / "fig_09_account_type_network.png", type_node_counts, type_edge_out, type_edge_in)
    write_source_type_heatmap(FIG_DIR / "fig_10_source_type_spread_matrix.png", heat_df, fig_num="10")
    write_source_bubble_html(FIG_DIR / "fig_07_top_source_posts.html", data["source_stats"])
    write_lollipop_top_nodes_html(FIG_DIR / "fig_08_top_repost_nodes.html", node_rank_df)
    write_account_type_distribution_html(FIG_DIR / "fig_09_account_type_network.html", type_node_counts, type_edge_out, type_edge_in)
    write_source_type_heatmap_html(FIG_DIR / "fig_10_source_type_spread_matrix.html", heat_df)

    write_report(data, check, node_rank_df, heat_df)
    print(f"传播层级：多跳边 {data['chain_depth']['multihop_rows']} 条；{data['chain_depth']['structure']}")

    outputs = [
        DATA_CHECK_PATH,
        REPORT_PATH,
        FIG_DIR / "fig_06_repost_network.html",
        FIG_DIR / "fig_07_top_source_posts.png",
        FIG_DIR / "fig_07_top_source_posts.html",
        FIG_DIR / "fig_08_top_repost_nodes.png",
        FIG_DIR / "fig_08_top_repost_nodes.html",
        FIG_DIR / "fig_09_account_type_network.png",
        FIG_DIR / "fig_09_account_type_network.html",
        FIG_DIR / "fig_10_source_type_spread_matrix.png",
        FIG_DIR / "fig_10_source_type_spread_matrix.html",
    ]
    print("分析完成，输出文件如下：")
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="C 组传播链/网络分析可视化")
    parser.parse_args()
    raise SystemExit(main())
