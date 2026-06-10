from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
COMMENTS_PATH = OUT / "weibo_comments_clean.csv"
QQ_PATH = OUT / "qqmusic_comments_clean.csv"
RULES_PATH = OUT / "label_rules.xlsx"
LOG_PATH = OUT / "data_cleaning_log.txt"

AUTHOR_TYPE_MAP = {
    "ordinary_user": "普通用户",
    "media": "媒体",
    "legal_account": "法律博主",
    "music_account": "音乐博主",
    "marketing": "营销号",
    "fan_account": "粉丝号",
    "官方/工作室": "官方",
}

FRAME_MAP = {
    "public_opinion_operation": "platform_meta",
}

VALID_STANCE = {"support_zhang", "support_wang", "neutral", "anti_fanwar", "unclear"}
VALID_FRAME = {
    "original_singer",
    "copyright_authorization",
    "creator_identity",
    "memory_emotion",
    "legal_discussion",
    "fan_conflict",
    "platform_meta",
    "unclear",
}
VALID_EMOTION = {"unclear"}

STOPWORDS = {
    "的", "了", "和", "是", "在", "就", "都", "而", "及", "与", "还", "也", "很", "这", "那", "一个",
    "你", "我", "他", "她", "它", "们", "吧", "啊", "呢", "嘛", "呀", "吗", "被", "把", "对", "着",
    "有", "没", "无", "从", "到", "给", "让", "又", "再", "去", "来", "说", "看", "听", "做",
    "真的", "还是", "就是", "但是", "因为", "所以", "如果", "这个", "那个", "什么", "怎么", "非常",
    "年轮", "张碧晨", "汪苏泷", "张碧晨版", "汪苏泷版", "唯一原唱", "原唱", "授权", "收回授权",
}

