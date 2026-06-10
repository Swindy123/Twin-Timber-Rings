from __future__ import annotations

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

URL_RE = re.compile(r"http[s]?://\S+", flags=re.IGNORECASE)
MENTION_RE = re.compile(r"@[^\s]+")
BRACKET_RE = re.compile(r"\[.*?\]")
ALLOWED_RE = re.compile(r"[^\u4E00-\u9FFF\u0020-\u007E\u3000-\u303F\uFF00-\uFFEF]", flags=re.UNICODE)
REPLY_AT_RE = re.compile(r"^回复\s*@[^:：]+[:：](.*)$")


def base_clean(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = URL_RE.sub("", text)
    text = MENTION_RE.sub("", text)
    text = BRACKET_RE.sub("", text)
    text = ALLOWED_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text_reply_fix(value: object) -> str:
    if pd.isna(value):
        return ""
    raw = str(value)
    if raw == "转发微博":
        return "转发微博"

    match = REPLY_AT_RE.match(raw)
    if match:
        tail = match.group(1).strip()
        return base_clean(tail)

    return base_clean(raw)


def sync_posts_text_clean(source_df: pd.DataFrame, target_df: pd.DataFrame) -> pd.DataFrame:
    mapping = source_df.set_index("id")["text_clean"]
    result = target_df.copy()
    result["text_clean"] = result["post_id"].map(mapping).combine_first(result["text_clean"])
    return result


def sync_comments_text_clean(source_df: pd.DataFrame, target_df: pd.DataFrame) -> pd.DataFrame:
    mapping = source_df.set_index("id")["text_clean"]
    result = target_df.copy()
    result["text_clean"] = result["comment_id"].map(mapping).combine_first(result["text_clean"])
    return result


def sync_reposts_text_clean(source_df: pd.DataFrame, target_df: pd.DataFrame) -> pd.DataFrame:
    source = source_df.copy()
    source["_sync_key"] = (
        source["source_id"].astype(str)
        + "|||"
        + source["publish_time"].astype(str)
        + "|||"
        + source["text_raw"].astype(str)
        + "|||"
        + source["author_name"].astype(str)
    )
    mapping = source.set_index("_sync_key")["text_clean"]

    result = target_df.copy()
    result["_sync_key"] = (
        result["source_post_id"].astype(str)
        + "|||"
        + result["repost_time"].astype(str)
        + "|||"
        + result["repost_text_raw"].astype(str)
        + "|||"
        + result["repost_user"].astype(str)
    )
    result["repost_text_clean"] = result["_sync_key"].map(mapping).combine_first(result["repost_text_clean"])
    result = result.drop(columns=["_sync_key"])
    return result


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")

    before_reply_only = int(all_df["text_clean"].astype(str).eq("回复").sum())
    before_reply_only_long_raw = int(
        ((all_df["text_clean"].astype(str).eq("回复"))
         & (all_df["text_raw"].fillna("").astype(str).str.len() > 4)).sum()
    )

    updated = all_df.copy()
    updated["text_clean"] = updated["text_raw"].map(clean_text_reply_fix)

    fixed_reply_rows = int(
        ((updated["text_clean"].astype(str).eq("回复"))
         & (updated["text_raw"].fillna("").astype(str).str.len() > 4)).sum()
    )

    if fixed_reply_rows:
        recheck = updated["text_clean"].astype(str).eq("回复") & updated["text_raw"].fillna("").astype(str).str.len().gt(4)
        updated.loc[recheck, "text_clean"] = updated.loc[recheck, "text_raw"].map(clean_text_reply_fix)

    after_reply_only = int(updated["text_clean"].astype(str).eq("回复").sum())
    repaired_rows = int((all_df["text_clean"].fillna("").astype(str) != updated["text_clean"].fillna("").astype(str)).sum())

    updated.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")

    posts_df = sync_posts_text_clean(updated.loc[updated["data_type"].eq("post"), ["id", "text_clean"]], posts_df)
    reposts_df = sync_reposts_text_clean(
        updated.loc[updated["data_type"].eq("repost"), ["source_id", "publish_time", "author_name", "text_raw", "text_clean"]],
        reposts_df,
    )
    comments_df = sync_comments_text_clean(updated.loc[updated["data_type"].eq("comment"), ["id", "text_clean"]], comments_df)

    posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
    reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
    comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            "\ntext_clean 回复@修复："
            f"修复前text_clean=回复共{before_reply_only}行，"
            f"修复前且text_raw较长的回复行{before_reply_only_long_raw}行，"
            f"修复后text_clean=回复共{after_reply_only}行，"
            f"本次覆盖修复{repaired_rows}行；"
            "已同步到三个子表。"
        )

    print("修复前，text_clean 为 回复 的行数:", before_reply_only)
    print("修复后，text_clean 为 回复 的行数:", after_reply_only)
    print("被修复的行数:", repaired_rows)
    print("saved", ALL_PATH)


if __name__ == "__main__":
    main()