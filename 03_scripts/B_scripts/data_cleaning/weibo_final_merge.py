"""
从已有的 _predicted_cleaned.csv 生成旧项目格式的微博 CSV：
- weibo_posts_clean.csv
- weibo_reposts_clean.csv
- weibo_comments_clean.csv
- all_weibo_texts_clean.csv
额外列全部保留，all_weibo 中会加上数据类别前缀。
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

# ============ 配置路径（按实际修改） ============
INPUT_DIR = Path(r"E:\大学\大二\大二下\数据可视化\大作业_传播学\0606\cleaned_data_20250606")
OUTPUT_DIR = Path(r"E:\大学\大二\大二下\数据可视化\大作业_传播学\0606\cleaned_data_20250606\output")
# ==============================================
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 文本清洗函数（生成 text_clean）----------
URL_RE = re.compile(r"http[s]?://\S+", flags=re.IGNORECASE)
MENTION_RE = re.compile(r"@[^\s]+")
BRACKET_RE = re.compile(r"\[.*?\]")
ALLOWED_RE = re.compile(r"[^\u4E00-\u9FFF\u0020-\u007E\u3000-\u303F\uFF00-\uFFEF]", flags=re.UNICODE)

def clean_text(txt):
    if pd.isna(txt):
        return ""
    s = str(txt)
    s = URL_RE.sub("", s)
    s = MENTION_RE.sub("", s)
    s = BRACKET_RE.sub("", s)
    s = ALLOWED_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ===================== 读取三个 cleaned 文件 =====================
posts_raw = pd.read_csv(INPUT_DIR / "weibo_posts_predicted_cleaned.csv", encoding="utf-8-sig")
reposts_raw = pd.read_csv(INPUT_DIR / "weibo_reposts_api_clean_multihop_filtered_predicted_cleaned.csv", encoding="utf-8-sig")
comments_raw = pd.read_csv(INPUT_DIR / "weibo_comments_all_predicted_cleaned.csv", encoding="utf-8-sig")

print(f"帖子: {len(posts_raw)} 行, 转发: {len(reposts_raw)} 行, 评论: {len(comments_raw)} 行")

# ===================== 处理帖子 =====================
posts = pd.DataFrame()
posts["post_id"] = posts_raw["post_id"].astype(str)
posts["url"] = posts_raw["url"]
posts["publish_time"] = posts_raw["publish_time"]      # 保持原始字符串，已有 event_stage 就不解析了
posts["author_name"] = posts_raw["author_name"]
posts["author_type"] = posts_raw["author_type"]
posts["text_raw"] = posts_raw["text"]
posts["text_clean"] = posts["text_raw"].map(clean_text)
posts["like_count"] = posts_raw["like_count"]
posts["comment_count"] = posts_raw["comment_count"]
posts["repost_count"] = posts_raw["repost_count"]
posts["crawl_time"] = posts_raw["crawl_time"]
posts["stance"] = posts_raw["predicted_stance"]          # 使用你已有的预测立场
posts["frame"] = "unclear"                               # 待填充
posts["event_stage"] = posts_raw["event_stage"]          # 你已经算好的
posts["keyword_hit"] = posts_raw["keyword_hit"].fillna("")
posts["is_valid"] = 1
posts["platform"] = "weibo"

# 保留新数据中的额外列（供子表和总表使用）
extra_post_cols = ["keyword", "prediction_source", "topic_tag", "userid"]
for col in extra_post_cols:
    posts[col] = posts_raw.get(col, pd.NA)

# 去重 post_id
posts = posts.drop_duplicates(subset=["post_id"], keep="first").reset_index(drop=True)
posts.to_csv(OUTPUT_DIR / "weibo_posts_clean.csv", index=False, encoding="utf-8-sig")
print(f"→ weibo_posts_clean.csv: {len(posts)} 行")

# ===================== 处理转发 =====================
reposts = pd.DataFrame()
reposts["source_post_id"] = reposts_raw["source_post_id"].astype(str)
reposts["source_post_url"] = reposts_raw["source_post_url"]
reposts["repost_time"] = reposts_raw["repost_time"]
reposts["repost_user"] = reposts_raw["repost_user_name"]
reposts["repost_text_raw"] = reposts_raw["repost_text"]
reposts["repost_text_clean"] = reposts["repost_text_raw"].map(clean_text)
reposts["repost_like_count"] = reposts_raw.get("repost_attitudes_count", 0)
reposts["repost_comments_count"] = reposts_raw.get("repost_comments_count", 0)
reposts["repost_reposts_count"] = reposts_raw.get("repost_reposts_count", 0)
reposts["user_type"] = "ordinary_user"
reposts["stance"] = reposts_raw["predicted_stance"]
reposts["frame"] = "unclear"
reposts["event_stage"] = reposts_raw["event_stage"]
reposts["keyword_hit"] = reposts_raw["keyword_hit"].fillna("")
reposts["is_valid"] = 1
reposts["platform"] = "weibo"
reposts["crawl_time"] = reposts_raw.get("crawl_time", pd.NA)

# 保留转发中所有未作为核心列使用的额外列（不加前缀，保留原列名）
core_repost_cols = set(reposts.columns)
extra_repost_cols = [c for c in reposts_raw.columns if c not in core_repost_cols]
for c in extra_repost_cols:
    reposts[c] = reposts_raw[c]

reposts.to_csv(OUTPUT_DIR / "weibo_reposts_clean.csv", index=False, encoding="utf-8-sig")
print(f"→ weibo_reposts_clean.csv: {len(reposts)} 行")

# ===================== 处理评论 =====================
comments = pd.DataFrame()
comments["comment_id"] = comments_raw["comment_id"].astype(str)
comments["source_post_id"] = comments_raw["source_post_id"].astype(str)
comments["source_post_url"] = comments_raw["source_post_url"]
comments["publish_time"] = comments_raw["comment_time"]
comments["author_name"] = comments_raw["user_name"]
comments["author_type"] = "ordinary_user"
comments["text_raw"] = comments_raw["comment_text"]
comments["text_clean"] = comments["text_raw"].map(clean_text)
comments["like_count"] = comments_raw["like_count"]
comments["reply_count"] = comments_raw.get("reply_count", 0)
comments["stance"] = comments_raw["predicted_stance"]
comments["frame"] = "unclear"
comments["event_stage"] = comments_raw["event_stage"]
comments["keyword_hit"] = comments_raw["keyword_hit"].fillna("")
comments["is_valid"] = 1
comments["platform"] = "weibo"
comments["crawl_time"] = comments_raw.get("crawl_time", pd.NA)

# 保留额外列
extra_comment_cols = ["user_id", "prediction_source"]
for col in extra_comment_cols:
    comments[col] = comments_raw.get(col, pd.NA)

comments.to_csv(OUTPUT_DIR / "weibo_comments_clean.csv", index=False, encoding="utf-8-sig")
print(f"→ weibo_comments_clean.csv: {len(comments)} 行")

# ===================== 构建 all_weibo_texts_clean.csv =====================
# 定义 all_weibo 核心列顺序（与旧项目完全一致）
CORE_COLS = [
    "id", "data_type", "platform", "source_id", "source_url",
    "publish_time", "author_name", "author_type", "text_raw", "text_clean",
    "like_count", "comment_count", "repost_count",
    "stance", "frame", "event_stage", "keyword_hit", "is_valid", "crawl_time"
]

# --- 帖子部分 ---
post_core = pd.DataFrame()
post_core["id"] = posts["post_id"].apply(lambda x: f"post_{x}")
post_core["data_type"] = "post"
post_core["platform"] = "weibo"
post_core["source_id"] = posts["post_id"]
post_core["source_url"] = posts["url"]
post_core["publish_time"] = posts["publish_time"]
post_core["author_name"] = posts["author_name"]
post_core["author_type"] = posts["author_type"]
post_core["text_raw"] = posts["text_raw"]
post_core["text_clean"] = posts["text_clean"]
post_core["like_count"] = posts["like_count"]
post_core["comment_count"] = posts["comment_count"]
post_core["repost_count"] = posts["repost_count"]
post_core["stance"] = posts["stance"]
post_core["frame"] = posts["frame"]
post_core["event_stage"] = posts["event_stage"]
post_core["keyword_hit"] = posts["keyword_hit"]
post_core["is_valid"] = posts["is_valid"]
post_core["crawl_time"] = posts["crawl_time"]

# 帖子额外列，加 post_ 前缀
post_extra = posts[extra_post_cols].copy()
post_extra.columns = [f"post_{c}" for c in post_extra.columns]

# --- 转发部分 ---
repost_core = pd.DataFrame()
repost_core["id"] = [f"repost_{i+1}" for i in range(len(reposts))]
repost_core["data_type"] = "repost"
repost_core["platform"] = "weibo"
repost_core["source_id"] = reposts["source_post_id"]
repost_core["source_url"] = reposts["source_post_url"]
repost_core["publish_time"] = reposts["repost_time"]
repost_core["author_name"] = reposts["repost_user"]
repost_core["author_type"] = reposts["user_type"]
repost_core["text_raw"] = reposts["repost_text_raw"]
repost_core["text_clean"] = reposts["repost_text_clean"]
repost_core["like_count"] = reposts["repost_like_count"]
repost_core["comment_count"] = reposts["repost_comments_count"]
repost_core["repost_count"] = reposts["repost_reposts_count"]
repost_core["stance"] = reposts["stance"]
repost_core["frame"] = reposts["frame"]
repost_core["event_stage"] = reposts["event_stage"]
repost_core["keyword_hit"] = reposts["keyword_hit"]
repost_core["is_valid"] = reposts["is_valid"]
repost_core["crawl_time"] = reposts["crawl_time"]

# 转发额外列，加 repost_ 前缀（全部保留）
repost_extra_cols_final = [c for c in reposts.columns if c not in set(repost_core.columns) and c not in
                           ["source_post_id","source_post_url","repost_time","repost_user","repost_text_raw",
                            "repost_text_clean","repost_like_count","repost_comments_count","repost_reposts_count",
                            "user_type","stance","frame","event_stage","keyword_hit","is_valid","platform","crawl_time"]]
repost_extra = reposts[repost_extra_cols_final].copy()
repost_extra.columns = [f"repost_{c}" for c in repost_extra.columns]

# --- 评论部分 ---
comment_core = pd.DataFrame()
comment_core["id"] = comments["comment_id"].apply(lambda x: f"comment_{x}")
comment_core["data_type"] = "comment"
comment_core["platform"] = "weibo"
comment_core["source_id"] = comments["source_post_id"]
comment_core["source_url"] = comments["source_post_url"]
comment_core["publish_time"] = comments["publish_time"]
comment_core["author_name"] = comments["author_name"]
comment_core["author_type"] = comments["author_type"]
comment_core["text_raw"] = comments["text_raw"]
comment_core["text_clean"] = comments["text_clean"]
comment_core["like_count"] = comments["like_count"]
comment_core["comment_count"] = 0          # 评论自身没有评论数
comment_core["repost_count"] = 0
comment_core["stance"] = comments["stance"]
comment_core["frame"] = comments["frame"]
comment_core["event_stage"] = comments["event_stage"]
comment_core["keyword_hit"] = comments["keyword_hit"]
comment_core["is_valid"] = comments["is_valid"]
comment_core["crawl_time"] = comments["crawl_time"]

# 评论额外列，加 comment_ 前缀
comment_extra = comments[extra_comment_cols].copy()
comment_extra.columns = [f"comment_{c}" for c in comment_extra.columns]

# 竖向拼接核心部分
all_core = pd.concat([post_core, repost_core, comment_core], ignore_index=True)

# 水平拼接额外列（按索引对齐）
all_extra = pd.concat([post_extra.reset_index(drop=True),
                       repost_extra.reset_index(drop=True),
                       comment_extra.reset_index(drop=True)],
                      axis=1)

all_weibo = pd.concat([all_core, all_extra], axis=1)
all_weibo.to_csv(OUTPUT_DIR / "all_weibo_texts_clean.csv", index=False, encoding="utf-8-sig")
print(f"→ all_weibo_texts_clean.csv: {len(all_weibo)} 行 (帖子{len(post_core)} + 转发{len(repost_core)} + 评论{len(comment_core)})")
print("全部 done。")