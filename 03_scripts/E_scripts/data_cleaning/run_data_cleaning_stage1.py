from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
BACKUP = BASE / "原始数据备份"
OUT = BASE / "output"
OUT.mkdir(parents=True, exist_ok=True)

LOG_LINES: list[str] = []


def log(line: str) -> None:
    LOG_LINES.append(line)


# Stage 2.1: clean platform_cases.csv
platform_path = BACKUP / "D_data" / "D_data" / "platform_cases.csv"
douyin_path = BACKUP / "D_data" / "D_data" / "douyin_cases.csv"
platform_df = pd.read_csv(platform_path, encoding="utf-8-sig")
douyin_df = pd.read_csv(douyin_path, encoding="utf-8-sig")

if "like_count" not in platform_df.columns:
    platform_df["like_count"] = pd.NA
if "video_type" not in platform_df.columns:
    platform_df["video_type"] = pd.NA
if "stance" not in platform_df.columns:
    platform_df["stance"] = pd.NA
if "main_viewpoint" not in platform_df.columns:
    platform_df["main_viewpoint"] = pd.NA


def infer_video_type(title: str) -> str:
    t = str(title or "")
    if any(k in t for k in ["法", "律师", "版权", "授权", "著作权"]):
        return "法律科普"
    if any(k in t for k in ["新闻", "报道", "采访", "发布会"]):
        return "新闻报道"
    if any(k in t for k in ["梳理", "来龙去脉", "时间线", "复盘", "全程"]):
        return "事件梳理"
    if any(k in t for k in ["混剪", "剪辑", "高燃", "舞台", "live", "现场"]):
        return "粉丝混剪"
    if any(k in t for k in ["怒", "怼", "开撕", "破防", "实锤", "骂", "离谱"]):
        return "情绪输出"
    return "事件梳理"


def infer_stance(platform: str, title: str, c1: str, c2: str) -> str:
    p = str(platform or "")
    text = " ".join([str(title or ""), str(c1 or ""), str(c2 or "")])

    if any(k in text for k in ["理性", "中立", "双方", "客观", "不站队"]):
        return "neutral"
    if any(k in text for k in ["别吵", "别撕", "反感", "饭圈", "粉圈", "争议太大"]):
        return "anti_fanwar"

    z_hits = sum(k in text for k in ["张碧晨", "唯一原唱", "豆瓣", "支持张", "女声版"])
    w_hits = sum(k in text for k in ["汪苏泷", "收回授权", "版权", "B站", "抖音"])

    if p in ["豆瓣"]:
        return "support_zhang"
    if p in ["B站", "抖音"]:
        if z_hits > w_hits:
            return "support_zhang"
        if w_hits > z_hits:
            return "support_wang"
        if p == "B站":
            return "support_wang"
        return "neutral"
    if p in ["知乎"]:
        if abs(z_hits - w_hits) <= 1:
            return "neutral"
        return "support_zhang" if z_hits > w_hits else "support_wang"

    if z_hits == 0 and w_hits == 0:
        return "unclear"
    if z_hits == w_hits:
        return "neutral"
    return "support_zhang" if z_hits > w_hits else "support_wang"


def infer_viewpoint(stance: str, title: str) -> str:
    t = str(title or "").strip()
    if stance == "support_zhang":
        return "围绕原唱身份与演唱版本差异，强调张碧晨在作品传播中的代表性与合理权益。"
    if stance == "support_wang":
        return "从词曲创作与授权关系出发，认为汪苏泷有权界定演唱授权和版本边界。"
    if stance == "neutral":
        return "尝试综合双方主张，解释事件中的版权、原唱定义和平台传播差异。"
    if stance == "anti_fanwar":
        return "关注粉圈对立与舆论撕裂，主张停止站队并回归作品讨论本身。"
    if t:
        return f"围绕“{t[:20]}”展开讨论，但立场信息不足，需结合上下文复核。"
    return "立场信息不足，需结合上下文复核。"


# Fill like_count for Douyin from douyin_cases
if "estimated_like" in douyin_df.columns:
    lookup = {}
    for _, r in douyin_df.iterrows():
        key = (str(r.get("video_title", "")).strip(), str(r.get("author", "")).strip())
        lookup[key] = r.get("estimated_like")

    for idx, row in platform_df.iterrows():
        if pd.isna(row.get("like_count")) and str(row.get("platform", "")) == "抖音":
            key = (str(row.get("video_title", "")).strip(), str(row.get("author", "")).strip())
            if key in lookup and pd.notna(lookup[key]):
                platform_df.at[idx, "like_count"] = lookup[key]

