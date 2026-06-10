from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
COMMENTS_PATH = OUT / "weibo_comments_clean.csv"
LOG_PATH = OUT / "data_cleaning_log.txt"

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

SUPPORT_WANG_PHRASES = [
    "吃水不忘挖井人",
    "创作者有最高权力",
    "硬刚维权",
    "收回的是演唱权",
    "比某些只唱歌的强",
    "年轮还给汪苏泷",
    "请张碧晨粉丝不要捂着眼睛",
]

SUPPORT_ZHANG_PHRASES = ["看厌了全网围攻一个女性"]

FAN_CONFLICT_PHRASES = ["你赶紧滚吧", "眼睛不要就扣了"]

MEANINGLESS_TEXTS = {"图片评论", "回复", "转发微博"}


def normalize_label(value: object, valid_labels: set[str]) -> str:
    if pd.isna(value):
        return "unclear"
    text = str(value).strip()
    if not text or text not in valid_labels:
        return "unclear"
    return text


def sync_posts(posts_df: pd.DataFrame, all_df: pd.DataFrame) -> pd.DataFrame:
    source = all_df.loc[all_df["data_type"] == "post", ["source_id", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]].copy()
    source = source.drop_duplicates(subset=["source_id"])
    merged = posts_df.merge(source, left_on="post_id", right_on="source_id", how="left", suffixes=("", "_new"))
    for col in ["stance", "frame", "stance_confidence", "frame_confidence", "confidence"]:
        new_col = f"{col}_new"
        if new_col in merged.columns:
            merged[col] = merged[new_col].combine_first(merged[col])
            merged = merged.drop(columns=[new_col])
    if "source_id" in merged.columns:
        merged = merged.drop(columns=["source_id"])
    return merged


def sync_comments(comments_df: pd.DataFrame, all_df: pd.DataFrame) -> pd.DataFrame:
    source = all_df.loc[all_df["data_type"] == "comment", ["id", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]].copy()
    source["comment_id"] = source["id"].astype(str).str.split("_", n=1).str[-1]
    source = source.drop_duplicates(subset=["comment_id"])
    comments = comments_df.copy()
    comments["comment_id"] = comments["comment_id"].astype(str)
    merged = comments.merge(source.drop(columns=["id"]), on="comment_id", how="left", suffixes=("", "_new"))
    for col in ["stance", "frame", "stance_confidence", "frame_confidence", "confidence"]:
        new_col = f"{col}_new"
        if new_col in merged.columns:
            merged[col] = merged[new_col].combine_first(merged[col])
            merged = merged.drop(columns=[new_col])
    return merged


def sync_reposts(reposts_df: pd.DataFrame, all_df: pd.DataFrame) -> pd.DataFrame:
    source = all_df.loc[all_df["data_type"] == "repost", ["source_id", "publish_time", "author_name", "text_raw", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]].copy()
    source = source.rename(
        columns={
            "source_id": "source_post_id",
            "publish_time": "repost_time",
            "author_name": "repost_user",
            "text_raw": "repost_text_raw",
        }
    )
    source["_sync_key"] = (
        source["source_post_id"].astype(str)
        + "|||"
        + source["repost_time"].astype(str)
        + "|||"
        + source["repost_text_raw"].astype(str)
        + "|||"
        + source["repost_user"].astype(str)
    )

    reposts = reposts_df.copy()
    reposts["_sync_key"] = (
        reposts["source_post_id"].astype(str)
        + "|||"
        + reposts["repost_time"].astype(str)
        + "|||"
        + reposts["repost_text_raw"].astype(str)
        + "|||"
        + reposts["repost_user"].astype(str)
    )

    merged = reposts.merge(source[["_sync_key", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]], on="_sync_key", how="left", suffixes=("", "_new"))
    for col in ["stance", "frame", "stance_confidence", "frame_confidence", "confidence"]:
        new_col = f"{col}_new"
        if new_col in merged.columns:
            merged[col] = merged[new_col].combine_first(merged[col])
            merged = merged.drop(columns=[new_col])
    merged = merged.drop(columns=["_sync_key"])
    return merged


def update_labels(all_df: pd.DataFrame) -> tuple[pd.DataFrame, int, int, int]:
    df = all_df.copy()
    df["text_clean"] = df["text_clean"].fillna("").astype(str)
    df["stance"] = df["stance"].map(lambda v: normalize_label(v, VALID_STANCE))
    df["frame"] = df["frame"].map(lambda v: normalize_label(v, VALID_FRAME))

    stance_hits = 0
    frame_hits = 0
    meaningless_hits = 0

    support_wang_mask = df["text_clean"].map(lambda text: any(phrase in text for phrase in SUPPORT_WANG_PHRASES)) & df["stance"].ne("support_wang")
    df.loc[support_wang_mask, "stance"] = "support_wang"
    df.loc[support_wang_mask, "stance_confidence"] = 1.0
    stance_hits += int(support_wang_mask.sum())

    support_zhang_mask = df["text_clean"].map(lambda text: any(phrase in text for phrase in SUPPORT_ZHANG_PHRASES)) & df["stance"].ne("support_zhang")
    df.loc[support_zhang_mask, "stance"] = "support_zhang"
    df.loc[support_zhang_mask, "stance_confidence"] = 1.0
    stance_hits += int(support_zhang_mask.sum())

    fan_conflict_mask = df["text_clean"].map(lambda text: any(phrase in text for phrase in FAN_CONFLICT_PHRASES)) & df["frame"].ne("fan_conflict")
    df.loc[fan_conflict_mask, "frame"] = "fan_conflict"
    df.loc[fan_conflict_mask, "frame_confidence"] = 1.0
    frame_hits += int(fan_conflict_mask.sum())

    meaningless_mask = df["text_clean"].str.strip().isin(MEANINGLESS_TEXTS)
    df.loc[meaningless_mask, "stance"] = "unclear"
    df.loc[meaningless_mask, "frame"] = "unclear"
    df.loc[meaningless_mask, ["stance_confidence", "frame_confidence"]] = 1.0
    meaningless_hits += int(meaningless_mask.sum())

    df["stance_confidence"] = pd.to_numeric(df["stance_confidence"], errors="coerce")
    df["frame_confidence"] = pd.to_numeric(df["frame_confidence"], errors="coerce")
    df["confidence"] = df[["stance_confidence", "frame_confidence"]].mean(axis=1)
    df["stance_confidence"] = df["stance_confidence"].fillna(0).round(4)
    df["frame_confidence"] = df["frame_confidence"].fillna(0).round(4)
    df["confidence"] = df["confidence"].fillna(0).round(4)
    return df, stance_hits, frame_hits, meaningless_hits


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")

    all_df, stance_hits, frame_hits, meaningless_hits = update_labels(all_df)
    all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")

    posts_df = sync_posts(posts_df, all_df)
    reposts_df = sync_reposts(reposts_df, all_df)
    comments_df = sync_comments(comments_df, all_df)

    posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
    reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
    comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            "\n最后一次保守规则清洗："
            f"stance命中{stance_hits}条，frame命中{frame_hits}条，无意义文本命中{meaningless_hits}条；"
            "已同步到三个子表。"
        )

    stance_counts = all_df["stance"].value_counts(dropna=False)
    frame_counts = all_df["frame"].value_counts(dropna=False)
    print("stance分布:")
    print(stance_counts.to_string())
    print("frame分布:")
    print(frame_counts.to_string())
    print("saved", ALL_PATH)


if __name__ == "__main__":
    main()