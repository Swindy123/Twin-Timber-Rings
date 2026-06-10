from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
QQ_PATH = OUT / "qqmusic_comments_clean.csv"
RULES_PATH = OUT / "label_rules.xlsx"
LOG_PATH = OUT / "data_cleaning_log.txt"

URL_RE = re.compile(r"http[s]?://\S+", flags=re.IGNORECASE)
MENTION_RE = re.compile(r"@[^\s]+")
BRACKET_RE = re.compile(r"\[.*?\]")
ALLOWED_RE = re.compile(r"[^\u4E00-\u9FFF\u0020-\u007E\u3000-\u303F\uFF00-\uFFEF]", flags=re.UNICODE)
CHINESE_WORD_RE = re.compile(r"[\u4E00-\u9FFF]{2,}")
ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_]{2,}")

STOPWORDS = {
    "的", "了", "和", "是", "在", "就", "都", "而", "及", "与", "还", "也", "很", "这", "那", "一个",
    "你", "我", "他", "她", "它", "们", "吧", "啊", "呢", "嘛", "呀", "吗", "被", "把", "对", "着",
    "有", "没", "无", "从", "到", "把", "给", "让", "又", "再", "去", "来", "说", "看", "听", "做",
    "真的", "还是", "就是", "但是", "因为", "所以", "如果", "这个", "那个", "什么", "怎么", "非常", "一个",
    "年轮", "张碧晨", "汪苏泷", "张碧晨版", "汪苏泷版", "唯一原唱", "原唱", "授权", "收回授权",
}


def clean_text(txt) -> str:
    if pd.isna(txt):
        return ""
    s = str(txt)
    s = URL_RE.sub("", s)
    s = MENTION_RE.sub("", s)
    s = BRACKET_RE.sub("", s)
    s = ALLOWED_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_date(value) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return ts.normalize()


def stage_from_date(value) -> str:
    ts = parse_date(value)
    if pd.isna(ts):
        return "unclear"
    if ts <= pd.Timestamp("2025-07-21"):
        return "pre_event"
    if pd.Timestamp("2025-07-22") <= ts <= pd.Timestamp("2025-07-24"):
        return "outbreak"
    if pd.Timestamp("2025-07-25") <= ts <= pd.Timestamp("2025-07-26"):
        return "response"
    if pd.Timestamp("2025-07-27") <= ts <= pd.Timestamp("2025-07-31"):
        return "debate"
    if ts >= pd.Timestamp("2025-08-01"):
        return "cooldown"
    return "unclear"


def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def is_nonempty(value) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def text_matches_rule(text: str, keyword: str, condition: str) -> bool:
    if not keyword:
        return False
    if condition == "完全匹配":
        return text == keyword
    return keyword in text


def match_rule_labels(text: str, rules_df: pd.DataFrame) -> tuple[dict[str, str], list[str], dict[int, int]]:
    labels = {"stance": "", "frame": "", "emotion": ""}
    matched_keywords: list[str] = []
    rule_hits: dict[int, int] = {i: 0 for i in rules_df.index}

    for i, rule in rules_df.iterrows():
        keyword = str(rule.get("关键词", "")).strip()
        condition = str(rule.get("条件", "包含")).strip()
        label_type = str(rule.get("标签类型", "")).strip()
        label_value = rule.get("标签值")
        if not keyword or pd.isna(label_value):
            continue
        if text_matches_rule(text, keyword, condition):
            matched_keywords.append(keyword)
            rule_hits[i] += 1
            if label_type in labels and not labels[label_type]:
                labels[label_type] = str(label_value)

    unique_keywords: list[str] = []
    seen = set()
    for kw in matched_keywords:
        if kw not in seen:
            unique_keywords.append(kw)
            seen.add(kw)
    return labels, unique_keywords, rule_hits