for idx, row in platform_df.iterrows():
    title = row.get("video_title", "")
    c1 = row.get("hot_comment_1", "")
    c2 = row.get("hot_comment_2", "")

    if pd.isna(row.get("video_type")) or str(row.get("video_type", "")).strip() == "":
        platform_df.at[idx, "video_type"] = infer_video_type(str(title))

    if pd.isna(row.get("stance")) or str(row.get("stance", "")).strip() == "":
        stance = infer_stance(str(row.get("platform", "")), str(title), str(c1), str(c2))
        platform_df.at[idx, "stance"] = stance
    else:
        stance = str(row.get("stance"))

    if pd.isna(row.get("main_viewpoint")) or str(row.get("main_viewpoint", "")).strip() == "":
        platform_df.at[idx, "main_viewpoint"] = infer_viewpoint(stance, str(title))

platform_out = OUT / "platform_cases_clean.csv"
platform_df.to_csv(platform_out, index=False, encoding="utf-8-sig")
log(f"阶段2.1：platform_cases.csv 共 {len(platform_df)} 条，已补全 like_count/video_type/stance/main_viewpoint，输出 platform_cases_clean.csv。")


# Stage 2.2: clean qqmusic_comments.csv
qq_path = BACKUP / "D_data" / "D_data" / "qqmusic_comments.csv"
qq_df = pd.read_csv(qq_path, encoding="utf-8-sig")

qq_out_cols = [
    "comment_id",
    "platform",
    "song_version",
    "source_id",
    "source_url",
    "publish_time",
    "user_name",
    "text_raw",
    "text_clean",
    "like_count",
    "reply_count",
    "stance",
    "frame",
    "emotion",
    "event_stage",
    "is_valid",
    "crawl_time",
]

qq_clean = pd.DataFrame(columns=qq_out_cols)
qq_clean["comment_id"] = [f"qq_{i+1}" for i in range(len(qq_df))]
qq_clean["platform"] = "qqmusic"
qq_clean["song_version"] = qq_df.get("song_version")
qq_clean["publish_time"] = qq_df.get("comment_time")
qq_clean["user_name"] = qq_df.get("comment_user")
qq_clean["text_raw"] = qq_df.get("comment_text")
qq_clean["text_clean"] = qq_clean["text_raw"]
qq_clean["like_count"] = qq_df.get("comment_likes")
qq_clean["reply_count"] = pd.NA
qq_clean["crawl_time"] = qq_df.get("crawl_time")
# label columns remain empty

qq_out = OUT / "qqmusic_comments_clean.csv"
qq_clean.to_csv(qq_out, index=False, encoding="utf-8-sig")
log(f"阶段2.2：QQ音乐评论原始 {len(qq_df)} 条，已转换为统一结构并新增标签空列，输出 qqmusic_comments_clean.csv。")


# Stage 3.1: clean weibo_posts.csv
posts_path = BACKUP / "A_data" / "weibo_posts.csv"
posts_df = pd.read_csv(posts_path, encoding="utf-8-sig")
raw_posts = len(posts_df)

# Deduplicate by post_id
posts_df = posts_df.drop_duplicates(subset=["post_id"], keep="first").copy()
dedup_posts = len(posts_df)

# Rename text -> text_raw
if "text" in posts_df.columns:
    posts_df = posts_df.rename(columns={"text": "text_raw"})

# Add text_clean and label columns
posts_df["text_clean"] = posts_df["text_raw"].astype(str)
for col in ["stance", "frame", "emotion", "event_stage"]:
    posts_df[col] = pd.NA
posts_df["platform"] = "weibo"


def normalize_weibo_time(val: str) -> str:
    s = str(val or "").strip()
    if not s:
        return ""
    dt = pd.to_datetime(s, errors="coerce")
    if pd.notna(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$", s)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        ss = ss or "00"
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d} {int(hh):02d}:{int(mm):02d}:{int(ss):02d}"
    return s


posts_df["publish_time"] = posts_df["publish_time"].map(normalize_weibo_time)


def is_invalid_text(s: str) -> bool:
    t = str(s or "").strip()
    if not t:
        return True
    # pure link
    if re.fullmatch(r"https?://\S+", t):
        return True
    # remove punctuation/space to check meaningful content
    compact = re.sub(r"[\s\W_]+", "", t, flags=re.UNICODE)
    if len(compact) < 2:
        return True
    # common spam hints
    spam_keys = ["加VX", "加v", "私信领", "推广", "商务合作"]
    if any(k in t for k in spam_keys):
        return True
    return False


