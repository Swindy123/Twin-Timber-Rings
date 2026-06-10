from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
COMMENTS_PATH = OUT / "weibo_comments_clean.csv"
RULES_PATH = OUT / "label_rules.xlsx"
LOG_PATH = OUT / "data_cleaning_log.txt"


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_rules() -> pd.DataFrame:
    rules = pd.read_excel(RULES_PATH, sheet_name="关键词规则")
    rules = rules.rename(columns=lambda x: str(x).strip())
    if "标签值" in rules.columns:
        rules["标签值"] = rules["标签值"].replace({"public_opinion_operation": "platform_meta"})
    if "优先级" in rules.columns:
        rules = rules.sort_values(by=["优先级"], ascending=True).reset_index(drop=True)
    else:
        rules = rules.reset_index(drop=True)
    return rules


def split_hits(value: object) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    parts = [part.strip() for part in text.replace("|", ";").split(";")]
    return [part for part in parts if part]


def merge_hits(existing: object, added: list[str]) -> str:
    hits: list[str] = []
    for part in split_hits(existing):
        if part not in hits:
            hits.append(part)
    for part in added:
        if part not in hits:
            hits.append(part)
    return ";".join(hits)


def sync_text_columns(all_df: pd.DataFrame, target_df: pd.DataFrame, key_col: str, text_col: str) -> pd.DataFrame:
    mapping = all_df.set_index("id")[text_col]
    result = target_df.copy()
    result[text_col] = result[key_col].map(mapping).combine_first(result[text_col])
    return result


def sync_repost_text(all_df: pd.DataFrame, reposts_df: pd.DataFrame) -> pd.DataFrame:
    source = all_df.loc[all_df["data_type"].eq("repost"), ["source_id", "publish_time", "author_name", "text_raw", "text_clean"]].copy()
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

    result = reposts_df.copy()
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
    return result.drop(columns=["_sync_key"])


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")
    rules = load_rules()

    all_df["text_clean"] = all_df["text_clean"].fillna("").astype(str)
    all_df["stance"] = all_df["stance"].fillna("").astype(str)
    all_df["keyword_hit"] = all_df["keyword_hit"].fillna("").astype(str)

    unclear_mask = all_df["stance"].eq("unclear")
    eligible_mask = unclear_mask & all_df["text_clean"].str.len().gt(0)

    stance_rules = rules[rules["标签类型"].astype(str).eq("stance")].copy()

    updated_rows = 0
    matched_rows = 0

    for idx, row in all_df.loc[eligible_mask].iterrows():
        text = str(row["text_clean"])
        matched_keywords: list[str] = []
        new_stance = row["stance"]

        for _, rule in stance_rules.iterrows():
            keyword = normalize_text(rule.get("关键词", ""))
            condition = normalize_text(rule.get("条件", "包含")) or "包含"
            label_value = normalize_text(rule.get("标签值", ""))
            if not keyword or not label_value:
                continue
            is_match = text == keyword if condition == "完全匹配" else keyword in text
            if not is_match:
                continue
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)
            if new_stance == "unclear":
                new_stance = label_value

        if matched_keywords and new_stance != "unclear":
            matched_rows += 1
            if all_df.at[idx, "stance"] != new_stance:
                all_df.at[idx, "stance"] = new_stance
                updated_rows += 1
            all_df.at[idx, "keyword_hit"] = merge_hits(all_df.at[idx, "keyword_hit"], matched_keywords)

    all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")

    posts_df = sync_text_columns(all_df, posts_df, "post_id", "text_clean")
    reposts_df = sync_repost_text(all_df, reposts_df)
    comments_df = sync_text_columns(all_df, comments_df, "comment_id", "text_clean")

    posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
    reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
    comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            "\nunclear stance 关键词回填："
            f"eligible={int(eligible_mask.sum())}，matched_rows={matched_rows}，updated_rows={updated_rows}；"
            "已同步到三个子表。"
        )

    print("new stance distribution:")
    print(all_df["stance"].value_counts(dropna=False).to_string())
    print("updated_rows", updated_rows)
    print("matched_rows", matched_rows)
    print("saved", ALL_PATH)


if __name__ == "__main__":
    main()