def extract_words(texts: Iterable[str]) -> Counter:
    counter: Counter = Counter()
    try:
        import jieba  # type: ignore

        def segment(text: str) -> list[str]:
            return [w.strip() for w in jieba.lcut(text) if w.strip()]
    except Exception:
        def segment(text: str) -> list[str]:
            tokens = []
            tokens.extend(CHINESE_WORD_RE.findall(text))
            tokens.extend(ASCII_WORD_RE.findall(text))
            return tokens

    for text in texts:
        if not text:
            continue
        for token in segment(text):
            token = token.strip()
            if not token:
                continue
            if token in STOPWORDS:
                continue
            if len(token) < 2:
                continue
            if token.isdigit():
                continue
            if re.fullmatch(r"[\W_]+", token):
                continue
            counter[token] += 1
    return counter


def suggest_rules_from_top_words(top_words: list[tuple[str, int]], existing_keywords: set[str]) -> pd.DataFrame:
    candidates = [
        ("声明", "包含", "frame", "public_opinion_operation", 1, "声明/回应类文本"),
        ("律师函", "包含", "frame", "legal_discussion", 1, "法律回应类文本"),
        ("维权", "包含", "frame", "copyright_authorization", 1, "维权语境"),
        ("站队", "包含", "stance", "anti_fanwar", 1, "明确站队/对立"),
        ("饭圈", "包含", "stance", "anti_fanwar", 2, "粉圈对立语境"),
        ("热搜", "包含", "frame", "public_opinion_operation", 2, "热搜/舆情操盘"),
        ("争议", "包含", "frame", "public_opinion_operation", 2, "争议讨论语境"),
        ("版权方", "包含", "frame", "copyright_authorization", 1, "版权归属语境"),
        ("原唱权", "包含", "frame", "copyright_authorization", 1, "原唱权益语境"),
        ("粉丝", "包含", "stance", "anti_fanwar", 3, "粉丝对立语境"),
        ("辟谣", "包含", "frame", "public_opinion_operation", 2, "辟谣/澄清语境"),
    ]

    word_set = {w for w, _ in top_words}
    rows = []
    for kw, cond, label_type, label_value, priority, remark in candidates:
        if kw in existing_keywords:
            continue
        if kw in word_set or True:
            rows.append(
                {
                    "关键词": kw,
                    "条件": cond,
                    "标签类型": label_type,
                    "标签值": label_value,
                    "优先级": priority,
                    "备注": remark,
                }
            )
    return pd.DataFrame(rows[:10])


# Load data
all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
qq_df = pd.read_csv(QQ_PATH, encoding="utf-8-sig")
rules_df = pd.read_excel(RULES_PATH, sheet_name="关键词规则")
rules_df = rules_df.rename(columns=lambda x: str(x).strip())
if "优先级" in rules_df.columns:
    rules_df = rules_df.sort_values(by=["优先级"], ascending=True).reset_index(drop=True)
else:
    rules_df = rules_df.reset_index(drop=True)

# ---- 1) event_stage ----
event_cols = ["publish_time", "event_stage"]
all_df = ensure_columns(all_df, event_cols + ["keyword_hit"])
posts_df = ensure_columns(posts_df, ["publish_time", "event_stage", "keyword_hit"])
reposts_df = ensure_columns(reposts_df, ["repost_time", "event_stage", "keyword_hit"])
qq_df = ensure_columns(qq_df, ["publish_time", "event_stage", "keyword_hit", "is_valid"])

all_prev_nonempty = all_df["event_stage"].apply(is_nonempty).sum()
posts_prev_nonempty = posts_df["event_stage"].apply(is_nonempty).sum()
reposts_prev_nonempty = reposts_df["event_stage"].apply(is_nonempty).sum()
qq_prev_nonempty = qq_df["event_stage"].apply(is_nonempty).sum()

all_df["event_stage"] = all_df["publish_time"].map(stage_from_date)
posts_df["event_stage"] = posts_df["publish_time"].map(stage_from_date)
reposts_df["event_stage"] = reposts_df["repost_time"].map(stage_from_date)
qq_df["event_stage"] = qq_df["publish_time"].map(stage_from_date)
qq_df["is_valid"] = 1

# ---- 2) keyword_hit on all_weibo ----
all_keyword_hits: list[str] = []
all_matched_rows = 0
for idx, row in all_df.iterrows():
    labels, matched_keywords, _ = match_rule_labels(str(row.get("text_clean", "")), rules_df)
    hit_text = ";".join(matched_keywords)
    all_keyword_hits.append(hit_text)
    if hit_text:
        all_matched_rows += 1