posts_df["is_valid"] = posts_df["text_raw"].map(lambda x: 0 if is_invalid_text(str(x)) else 1)
invalid_posts = int((posts_df["is_valid"] == 0).sum())
posts_clean_df = posts_df[posts_df["is_valid"] == 1].copy()

posts_out = OUT / "weibo_posts_clean.csv"
posts_clean_df.to_csv(posts_out, index=False, encoding="utf-8-sig")
log(
    f"阶段3.1：微博主帖原始 {raw_posts} 条，按 post_id 去重后 {dedup_posts} 条，删除无效帖 {invalid_posts} 条，保留有效 {len(posts_clean_df)} 条，输出 weibo_posts_clean.csv。"
)


# Stage 4.1: clean weibo reposts
reposts_path = BACKUP / "C_output" / "output" / "weibo_reposts_clean.csv"
reposts_df = pd.read_csv(reposts_path, encoding="utf-8-sig")
raw_reposts = len(reposts_df)

for c in ["repost_user_desc", "repost_user_verified"]:
    if c in reposts_df.columns:
        reposts_df = reposts_df.drop(columns=[c])

for col in ["stance", "frame", "emotion", "event_stage", "is_valid"]:
    if col not in reposts_df.columns:
        reposts_df[col] = pd.NA

reposts_df["platform"] = "weibo"
reposts_df["is_valid"] = reposts_df["is_valid"].fillna(1)

if "repost_text_raw" in reposts_df.columns and "repost_text_clean" in reposts_df.columns:
    reposts_df["repost_text_clean"] = reposts_df["repost_text_clean"].fillna(reposts_df["repost_text_raw"])
elif "repost_text_raw" in reposts_df.columns and "repost_text_clean" not in reposts_df.columns:
    reposts_df["repost_text_clean"] = reposts_df["repost_text_raw"]

reposts_df["repost_time"] = reposts_df["repost_time"].map(normalize_weibo_time)

reposts_out = OUT / "weibo_reposts_clean.csv"
reposts_df.to_csv(reposts_out, index=False, encoding="utf-8-sig")
log(f"阶段4.1：微博转发原始 {raw_reposts} 条，已删除空列 repost_user_desc/repost_user_verified，统一时间格式并补齐标签列，输出 weibo_reposts_clean.csv。")


# Stage 5.1: merge posts + reposts
merged_cols = [
    "id",
    "data_type",
    "platform",
    "source_id",
    "source_url",
    "publish_time",
    "author_name",
    "author_type",
    "text_raw",
    "text_clean",
    "like_count",
    "comment_count",
    "repost_count",
    "stance",
    "frame",
    "emotion",
    "event_stage",
    "keyword_hit",
    "is_valid",
    "crawl_time",
]

post_part = pd.DataFrame(columns=merged_cols)
post_part["id"] = posts_clean_df["post_id"].map(lambda x: f"post_{x}")
post_part["data_type"] = "post"
post_part["platform"] = "weibo"
post_part["source_id"] = posts_clean_df["post_id"]
post_part["source_url"] = posts_clean_df.get("url")
post_part["publish_time"] = posts_clean_df.get("publish_time")
post_part["author_name"] = posts_clean_df.get("author_name")
post_part["author_type"] = posts_clean_df.get("author_type")
post_part["text_raw"] = posts_clean_df.get("text_raw")
post_part["text_clean"] = posts_clean_df.get("text_clean")
post_part["like_count"] = posts_clean_df.get("like_count")
post_part["comment_count"] = posts_clean_df.get("comment_count")
post_part["repost_count"] = posts_clean_df.get("repost_count")
post_part["stance"] = posts_clean_df.get("stance")
post_part["frame"] = posts_clean_df.get("frame")
post_part["emotion"] = posts_clean_df.get("emotion")
post_part["event_stage"] = posts_clean_df.get("event_stage")
post_part["keyword_hit"] = posts_clean_df.get("keyword")
post_part["is_valid"] = posts_clean_df.get("is_valid")
post_part["crawl_time"] = posts_clean_df.get("crawl_time")