URL_RE = re.compile(r"http[s]?://\S+", flags=re.IGNORECASE)
MENTION_RE = re.compile(r"@[^\s]+")
BRACKET_RE = re.compile(r"\[.*?\]")
ALLOWED_RE = re.compile(r"[^\u4E00-\u9FFF\u0020-\u007E\u3000-\u303F\uFF00-\uFFEF]", flags=re.UNICODE)
TIME_ONLY_RE = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?")
DATE_NO_YEAR_RE = re.compile(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日?")
DATE_WITH_YEAR_RE = re.compile(r"(?P<year>\d{4})[/-](?P<month>\d{1,2})[/-](?P<day>\d{1,2})")
DATE_CN_RE = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日?")
REFERENCE_DATE = pd.Timestamp("2026-05-30")


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
    if "标签值" in rules.columns:
        rules["标签值"] = rules["标签值"].replace({"public_opinion_operation": "platform_meta"})
    if "优先级" in rules.columns:
        rules = rules.sort_values(by=["优先级"], ascending=True).reset_index(drop=True)
    else:
        rules = rules.reset_index(drop=True)
    return rules


def save_rules(rules: pd.DataFrame) -> None:
    with pd.ExcelWriter(RULES_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        rules.to_excel(writer, sheet_name="关键词规则", index=False)


def append_suggestions_to_rules() -> tuple[int, pd.DataFrame]:
    rules = load_rules()
    suggestions = pd.read_excel(RULES_PATH, sheet_name="新增规则建议")
    suggestions = suggestions.rename(columns=lambda x: str(x).strip())
    if "标签值" in suggestions.columns:
        suggestions["标签值"] = suggestions["标签值"].replace({"public_opinion_operation": "platform_meta"})
    if suggestions.empty:
        return 0, rules
    rules = pd.concat([rules, suggestions], ignore_index=True)
    rules = rules.drop_duplicates(subset=["关键词", "条件", "标签类型", "标签值"], keep="first").reset_index(drop=True)
    save_rules(rules)
    return len(suggestions), rules


def normalize_common_values(frame_df: pd.DataFrame) -> pd.DataFrame:
    if "author_type" in frame_df.columns:
        frame_df["author_type"] = frame_df["author_type"].replace(AUTHOR_TYPE_MAP).fillna("").astype(str)
    if "frame" in frame_df.columns:
        frame_df["frame"] = frame_df["frame"].replace(FRAME_MAP).fillna("").astype(str)
        frame_df.loc[~frame_df["frame"].isin(VALID_FRAME), "frame"] = "unclear"
    if "stance" in frame_df.columns:
        frame_df["stance"] = frame_df["stance"].fillna("").astype(str)
        frame_df.loc[~frame_df["stance"].isin(VALID_STANCE), "stance"] = "unclear"
    if "emotion" in frame_df.columns:
        frame_df["emotion"] = frame_df["emotion"].fillna("").astype(str)
        frame_df.loc[~frame_df["emotion"].isin(VALID_EMOTION), "emotion"] = "unclear"
    return frame_df


def build_rule_stats(rules: pd.DataFrame, texts: pd.Series) -> pd.DataFrame:
    records = []
    for _, rule in rules.iterrows():
        kw = str(rule.get("关键词", "")).strip()
        cond = str(rule.get("条件", "包含")).strip()
        hits = int(texts.fillna("").astype(str).map(lambda t: kw == t if cond == "完全匹配" else kw in t).sum()) if kw else 0
        rec = rule.to_dict()
        rec["命中次数"] = hits
        rec["命中率"] = hits / len(texts) if len(texts) else 0
        records.append(rec)
    return pd.DataFrame(records)


def apply_keyword_labels(df: pd.DataFrame, rules: pd.DataFrame) -> tuple[int, int]:
    changed_rows = 0
    matched_rows = 0
    for idx, row in df.iterrows():
        text = str(row.get("text_clean", ""))
        existing_stance = str(row.get("stance", "")).strip()
        existing_frame = str(row.get("frame", "")).strip()
        existing_emotion = str(row.get("emotion", "")).strip()
        if existing_stance != "unclear" and existing_frame != "unclear":
            continue

        hits: list[str] = []
        new_stance = existing_stance if existing_stance else ""
        new_frame = existing_frame if existing_frame else ""
        new_emotion = existing_emotion if existing_emotion else ""

        for _, rule in rules.iterrows():
            keyword = str(rule.get("关键词", "")).strip()
            condition = str(rule.get("条件", "包含")).strip()
            label_type = str(rule.get("标签类型", "")).strip()
            label_value = str(rule.get("标签值", "")).strip()
            if not keyword or not label_type or not label_value:
                continue
            matched = text == keyword if condition == "完全匹配" else keyword in text
            if not matched:
                continue
            if keyword not in hits:
                hits.append(keyword)
            if label_type == "stance" and (not new_stance or new_stance == "unclear"):
                new_stance = label_value
            elif label_type == "frame" and (not new_frame or new_frame == "unclear"):
                new_frame = label_value
            elif label_type == "emotion" and (not new_emotion or new_emotion == "unclear"):
                new_emotion = label_value

        if hits:
            matched_rows += 1
            current_hits = str(row.get("keyword_hit", "")).strip()
            merged_hits = [h for h in current_hits.split(";") if h] if current_hits else []
            for h in hits:
                if h not in merged_hits:
                    merged_hits.append(h)
            df.at[idx, "keyword_hit"] = ";".join(merged_hits)

        updated = False
        if existing_stance == "unclear" and new_stance and new_stance != existing_stance:
            df.at[idx, "stance"] = new_stance
            updated = True
        if existing_frame == "unclear" and new_frame and new_frame != existing_frame:
            df.at[idx, "frame"] = new_frame
            updated = True
        if existing_emotion == "unclear" and new_emotion and new_emotion != existing_emotion:
            df.at[idx, "emotion"] = new_emotion
            updated = True
        if updated:
            changed_rows += 1
    return changed_rows, matched_rows


# Load tables
all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")
qq_df = pd.read_csv(QQ_PATH, encoding="utf-8-sig")
rules_df = load_rules()

# 1-2) author_type and frame normalization
all_before_author = all_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)
posts_before_author = posts_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)
reposts_before_author = reposts_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)
comments_before_author = comments_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)

all_df = normalize_common_values(all_df)
posts_df = normalize_common_values(posts_df)
reposts_df = normalize_common_values(reposts_df)
comments_df = normalize_common_values(comments_df)
qq_df = normalize_common_values(qq_df)

all_author_changes = int((all_before_author != all_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)).sum()) if "author_type" in all_df.columns else 0
posts_author_changes = int((posts_before_author != posts_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)).sum()) if "author_type" in posts_df.columns else 0
reposts_author_changes = int((reposts_before_author != reposts_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)).sum()) if "author_type" in reposts_df.columns else 0
comments_author_changes = int((comments_before_author != comments_df.get("author_type", pd.Series(dtype=str)).fillna("").astype(str)).sum()) if "author_type" in comments_df.columns else 0

frame_replaced_total = 0
for frame_df in [all_df, posts_df, reposts_df, comments_df, qq_df]:
    if "frame" in frame_df.columns:
        frame_replaced_total += int((frame_df["frame"].fillna("").astype(str) == "platform_meta").sum())

stance_invalid_count = 0
emotion_invalid_count = 0
for frame_df in [all_df, posts_df, reposts_df, comments_df, qq_df]:
    if "stance" in frame_df.columns:
        stance_series = frame_df["stance"].fillna("").astype(str)
        stance_invalid_count += int((~stance_series.isin(VALID_STANCE) & (stance_series != "")).sum())
    if "emotion" in frame_df.columns:
        emotion_series = frame_df["emotion"].fillna("").astype(str)
        emotion_invalid_count += int((~emotion_series.isin(VALID_EMOTION) & (emotion_series != "")).sum())

