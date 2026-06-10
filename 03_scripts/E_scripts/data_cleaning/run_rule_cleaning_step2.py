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

PLACEHOLDER_TEXTS = {"图片评论", "回复", "转发微博"}
ZHANG_MARKERS = re.compile(r"(张碧晨|张女士|张方|张碧晨方)")
LEGAL_KEYWORDS = re.compile(r"(版权|著作权|授权|合同|条款|法定|法律|归属|权益|维权|演唱权|原唱|版权方)")
STANCE_MARKERS = re.compile(r"(支持|站队|偏向|偏袒|喜欢|讨厌|心疼|活该|太过分|无语|恶心|抹黑|洗白|黑粉|粉黑大战)")
SARCASTIC_MARKERS = re.compile(r"(笑死|无语|离谱|绝了|服了|真会|真行|好家伙|呵呵|不是吧|难道|你说呢|可真|双关|？？|\?\?)")


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


def is_placeholder(text: str) -> bool:
    return text.strip() in PLACEHOLDER_TEXTS


def is_zhang_support_rule(text: str, stance: str) -> bool:
    return stance == "support_wang" and bool(ZHANG_MARKERS.search(text)) and "唯一原唱" in text and not re.search(r"(不是|并非|不算|双原唱|双主唱|非唯一)", text)


def is_pure_legal_discussion(text: str, frame: str, stance: str) -> bool:
    if frame != "legal_discussion" or stance == "neutral":
        return False
    if not LEGAL_KEYWORDS.search(text):
        return False
    return not STANCE_MARKERS.search(text)


def looks_uncertain_low_confidence(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 10:
        return True
    if SARCASTIC_MARKERS.search(stripped):
        return True
    if "?" in stripped or "？" in stripped:
        if re.search(r"(吗|呢|吧|难道|为什么|怎么|凭什么|不是|不就|还不是)", stripped):
            return True
    return False


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

    before = all_df[["stance", "frame", "stance_confidence", "frame_confidence"]].copy()

    placeholder_mask = all_df["text_clean"].map(is_placeholder)
    all_df.loc[placeholder_mask, ["stance", "frame"]] = "unclear"
    all_df.loc[placeholder_mask, ["stance_confidence", "frame_confidence"]] = 1.0

    zhang_support_mask = (
        ~placeholder_mask
        & all_df["stance"].eq("support_wang")
        & all_df["text_clean"].map(lambda text: is_zhang_support_rule(text, "support_wang"))
    )
    all_df.loc[zhang_support_mask, "stance"] = "support_zhang"
    all_df.loc[zhang_support_mask, "stance_confidence"] = 1.0

    legal_neutral_mask = all_df.apply(
        lambda row: is_pure_legal_discussion(str(row["text_clean"]), str(row["frame"]), str(row["stance"])),
        axis=1,
    )
    all_df.loc[legal_neutral_mask, "stance"] = "neutral"
    all_df.loc[legal_neutral_mask, "stance_confidence"] = 1.0

    low_conf_mask = (
        all_df["stance_confidence"].lt(0.55)
        & all_df["stance"].ne("unclear")
    )
    low_conf_safety_mask = low_conf_mask & (
        all_df["text_clean"].map(looks_uncertain_low_confidence)
        | all_df["frame_confidence"].lt(0.55)
    )
    all_df.loc[low_conf_safety_mask, "stance"] = "unclear"

    stance_changed = int((before["stance"] != all_df["stance"]).sum())
    frame_changed = int((before["frame"] != all_df["frame"]).sum())

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

    placeholder_count = int(placeholder_mask.sum())
    zhang_support_count = int(zhang_support_mask.sum())
    legal_neutral_count = int(legal_neutral_mask.sum())
    low_conf_safety_count = int(low_conf_safety_mask.sum())

    pattern_summary = (
        f"规则清理：占位符转unclear {placeholder_count} 条；"
        f"唯一原唱支持张碧晨修复 {zhang_support_count} 条；"
        f"纯法律讨论转neutral {legal_neutral_count} 条；"
        f"低置信度收回stance {low_conf_safety_count} 条；"
        f"stance变更 {stance_changed} 条，frame变更 {frame_changed} 条。"
    )
    append_log(pattern_summary)

    print(pattern_summary)
    print("saved", ALL_PATH)
    print("saved", POSTS_PATH)
    print("saved", REPOSTS_PATH)
    print("saved", COMMENTS_PATH)


if __name__ == "__main__":
    main()