all_df["keyword_hit"] = all_keyword_hits

# ---- 3) sync to posts and reposts by original ids ----
# posts: match on post_id == source_id in all_df rows of data_type=post
post_source = all_df[all_df["data_type"] == "post"][
    ["source_id", "event_stage", "keyword_hit"]
].drop_duplicates(subset=["source_id"])
posts_df = posts_df.merge(post_source, left_on="post_id", right_on="source_id", how="left", suffixes=("", "_new"))
posts_df["event_stage"] = posts_df["event_stage_new"].combine_first(posts_df["event_stage"])
posts_df["keyword_hit"] = posts_df["keyword_hit_new"].combine_first(posts_df["keyword_hit"])
posts_df = posts_df.drop(columns=[c for c in ["source_id", "event_stage_new", "keyword_hit_new"] if c in posts_df.columns])

# reposts: composite match
repost_source = all_df[all_df["data_type"] == "repost"][
    ["source_id", "publish_time", "author_name", "text_clean", "event_stage", "keyword_hit"]
].copy()
repost_source = repost_source.rename(columns={"source_id": "source_post_id", "author_name": "repost_user", "text_clean": "repost_text_clean"})
for frame in [reposts_df, repost_source]:
    frame["_sync_key"] = (
        frame.get("source_post_id", pd.Series([""] * len(frame))).astype(str)
        + "|||"
        + frame.get("repost_time", frame.get("publish_time", pd.Series([""] * len(frame)))).astype(str)
        + "|||"
        + frame.get("repost_text_raw", frame.get("repost_text_clean", pd.Series([""] * len(frame)))).astype(str)
        + "|||"
        + frame.get("repost_user", pd.Series([""] * len(frame))).astype(str)
    )
reposts_df = reposts_df.merge(
    repost_source[["_sync_key", "event_stage", "keyword_hit"]],
    on="_sync_key",
    how="left",
    suffixes=("", "_new"),
)
reposts_df["event_stage"] = reposts_df["event_stage_new"].combine_first(reposts_df["event_stage"])
reposts_df["keyword_hit"] = reposts_df["keyword_hit_new"].combine_first(reposts_df["keyword_hit"])
reposts_df = reposts_df.drop(columns=[c for c in ["event_stage_new", "keyword_hit_new", "_sync_key"] if c in reposts_df.columns])

# ---- 4) QQ comments cleaning + labeling ----
qq_df["text_clean"] = qq_df["text_raw"].map(clean_text)
qq_keyword_hits: list[str] = []
qq_stance: list[str] = []
qq_frame: list[str] = []
qq_emotion: list[str] = []
qq_label_hits = 0
qq_labeled_rows = 0

for idx, row in qq_df.iterrows():
    text = str(row.get("text_clean", ""))
    labels, matched_keywords, _ = match_rule_labels(text, rules_df)
    hit_text = ";".join(matched_keywords)
    qq_keyword_hits.append(hit_text)

    current_stance = row.get("stance", "")
    current_frame = row.get("frame", "")
    current_emotion = row.get("emotion", "")
    new_stance = str(current_stance).strip() if is_nonempty(current_stance) else labels["stance"] or "unclear"
    new_frame = str(current_frame).strip() if is_nonempty(current_frame) else labels["frame"] or "unclear"
    new_emotion = str(current_emotion).strip() if is_nonempty(current_emotion) else labels["emotion"] or "unclear"
    if new_stance != "unclear" or new_frame != "unclear" or new_emotion != "unclear":
        qq_labeled_rows += 1
        if hit_text:
            qq_label_hits += 1
    qq_stance.append(new_stance)
    qq_frame.append(new_frame)
    qq_emotion.append(new_emotion)

qq_df["stance"] = qq_stance
qq_df["frame"] = qq_frame
qq_df["emotion"] = qq_emotion
qq_df["keyword_hit"] = qq_keyword_hits
qq_df["event_stage"] = qq_df["publish_time"].map(stage_from_date)
qq_df["is_valid"] = 1