repost_part = pd.DataFrame(columns=merged_cols)
repost_part["id"] = [f"repost_{i+1}" for i in range(len(reposts_df))]
repost_part["data_type"] = "repost"
repost_part["platform"] = "weibo"
repost_part["source_id"] = reposts_df.get("source_post_id")
repost_part["source_url"] = reposts_df.get("source_post_url")
repost_part["publish_time"] = reposts_df.get("repost_time")
repost_part["author_name"] = reposts_df.get("repost_user")
repost_part["author_type"] = reposts_df.get("user_type")
repost_part["text_raw"] = reposts_df.get("repost_text_raw")
repost_part["text_clean"] = reposts_df.get("repost_text_clean")
repost_part["like_count"] = reposts_df.get("repost_like_count")
repost_part["comment_count"] = 0
repost_part["repost_count"] = 0
repost_part["stance"] = reposts_df.get("stance")
repost_part["frame"] = reposts_df.get("frame")
repost_part["emotion"] = reposts_df.get("emotion")
repost_part["event_stage"] = reposts_df.get("event_stage")
repost_part["keyword_hit"] = pd.NA
repost_part["is_valid"] = reposts_df.get("is_valid")
repost_part["crawl_time"] = reposts_df.get("crawl_time")

all_weibo = pd.concat([post_part, repost_part], ignore_index=True)
all_weibo_out = OUT / "all_weibo_texts_clean.csv"
all_weibo.to_csv(all_weibo_out, index=False, encoding="utf-8-sig")
log(
    f"阶段5.1：总表 all_weibo_texts_clean.csv 已生成，包含 {len(post_part)} 条 posts + {len(repost_part)} 条 reposts，共 {len(all_weibo)} 条。"
)


# Stage 6.1: label rules
rules = [
    ["唯一原唱", "包含", "stance", "support_zhang", 1, "强调原唱身份"],
    ["原唱只有", "包含", "stance", "support_zhang", 2, "与唯一原唱同类"],
    ["支持张碧晨", "包含", "stance", "support_zhang", 1, "显式支持张"],
    ["作词作曲", "包含", "frame", "creator_identity", 1, "强调创作者身份"],
    ["词曲作者", "包含", "frame", "creator_identity", 1, "同创作者框架"],
    ["收回授权", "包含", "frame", "copyright_authorization", 1, "授权关系争议"],
    ["授权", "包含", "frame", "copyright_authorization", 2, "需结合语境"],
    ["著作权", "包含", "frame", "legal_discussion", 1, "法律讨论"],
    ["永久演唱权", "包含", "frame", "legal_discussion", 1, "权利范围讨论"],
    ["法律", "包含", "frame", "legal_discussion", 2, "广义法律词"],
    ["汪苏泷有权", "包含", "stance", "support_wang", 1, "显式支持汪"],
    ["支持汪苏泷", "包含", "stance", "support_wang", 1, "显式支持汪"],
    ["别吵了", "包含", "stance", "anti_fanwar", 1, "反感粉圈对立"],
    ["饭圈", "包含", "stance", "anti_fanwar", 2, "结合语境判定"],
    ["路人", "包含", "stance", "neutral", 2, "自称中立常见词"],
    ["理性讨论", "包含", "stance", "neutral", 1, "中立解释倾向"],
    ["杜鹃", "包含", "stance", "unclear", 3, "需人工复核"],
    ["公关", "包含", "frame", "public_opinion_operation", 2, "舆论操盘框架"],
    ["黑热搜", "包含", "frame", "public_opinion_operation", 2, "舆论操盘词"],
]

rules_df = pd.DataFrame(
    rules,
    columns=["关键词", "条件", "标签类型", "标签值", "优先级", "备注"],
)
rules_out = OUT / "label_rules.xlsx"
rules_df.to_excel(rules_out, index=False, sheet_name="关键词规则")
log(f"阶段6.1：已创建 label_rules.xlsx，初始化 {len(rules_df)} 条关键词规则。")


# Stage 6.2: write cleaning log
log_file = OUT / "data_cleaning_log.txt"
summary_lines = [
    "阶段一：已确认仅在原始数据备份目录读取数据，输出统一写入 output 目录。",
    *LOG_LINES,
    "阶段七：输出文件检查将在脚本执行后单独核验。",
]
log_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8-sig")

print("Done")
print("posts_valid", len(posts_clean_df), "posts_invalid_removed", invalid_posts)
print("reposts", len(reposts_df))
print("all_weibo", len(all_weibo))
print("platform_cases", len(platform_df), "qqmusic", len(qq_clean), "rules", len(rules_df))