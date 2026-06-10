from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
QQ_PATH = OUT / "qqmusic_comments_clean.csv"
LOG_PATH = OUT / "data_cleaning_log.txt"

REFERENCE_DATE = pd.Timestamp("2026-05-29")

DATE_PATTERNS = [
    re.compile(r"(?P<year>\d{4})[年/-](?P<month>\d{1,2})[月/-](?P<day>\d{1,2})[日\s]*?(?P<hour>\d{1,2})[:：](?P<minute>\d{1,2})(?:[:：](?P<second>\d{1,2}))?"),
    re.compile(r"(?P<year>\d{4})[年/-](?P<month>\d{1,2})[月/-](?P<day>\d{1,2})"),
    re.compile(r"(?P<month>\d{1,2})[月/-](?P<day>\d{1,2})[日\s]*?(?P<hour>\d{1,2})[:：](?P<minute>\d{1,2})(?:[:：](?P<second>\d{1,2}))?"),
    re.compile(r"(?P<month>\d{1,2})[月/-](?P<day>\d{1,2})"),
]

TIME_ONLY_RE = re.compile(r"(?P<hour>\d{1,2})[:：](?P<minute>\d{1,2})(?:[:：](?P<second>\d{1,2}))?")


def clean_time_string(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip()
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s)
    # Remove trailing crawl comments such as "转赞人数超过200"
    s = re.split(r"\s+转赞人数超过\d+.*$", s)[0].strip()
    s = re.split(r"\s+点赞人数超过\d+.*$", s)[0].strip()
    s = re.split(r"\s+评论人数超过\d+.*$", s)[0].strip()
    return s


def parse_time(value) -> pd.Timestamp | pd.NaT:
    s = clean_time_string(value)
    if not s:
        return pd.NaT

    # Relative days first
    rel_match = re.match(r"^(今天|昨日|昨天|前天)\s*(.*)$", s)
    if rel_match:
        rel_word = rel_match.group(1)
        tail = rel_match.group(2).strip()
        if rel_word == "今天":
            base = REFERENCE_DATE
        elif rel_word in ("昨日", "昨天"):
            base = REFERENCE_DATE - pd.Timedelta(days=1)
        else:
            base = REFERENCE_DATE - pd.Timedelta(days=2)
        t_match = TIME_ONLY_RE.search(tail)
        if t_match:
            hour = int(t_match.group("hour"))
            minute = int(t_match.group("minute"))
            second = int(t_match.group("second") or 0)
            return pd.Timestamp(base.year, base.month, base.day, hour, minute, second)
        return base

    # Try year-bearing formats first
    for pattern in DATE_PATTERNS[:2]:
        m = pattern.search(s)
        if m:
            year = int(m.groupdict().get("year", REFERENCE_DATE.year))
            month = int(m.groupdict().get("month", 1))
            day = int(m.groupdict().get("day", 1))
            hour = int(m.groupdict().get("hour") or 0)
            minute = int(m.groupdict().get("minute") or 0)
            second = int(m.groupdict().get("second") or 0)
            try:
                return pd.Timestamp(year, month, day, hour, minute, second)
            except Exception:
                pass

    # No year: force 2026 as the default year
    for pattern in DATE_PATTERNS[2:]:
        m = pattern.search(s)
        if m:
            month = int(m.groupdict().get("month", 1))
            day = int(m.groupdict().get("day", 1))
            hour = int(m.groupdict().get("hour") or 0)
            minute = int(m.groupdict().get("minute") or 0)
            second = int(m.groupdict().get("second") or 0)
            try:
                return pd.Timestamp(2026, month, day, hour, minute, second)
            except Exception:
                pass

    # Final fallback: let pandas try after appending 2026 if a month/day-like string exists
    if re.search(r"\d{1,2}[月/-]\d{1,2}", s):
        candidate = "2026-" + s
        candidate = candidate.replace("年", "-").replace("月", "-").replace("日", " ")
        candidate = re.sub(r"\s+", " ", candidate)
        ts = pd.to_datetime(candidate, errors="coerce")
        if pd.notna(ts):
            return ts

    ts = pd.to_datetime(s, errors="coerce")
    if pd.notna(ts):
        return ts
    return pd.NaT


