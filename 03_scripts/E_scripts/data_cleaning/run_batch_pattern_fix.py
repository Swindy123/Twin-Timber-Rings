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

SUPPORT_WANG_STRONG = [
    "吃水不忘挖井人",
    "创作者有最高权力",
    "硬刚维权",
    "收回的是演唱权",
    "比某些只唱歌的强",
    "年轮还给汪苏泷",
    "请张碧晨粉丝不要捂着眼睛",
]

SUPPORT_WANG_CONTEXT = [
    "双原唱",
    "唯一原唱",
    "版权",
    "演唱权",
    "永久演唱权",
    "收回版权",
    "收回演唱权",
    "收回授权",
    "作词作曲",
    "原唱籍",
    "没有任何著作权",
    "拿起法律武器",
    "不厚道",
    "不再唱",
    "汪苏泷方",
    "汪苏泷",
    "收回一切授权",
    "收回版权了",
    "只能在汪苏泷演唱会上听",
    "哪条法律规定",
    "法律都不保护张碧晨",
    "人家一个男生不好跟她计较",
    "给你双原唱你不要",
]

SUPPORT_ZHANG_STRONG = [
    "看厌了全网围攻一个女性",
    "支持张碧晨",
    "张碧晨占理",
    "张碧晨挺倒霉",
    "张碧晨是被迫反击",
    "张碧晨是无妄之灾",
    "张碧晨没错",
    "张碧晨的一切决定",
]

SUPPORT_ZHANG_CONTEXT = [
    "张碧晨方",
    "她也是唯一原唱",
    "张碧晨是唯一原唱",
    "支持张碧晨的一切决定",
    "出道十一周年快乐",
    "张碧晨今后将不再唱",
    "张碧晨不再演唱年轮",
    "张碧晨方回应",
    "张碧晨方称",
    "张碧晨方强调",
    "张碧晨方认为",
    "张碧晨方表示",
]


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


def has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def apply_rules(all_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    df = all_df.copy()
    df["text_clean"] = df["text_clean"].fillna("").astype(str)
    df["stance"] = df["stance"].map(lambda v: normalize_label(v, VALID_STANCE))
    df["frame"] = df["frame"].map(lambda v: normalize_label(v, VALID_FRAME))
    df["stance_confidence"] = pd.to_numeric(df["stance_confidence"], errors="coerce")
    df["frame_confidence"] = pd.to_numeric(df["frame_confidence"], errors="coerce")

    eligible = df["stance"].eq("neutral") & df["stance_confidence"].lt(0.65)

    support_wang_mask = eligible & df["text_clean"].map(
        lambda text: has_any(text, SUPPORT_WANG_STRONG) or (
            has_any(text, SUPPORT_WANG_CONTEXT)
            and ("年轮" in text or "张碧晨" in text or "汪苏泷" in text or "原唱" in text)
        )
    )
    support_zhang_mask = eligible & ~support_wang_mask & df["text_clean"].map(
        lambda text: has_any(text, SUPPORT_ZHANG_STRONG) or (
            has_any(text, SUPPORT_ZHANG_CONTEXT)
            and ("张碧晨" in text or "原唱" in text or "年轮" in text)
            and ("支持" in text or "体面" in text or "无妄之灾" in text or "倒霉" in text or "被迫反击" in text or "占理" in text or "没错" in text)
        )
    )

    df.loc[support_wang_mask, "stance"] = "support_wang"
    df.loc[support_zhang_mask, "stance"] = "support_zhang"
    df.loc[support_wang_mask | support_zhang_mask, "stance_confidence"] = 1.0
    df["confidence"] = df[["stance_confidence", "frame_confidence"]].mean(axis=1)
    df["stance_confidence"] = df["stance_confidence"].fillna(0).round(4)
    df["frame_confidence"] = df["frame_confidence"].fillna(0).round(4)
    df["confidence"] = df["confidence"].fillna(0).round(4)

    counts = {
        "support_wang": int(support_wang_mask.sum()),
        "support_zhang": int(support_zhang_mask.sum()),
        "eligible": int(eligible.sum()),
    }
    return df, counts


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")

    all_df, counts = apply_rules(all_df)
    all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")

    posts_df = sync_posts(posts_df, all_df)
    reposts_df = sync_reposts(reposts_df, all_df)
    comments_df = sync_comments(comments_df, all_df)

    posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
    reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
    comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            "\n批量规则修正（batch_review_1 模式学习）："
            f"eligible={counts['eligible']}，support_wang={counts['support_wang']}，support_zhang={counts['support_zhang']}，"
            "已同步到三个子表。"
        )

    print("stance分布:")
    print(all_df["stance"].value_counts(dropna=False).to_string())
    print("saved", ALL_PATH)


if __name__ == "__main__":
    main()