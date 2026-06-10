from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

# Clean text with whitelist: keep CJK, ASCII printable, common fullwidth punctuation
ALLOWED_RE = re.compile(r"[^\u4E00-\u9FFF\u0020-\u007E\u3000-\u303F\uFF00-\uFFEF]", flags=re.UNICODE)


def clean_text(txt: str) -> str:
    if txt is None:
        return ""
    s = str(txt)
    # 1. remove URLs
    s = re.sub(r"http[s]?://\S+", "", s)
    # 2. remove @mentions
    s = re.sub(r"@[^\s]+", "", s)
    # 3. remove [xxx] emoticons
    s = re.sub(r"\[.*?\]", "", s)
    # 4. remove characters outside allowed ranges (this removes emoji and other symbols)
    s = ALLOWED_RE.sub("", s)
    # 5. collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---- Task 1: 清洗 ----
all_path = OUT / "all_weibo_texts_clean.csv"
df = pd.read_csv(all_path, encoding="utf-8-sig")
orig_texts = df.get("text_raw", pd.Series([""]*len(df))).fillna("").astype(str)
print("Total rows:", len(df))

df["text_clean"] = orig_texts.map(clean_text)
df["text_clean"] = df["text_clean"].astype(str)
df.to_csv(all_path, index=False, encoding="utf-8-sig")

# ---- Task 2: 自动标注 ----
rules_path = OUT / "label_rules.xlsx"
rules_df = pd.read_excel(rules_path, sheet_name="关键词规则")
rules_df = rules_df.rename(columns=lambda x: str(x).strip())
if "优先级" in rules_df.columns:
    rules_df = rules_df.sort_values(by="优先级", ascending=True).reset_index(drop=True)
else:
    rules_df = rules_df.reset_index(drop=True)

rule_hits = [0] * len(rules_df)
for col in ["stance", "frame", "emotion"]:
    if col not in df.columns:
        df[col] = pd.NA


def is_nonempty(val) -> bool:
    return pd.notna(val) and str(val).strip() != ""

skipped_existing = 0
applied_count = 0

for idx, row in df.iterrows():
    if any(is_nonempty(row.get(c)) for c in ["stance", "frame", "emotion"]):
        skipped_existing += 1
        continue
    text = str(row.get("text_clean", ""))
    matched_any = False
    for r_i, r in rules_df.iterrows():
        kw = str(r.get("关键词", "")).strip()
        cond = str(r.get("条件", "包含")).strip()
        label_type = str(r.get("标签类型", "")).strip()
        label_value = r.get("标签值")
        if not kw or pd.isna(label_value):
            continue
        matched = False
        if cond == "完全匹配":
            if text == kw:
                matched = True
        else:
            if kw in text:
                matched = True
        if matched:
            if label_type in ["stance", "frame", "emotion"]:
                if not is_nonempty(df.at[idx, label_type]):
                    df.at[idx, label_type] = str(label_value)
                    matched_any = True
            rule_hits[r_i] += 1
    if matched_any:
        applied_count += 1

# set unclear for rows still empty
for idx, row in df.iterrows():
    if any(is_nonempty(row.get(c)) for c in ["stance", "frame", "emotion"]):
        continue
    df.at[idx, "stance"] = "unclear"
    df.at[idx, "frame"] = "unclear"
    df.at[idx, "emotion"] = "unclear"

# save
df.to_csv(all_path, index=False, encoding="utf-8-sig")

# ---- Task 3: 同步子表 ----
posts_path = OUT / "weibo_posts_clean.csv"
reposts_path = OUT / "weibo_reposts_clean.csv"
posts_df = pd.read_csv(posts_path, encoding="utf-8-sig")
reposts_df = pd.read_csv(reposts_path, encoding="utf-8-sig")

posts_map = df[df["data_type"] == "post"][ ["source_id", "stance", "frame", "emotion", "is_valid"] ].drop_duplicates(subset=["source_id"]).set_index("source_id")
for pid, vals in posts_map.iterrows():
    mask = posts_df["post_id"] == pid
    if mask.any():
        for col in ["stance","frame","emotion","is_valid"]:
            if col in posts_df.columns:
                cur = posts_df.loc[mask, col]
                if cur.isnull().all() or (cur.astype(str).str.strip()=="").all():
                    posts_df.loc[mask, col] = vals[col]

repost_all = df[df["data_type"] == "repost"][ ["source_id","text_raw","publish_time","stance","frame","emotion","is_valid"] ]
repost_all = repost_all.rename(columns={"source_id":"source_post_id","text_raw":"repost_text_raw","publish_time":"repost_time"})
reposts_df["_key"] = reposts_df["source_post_id"].astype(str) + "|||" + reposts_df["repost_text_raw"].astype(str) + "|||" + reposts_df["repost_time"].astype(str)
repost_all["_key"] = repost_all["source_post_id"].astype(str) + "|||" + repost_all["repost_text_raw"].astype(str) + "|||" + repost_all["repost_time"].astype(str)
repost_map = repost_all.set_index("_key")
for i, row in reposts_df.iterrows():
    k = row.get("_key")
    if k in repost_map.index:
        vals = repost_map.loc[k]
        for col in ["stance","frame","emotion","is_valid"]:
            if col in reposts_df.columns:
                cur = reposts_df.at[i, col]
                if pd.isna(cur) or str(cur).strip() == "":
                    reposts_df.at[i, col] = vals[col]
if "_key" in reposts_df.columns:
    reposts_df = reposts_df.drop(columns=["_key"])

posts_df.to_csv(posts_path, index=False, encoding="utf-8-sig")
reposts_df.to_csv(reposts_path, index=False, encoding="utf-8-sig")

# ---- Task 4: 日志与规则统计 ----
log_path = OUT / "data_cleaning_log.txt"
from datetime import datetime
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

total = len(df)
cleaned_nonempty = (df["text_clean"].astype(str).str.strip() != "").sum()
label_applied = applied_count
skipped = skipped_existing
processed_total = total - skipped
match_rate = label_applied / processed_total if processed_total>0 else 0.0

with open(log_path, 'a', encoding='utf-8-sig') as f:
    f.write(f"\n[{now}] 阶段2文本清洗：处理 {total} 条，清洗后非空 {cleaned_nonempty} 条。\n")
    f.write(f"[{now}] 阶段2自动标注：跳过已有人为标注 {skipped} 条，本轮自动标注应用于 {processed_total} 条，命中 {label_applied} 条，命中率 {match_rate:.2%}。\n")

rules_df2 = rules_df.copy()
rules_df2['命中次数'] = rule_hits
rules_df2['命中率'] = rules_df2['命中次数'] / total
with pd.ExcelWriter(rules_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
    rules_df2.to_excel(writer, sheet_name='标注统计', index=False)

print('Done stage2')
print('total', total, 'clean_nonempty', cleaned_nonempty, 'label_applied', label_applied, 'skipped', skipped)
