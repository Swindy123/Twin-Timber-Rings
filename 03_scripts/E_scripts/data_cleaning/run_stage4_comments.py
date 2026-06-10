from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"
B_RAW = BASE / "原始数据备份" / "B_data" / "weibo_comments_raw.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
COMMENTS_PATH = OUT / "weibo_comments_clean.csv"
ALL_PATH = OUT / "all_weibo_texts_clean.csv"
RULES_PATH = OUT / "label_rules.xlsx"
LOG_PATH = OUT / "data_cleaning_log.txt"

REFERENCE_DATE = pd.Timestamp("2026-05-30")

URL_RE = re.compile(r"http[s]?://\S+", flags=re.IGNORECASE)
MENTION_RE = re.compile(r"@[^\s]+")
BRACKET_RE = re.compile(r"\[.*?\]")
ALLOWED_RE = re.compile(r"[^\u4E00-\u9FFF\u0020-\u007E\u3000-\u303F\uFF00-\uFFEF]", flags=re.UNICODE)
DATE_WITH_YEAR_RE = re.compile(r"(?P<year>\d{4})[/-](?P<month>\d{1,2})[/-](?P<day>\d{1,2})")
DATE_CN_RE = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日?")
DATE_NO_YEAR_RE = re.compile(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日?")
TIME_ONLY_RE = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?")


def is_nonempty(value) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = URL_RE.sub("", text)
    text = MENTION_RE.sub("", text)
    text = BRACKET_RE.sub("", text)
    text = ALLOWED_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_time(value) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if not text:
        return pd.NaT
    text = re.split(r"\s+转赞人数超过\d+.*$", text)[0].strip()
    text = re.split(r"\s+点赞人数超过\d+.*$", text)[0].strip()
    text = re.split(r"\s+评论人数超过\d+.*$", text)[0].strip()
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)

    rel = re.match(r"^(今天|昨天|前天)\s*(.*)$", text)
    if rel:
        word = rel.group(1)
        tail = rel.group(2).strip()
        base = REFERENCE_DATE
        if word == "昨天":
            base -= pd.Timedelta(days=1)
        elif word == "前天":
            base -= pd.Timedelta(days=2)
        time_match = TIME_ONLY_RE.search(tail)
        if time_match:
            hour = int(time_match.group("hour"))
            minute = int(time_match.group("minute"))
            second = int(time_match.group("second") or 0)
            return pd.Timestamp(base.year, base.month, base.day, hour, minute, second)
        return base

    for pattern in (DATE_CN_RE, DATE_WITH_YEAR_RE):
        match = pattern.search(text)
        if match:
            year = int(match.groupdict().get("year") or REFERENCE_DATE.year)
            month = int(match.group("month"))
            day = int(match.group("day"))
            time_match = TIME_ONLY_RE.search(text)
            hour = int(time_match.group("hour")) if time_match else 0
            minute = int(time_match.group("minute")) if time_match else 0
            second = int(time_match.group("second") or 0) if time_match else 0
            try:
                return pd.Timestamp(year, month, day, hour, minute, second)
            except Exception:
                pass

    match = DATE_NO_YEAR_RE.search(text)
    if match:
        month = int(match.group("month"))
        day = int(match.group("day"))
        time_match = TIME_ONLY_RE.search(text)
        hour = int(time_match.group("hour")) if time_match else 0
        minute = int(time_match.group("minute")) if time_match else 0
        second = int(time_match.group("second") or 0) if time_match else 0
        try:
            return pd.Timestamp(2026, month, day, hour, minute, second)
        except Exception:
            pass

    ts = pd.to_datetime(text, errors="coerce")
    if pd.notna(ts):
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.tz_localize(None)
        return ts
    return pd.NaT


def stage_from_ts(value) -> str:
    ts = parse_time(value)
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


def load_rules() -> pd.DataFrame:
    rules = pd.read_excel(RULES_PATH, sheet_name="关键词规则")
    rules = rules.rename(columns=lambda x: str(x).strip())
    if "优先级" in rules.columns:
        rules = rules.sort_values(by=["优先级"], ascending=True).reset_index(drop=True)
    else:
        rules = rules.reset_index(drop=True)
    return rules