def stage_from_timestamp(ts: pd.Timestamp | pd.NaT) -> str:
    if pd.isna(ts):
        return "unclear"
    day = ts.normalize()
    if day <= pd.Timestamp("2025-07-21"):
        return "pre_event"
    if pd.Timestamp("2025-07-22") <= day <= pd.Timestamp("2025-07-24"):
        return "outbreak"
    if pd.Timestamp("2025-07-25") <= day <= pd.Timestamp("2025-07-26"):
        return "response"
    if pd.Timestamp("2025-07-27") <= day <= pd.Timestamp("2025-07-31"):
        return "debate"
    if day >= pd.Timestamp("2025-08-01"):
        return "cooldown"
    return "unclear"


def apply_stage(df: pd.DataFrame, time_col: str, target_col: str) -> tuple[pd.Series, pd.Series]:
    parsed = df[time_col].map(parse_time)
    stages = parsed.map(stage_from_timestamp)
    df[target_col] = stages
    return parsed, stages


all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
qq_df = pd.read_csv(QQ_PATH, encoding="utf-8-sig")

# Keep original stage for comparison
all_before = all_df.get("event_stage", pd.Series(["unclear"] * len(all_df))).fillna("unclear").astype(str)
posts_before = posts_df.get("event_stage", pd.Series(["unclear"] * len(posts_df))).fillna("unclear").astype(str)
reposts_before = reposts_df.get("event_stage", pd.Series(["unclear"] * len(reposts_df))).fillna("unclear").astype(str)
qq_before = qq_df.get("event_stage", pd.Series(["unclear"] * len(qq_df))).fillna("unclear").astype(str)

all_parsed, all_stages = apply_stage(all_df, "publish_time", "event_stage")
posts_parsed, posts_stages = apply_stage(posts_df, "publish_time", "event_stage")
reposts_parsed, reposts_stages = apply_stage(reposts_df, "repost_time", "event_stage")
qq_parsed, qq_stages = apply_stage(qq_df, "publish_time", "event_stage")
qq_df["is_valid"] = 1

# Repost rows often have missing repost_time; fall back to the source post's stage.
post_stage_lookup = all_df[all_df["data_type"] == "post"][ ["source_id", "event_stage"] ].drop_duplicates(subset=["source_id"]).set_index("source_id")["event_stage"]
if "source_id" in all_df.columns:
    repost_mask = all_df["data_type"] == "repost"
    repost_fallback = all_df.loc[repost_mask, "source_id"].map(post_stage_lookup)
    all_df.loc[repost_mask, "event_stage"] = all_df.loc[repost_mask, "event_stage"].where(
        all_df.loc[repost_mask, "event_stage"].astype(str) != "unclear",
        repost_fallback.fillna("unclear"),
    )

if "source_post_id" in reposts_df.columns:
    repost_stage_fallback = reposts_df["source_post_id"].map(post_stage_lookup)
    reposts_df["event_stage"] = reposts_df["event_stage"].where(
        reposts_df["event_stage"].astype(str) != "unclear",
        repost_stage_fallback.fillna("unclear"),
    )

# Synchronize event_stage back into posts and reposts from all_df, keyed by original ids
post_stage_map = all_df[all_df["data_type"] == "post"][ ["source_id", "event_stage"] ].drop_duplicates(subset=["source_id"]).set_index("source_id")
if "post_id" in posts_df.columns:
    posts_df["event_stage"] = posts_df["post_id"].map(post_stage_map["event_stage"]).combine_first(posts_df["event_stage"])

