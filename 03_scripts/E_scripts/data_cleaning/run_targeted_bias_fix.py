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

NEGATION_RE = re.compile(r"(?:不是|没有|凭什么)")
ATTACK_RE = re.compile(
    r"(?:吃相很难看|未婚生子|去父留子|唯一原唱咋唱不了了|张碧晨破防了|张碧晨错在没有会营销的团队|你赶紧滚吧|滚吧|捂着眼睛)"
)
WANG_CREATOR_RE = re.compile(
    r"(?:吃水不忘挖井人|创作者有最高权力|工作室没常识|硬刚维权|支持原创|尊重版权|比某些只唱歌还试图抢歌的强|收回的是演唱权|没有版权|汪苏泷说双原唱|张不承认|干脆别唱了|年轮还给汪苏泷|孩子还给华晨宇|请张碧晨粉丝不要捂着眼睛)"
)
WANG_CRITICIZE_RE = re.compile(
    r"(?:吃相很难看|未婚生子|去父留子|唯一原唱咋唱不了了|张碧晨破防了|张碧晨错在没有会营销的团队)"
)
ZHANG_SUPPORT_RE = re.compile(
    r"(?:看厌了全网围攻一个女性|对面.*靠嘴|张碧晨讲证据)"
)


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


def contains_any(series: pd.Series, regex: re.Pattern[str]) -> pd.Series:
    return series.str.contains(regex, na=False)


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
    neutral_mask = all_df["stance"].eq("neutral") & (all_df["text_clean"].str.len() > 10)

    # 1) 明确支持创作者的文本 -> support_wang
    wang_creator_mask = neutral_mask & (
        contains_any(all_df["text_clean"], WANG_CREATOR_RE)
        & (
            ~contains_any(all_df["text_clean"], NEGATION_RE)
            | contains_any(all_df["text_clean"], re.compile(r"(?:没有版权|工作室没常识)"))
        )
    )

    # 2) 对张碧晨的批评/嘲讽 -> support_wang
    wang_criticize_mask = neutral_mask & contains_any(all_df["text_clean"], WANG_CRITICIZE_RE)

    # 3) 对张碧晨的明确支持/同情 -> support_zhang
    zhang_support_mask = neutral_mask & (
        contains_any(all_df["text_clean"], ZHANG_SUPPORT_RE)
        | contains_any(all_df["text_clean"], re.compile(r"(?:张碧晨错在没有会营销的团队)"))
    )
    # 与第2条冲突时，按优先级保留第2条，避免把明显批评误判成同情。
    zhang_support_mask = zhang_support_mask & ~wang_criticize_mask

    # 4) 粉丝冲突倾向性 -> anti_fanwar
    anti_fanwar_mask = neutral_mask & contains_any(all_df["text_clean"], re.compile(r"(?:你赶紧滚吧|滚吧|捂着眼睛)"))

    # 5) 框架修正
    attack_or_taunt_mask = neutral_mask & contains_any(all_df["text_clean"], ATTACK_RE)
    frame_fix_mask = attack_or_taunt_mask & all_df["frame"].isin(["platform_meta", "legal_discussion"])

    placeholder_mask = neutral_mask & all_df["text_clean"].str.strip().isin(PLACEHOLDER_TEXTS)

    all_df.loc[wang_creator_mask, "stance"] = "support_wang"
    all_df.loc[wang_criticize_mask, "stance"] = "support_wang"
    all_df.loc[zhang_support_mask, "stance"] = "support_zhang"
    all_df.loc[anti_fanwar_mask, "stance"] = "anti_fanwar"

    all_df.loc[frame_fix_mask, "frame"] = "fan_conflict"
    all_df.loc[placeholder_mask, "frame"] = "unclear"

    touched_mask = wang_creator_mask | wang_criticize_mask | zhang_support_mask | anti_fanwar_mask | frame_fix_mask | placeholder_mask
    all_df.loc[touched_mask, "stance_confidence"] = 1.0
    all_df.loc[touched_mask, "frame_confidence"] = 1.0
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

    stance_counts = all_df["stance"].value_counts(dropna=False)
    frame_counts = all_df["frame"].value_counts(dropna=False)
    stance_before = before["stance"].value_counts(dropna=False)
    stance_after_unclear = int(all_df["stance"].eq("unclear").sum())
    frame_after_unclear = int(all_df["frame"].eq("unclear").sum())

    log_message = (
        "靶向修复：纠正弱推断导致的立场偏差。"
        f"仅修改当前 stance 为 neutral 且 text_clean 长度>10 的样本；"
        f"按创作者支持、张碧晨批评、张碧晨同情、粉丝冲突倾向与框架攻击修正依次执行；"
        f"本轮命中 stance 修复 {int((wang_creator_mask | wang_criticize_mask | zhang_support_mask | anti_fanwar_mask).sum())} 条，"
        f"frame 修复 {int(frame_fix_mask.sum())} 条，placeholder frame 设为 unclear {int(placeholder_mask.sum())} 条；"
        f"stance unclear 由 {int(before['stance'].eq('unclear').sum())} 条降至 {stance_after_unclear} 条，"
        f"frame unclear 当前 {frame_after_unclear} 条。"
    )
    append_log(log_message)

    print(log_message)
    print(f"neutral_rows_before {int(before['stance'].eq('neutral').sum())}")
    print(f"stance_unclear_after {stance_after_unclear}")
    print(f"stance_unclear_ratio {stance_after_unclear / len(all_df):.2%}")
    print(f"frame_unclear_after {frame_after_unclear}")
    print(f"frame_unclear_ratio {frame_after_unclear / len(all_df):.2%}")
    print('stance_distribution\n', stance_counts.to_string())
    print('frame_distribution\n', frame_counts.to_string())
    print('saved', ALL_PATH)
    print('saved', POSTS_PATH)
    print('saved', REPOSTS_PATH)
    print('saved', COMMENTS_PATH)


if __name__ == "__main__":
    main()