from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import pandas as pd


from c_project_paths import PROFILE_DIR, RECRAWL_DIR as OUT_DIR, SOURCE_PATH

RAW_OUT = OUT_DIR / "weibo_reposts_api_raw.csv"
CLEAN_OUT = OUT_DIR / "weibo_reposts_api_clean.csv"
EDGES_OUT = OUT_DIR / "repost_edges_api.csv"
NODES_OUT = OUT_DIR / "repost_nodes_api.csv"
QUALITY_OUT = OUT_DIR / "recrawl_api_quality_check.md"
TIME_WINDOW_OUT = OUT_DIR / "recrawl_time_window_summary.csv"


RAW_COLUMNS = [
    "source_post_id",
    "source_post_url",
    "source_author",
    "source_publish_time",
    "root_source_id",
    "root_source_mblogid",
    "root_source_user_id",
    "root_source_user_name",
    "repost_id",
    "repost_mid",
    "repost_mblogid",
    "repost_url",
    "repost_user_id",
    "repost_user_name",
    "repost_user_url",
    "repost_time",
    "repost_text",
    "is_generic_repost",
    "repost_source_device",
    "repost_reposts_count",
    "repost_comments_count",
    "repost_attitudes_count",
    "parent_id",
    "parent_mblogid",
    "parent_user_id",
    "parent_user_name",
    "api_page",
    "rank_in_page",
    "is_first_page",
    "possible_hot_repost",
    "sampling_bucket",
    "is_source_day_repost",
    "is_sampling_kept",
    "api_total_number",
    "api_max_page",
    "raw_json",
    "crawl_time",
]


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def parse_weibo_created_at(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value


def same_calendar_day(left: str, right: str) -> bool:
    left_dt = pd.to_datetime(clean(left), errors="coerce")
    right_dt = pd.to_datetime(clean(right), errors="coerce")
    if pd.isna(left_dt) or pd.isna(right_dt):
        return False
    return left_dt.date() == right_dt.date()


def bucket_for_row(row: dict[str, Any]) -> str:
    if bool(row.get("possible_hot_repost")):
        return "hot_repost"
    source_dt = pd.to_datetime(clean(row.get("source_publish_time")), errors="coerce")
    repost_dt = pd.to_datetime(clean(row.get("repost_time")), errors="coerce")
    if pd.isna(source_dt) or pd.isna(repost_dt):
        return "other_time"
    day_delta = (repost_dt.date() - source_dt.date()).days
    if day_delta == 0:
        return "source_day"
    if day_delta == 1:
        return "plus_1_day"
    if 2 <= day_delta <= 3:
        return "plus_3_day"
    if 4 <= day_delta <= 7:
        return "plus_7_day"
    return "other_time"


def is_countable_sampling_row(row: dict[str, Any], keep_generic: bool) -> bool:
    if not keep_generic and bool(row.get("is_generic_repost")):
        return False
    return bucket_for_row(row) in {"hot_repost", "source_day", "plus_1_day", "plus_3_day", "plus_7_day"}


def parse_source_publish_time(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    normalized = (
        value.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .strip()
    )
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return value


def is_generic_repost_text(text: str) -> bool:
    text = clean(text)
    text = re.sub(r"//@.*$", "", text).strip()
    generic_values = {
        "转发微博",
        "轉發微博",
        "转发",
        "repost",
        "Repost",
    }
    return text in generic_values or text == ""


def read_sources(limit: int) -> pd.DataFrame:
    return pd.read_csv(SOURCE_PATH, encoding="utf-8-sig", dtype=str).fillna("").head(limit)


def get_user_url(user: dict[str, Any]) -> str:
    profile = clean(user.get("profile_url"))
    if profile.startswith("/"):
        return "https://weibo.com" + profile
    if profile:
        return profile
    uid = clean(user.get("idstr") or user.get("id"))
    return f"https://weibo.com/u/{uid}" if uid else ""


def get_repost_url(user: dict[str, Any], item: dict[str, Any]) -> str:
    uid = clean(user.get("idstr") or user.get("id"))
    mblogid = clean(item.get("mblogid"))
    if uid and mblogid:
        return f"https://weibo.com/{uid}/{mblogid}"
    rid = clean(item.get("idstr") or item.get("id"))
    return f"https://weibo.com/status/{rid}" if rid else ""


def safe_to_csv(df: pd.DataFrame, path: Path, **kwargs) -> Path:
    try:
        df.to_csv(path, **kwargs)
        return path
    except PermissionError:
        alt = path.with_name(f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}")
        df.to_csv(alt, **kwargs)
        print(f"[文件占用] {path} 无法覆盖，已写入 {alt}")
        return alt


def parse_item(source: pd.Series, item: dict[str, Any], page: int, rank_in_page: int, meta: dict[str, Any]) -> dict[str, Any]:
    user = item.get("user") or {}
    parent = item.get("retweeted_status") or {}
    parent_user = parent.get("user") or {}
    source_post_id = clean(source.get("source_post_id"))
    row = {
        "source_post_id": source_post_id,
        "source_post_url": clean(source.get("source_post_url")),
        "source_author": clean(source.get("source_author")),
        "source_publish_time": parse_source_publish_time(source.get("publish_time")),
        "root_source_id": clean(parent.get("idstr") or parent.get("id") or source_post_id),
        "root_source_mblogid": clean(parent.get("mblogid")),
        "root_source_user_id": clean(parent_user.get("idstr") or parent_user.get("id")),
        "root_source_user_name": clean(parent_user.get("screen_name") or source.get("source_author")),
        "repost_id": clean(item.get("idstr") or item.get("id")),
        "repost_mid": clean(item.get("mid")),
        "repost_mblogid": clean(item.get("mblogid")),
        "repost_url": get_repost_url(user, item),
        "repost_user_id": clean(user.get("idstr") or user.get("id")),
        "repost_user_name": clean(user.get("screen_name")),
        "repost_user_url": get_user_url(user),
        "repost_time": parse_weibo_created_at(item.get("created_at")),
        "repost_text": clean(item.get("text_raw") or item.get("text")),
        "is_generic_repost": is_generic_repost_text(item.get("text_raw") or item.get("text")),
        "repost_source_device": clean(item.get("source")),
        "repost_reposts_count": int(item.get("reposts_count") or 0),
        "repost_comments_count": int(item.get("comments_count") or 0),
        "repost_attitudes_count": int(item.get("attitudes_count") or 0),
        "parent_id": clean(parent.get("idstr") or parent.get("id") or source_post_id),
        "parent_mblogid": clean(parent.get("mblogid")),
        "parent_user_id": clean(parent_user.get("idstr") or parent_user.get("id")),
        "parent_user_name": clean(parent_user.get("screen_name") or source.get("source_author")),
        "api_page": page,
        "rank_in_page": rank_in_page,
        "is_first_page": page == 1,
        "possible_hot_repost": page == 1 and rank_in_page <= 5,
        "sampling_bucket": "",
        "is_source_day_repost": "",
        "is_sampling_kept": "",
        "api_total_number": meta.get("total_number", ""),
        "api_max_page": meta.get("max_page", ""),
        "raw_json": json.dumps(item, ensure_ascii=False),
        "crawl_time": now_string(),
    }
    row["sampling_bucket"] = bucket_for_row(row)
    row["is_source_day_repost"] = row["sampling_bucket"] == "source_day"
    row["is_sampling_kept"] = row["sampling_bucket"] in {"hot_repost", "source_day"}
    return row


def fetch_reposts_for_source(
    context,
    source: pd.Series,
    max_items: int,
    target_day_hot_count: int,
    keep_generic: bool,
    sleep: float,
) -> list[dict[str, Any]]:
    source_id = clean(source.get("source_post_id"))
    mblogid = ""
    url = clean(source.get("source_post_url"))
    if "/" in url:
        mblogid = url.split("?")[0].rstrip("/").split("/")[-1]
    referer = url or "https://weibo.com"
    rows: list[dict[str, Any]] = []
    countable_rows = 0
    page = 1
    while len(rows) < max_items and countable_rows < target_day_hot_count:
        api_url = f"https://weibo.com/ajax/statuses/repostTimeline?id={source_id or mblogid}&page={page}&count=20&moduleID=feed"
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
            row = parse_item(source, item, page, rank_in_page, data)
            rows.append(row)
            if is_countable_sampling_row(row, keep_generic):
                countable_rows += 1
            if len(rows) >= max_items:
                break
        max_page = int(data.get("max_page") or page)
        if page >= max_page:
            break
        page += 1
        if sleep:
            import time

            time.sleep(sleep)
    return rows


def apply_dynamic_time_window(clean_df: pd.DataFrame, min_kept_per_source: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prefer same-day reposts; widen the window only when one source has too few usable reposts."""
    if clean_df.empty or "source_publish_time" not in clean_df.columns:
        return clean_df.copy(), pd.DataFrame()

    work = clean_df.copy()
    work["_source_dt"] = pd.to_datetime(work["source_publish_time"], errors="coerce")
    work["_repost_dt"] = pd.to_datetime(work["repost_time"], errors="coerce")
    windows = [0, 1, 3, 7]
    kept_parts = []
    summary_rows = []

    for source_id, sub in work.groupby("source_post_id", dropna=False):
        publish_dt = sub["_source_dt"].dropna()
        valid_time = sub[sub["_repost_dt"].notna()].copy()
        if publish_dt.empty or valid_time.empty:
            chosen = sub.copy()
            summary_rows.append(
                {
                    "source_post_id": source_id,
                    "source_author": sub["source_author"].iloc[0] if "source_author" in sub else "",
                    "source_publish_time": sub["source_publish_time"].iloc[0] if "source_publish_time" in sub else "",
                    "raw_after_generic_filter": len(sub),
                    "chosen_window_days": "unfiltered",
                    "kept_count": len(chosen),
                    "reason": "missing source/repost time",
                }
            )
            kept_parts.append(chosen)
            continue

        start = publish_dt.iloc[0].normalize()
        chosen = valid_time.iloc[0:0].copy()
        chosen_window: str | int = windows[-1]
        for days in windows:
            end = start + pd.Timedelta(days=days + 1)
            candidate = valid_time[(valid_time["_repost_dt"] >= start) & (valid_time["_repost_dt"] < end)].copy()
            chosen = candidate
            chosen_window = days
            if len(candidate) >= min_kept_per_source:
                break

        summary_rows.append(
            {
                "source_post_id": source_id,
                "source_author": sub["source_author"].iloc[0] if "source_author" in sub else "",
                "source_publish_time": sub["source_publish_time"].iloc[0] if "source_publish_time" in sub else "",
                "raw_after_generic_filter": len(sub),
                "chosen_window_days": chosen_window,
                "kept_count": len(chosen),
                "reason": f"target>={min_kept_per_source}; windows=same day,+1,+3,+7",
            }
        )
        kept_parts.append(chosen)

    if kept_parts:
        filtered = pd.concat(kept_parts, ignore_index=True)
    else:
        filtered = work.iloc[0:0].copy()
    filtered = filtered.drop(columns=[c for c in ["_source_dt", "_repost_dt"] if c in filtered.columns])
    return filtered, pd.DataFrame(summary_rows)


def apply_hot_and_source_day_filter(clean_df: pd.DataFrame, min_kept_per_source: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep hot reposts and source-day reposts first; fill with +1/+3/+7 day windows if needed."""
    if clean_df.empty:
        return clean_df.copy(), pd.DataFrame()

    work = clean_df.copy()
    work["_source_dt"] = pd.to_datetime(work["source_publish_time"], errors="coerce")
    work["_repost_dt"] = pd.to_datetime(work["repost_time"], errors="coerce")
    work["possible_hot_repost"] = work["possible_hot_repost"].astype(str).str.lower().isin(["true", "1"])
    day_delta = (work["_repost_dt"].dt.normalize() - work["_source_dt"].dt.normalize()).dt.days
    work["is_source_day_repost"] = day_delta.eq(0).fillna(False)
    work["sampling_bucket"] = "other_time"
    work.loc[day_delta.eq(0), "sampling_bucket"] = "source_day"
    work.loc[day_delta.eq(1), "sampling_bucket"] = "plus_1_day"
    work.loc[day_delta.between(2, 3), "sampling_bucket"] = "plus_3_day"
    work.loc[day_delta.between(4, 7), "sampling_bucket"] = "plus_7_day"
    work.loc[work["possible_hot_repost"], "sampling_bucket"] = "hot_repost"
    work["is_sampling_kept"] = False

    kept_parts = []
    summary_rows = []
    for source_id, sub in work.groupby("source_post_id", dropna=False):
        selected_buckets = ["hot_repost", "source_day"]
        kept_sub = sub[sub["sampling_bucket"].isin(selected_buckets)].copy()
        chosen_window = "source_day"
        if len(kept_sub) < min_kept_per_source:
            selected_buckets.append("plus_1_day")
            kept_sub = sub[sub["sampling_bucket"].isin(selected_buckets)].copy()
            chosen_window = "+1"
        if len(kept_sub) < min_kept_per_source:
            selected_buckets.append("plus_3_day")
            kept_sub = sub[sub["sampling_bucket"].isin(selected_buckets)].copy()
            chosen_window = "+3"
        if len(kept_sub) < min_kept_per_source:
            selected_buckets.append("plus_7_day")
            kept_sub = sub[sub["sampling_bucket"].isin(selected_buckets)].copy()
            chosen_window = "+7"
        kept_sub["is_sampling_kept"] = True
        kept_parts.append(kept_sub)
        summary_rows.append(
            {
                "source_post_id": source_id,
                "source_author": sub["source_author"].iloc[0] if "source_author" in sub else "",
                "source_publish_time": sub["source_publish_time"].iloc[0] if "source_publish_time" in sub else "",
                "raw_after_generic_filter": len(sub),
                "hot_repost_count": int((sub["sampling_bucket"] == "hot_repost").sum()),
                "source_day_count": int((sub["sampling_bucket"] == "source_day").sum()),
                "plus_1_day_count": int((sub["sampling_bucket"] == "plus_1_day").sum()),
                "plus_3_day_count": int((sub["sampling_bucket"] == "plus_3_day").sum()),
                "plus_7_day_count": int((sub["sampling_bucket"] == "plus_7_day").sum()),
                "chosen_window": chosen_window,
                "kept_count": len(kept_sub),
                "target_count": min_kept_per_source,
                "max_api_page": sub["api_page"].max() if "api_page" in sub else "",
                "reached_target": len(kept_sub) >= min_kept_per_source,
                "reason": "hot+source_day first; fill with +1/+3/+7 if target is not reached",
            }
        )

    kept = pd.concat(kept_parts, ignore_index=True) if kept_parts else work.iloc[0:0].copy()
    kept = kept.drop(columns=[c for c in ["_source_dt", "_repost_dt"] if c in kept.columns])
    return kept, pd.DataFrame(summary_rows)


def write_outputs(raw_df: pd.DataFrame, keep_generic: bool, min_kept_per_source: int):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for col in RAW_COLUMNS:
        if col not in raw_df.columns:
            raw_df[col] = ""
    raw_df = raw_df[RAW_COLUMNS]
    raw_path = safe_to_csv(raw_df, RAW_OUT, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    clean_df = raw_df.copy()
    if not keep_generic:
        clean_df = clean_df[~clean_df["is_generic_repost"].astype(str).str.lower().isin(["true", "1"])].copy()
    before_time_filter_count = len(clean_df)
    clean_df, time_summary = apply_hot_and_source_day_filter(clean_df, min_kept_per_source)
    clean_path = safe_to_csv(clean_df, CLEAN_OUT, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    time_summary_path = safe_to_csv(time_summary, TIME_WINDOW_OUT, index=False, encoding="utf-8-sig")

    edges = pd.DataFrame(
        {
            "source_post_id": clean_df["source_post_id"],
            "source_post_url": clean_df["source_post_url"],
            "source_user": clean_df["parent_user_name"].where(clean_df["parent_user_name"].astype(str).str.len().gt(0), clean_df["source_author"]),
            "target_user": clean_df["repost_user_name"],
            "edge_type": "api_repost",
            "repost_time": clean_df["repost_time"],
            "repost_id": clean_df["repost_id"],
            "repost_url": clean_df["repost_url"],
            "repost_text": clean_df["repost_text"],
            "repost_attitudes_count": clean_df["repost_attitudes_count"],
            "repost_comments_count": clean_df["repost_comments_count"],
            "is_generic_repost": clean_df["is_generic_repost"],
            "api_page": clean_df["api_page"],
            "rank_in_page": clean_df["rank_in_page"],
            "possible_hot_repost": clean_df["possible_hot_repost"],
            "sampling_bucket": clean_df["sampling_bucket"],
            "is_source_day_repost": clean_df["is_source_day_repost"],
            "is_sampling_kept": clean_df["is_sampling_kept"],
            "crawl_time": clean_df["crawl_time"],
        }
    )
    edges_path = safe_to_csv(edges, EDGES_OUT, index=False, encoding="utf-8-sig")

    node_rows = []
    for user, sub in clean_df.groupby("repost_user_name", dropna=True):
        if not clean(user):
            continue
        node_rows.append(
            {
                "user_name": user,
                "user_id": sub["repost_user_id"].iloc[0],
                "user_url": sub["repost_user_url"].iloc[0],
                "repost_count": len(sub),
                "first_seen_time": sub["repost_time"].min(),
                "last_seen_time": sub["repost_time"].max(),
            }
        )
    nodes_path = safe_to_csv(pd.DataFrame(node_rows), NODES_OUT, index=False, encoding="utf-8-sig")

    field_rates = {
        col: int(clean_df[col].astype(str).str.len().gt(0).sum())
        for col in [
            "repost_id",
            "repost_mblogid",
            "repost_url",
            "repost_user_id",
            "repost_user_name",
            "repost_user_url",
            "repost_time",
            "repost_text",
        ]
    }
    lines = [
        "# API 结构化重爬质量检查",
        "",
        f"- 生成时间：{now_string()}",
        f"- raw 抓取记录数：{len(raw_df)}",
        f"- clean 保留记录数：{len(clean_df)}",
        f"- 剔除纯 `转发微博` 记录数：{int(raw_df['is_generic_repost'].astype(str).str.lower().isin(['true', '1']).sum()) if not raw_df.empty else 0}",
        f"- 输出目录：`{OUT_DIR}`",
        "",
        "## 字段非空数量",
        "",
    ]
    for col, value in field_rates.items():
        lines.append(f"- `{col}`：{value} / {len(raw_df)}")
    lines.extend(
        [
            "",
            "## 判断",
            "",
        "- 本文件来自微博 `ajax/statuses/repostTimeline`，是转发列表接口，不是评论接口。",
        "- raw 文件保留所有转发；clean、edges、nodes 默认剔除纯 `转发微博` 这类无正文转发。",
        "- `repost_url` 可用于单条转发复核；如果浏览器打不开，可能是权限、删除或登录状态问题。",
            "",
            "## 前 10 条样本",
            "",
            clean_df.head(10)[["source_author", "repost_user_name", "repost_time", "repost_url", "repost_attitudes_count", "repost_text"]].to_markdown(index=False),
        ]
    )
    try:
        QUALITY_OUT.write_text("\n".join(lines), encoding="utf-8")
    except PermissionError:
        alt = QUALITY_OUT.with_name(f"{QUALITY_OUT.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{QUALITY_OUT.suffix}")
        alt.write_text("\n".join(lines), encoding="utf-8")
        print(f"[文件占用] {QUALITY_OUT} 无法覆盖，已写入 {alt}")


def write_outputs_v2(raw_df: pd.DataFrame, keep_generic: bool, min_kept_per_source: int):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for col in RAW_COLUMNS:
        if col not in raw_df.columns:
            raw_df[col] = ""
    raw_df = raw_df[RAW_COLUMNS]
    raw_path = safe_to_csv(raw_df, RAW_OUT, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)

    clean_df = raw_df.copy()
    if not keep_generic:
        clean_df = clean_df[~clean_df["is_generic_repost"].astype(str).str.lower().isin(["true", "1"])].copy()
    before_time_filter_count = len(clean_df)
    clean_df, time_summary = apply_hot_and_source_day_filter(clean_df, min_kept_per_source)

    clean_path = safe_to_csv(clean_df, CLEAN_OUT, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    time_summary_path = safe_to_csv(time_summary, TIME_WINDOW_OUT, index=False, encoding="utf-8-sig")

    edges = pd.DataFrame(
        {
            "source_post_id": clean_df["source_post_id"],
            "source_post_url": clean_df["source_post_url"],
            "source_user": clean_df["parent_user_name"].where(
                clean_df["parent_user_name"].astype(str).str.len().gt(0), clean_df["source_author"]
            ),
            "target_user": clean_df["repost_user_name"],
            "edge_type": "api_repost",
            "repost_time": clean_df["repost_time"],
            "repost_id": clean_df["repost_id"],
            "repost_url": clean_df["repost_url"],
            "repost_text": clean_df["repost_text"],
            "repost_attitudes_count": clean_df["repost_attitudes_count"],
            "repost_comments_count": clean_df["repost_comments_count"],
            "is_generic_repost": clean_df["is_generic_repost"],
            "api_page": clean_df["api_page"],
            "rank_in_page": clean_df["rank_in_page"],
            "possible_hot_repost": clean_df["possible_hot_repost"],
            "sampling_bucket": clean_df["sampling_bucket"],
            "is_source_day_repost": clean_df["is_source_day_repost"],
            "is_sampling_kept": clean_df["is_sampling_kept"],
            "crawl_time": clean_df["crawl_time"],
        }
    )
    edges_path = safe_to_csv(edges, EDGES_OUT, index=False, encoding="utf-8-sig")

    node_rows = []
    for user, sub in clean_df.groupby("repost_user_name", dropna=True):
        if not clean(user):
            continue
        node_rows.append(
            {
                "user_name": user,
                "user_id": sub["repost_user_id"].iloc[0],
                "user_url": sub["repost_user_url"].iloc[0],
                "repost_count": len(sub),
                "first_seen_time": sub["repost_time"].min(),
                "last_seen_time": sub["repost_time"].max(),
            }
        )
    nodes_path = safe_to_csv(pd.DataFrame(node_rows), NODES_OUT, index=False, encoding="utf-8-sig")

    field_cols = [
        "repost_id",
        "repost_mblogid",
        "repost_url",
        "repost_user_id",
        "repost_user_name",
        "repost_user_url",
        "repost_time",
        "repost_text",
        "api_page",
        "rank_in_page",
    ]
    field_rates = {col: int(clean_df[col].astype(str).str.len().gt(0).sum()) for col in field_cols}
    generic_count = int(raw_df["is_generic_repost"].astype(str).str.lower().isin(["true", "1"]).sum()) if not raw_df.empty else 0
    sample_cols = ["source_author", "repost_user_name", "repost_time", "repost_url", "repost_attitudes_count", "repost_text"]
    sample_md = clean_df.head(10)[sample_cols].to_markdown(index=False) if not clean_df.empty else "无 clean 样本。"
    time_md = time_summary.to_markdown(index=False) if not time_summary.empty else "无时间窗汇总。"

    lines = [
        "# API 结构化重爬质量检查",
        "",
        f"- 生成时间：{now_string()}",
        f"- raw 抓取记录数：{len(raw_df)}",
        f"- 剔除纯 `转发微博` 后记录数：{before_time_filter_count}",
        f"- clean 保留记录数：{len(clean_df)}",
        f"- 剔除纯 `转发微博` 记录数：{generic_count}",
        f"- 时间窗策略：每条源微博先保留源帖发布当天；不足 {min_kept_per_source} 条时依次扩展到 +1、+3、+7 天；仍不足则保留 +7 天内可用记录。",
        f"- 输出目录：`{OUT_DIR}`",
        f"- raw：`{raw_path}`",
        f"- clean：`{clean_path}`",
        f"- edges：`{edges_path}`",
        f"- nodes：`{nodes_path}`",
        f"- 时间窗汇总：`{time_summary_path}`",
        "",
        "## 字段非空数量",
        "",
    ]
    for col, value in field_rates.items():
        lines.append(f"- `{col}`：{value} / {len(raw_df)}")
    lines.extend(
        [
            "",
            "## 时间窗汇总",
            "",
            time_md,
            "",
            "## 判断",
            "",
            "- 本文件来自微博 `ajax/statuses/repostTimeline`，是转发列表接口，不是评论接口。",
            "- raw 文件保留所有接口返回转发；clean、edges、nodes 默认剔除纯 `转发微博`，并按源帖发布时间动态筛选时间窗。",
            "- `repost_url` 可用于单条转发复核；若浏览器打不开，可能是权限、删除或登录状态问题。",
            "",
            "## 前 10 条 clean 样本",
            "",
            sample_md,
        ]
    )
    try:
        QUALITY_OUT.write_text("\n".join(lines), encoding="utf-8")
    except PermissionError:
        alt = QUALITY_OUT.with_name(f"{QUALITY_OUT.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{QUALITY_OUT.suffix}")
        alt.write_text("\n".join(lines), encoding="utf-8")
        print(f"[文件占用] {QUALITY_OUT} 无法覆盖，已写入 {alt}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-sources", type=int, default=20)
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--sleep", type=float, default=0.8)
    parser.add_argument("--headful", action="store_true", help="打开可见浏览器，用于确认登录状态")
    parser.add_argument("--login-wait", type=int, default=20)
    parser.add_argument("--keep-generic", action="store_true", help="保留纯“转发微博”记录进入 clean/edges/nodes；默认剔除")
    parser.add_argument("--min-kept-per-source", type=int, default=50, help="单条源微博至少保留的热门+源帖当天非泛转发数量；不足时用+1/+3/+7天补足")
    args = parser.parse_args()

    sources = read_sources(args.limit_sources)
    print(
        f"计划抓取：{len(sources)} 条核心源微博；每条最多 {args.max_items} 条真实转发 raw；"
        f"clean 默认剔除纯“转发微博”，优先保留第一页热门转发和源帖发布当天转发；"
        f"不足 {args.min_kept_per_source} 条时再按 +1/+3/+7 天补足。"
    )
    from playwright.sync_api import sync_playwright

    rows: list[dict[str, Any]] = []
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
        for idx, source in sources.iterrows():
            print(f"[{idx + 1}/{len(sources)}] API 转发列表：{source.get('source_post_id')} {source.get('source_author')}")
            got = fetch_reposts_for_source(context, source, args.max_items, args.min_kept_per_source, args.keep_generic, args.sleep)
            print(f"  got {len(got)}")
            rows.extend(got)
        context.close()
    raw_df = pd.DataFrame(rows)
    write_outputs_v2(raw_df, keep_generic=args.keep_generic, min_kept_per_source=args.min_kept_per_source)
    print("API 结构化重爬完成：")
    print(RAW_OUT)
    print(EDGES_OUT)
    print(QUALITY_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