repost_stage_source = all_df[all_df["data_type"] == "repost"][ ["source_id", "publish_time", "text_clean", "author_name", "event_stage"] ].copy()
repost_stage_source = repost_stage_source.rename(columns={"source_id": "source_post_id", "text_clean": "repost_text_clean", "author_name": "repost_user"})
for frame in [reposts_df, repost_stage_source]:
    time_col = "repost_time" if "repost_time" in frame.columns else "publish_time"
    text_col = "repost_text_raw" if "repost_text_raw" in frame.columns else "repost_text_clean"
    user_col = "repost_user" if "repost_user" in frame.columns else "author_name"
    frame["_sync_key"] = (
        frame["source_post_id"].astype(str)
        + "|||"
        + frame[time_col].astype(str)
        + "|||"
        + frame[text_col].astype(str)
        + "|||"
        + frame[user_col].astype(str)
    )
repost_stage_map = repost_stage_source.set_index("_sync_key")["event_stage"]
reposts_df["event_stage"] = reposts_df["_sync_key"].map(repost_stage_map).combine_first(reposts_df["event_stage"])

# Remove helper columns if present
for frame in [posts_df, reposts_df]:
    if "_sync_key" in frame.columns:
        frame.drop(columns=["_sync_key"], inplace=True)

# Count changes and distribution
all_before_unclear = int((all_before == "unclear").sum())
posts_before_unclear = int((posts_before == "unclear").sum())
reposts_before_unclear = int((reposts_before == "unclear").sum())
qq_before_unclear = int((qq_before == "unclear").sum())

all_dist = all_df["event_stage"].value_counts(dropna=False).to_dict()
posts_dist = posts_df["event_stage"].value_counts(dropna=False).to_dict()
reposts_dist = reposts_df["event_stage"].value_counts(dropna=False).to_dict()
qq_dist = qq_df["event_stage"].value_counts(dropna=False).to_dict()

all_after_unclear = int((all_df["event_stage"].astype(str) == "unclear").sum())
posts_after_unclear = int((posts_df["event_stage"].astype(str) == "unclear").sum())
reposts_after_unclear = int((reposts_df["event_stage"].astype(str) == "unclear").sum())
qq_after_unclear = int((qq_df["event_stage"].astype(str) == "unclear").sum())

# Persist
all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
qq_df.to_csv(QQ_PATH, index=False, encoding="utf-8-sig")

# Append log
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open(LOG_PATH, "a", encoding="utf-8-sig") as f:
    f.write(f"\n[{now}] 第三轮修复：统一重解析 publish_time，缺年份默认补 2026，今天/昨天/前天按 2026-05-29 参照展开。\n")
    f.write(f"[{now}] 第三轮修复：all_weibo event_stage 由 unclear {all_before_unclear} 条降至 {all_after_unclear} 条，分布 {all_dist}。\n")
    f.write(f"[{now}] 第三轮修复：weibo_posts_clean event_stage 由 unclear {posts_before_unclear} 条降至 {posts_after_unclear} 条，分布 {posts_dist}。\n")
    f.write(f"[{now}] 第三轮修复：weibo_reposts_clean event_stage 由 unclear {reposts_before_unclear} 条降至 {reposts_after_unclear} 条，分布 {reposts_dist}。\n")
    f.write(f"[{now}] 第三轮修复：qqmusic_comments_clean event_stage 由 unclear {qq_before_unclear} 条降至 {qq_after_unclear} 条，分布 {qq_dist}。\n")
    f.write(f"[{now}] 第三轮修复：已同步回写 all_weibo_texts_clean.csv、weibo_posts_clean.csv、weibo_reposts_clean.csv 和 qqmusic_comments_clean.csv。\n")

print("Done stage3 timefix")
print("all unclear:", all_before_unclear, "->", all_after_unclear)
print("posts unclear:", posts_before_unclear, "->", posts_after_unclear)
print("reposts unclear:", reposts_before_unclear, "->", reposts_after_unclear)
print("qq unclear:", qq_before_unclear, "->", qq_after_unclear)
print("all dist:", all_dist)
print("posts dist:", posts_dist)
print("reposts dist:", reposts_dist)
print("qq dist:", qq_dist)
