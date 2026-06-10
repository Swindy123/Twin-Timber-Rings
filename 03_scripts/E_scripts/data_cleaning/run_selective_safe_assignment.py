from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

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

FRAME_TO_STANCE = {
    "copyright_authorization": "neutral",
    "creator_identity": "neutral",
    "original_singer": "support_zhang",
    "fan_conflict": "anti_fanwar",
    "platform_meta": "neutral",
    "memory_emotion": "neutral",
    "legal_discussion": "neutral",
}

PLACEHOLDER_TEXTS = {"图片评论", "回复", "转发微博"}


def normalize_label(value: object, valid_labels: set[str]) -> str:
    if pd.isna(value):
        return "unclear"
    text = str(value).strip()
    if not text or text not in valid_labels:
        return "unclear"
    return text


def update_by_key(
    base_df: pd.DataFrame,
    updates_df: pd.DataFrame,
    key_cols: list[str],
    value_cols: list[str],
) -> pd.DataFrame:
    base = base_df.copy()
    updates = updates_df.copy()
    for key in key_cols:
        base[key] = base[key].astype(str)
        updates[key] = updates[key].astype(str)

    merged = base.merge(
        updates[key_cols + value_cols].drop_duplicates(subset=key_cols),
        on=key_cols,
        how="left",
        suffixes=("", "_new"),
    )
    for col in value_cols:
        new_col = f"{col}_new"
        if new_col in merged.columns:
            merged[col] = merged[new_col].combine_first(merged[col])
            merged = merged.drop(columns=[new_col])
    return merged


def append_log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")

    all_df = all_df.copy()
    all_df["text_clean"] = all_df["text_clean"].fillna("").astype(str)
    all_df["stance"] = all_df["stance"].map(lambda v: normalize_label(v, VALID_STANCE))
    all_df["frame"] = all_df["frame"].map(lambda v: normalize_label(v, VALID_FRAME))
    all_df["stance_confidence"] = pd.to_numeric(all_df["stance_confidence"], errors="coerce")
    all_df["frame_confidence"] = pd.to_numeric(all_df["frame_confidence"], errors="coerce")

    before = all_df[["stance", "frame"]].copy()

    target_mask = all_df["stance"].eq("unclear") & (all_df["text_clean"].str.len() > 10)
    target_frame_unclear_mask = target_mask & all_df["frame"].eq("unclear")
    target_frame_clear_mask = target_mask & all_df["frame"].ne("unclear")

    frame_to_stance_series = all_df.loc[target_frame_clear_mask, "frame"].map(FRAME_TO_STANCE)
    frame_assignable_mask = frame_to_stance_series.notna()
    frame_assignable_index = frame_to_stance_series.index[frame_assignable_mask]
    all_df.loc[frame_assignable_index, "stance"] = frame_to_stance_series.loc[frame_assignable_mask].values

    all_df.loc[target_frame_unclear_mask, "frame"] = "platform_meta"
    all_df.loc[target_frame_unclear_mask, "stance"] = "neutral"

    # For the row set we touched, confidence is a fresh safe assignment rather than a model score.
    touched_mask = target_mask
    all_df.loc[touched_mask, "stance_confidence"] = 1.0
    all_df.loc[touched_mask, "frame_confidence"] = 1.0
    all_df.loc[target_frame_unclear_mask, "frame_confidence"] = 1.0

    all_df["confidence"] = all_df[["stance_confidence", "frame_confidence"]].mean(axis=1)
    all_df["stance_confidence"] = all_df["stance_confidence"].astype(float).round(4)
    all_df["frame_confidence"] = all_df["frame_confidence"].astype(float).round(4)
    all_df["confidence"] = all_df["confidence"].astype(float).round(4)

    all_updates = all_df.copy()

    posts_updates = all_updates.loc[all_updates["data_type"].eq("post"), ["source_id", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]].copy()
    posts_updates = posts_updates.rename(columns={"source_id": "post_id"})
    posts_df = update_by_key(posts_df, posts_updates, ["post_id"], ["stance", "frame", "stance_confidence", "frame_confidence", "confidence"])

    comments_updates = all_updates.loc[all_updates["data_type"].eq("comment"), ["id", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]].copy()
    comments_updates["comment_id"] = comments_updates["id"].astype(str).str.split("_", n=1).str[-1]
    comments_updates = comments_updates.drop(columns=["id"])
    comments_df = update_by_key(comments_df, comments_updates, ["comment_id"], ["stance", "frame", "stance_confidence", "frame_confidence", "confidence"])

    repost_updates = all_updates.loc[all_updates["data_type"].eq("repost"), ["source_id", "publish_time", "author_name", "text_raw", "stance", "frame", "stance_confidence", "frame_confidence", "confidence"]].copy()
    repost_updates = repost_updates.rename(
        columns={
            "source_id": "source_post_id",
            "publish_time": "repost_time",
            "author_name": "repost_user",
            "text_raw": "repost_text_raw",
        }
    )
    reposts_df = update_by_key(
        reposts_df,
        repost_updates,
        ["source_post_id", "repost_time", "repost_user", "repost_text_raw"],
        ["stance", "frame", "stance_confidence", "frame_confidence", "confidence"],
    )

    all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")
    posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
    reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
    comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

    stance_before_unclear = int(before["stance"].eq("unclear").sum())
    stance_after_unclear = int(all_df["stance"].eq("unclear").sum())
    frame_after_unclear = int(all_df["frame"].eq("unclear").sum())

    frame_distribution = all_df.loc[target_mask, "frame"].value_counts(dropna=False).to_dict()
    stance_distribution = all_df.loc[target_mask, "stance"].value_counts(dropna=False).to_dict()

    log_message = (
        "有选择的安全赋值（弱推断）：仅处理 stance 为 unclear 且 text_clean 长度>10 的 5755 条；"
        f"按框架推断 stance，frame 不明确时统一赋为 platform_meta + neutral；"
        f"stance unclear 由 {stance_before_unclear} 条降至 {stance_after_unclear} 条，"
        f"frame unclear 由 {frame_after_unclear} 条保留不变；"
        f"目标集赋值后 stance 分布 {stance_distribution}，frame 分布 {frame_distribution}。"
    )
    append_log(log_message)

    print(log_message)
    print("rows", len(all_df))
    print("stance_distribution\n", all_df['stance'].value_counts(dropna=False).to_string())
    print("frame_distribution\n", all_df['frame'].value_counts(dropna=False).to_string())
    print(f"stance_unclear_ratio {stance_after_unclear / len(all_df):.2%}")
    print(f"frame_unclear_ratio {frame_after_unclear / len(all_df):.2%}")
    print("saved", ALL_PATH)
    print("saved", POSTS_PATH)
    print("saved", REPOSTS_PATH)
    print("saved", COMMENTS_PATH)


if __name__ == "__main__":
    main()