def apply_rules(text: str, rules: pd.DataFrame) -> tuple[str, dict[str, str]]:
    hits: list[str] = []
    labels = {"stance": "", "frame": "", "emotion": ""}
    for _, rule in rules.iterrows():
        keyword = str(rule.get("关键词", "")).strip()
        condition = str(rule.get("条件", "包含")).strip()
        label_type = str(rule.get("标签类型", "")).strip()
        label_value = str(rule.get("标签值", "")).strip()
        if not keyword or not label_type or not label_value:
            continue
        matched = text == keyword if condition == "完全匹配" else keyword in text
        if matched:
            if keyword not in hits:
                hits.append(keyword)
            if label_type in labels and not labels[label_type]:
                labels[label_type] = label_value
    hit_text = ";".join(hits)
    if not labels["stance"]:
        labels["stance"] = "unclear"
    if not labels["frame"]:
        labels["frame"] = "unclear"
    if not labels["emotion"]:
        labels["emotion"] = "unclear"
    return hit_text, labels


# Load files
raw_df = pd.read_csv(B_RAW, encoding="utf-8-sig")
posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
rules_df = load_rules()

# Exploration stats
raw_rows = len(raw_df)
dedup_rows = len(raw_df.drop_duplicates(subset=["comment_id"]))
empty_comment_text_rows = int(raw_df["comment_text"].fillna("").astype(str).str.strip().eq("").sum())
unique_source_ids = raw_df["source_post_id"].dropna().astype(str).nunique()
post_ids = set(posts_df["post_id"].dropna().astype(str))
source_in_posts = raw_df["source_post_id"].dropna().astype(str).isin(post_ids)
matched_unique_source_ids = raw_df.loc[source_in_posts, "source_post_id"].dropna().astype(str).nunique()
source_match_ratio = matched_unique_source_ids / unique_source_ids if unique_source_ids else 0.0
rows_after_source_and_nonempty = int(
    raw_df.loc[
        source_in_posts & raw_df["comment_text"].fillna("").astype(str).str.strip().ne("")
    ].shape[0]
)

# Data convergence
filtered = raw_df.drop_duplicates(subset=["comment_id"]).copy()
filtered = filtered[
    filtered["source_post_id"].dropna().astype(str).isin(post_ids)
    & filtered["comment_text"].fillna("").astype(str).str.strip().ne("")
].copy()
filtered["like_count"] = pd.to_numeric(filtered["like_count"], errors="coerce").fillna(0)
filtered["reply_count"] = pd.to_numeric(filtered["reply_count"], errors="coerce").fillna(0)

filtered_count_before_cap = len(filtered)
cap_applied = filtered_count_before_cap > 8000
if cap_applied:
    filtered = filtered.sort_values(by=["like_count", "comment_id"], ascending=[False, True]).head(5000).copy()
final_converged_rows = len(filtered)

# Clean comments table
comments_df = pd.DataFrame()
comments_df["comment_id"] = filtered["comment_id"].astype(str)
comments_df["source_post_id"] = filtered["source_post_id"].astype(str)
comments_df["source_post_url"] = filtered["source_post_url"]
comments_df["publish_time"] = filtered["comment_time"]
comments_df["author_name"] = filtered["user_name"]
comments_df["text_raw"] = filtered["comment_text"]
comments_df["text_clean"] = comments_df["text_raw"].map(clean_text)
comments_df["like_count"] = filtered["like_count"].astype("Int64")
comments_df["reply_count"] = filtered["reply_count"].astype("Int64")
comments_df["crawl_time"] = filtered["crawl_time"]
comments_df["platform"] = "weibo"
for col in ["stance", "frame", "emotion", "event_stage", "keyword_hit"]:
    comments_df[col] = ""
comments_df["is_valid"] = 1
comments_df = comments_df[
    [
        "comment_id",
        "source_post_id",
        "source_post_url",
        "publish_time",
        "author_name",
        "text_raw",
        "text_clean",
        "like_count",
        "reply_count",
        "platform",
        "stance",
        "frame",
        "emotion",
        "event_stage",
        "keyword_hit",
        "is_valid",
        "crawl_time",
    ]
].copy()
comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