# 3) append suggestions to rules and rebuild stats
added_rules_count, rules_df = append_suggestions_to_rules()

# 4) re-label only rows with stance unclear or frame unclear, preserving existing non-empty labels
all_df["keyword_hit"] = all_df["keyword_hit"].fillna("").astype(str)
all_df["stance"] = all_df["stance"].fillna("").astype(str)
all_df["frame"] = all_df["frame"].fillna("").astype(str)
all_df["emotion"] = all_df["emotion"].fillna("").astype(str)

pre_relabeled_rows = int(((all_df["stance"] == "unclear") | (all_df["frame"] == "unclear")).sum())
changed_rows, matched_rows = apply_keyword_labels(all_df, rules_df)

# ensure labels remain valid, and fill any still-blank label fields for rows that were touched
for col in ["stance", "frame", "emotion"]:
    all_df[col] = all_df[col].fillna("").astype(str)
    all_df.loc[all_df[col].astype(str).str.strip().eq(""), col] = "unclear"

# 5) sync labels back to sub tables
post_lookup = all_df[all_df["data_type"].astype(str) == "post"][
    ["source_id", "stance", "frame", "emotion", "keyword_hit"]
].drop_duplicates(subset=["source_id"]).set_index("source_id")
for target_df, key_col in [(posts_df, "post_id")]:
    if key_col in target_df.columns:
        for col in ["stance", "frame", "emotion", "keyword_hit"]:
            if col not in target_df.columns:
                target_df[col] = ""
        mapped = target_df[key_col].astype(str).map(post_lookup["stance"])
        target_df["stance"] = mapped.combine_first(target_df["stance"]).fillna("unclear").astype(str)
        target_df["frame"] = target_df[key_col].astype(str).map(post_lookup["frame"]).combine_first(target_df["frame"]).fillna("unclear").astype(str)
        target_df["emotion"] = target_df[key_col].astype(str).map(post_lookup["emotion"]).combine_first(target_df["emotion"]).fillna("unclear").astype(str)
        target_df["keyword_hit"] = target_df[key_col].astype(str).map(post_lookup["keyword_hit"]).combine_first(target_df["keyword_hit"]).fillna("").astype(str)

repost_lookup = all_df[all_df["data_type"].astype(str) == "repost"].copy()
repost_lookup["sync_key"] = (
    repost_lookup["source_id"].astype(str)
    + "|||"
    + repost_lookup["publish_time"].astype(str)
    + "|||"
    + repost_lookup["text_clean"].astype(str)
    + "|||"
    + repost_lookup["author_name"].astype(str)
)
repost_lookup = repost_lookup[["sync_key", "stance", "frame", "emotion", "keyword_hit"]].drop_duplicates(subset=["sync_key"]).set_index("sync_key")
if "sync_key" not in reposts_df.columns:
    reposts_df["sync_key"] = (
        reposts_df["source_post_id"].astype(str)
        + "|||"
        + reposts_df["repost_time"].astype(str)
        + "|||"
        + reposts_df["repost_text_raw"].astype(str)
        + "|||"
        + reposts_df["repost_user"].astype(str)
    )
for col in ["stance", "frame", "emotion", "keyword_hit"]:
    if col not in reposts_df.columns:
        reposts_df[col] = ""
    reposts_df[col] = reposts_df["sync_key"].map(repost_lookup[col]).combine_first(reposts_df[col]).fillna("").astype(str)
reposts_df = reposts_df.drop(columns=["sync_key"], errors="ignore")

comment_lookup = all_df[all_df["data_type"].astype(str) == "comment"][["id", "stance", "frame", "emotion", "keyword_hit"]].drop_duplicates(subset=["id"]).set_index("id")
if "comment_id" in comments_df.columns:
    for col in ["stance", "frame", "emotion", "keyword_hit"]:
        if col not in comments_df.columns:
            comments_df[col] = ""
    comment_key = comments_df["comment_id"].astype(str).map(lambda x: f"comment_{x}")
    comments_df["stance"] = comment_key.map(comment_lookup["stance"]).combine_first(comments_df["stance"]).fillna("unclear").astype(str)
    comments_df["frame"] = comment_key.map(comment_lookup["frame"]).combine_first(comments_df["frame"]).fillna("unclear").astype(str)
    comments_df["emotion"] = comment_key.map(comment_lookup["emotion"]).combine_first(comments_df["emotion"]).fillna("unclear").astype(str)
    comments_df["keyword_hit"] = comment_key.map(comment_lookup["keyword_hit"]).combine_first(comments_df["keyword_hit"]).fillna("").astype(str)