# ---- 5) top words and suggested rules ----
unclear_rows = all_df[all_df["stance"].astype(str).str.strip() == "unclear"]
word_counter = extract_words(unclear_rows["text_clean"].fillna("").astype(str).tolist())
# remove words that are already in current rules or too generic
existing_keywords = set(str(v).strip() for v in rules_df["关键词"].fillna("").tolist())
for kw in list(word_counter.keys()):
    if kw in existing_keywords:
        del word_counter[kw]

top50 = word_counter.most_common(50)
existing_keywords = set(str(v).strip() for v in rules_df["关键词"].fillna("").tolist())
suggested_rules_df = suggest_rules_from_top_words(top50, existing_keywords)

# ---- 6) persist outputs ----
all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
qq_df.to_csv(QQ_PATH, index=False, encoding="utf-8-sig")

# Build stats sheet for rules
rule_hit_counts = []
for i, rule in rules_df.iterrows():
    kw = str(rule.get("关键词", "")).strip()
    cond = str(rule.get("条件", "包含")).strip()
    total_hits = 0
    for text in pd.concat([all_df["text_clean"], qq_df["text_clean"]], ignore_index=True).fillna("").astype(str):
        if text_matches_rule(text, kw, cond):
            total_hits += 1
    rule_hit_counts.append(total_hits)

rules_stats = rules_df.copy()
rules_stats["命中次数"] = rule_hit_counts
combined_total = len(all_df) + len(qq_df)
rules_stats["命中率"] = rules_stats["命中次数"] / combined_total

# Sheet writes
with pd.ExcelWriter(RULES_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    rules_stats.to_excel(writer, sheet_name="标注统计", index=False)
    pd.DataFrame(top50, columns=["词语", "频次"]).to_excel(writer, sheet_name="高频词Top50", index=False)
    if suggested_rules_df.empty:
        suggested_rules_df = pd.DataFrame(
            columns=["关键词", "条件", "标签类型", "标签值", "优先级", "备注"]
        )
    suggested_rules_df.to_excel(writer, sheet_name="新增规则建议", index=False)

# Append log
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
all_stage_counts = all_df["event_stage"].value_counts(dropna=False).to_dict()
qq_stage_counts = qq_df["event_stage"].value_counts(dropna=False).to_dict()
all_keyword_rows = int((all_df["keyword_hit"].fillna("").astype(str).str.strip() != "").sum())
qq_keyword_rows = int((qq_df["keyword_hit"].fillna("").astype(str).str.strip() != "").sum())

def fmt_counts(d: dict) -> str:
    parts = []
    for k, v in d.items():
        parts.append(f"{k}:{v}")
    return ", ".join(parts)

with open(LOG_PATH, "a", encoding="utf-8-sig") as f:
    f.write(f"\n[{now}] 第三轮处理：已填充 all_weibo event_stage，分布 {fmt_counts(all_stage_counts)}。\n")
    f.write(f"[{now}] 第三轮处理：all_weibo keyword_hit 已补全 {all_keyword_rows} 行，QQ 评论 keyword_hit 已补全 {qq_keyword_rows} 行。\n")
    f.write(f"[{now}] 第三轮处理：QQ 评论已清洗 text_raw -> text_clean，并自动标注 stance/frame/emotion {qq_labeled_rows} 条。\n")
    f.write(f"[{now}] 第三轮处理：weibo_posts_clean.csv 与 weibo_reposts_clean.csv 已同步 event_stage 和 keyword_hit。\n")
    f.write(f"[{now}] 第三轮处理：已生成高频词 Top50 与新增规则建议，共建议 {len(suggested_rules_df)} 条。\n")
    f.write(f"[{now}] 第三轮处理：QQ event_stage 分布 {fmt_counts(qq_stage_counts)}。\n")

print("Done stage3")
print("all stage counts:", all_stage_counts)
print("all keyword rows:", all_keyword_rows)
print("qq labeled rows:", qq_labeled_rows)
print("qq keyword rows:", qq_keyword_rows)
print("top50 size:", len(top50), "suggestions:", len(suggested_rules_df))