# Append to total table
comment_total = pd.DataFrame()
comment_total["id"] = comments_df["comment_id"].map(lambda x: f"comment_{x}")
comment_total["data_type"] = "comment"
comment_total["platform"] = "weibo"
comment_total["source_id"] = comments_df["source_post_id"]
comment_total["source_url"] = comments_df["source_post_url"]
comment_total["publish_time"] = comments_df["publish_time"]
comment_total["author_name"] = comments_df["author_name"]
comment_total["author_type"] = "ordinary_user"
comment_total["text_raw"] = comments_df["text_raw"]
comment_total["text_clean"] = comments_df["text_clean"]
comment_total["like_count"] = comments_df["like_count"]
comment_total["comment_count"] = 0
comment_total["repost_count"] = 0
comment_total["stance"] = comments_df["stance"]
comment_total["frame"] = comments_df["frame"]
comment_total["emotion"] = comments_df["emotion"]
comment_total["event_stage"] = comments_df["event_stage"]
comment_total["keyword_hit"] = comments_df["keyword_hit"]
comment_total["is_valid"] = comments_df["is_valid"]
comment_total["crawl_time"] = comments_df["crawl_time"]

all_df = all_df.copy()
if "comment" not in set(all_df["data_type"].astype(str)):
    all_df = pd.concat([all_df, comment_total[all_df.columns]], ignore_index=True)
else:
    # If rerun, replace existing comment rows by id
    all_df = all_df[all_df["data_type"].astype(str) != "comment"].copy()
    all_df = pd.concat([all_df, comment_total[all_df.columns]], ignore_index=True)

# Time parsing and event_stage fill for empty rows only
all_df["event_stage"] = all_df["event_stage"].fillna("").astype(str)
empty_stage_mask = all_df["event_stage"].str.strip().eq("")
all_df.loc[empty_stage_mask, "event_stage"] = all_df.loc[empty_stage_mask, "publish_time"].map(stage_from_ts)

# Keyword labeling for rows with empty keyword_hit only
all_df["keyword_hit"] = all_df["keyword_hit"].fillna("").astype(str)
all_df["stance"] = all_df["stance"].fillna("").astype(str)
all_df["frame"] = all_df["frame"].fillna("").astype(str)
all_df["emotion"] = all_df["emotion"].fillna("").astype(str)

keyword_assigned_rows = 0
for idx, row in all_df.iterrows():
    if str(row.get("keyword_hit", "")).strip():
        continue
    text = str(row.get("text_clean", ""))
    hit_text, labels = apply_rules(text, rules_df)
    all_df.at[idx, "keyword_hit"] = hit_text
    if not str(row.get("stance", "")).strip():
        all_df.at[idx, "stance"] = labels["stance"]
    if not str(row.get("frame", "")).strip():
        all_df.at[idx, "frame"] = labels["frame"]
    if not str(row.get("emotion", "")).strip():
        all_df.at[idx, "emotion"] = labels["emotion"]
    if hit_text:
        keyword_assigned_rows += 1

# Ensure all new comment rows have labels even if not matched
comment_mask = all_df["data_type"].astype(str).eq("comment")
for col in ["stance", "frame", "emotion"]:
    all_df.loc[comment_mask & all_df[col].astype(str).str.strip().eq(""), col] = "unclear"
all_df.loc[comment_mask & all_df["keyword_hit"].astype(str).str.strip().eq(""), "keyword_hit"] = ""

# Synchronize back to sub tables
post_mask = all_df["data_type"].astype(str).eq("post")
repost_mask = all_df["data_type"].astype(str).eq("repost")
comment_mask = all_df["data_type"].astype(str).eq("comment")

post_sync = all_df.loc[post_mask, ["source_id", "event_stage", "keyword_hit", "stance", "frame", "emotion"]].drop_duplicates(subset=["source_id"])
posts_df = posts_df.drop(columns=[c for c in ["event_stage", "keyword_hit", "stance", "frame", "emotion"] if c in posts_df.columns], errors="ignore")
posts_df = posts_df.merge(post_sync, left_on="post_id", right_on="source_id", how="left")
posts_df["event_stage"] = posts_df["event_stage"].fillna("").astype(str)
posts_df["keyword_hit"] = posts_df["keyword_hit"].fillna("").astype(str)
posts_df["stance"] = posts_df["stance"].fillna("").astype(str)
posts_df["frame"] = posts_df["frame"].fillna("").astype(str)
posts_df["emotion"] = posts_df["emotion"].fillna("").astype(str)
posts_df = posts_df.drop(columns=["source_id"], errors="ignore")
posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")

