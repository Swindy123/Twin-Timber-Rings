from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
COMMENTS_PATH = OUT / "weibo_comments_clean.csv"

EXPLICIT_REPAIRS: dict[str, dict[str, str]] = {
    "comment_5192447267444830": {"stance": "unclear", "frame": "unclear"},
    "comment_5194332330000732": {"stance": "support_zhang"},
    "comment_5192379487225092": {"stance": "neutral", "frame": "unclear"},
    "comment_5192722109433168": {"frame": "unclear"},
    "repost_657": {"stance": "support_zhang"},
    "repost_1508": {"frame": "original_singer"},
    "repost_1386": {"frame": "original_singer"},
    "comment_5192441670926884": {"stance": "neutral"},
    "repost_83": {"stance": "support_wang"},
    "post_5193817646696888": {"stance": "support_zhang"},
    "post_5195188223610429": {"stance": "support_zhang"},
    "repost_666": {"stance": "support_wang"},
    "post_5251716258990461": {"stance": "neutral"},
    "comment_5192290639546385": {"stance": "unclear", "frame": "unclear"},
    "repost_2139": {"stance": "support_wang"},
    "repost_2183": {"stance": "neutral"},
    "comment_5192643267266757": {"stance": "unclear"},
    "comment_5192201979561192": {"stance": "unclear"},
    "comment_5192288808468919": {"stance": "unclear"},
    "comment_5193833591867176": {"stance": "support_wang"},
    "comment_5192222861430035": {"frame": "unclear"},
    "comment_5192713848228836": {"stance": "unclear", "frame": "unclear"},
    "comment_5192309500281272": {"stance": "support_zhang"},
    "comment_5192379839025991": {"stance": "support_wang"},
    "comment_5192382070391377": {"stance": "support_wang"},
    "comment_5192420687086989": {"stance": "unclear", "frame": "unclear"},
    "repost_2007": {"stance": "support_wang"},
}


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


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")

    all_df["text_clean"] = all_df["text_clean"].fillna("").astype(str)
    all_df["stance"] = all_df["stance"].fillna("unclear").astype(str)
    all_df["frame"] = all_df["frame"].fillna("unclear").astype(str)
    all_df["stance_confidence"] = pd.to_numeric(all_df["stance_confidence"], errors="coerce")
    all_df["frame_confidence"] = pd.to_numeric(all_df["frame_confidence"], errors="coerce")

    before = all_df[["stance", "frame", "stance_confidence", "frame_confidence"]].copy()

    missing_ids: list[str] = []
    for row_id, changes in EXPLICIT_REPAIRS.items():
        hit = all_df[all_df["id"].astype(str).eq(row_id)]
        if hit.empty:
            missing_ids.append(row_id)
            continue
        idx = hit.index
        for field, value in changes.items():
            all_df.loc[idx, field] = value
            if field in {"stance", "frame"}:
                conf_field = f"{field}_confidence"
                if conf_field in all_df.columns:
                    all_df.loc[idx, conf_field] = 1.0

    placeholder_mask = all_df["text_clean"].str.strip().isin({"图片评论", "回复"})
    all_df.loc[placeholder_mask, ["stance", "frame"]] = "unclear"
    all_df.loc[placeholder_mask, ["stance_confidence", "frame_confidence"]] = 1.0

    changed_stance = int((before["stance"] != all_df["stance"]).sum())
    changed_frame = int((before["frame"] != all_df["frame"]).sum())
    placeholder_count = int(placeholder_mask.sum())
    explicit_count = len(EXPLICIT_REPAIRS) - len(missing_ids)

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

    print("explicit_repairs_applied", explicit_count)
    if missing_ids:
        print("missing_ids", ",".join(missing_ids))
    print("placeholder_rows_fixed", placeholder_count)
    print("stance_changed_rows", changed_stance)
    print("frame_changed_rows", changed_frame)
    print("saved", ALL_PATH)
    print("saved", POSTS_PATH)
    print("saved", REPOSTS_PATH)
    print("saved", COMMENTS_PATH)


if __name__ == "__main__":
    main()