# QQ music: keep as is but normalize frame and author_type if present
if "frame" in qq_df.columns:
    qq_df["frame"] = qq_df["frame"].replace(FRAME_MAP).fillna("").astype(str)
if "author_type" in qq_df.columns:
    qq_df["author_type"] = qq_df["author_type"].replace(AUTHOR_TYPE_MAP).fillna("").astype(str)

# 6) rebuild stats sheets
all_texts_for_stats = pd.concat([
    all_df.get("text_clean", pd.Series(dtype=str)),
    comments_df.get("text_clean", pd.Series(dtype=str)),
    qq_df.get("text_clean", pd.Series(dtype=str)),
], ignore_index=True)

rules_stats = build_rule_stats(rules_df, all_texts_for_stats)
with pd.ExcelWriter(RULES_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    rules_df.to_excel(writer, sheet_name="关键词规则", index=False)
    rules_stats.to_excel(writer, sheet_name="标注统计", index=False)
    # preserve existing supporting sheets if they exist, rewrite them unchanged
    pd.read_excel(RULES_PATH, sheet_name="高频词Top50").to_excel(writer, sheet_name="高频词Top50", index=False)
    pd.read_excel(RULES_PATH, sheet_name="新增规则建议").to_excel(writer, sheet_name="新增规则建议", index=False)

# 7) save tables
all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")
qq_df.to_csv(QQ_PATH, index=False, encoding="utf-8-sig")

# 8) log
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
all_author_mapped = {
    "ordinary_user": "普通用户",
    "media": "媒体",
    "legal_account": "法律博主",
    "music_account": "音乐博主",
    "marketing": "营销号",
    "fan_account": "粉丝号",
    "官方/工作室": "官方",
}
frame_replaced_total = 0
for frame_df in [all_df, posts_df, reposts_df, comments_df, qq_df]:
    if "frame" in frame_df.columns:
        frame_replaced_total += int((frame_df["frame"].fillna("").astype(str) == "platform_meta").sum())

final_all = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
stance_dist = final_all["stance"].fillna("unclear").astype(str).value_counts().to_dict() if "stance" in final_all.columns else {}
frame_dist = final_all["frame"].fillna("unclear").astype(str).value_counts().to_dict() if "frame" in final_all.columns else {}
event_dist = final_all["event_stage"].fillna("unclear").astype(str).value_counts().to_dict() if "event_stage" in final_all.columns else {}
emotion_nonempty = int(final_all.get("emotion", pd.Series([""] * len(final_all))).fillna("").astype(str).str.strip().ne("").sum()) if "emotion" in final_all.columns else 0
emotion_rate = emotion_nonempty / len(final_all) if len(final_all) else 0

with open(LOG_PATH, "a", encoding="utf-8-sig") as f:
    f.write(f"\n[{now}] 收尾处理：author_type 已统一中文映射，涉及 all_weibo {all_author_changes} 条、posts {posts_author_changes} 条、reposts {reposts_author_changes} 条、comments {comments_author_changes} 条。\n")
    f.write(f"[{now}] 收尾处理：frame 中 public_opinion_operation 已统一为 platform_meta，累计替换 {frame_replaced_total} 行。stance 无新增非法值，emotion 统一保留为 unclear。\n")
    f.write(f"[{now}] 收尾处理：已将 label_rules.xlsx 的新增规则建议追加到关键词规则，共新增 {added_rules_count} 条；对 stance/frame 仍为 unclear 的文本进行重标注，额外命中 {changed_rows} 条，关键词命中 {matched_rows} 条。\n")
    f.write(f"[{now}] 收尾处理：当前总表 {len(final_all)} 条，stance 分布 {stance_dist}，frame 分布 {frame_dist}，event_stage 分布 {event_dist}，emotion 非空率 {emotion_rate:.2%}。\n")
    f.write(f"[{now}] 收尾处理：已同步回写 all_weibo_texts_clean.csv、weibo_posts_clean.csv、weibo_reposts_clean.csv、weibo_comments_clean.csv、qqmusic_comments_clean.csv 与 label_rules.xlsx。\n")

print("Done final cleanup")
print({
    "all_author_changes": all_author_changes,
    "posts_author_changes": posts_author_changes,
    "reposts_author_changes": reposts_author_changes,
    "comments_author_changes": comments_author_changes,
    "frame_replaced_total": frame_replaced_total,
    "added_rules_count": added_rules_count,
    "changed_rows": changed_rows,
    "matched_rows": matched_rows,
    "total_rows": len(final_all),
    "emotion_rate": emotion_rate,
})