repost_sync = all_df.loc[repost_mask, ["source_id", "publish_time", "text_clean", "author_name", "event_stage", "keyword_hit", "stance", "frame", "emotion"]].copy()
repost_sync = repost_sync.rename(columns={"source_id": "source_post_id", "text_clean": "repost_text_clean", "author_name": "repost_user"})
reposts_df = reposts_df.copy()
reposts_df["_sync_key"] = (
    reposts_df["source_post_id"].astype(str)
    + "|||"
    + reposts_df["repost_time"].astype(str)
    + "|||"
    + reposts_df["repost_text_raw"].astype(str)
    + "|||"
    + reposts_df["repost_user"].astype(str)
)
repost_sync["_sync_key"] = (
    repost_sync["source_post_id"].astype(str)
    + "|||"
    + repost_sync["publish_time"].astype(str)
    + "|||"
    + repost_sync["repost_text_clean"].astype(str)
    + "|||"
    + repost_sync["repost_user"].astype(str)
)
repost_sync = repost_sync.drop_duplicates(subset=["_sync_key"]).set_index("_sync_key")
for col in ["event_stage", "keyword_hit", "stance", "frame", "emotion"]:
    if col not in reposts_df.columns:
        reposts_df[col] = ""
    mapped = reposts_df["_sync_key"].map(repost_sync[col])
    reposts_df[col] = mapped.combine_first(reposts_df[col]).fillna("").astype(str)
reposts_df = reposts_df.drop(columns=["_sync_key"], errors="ignore")
reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")

comments_df["event_stage"] = comments_df["publish_time"].map(stage_from_ts)
comments_rules_hits = 0
for idx, row in comments_df.iterrows():
    hit_text, labels = apply_rules(str(row["text_clean"]), rules_df)
    comments_df.at[idx, "keyword_hit"] = hit_text
    comments_df.at[idx, "stance"] = labels["stance"]
    comments_df.at[idx, "frame"] = labels["frame"]
    comments_df.at[idx, "emotion"] = labels["emotion"]
    if hit_text:
        comments_rules_hits += 1
comments_df["is_valid"] = 1
comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

# Write total table after sync
all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")

# Re-read for final summary
final_all = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
final_posts = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
final_reposts = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
final_comments = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")

# Stats and logging
comment_final_rows = len(final_comments)
comment_hit_rows = int(final_comments["keyword_hit"].fillna("").astype(str).str.strip().ne("").sum())
comment_hit_rate = comment_hit_rows / comment_final_rows if comment_final_rows else 0.0
final_total_rows = len(final_all)
final_stage_dist = final_all["event_stage"].value_counts(dropna=False).to_dict()
comment_stage_dist = final_comments["event_stage"].value_counts(dropna=False).to_dict()

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open(LOG_PATH, "a", encoding="utf-8-sig") as f:
    f.write(f"\n[{now}] 第四轮处理：B 评论原始 {raw_rows} 条，按 comment_id 去重后 {dedup_rows} 条，comment_text 为空 {empty_comment_text_rows} 条。\n")
    f.write(f"[{now}] 第四轮处理：unique source_post_id {unique_source_ids} 个，其中 {matched_unique_source_ids} 个可在主帖表匹配，匹配比例 {source_match_ratio:.2%}。\n")
    f.write(f"[{now}] 第四轮处理：按 source_post_id 主帖收敛后剩余 {rows_after_source_and_nonempty} 条，进一步按 like_count 截断后最终保留 {final_converged_rows} 条。\n")
    f.write(f"[{now}] 第四轮处理：已生成 weibo_comments_clean.csv {comment_final_rows} 条，并追加到总表；当前总表最终 {final_total_rows} 条。\n")
    f.write(f"[{now}] 第四轮处理：总表 event_stage 分布 {final_stage_dist}。\n")
    f.write(f"[{now}] 第四轮处理：评论 keyword_hit 命中 {comment_hit_rows} 条，命中率 {comment_hit_rate:.2%}；评论 event_stage 分布 {comment_stage_dist}。\n")
    f.write(f"[{now}] 第四轮处理：已同步回写 weibo_posts_clean.csv、weibo_reposts_clean.csv、weibo_comments_clean.csv 与 all_weibo_texts_clean.csv。\n")

print("Done stage4")
print({
    "raw_rows": raw_rows,
    "dedup_comment_id": dedup_rows,
    "empty_comment_text": empty_comment_text_rows,
    "unique_source_post_id": unique_source_ids,
    "matched_unique_source_post_id": matched_unique_source_ids,
    "matched_ratio": source_match_ratio,
    "after_source_match_and_nonempty": rows_after_source_and_nonempty,
    "after_cap": final_converged_rows,
    "comment_keyword_hit_rows": comment_hit_rows,
    "comment_keyword_hit_rate": comment_hit_rate,
    "final_total_rows": final_total_rows,
})
