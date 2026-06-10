"""
多层转发爬取（二层为主、三层止损）

不覆盖 output_recrawl 下原有 *_api.csv。
产出见 MULTIHOP_* 路径与 multihop_crawl_summary.md。

一层：20 源 × 最多 200 条 raw，clean 优先当天再 +1/+3/+7（与 api 版相同逻辑）
二层：每源 Top10 热门种子 × 每种子最多 50 条
三层：仅当二层帖 reposts_count>=50，每帖最多 30 条，全局最多 1000 条
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# 复用一层爬虫的解析与工具（不修改原文件）
import recrawl_weibo_reposts_api as api

from c_project_paths import PROFILE_DIR, RECRAWL_DIR as OUT_DIR, SOURCE_PATH

RAW_MULTIHOP = OUT_DIR / "weibo_reposts_api_raw_multihop.csv"
CLEAN_MULTIHOP = OUT_DIR / "weibo_reposts_api_clean_multihop.csv"
EDGES_MULTIHOP = OUT_DIR / "repost_edges_multihop.csv"
NODES_MULTIHOP = OUT_DIR / "repost_nodes_multihop.csv"
SEEDS_OUT = OUT_DIR / "hot_repost_seeds.csv"
SUMMARY_OUT = OUT_DIR / "multihop_crawl_summary.md"

EXTRA_COLUMNS = [
    "crawl_hop",
    "root_source_post_id",
    "timeline_post_id",
    "parent_seed_repost_id",
]

RAW_COLUMNS_MULTIHOP = api.RAW_COLUMNS + EXTRA_COLUMNS


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def engagement_score(row: pd.Series) -> int:
    return (
        int(pd.to_numeric(row.get("repost_reposts_count"), errors="coerce") or 0)
        + int(pd.to_numeric(row.get("repost_comments_count"), errors="coerce") or 0)
        + int(pd.to_numeric(row.get("repost_attitudes_count"), errors="coerce") or 0)
    )


def enrich_row(
    row: dict[str, Any],
    hop: int,
    root_source_post_id: str,
    timeline_post_id: str,
    parent_seed_repost_id: str = "",
) -> dict[str, Any]:
    row = dict(row)
    row["crawl_hop"] = hop
    row["root_source_post_id"] = root_source_post_id
    row["timeline_post_id"] = timeline_post_id
    row["parent_seed_repost_id"] = parent_seed_repost_id
    return row


def fetch_timeline(
    context,
    timeline_meta: pd.Series,
    timeline_post_id: str,
    max_items: int,
    sleep: float,
    hop: int,
    root_source_post_id: str,
    parent_seed_repost_id: str = "",
) -> list[dict[str, Any]]:
    """对指定帖子 id 拉转发列表（不按 countable 提前停止，最多 max_items 条）。"""
    url = api.clean(timeline_meta.get("source_post_url", ""))
    mblogid = ""
    if "/" in url:
        mblogid = url.split("?")[0].rstrip("/").split("/")[-1]
    post_id = api.clean(timeline_post_id) or api.clean(timeline_meta.get("source_post_id"))
    referer = url or "https://weibo.com"
    rows: list[dict[str, Any]] = []
    page = 1
    while len(rows) < max_items:
        api_url = f"https://weibo.com/ajax/statuses/repostTimeline?id={post_id or mblogid}&page={page}&count=20&moduleID=feed"
        response = context.request.get(api_url, headers={"Referer": referer})
        if response.status != 200:
            raise RuntimeError(f"API status={response.status}, url={api_url}, body={response.text()[:300]}")
        data = response.json()
        if data.get("ok") != 1:
            raise RuntimeError(f"API ok != 1, url={api_url}, body={json.dumps(data, ensure_ascii=False)[:500]}")
        items = data.get("data") or []
        if not items:
            break
        for rank_in_page, item in enumerate(items, start=1):
            row = api.parse_item(timeline_meta, item, page, rank_in_page, data)
            rows.append(
                enrich_row(row, hop, root_source_post_id, post_id or mblogid, parent_seed_repost_id)
            )
            if len(rows) >= max_items:
                break
        max_page = int(data.get("max_page") or page)
        if page >= max_page:
            break
        page += 1
        if sleep:
            time.sleep(sleep)
    return rows


def layer1_from_existing_api_clean() -> pd.DataFrame:
    """把已有的一层 api clean 标上 hop 字段，用于 --reuse-layer1。"""
    path = OUT_DIR / "weibo_reposts_api_clean.csv"
    if not path.exists():
        raise FileNotFoundError(f"未找到一层数据：{path}，请先运行 recrawl_weibo_reposts_api.py 或去掉 --reuse-layer1")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    df["crawl_hop"] = "1"
    df["root_source_post_id"] = df["source_post_id"].map(api.clean)
    df["timeline_post_id"] = df["root_source_post_id"]
    df["parent_seed_repost_id"] = ""
    return df


def clean_layer1(raw_l1: pd.DataFrame, min_kept_per_source: int) -> pd.DataFrame:
    work = raw_l1.copy()
    if "crawl_hop" not in work.columns:
        work["crawl_hop"] = "1"
    work = work[~work["is_generic_repost"].astype(str).str.lower().isin(["true", "1"])].copy()
    # 时间窗按 root 源帖分组
    kept_parts = []
    for root_id, sub in work.groupby("root_source_post_id", dropna=False):
        sub = sub.copy()
        sub["source_post_id"] = root_id
        kept_sub, _ = api.apply_hot_and_source_day_filter(sub, min_kept_per_source)
        kept_parts.append(kept_sub)
    if not kept_parts:
        return work.iloc[0:0].copy()
    out = pd.concat(kept_parts, ignore_index=True)
    for col in EXTRA_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out["crawl_hop"] = "1"
    return out


def clean_generic_only(raw_df: pd.DataFrame) -> pd.DataFrame:
    return raw_df[~raw_df["is_generic_repost"].astype(str).str.lower().isin(["true", "1"])].copy()


def select_layer2_seeds(l1_clean: pd.DataFrame, seeds_per_source: int, require_reposts: bool) -> pd.DataFrame:
    rows = []
    for root_id, sub in l1_clean.groupby("root_source_post_id", dropna=False):
        cand = sub.copy()
        if require_reposts:
            cand = cand[pd.to_numeric(cand["repost_reposts_count"], errors="coerce").fillna(0) > 0]
        if cand.empty:
            cand = sub.copy()
        cand["_score"] = cand.apply(engagement_score, axis=1)
        cand = cand.sort_values("_score", ascending=False).head(seeds_per_source)
        for rank, (_, row) in enumerate(cand.iterrows(), start=1):
            rows.append(
                {
                    "root_source_post_id": root_id,
                    "root_source_author": api.clean(row.get("source_author", "")),
                    "seed_rank": rank,
                    "seed_repost_id": api.clean(row.get("repost_id", "")),
                    "seed_mblogid": api.clean(row.get("repost_mblogid", "")),
                    "seed_repost_url": api.clean(row.get("repost_url", "")),
                    "seed_user_name": api.clean(row.get("repost_user_name", "")),
                    "seed_reposts_count": api.clean(row.get("repost_reposts_count", "")),
                    "seed_comments_count": api.clean(row.get("repost_comments_count", "")),
                    "seed_attitudes_count": api.clean(row.get("repost_attitudes_count", "")),
                    "engagement_score": int(row["_score"]),
                    "crawl_hop_planned": 2,
                }
            )
    return pd.DataFrame(rows)


def build_edges_nodes(clean_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edges = pd.DataFrame(
        {
            "root_source_post_id": clean_df["root_source_post_id"],
            "source_post_id": clean_df["source_post_id"],
            "crawl_hop": clean_df["crawl_hop"],
            "timeline_post_id": clean_df["timeline_post_id"],
            "parent_seed_repost_id": clean_df.get("parent_seed_repost_id", ""),
            "source_user": clean_df["parent_user_name"].where(
                clean_df["parent_user_name"].astype(str).str.len().gt(0), clean_df["source_author"]
            ),
            "target_user": clean_df["repost_user_name"],
            "edge_type": clean_df["crawl_hop"].map(lambda h: f"hop_{h}"),
            "repost_time": clean_df["repost_time"],
            "repost_id": clean_df["repost_id"],
            "repost_url": clean_df["repost_url"],
            "repost_text": clean_df["repost_text"],
            "repost_reposts_count": clean_df["repost_reposts_count"],
            "repost_comments_count": clean_df["repost_comments_count"],
            "repost_attitudes_count": clean_df["repost_attitudes_count"],
            "sampling_bucket": clean_df.get("sampling_bucket", ""),
            "possible_hot_repost": clean_df.get("possible_hot_repost", ""),
            "crawl_time": clean_df["crawl_time"],
        }
    )
    node_rows = []
    for user, sub in clean_df.groupby("repost_user_name", dropna=True):
        if not api.clean(user):
            continue
        node_rows.append(
            {
                "user_name": user,
                "user_id": sub["repost_user_id"].iloc[0],
                "user_url": sub["repost_user_url"].iloc[0],
                "repost_count": len(sub),
                "max_crawl_hop": int(pd.to_numeric(sub["crawl_hop"], errors="coerce").max()),
                "first_seen_time": sub["repost_time"].min(),
                "last_seen_time": sub["repost_time"].max(),
            }
        )
    return edges, pd.DataFrame(node_rows)


def write_summary(
    raw_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    seeds_df: pd.DataFrame,
    stats: dict[str, Any],
) -> None:
    hop_counts = clean_df["crawl_hop"].value_counts().to_dict() if not clean_df.empty else {}
    lines = [
        "# 多层转发爬取汇总 (multihop)",
        "",
        f"- 生成时间：{now_string()}",
        f"- 策略：一层 20 源×200；二层每源 10 种子×50；三层 reposts_count≥50 每帖 30、全局≤1000",
        "",
        "## 规模",
        "",
        f"- raw 总行数：{len(raw_df)}",
        f"- clean 总行数：{len(clean_df)}",
        f"- 二层种子数：{len(seeds_df)}",
        f"- 各层 clean 条数：{hop_counts}",
        f"- 实际二层爬取种子：{stats.get('l2_crawled', 0)}",
        f"- 实际三层爬取帖子：{stats.get('l3_crawled', 0)}",
        "",
        "## 输出文件",
        "",
        f"- `{RAW_MULTIHOP}`",
        f"- `{CLEAN_MULTIHOP}`",
        f"- `{EDGES_MULTIHOP}`",
        f"- `{NODES_MULTIHOP}`",
        f"- `{SEEDS_OUT}`",
        "",
        "## 边语义",
        "",
        "- hop_1：核心源作者 → 直接转发用户（源帖时间线）",
        "- hop_2：一层热门种子用户 → 该帖的转发者",
        "- hop_3：二层高互动帖作者 → 该帖的转发者",
        "",
        "## 与一层 api 数据关系",
        "",
        "- 原 `repost_edges_api.csv` 等**不覆盖**，仍可继续做「仅直接转发」分析。",
        "- 传播链网络分析请优先读 `repost_edges_multihop.csv`。",
        "",
    ]
    SUMMARY_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="二层/三层转发爬取（新文件，不覆盖 api 版）")
    parser.add_argument("--limit-sources", type=int, default=20)
    parser.add_argument("--layer1-max", type=int, default=200, help="每层源帖一层转发 raw 上限")
    parser.add_argument("--layer1-min-kept", type=int, default=50, help="一层 clean 每源至少保留（时间窗补足）")
    parser.add_argument("--seeds-per-source", type=int, default=10)
    parser.add_argument("--layer2-max", type=int, default=50)
    parser.add_argument("--layer3-max", type=int, default=30)
    parser.add_argument("--layer3-min-reposts", type=int, default=50)
    parser.add_argument("--layer3-global-cap", type=int, default=1000)
    parser.add_argument("--sleep", type=float, default=0.8)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--login-wait", type=int, default=20)
    parser.add_argument(
        "--reuse-layer1",
        action="store_true",
        help="不重新爬一层，从已有 weibo_reposts_api_clean.csv 导入（仍写入 multihop 文件）",
    )
    parser.add_argument(
        "--seeds-only",
        action="store_true",
        help="仅根据已有 clean_multihop 的一层生成 hot_repost_seeds.csv 后退出（不请求 API）",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stats: dict[str, Any] = {"l2_crawled": 0, "l3_crawled": 0}

    if args.seeds_only:
        if not CLEAN_MULTIHOP.exists():
            raise FileNotFoundError(f"需要已有 {CLEAN_MULTIHOP}")
        l1 = pd.read_csv(CLEAN_MULTIHOP, encoding="utf-8-sig", dtype=str).fillna("")
        l1 = l1[l1["crawl_hop"].astype(str) == "1"]
        seeds = select_layer2_seeds(l1, args.seeds_per_source, require_reposts=True)
        api.safe_to_csv(seeds, SEEDS_OUT, index=False, encoding="utf-8-sig")
        print(f"已写入种子表：{SEEDS_OUT}（{len(seeds)} 条）")
        return 0

    all_raw: list[dict[str, Any]] = []
    l1_clean = pd.DataFrame()
    l2_raw_rows: list[dict[str, Any]] = []
    l3_raw_rows: list[dict[str, Any]] = []
    seeds_df = pd.DataFrame()
    sources = api.read_sources(args.limit_sources)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=not args.headful,
            viewport={"width": 1360, "height": 900},
            locale="zh-CN",
        )
        if args.headful:
            page = context.new_page()
            page.goto("https://weibo.com", wait_until="domcontentloaded", timeout=45_000)
            print(f"请确认微博已登录；等待 {args.login_wait} 秒。")
            page.wait_for_timeout(args.login_wait * 1000)
            page.close()

        # —— 一层 ——
        if args.reuse_layer1:
            print("复用已有 weibo_reposts_api_clean.csv 作为一层…")
            l1_clean = layer1_from_existing_api_clean()
            raw_l1_path = OUT_DIR / "weibo_reposts_api_raw.csv"
            if raw_l1_path.exists():
                raw_l1 = pd.read_csv(raw_l1_path, encoding="utf-8-sig", dtype=str).fillna("")
                for col in EXTRA_COLUMNS:
                    if col not in raw_l1.columns:
                        if col == "crawl_hop":
                            raw_l1[col] = "1"
                        elif col == "root_source_post_id":
                            raw_l1[col] = raw_l1["source_post_id"]
                        elif col == "timeline_post_id":
                            raw_l1[col] = raw_l1["source_post_id"]
                        else:
                            raw_l1[col] = ""
                all_raw.extend(raw_l1.to_dict("records"))
        else:
            print(f"爬取一层：{len(sources)} 条核心源…")
            for idx, source in sources.iterrows():
                root_id = api.clean(source.get("source_post_id", ""))
                print(f"  [L1 {idx+1}/{len(sources)}] {root_id} {source.get('source_author','')}")
                got = api.fetch_reposts_for_source(
                    context,
                    source,
                    args.layer1_max,
                    args.layer1_min_kept,
                    keep_generic=True,
                    sleep=args.sleep,
                )
                for row in got:
                    all_raw.append(
                        enrich_row(row, 1, root_id, root_id, "")
                    )
                print(f"    got {len(got)}")
            l1_raw = pd.DataFrame(all_raw)
            l1_raw = l1_raw[l1_raw["crawl_hop"].astype(str) == "1"] if "crawl_hop" in l1_raw.columns else l1_raw
            l1_clean = clean_layer1(l1_raw, args.layer1_min_kept)

        # —— 二层种子 ——
        seeds_df = select_layer2_seeds(l1_clean, args.seeds_per_source, require_reposts=True)
        api.safe_to_csv(seeds_df, SEEDS_OUT, index=False, encoding="utf-8-sig")
        print(f"二层种子：{len(seeds_df)} 条 → {SEEDS_OUT}")

        # —— 二层爬取 ——
        for i, seed in seeds_df.iterrows():
            root_id = api.clean(seed["root_source_post_id"])
            seed_id = api.clean(seed["seed_repost_id"])
            if not seed_id:
                continue
            root_row = sources[sources["source_post_id"].astype(str) == str(root_id)]
            if root_row.empty:
                meta = pd.Series(
                    {
                        "source_post_id": root_id,
                        "source_post_url": "",
                        "source_author": seed.get("root_source_author", ""),
                        "publish_time": "",
                    }
                )
            else:
                meta = root_row.iloc[0]
            timeline_meta = pd.Series(
                {
                    "source_post_id": seed_id,
                    "source_post_url": api.clean(seed.get("seed_repost_url", "")),
                    "source_author": api.clean(seed.get("seed_user_name", "")),
                    "publish_time": api.clean(meta.get("publish_time", "")),
                }
            )
            print(f"  [L2 {i+1}/{len(seeds_df)}] seed={seed_id[:12]}… user={seed.get('seed_user_name','')}")
            try:
                got2 = fetch_timeline(
                    context,
                    timeline_meta,
                    seed_id,
                    args.layer2_max,
                    args.sleep,
                    hop=2,
                    root_source_post_id=root_id,
                    parent_seed_repost_id="",
                )
                l2_raw_rows.extend(got2)
                stats["l2_crawled"] += 1
                print(f"    got {len(got2)}")
            except Exception as exc:
                print(f"    L2 失败: {exc}")
            time.sleep(args.sleep)

        all_raw.extend(l2_raw_rows)
        l2_clean = clean_generic_only(pd.DataFrame(l2_raw_rows)) if l2_raw_rows else pd.DataFrame()

        # —— 三层 ——
        l3_count = 0
        if not l2_clean.empty:
            l2_clean["_rp"] = pd.to_numeric(l2_clean["repost_reposts_count"], errors="coerce").fillna(0)
            l3_candidates = l2_clean[l2_clean["_rp"] >= args.layer3_min_reposts].copy()
            l3_candidates["_score"] = l3_candidates.apply(engagement_score, axis=1)
            l3_candidates = l3_candidates.sort_values("_score", ascending=False)
            for _, row in l3_candidates.iterrows():
                if l3_count >= args.layer3_global_cap:
                    break
                root_id = api.clean(row["root_source_post_id"])
                post_id = api.clean(row["repost_id"])
                if not post_id:
                    continue
                timeline_meta = pd.Series(
                    {
                        "source_post_id": post_id,
                        "source_post_url": api.clean(row.get("repost_url", "")),
                        "source_author": api.clean(row.get("repost_user_name", "")),
                        "publish_time": "",
                    }
                )
                parent_seed = api.clean(row.get("parent_seed_repost_id", ""))
                print(f"  [L3] post={post_id[:12]}… reposts={row['_rp']}")
                try:
                    got3 = fetch_timeline(
                        context,
                        timeline_meta,
                        post_id,
                        args.layer3_max,
                        args.sleep,
                        hop=3,
                        root_source_post_id=root_id,
                        parent_seed_repost_id=parent_seed or api.clean(row.get("timeline_post_id", "")),
                    )
                    l3_raw_rows.extend(got3)
                    l3_count += len(got3)
                    stats["l3_crawled"] += 1
                    print(f"    got {len(got3)} (累计 L3 raw {l3_count})")
                except Exception as exc:
                    print(f"    L3 失败: {exc}")
                time.sleep(args.sleep)

        all_raw.extend(l3_raw_rows)
        context.close()

    raw_df = pd.DataFrame(all_raw)
    for col in RAW_COLUMNS_MULTIHOP:
        if col not in raw_df.columns:
            raw_df[col] = ""
    raw_df = raw_df[RAW_COLUMNS_MULTIHOP]
    api.safe_to_csv(raw_df, RAW_MULTIHOP, index=False, encoding="utf-8-sig")

    l2_final = clean_generic_only(pd.DataFrame(l2_raw_rows)) if l2_raw_rows else pd.DataFrame()
    l3_final = clean_generic_only(pd.DataFrame(l3_raw_rows)) if l3_raw_rows else pd.DataFrame()
    clean_parts = [x for x in (l1_clean, l2_final, l3_final) if not x.empty]
    clean_df = pd.concat(clean_parts, ignore_index=True) if clean_parts else pd.DataFrame()
    for col in RAW_COLUMNS_MULTIHOP:
        if col not in clean_df.columns:
            clean_df[col] = ""
    api.safe_to_csv(clean_df, CLEAN_MULTIHOP, index=False, encoding="utf-8-sig")

    edges_df, nodes_df = build_edges_nodes(clean_df)
    api.safe_to_csv(edges_df, EDGES_MULTIHOP, index=False, encoding="utf-8-sig")
    api.safe_to_csv(nodes_df, NODES_MULTIHOP, index=False, encoding="utf-8-sig")

    write_summary(raw_df, clean_df, seeds_df, stats)

    print("多层爬取完成：")
    for path in (RAW_MULTIHOP, CLEAN_MULTIHOP, EDGES_MULTIHOP, NODES_MULTIHOP, SEEDS_OUT, SUMMARY_OUT):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
