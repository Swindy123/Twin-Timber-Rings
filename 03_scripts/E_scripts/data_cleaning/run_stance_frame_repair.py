from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"

ALL_PATH = OUT / "all_weibo_texts_clean.csv"
POSTS_PATH = OUT / "weibo_posts_clean.csv"
REPOSTS_PATH = OUT / "weibo_reposts_clean.csv"
COMMENTS_PATH = OUT / "weibo_comments_clean.csv"
REVIEW_PATH = OUT / "stance_review_sample.csv"
MODEL_PATH = OUT / "stance_frame_repair_models.pkl"

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


def normalize_label(value: object, valid_labels: set[str]) -> str:
    if pd.isna(value):
        return "unclear"
    text = str(value).strip()
    if not text or text not in valid_labels:
        return "unclear"
    return text


def build_training_frame(review_df: pd.DataFrame) -> pd.DataFrame:
    df = review_df.copy()
    df["text_clean"] = df["text_clean"].fillna("").astype(str)
    df["修正_stance"] = df["修正_stance"].map(lambda v: normalize_label(v, VALID_STANCE))
    df["修正_frame"] = df["修正_frame"].map(lambda v: normalize_label(v, VALID_FRAME))
    return df


def fit_text_classifier(texts: pd.Series, labels: pd.Series) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(2, 4),
                    min_df=1,
                    max_features=8000,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=3000,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )
    pipeline.fit(texts, labels)
    return pipeline


def predict_with_confidence(model: Pipeline, texts: pd.Series) -> tuple[pd.Series, pd.Series]:
    proba = model.predict_proba(texts)
    classes = model.named_steps["clf"].classes_
    best_idx = proba.argmax(axis=1)
    predicted = pd.Series([classes[i] for i in best_idx], index=texts.index)
    confidence = pd.Series(proba.max(axis=1), index=texts.index)
    return predicted, confidence


def label_probability(model: Pipeline, texts: pd.Series, labels: pd.Series) -> pd.Series:
    proba = model.predict_proba(texts)
    classes = list(model.named_steps["clf"].classes_)
    class_to_idx = {cls: idx for idx, cls in enumerate(classes)}
    values = []
    for row_idx, label in enumerate(labels.tolist()):
        idx = class_to_idx.get(label)
        if idx is None:
            values.append(float(proba[row_idx].max()))
        else:
            values.append(float(proba[row_idx, idx]))
    return pd.Series(values, index=texts.index)


def ensure_column(df: pd.DataFrame, column: str, default=pd.NA) -> pd.DataFrame:
    if column not in df.columns:
        df[column] = default
    return df


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


def main() -> None:
    all_df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
    posts_df = pd.read_csv(POSTS_PATH, encoding="utf-8-sig")
    reposts_df = pd.read_csv(REPOSTS_PATH, encoding="utf-8-sig")
    comments_df = pd.read_csv(COMMENTS_PATH, encoding="utf-8-sig")
    review_df = build_training_frame(pd.read_csv(REVIEW_PATH, encoding="utf-8-sig"))

    stance_train = review_df.loc[review_df["修正_stance"].isin(VALID_STANCE - {"unclear"}), ["text_clean", "修正_stance"]].copy()
    frame_train = review_df.loc[review_df["修正_frame"].isin(VALID_FRAME - {"unclear"}), ["text_clean", "修正_frame"]].copy()

    if stance_train.empty:
        raise RuntimeError("没有可用于训练 stance 的修正样本。")
    if frame_train.empty:
        raise RuntimeError("没有可用于训练 frame 的修正样本。")

    stance_model = fit_text_classifier(stance_train["text_clean"], stance_train["修正_stance"])
    frame_model = fit_text_classifier(frame_train["text_clean"], frame_train["修正_frame"])

    all_df = all_df.copy()
    all_df["text_clean"] = all_df["text_clean"].fillna("").astype(str)
    all_df["stance"] = all_df["stance"].map(lambda v: normalize_label(v, VALID_STANCE))
    all_df["frame"] = all_df["frame"].map(lambda v: normalize_label(v, VALID_FRAME))
    ensure_column(all_df, "stance_confidence")
    ensure_column(all_df, "frame_confidence")
    ensure_column(all_df, "confidence")

    corrected_map = review_df.set_index("id")
    reviewed_mask = all_df["id"].isin(corrected_map.index)
    if reviewed_mask.any():
        stance_override = all_df.loc[reviewed_mask, "id"].map(corrected_map["修正_stance"]).map(lambda v: normalize_label(v, VALID_STANCE))
        frame_override = all_df.loc[reviewed_mask, "id"].map(corrected_map["修正_frame"]).map(lambda v: normalize_label(v, VALID_FRAME))
        all_df.loc[reviewed_mask, "stance"] = stance_override.values
        all_df.loc[reviewed_mask, "frame"] = frame_override.values
        all_df.loc[reviewed_mask, "stance_confidence"] = 1.0
        all_df.loc[reviewed_mask, "frame_confidence"] = 1.0

    stance_missing = all_df["stance"].eq("unclear")
    frame_missing = all_df["frame"].eq("unclear")

    if stance_missing.any():
        stance_pred, stance_pred_conf = predict_with_confidence(stance_model, all_df.loc[stance_missing, "text_clean"])
        all_df.loc[stance_missing, "stance"] = stance_pred.values
        all_df.loc[stance_missing, "stance_confidence"] = stance_pred_conf.values

    if frame_missing.any():
        frame_pred, frame_pred_conf = predict_with_confidence(frame_model, all_df.loc[frame_missing, "text_clean"])
        all_df.loc[frame_missing, "frame"] = frame_pred.values
        all_df.loc[frame_missing, "frame_confidence"] = frame_pred_conf.values

    known_stance = all_df["stance_confidence"].isna()
    if known_stance.any():
        all_df.loc[known_stance, "stance_confidence"] = label_probability(stance_model, all_df.loc[known_stance, "text_clean"], all_df.loc[known_stance, "stance"])

    known_frame = all_df["frame_confidence"].isna()
    if known_frame.any():
        all_df.loc[known_frame, "frame_confidence"] = label_probability(frame_model, all_df.loc[known_frame, "text_clean"], all_df.loc[known_frame, "frame"])

    all_df["confidence"] = all_df[["stance_confidence", "frame_confidence"]].mean(axis=1)
    all_df["stance_confidence"] = all_df["stance_confidence"].astype(float).round(4)
    all_df["frame_confidence"] = all_df["frame_confidence"].astype(float).round(4)
    all_df["confidence"] = all_df["confidence"].astype(float).round(4)

    all_df.to_csv(ALL_PATH, index=False, encoding="utf-8-sig")

    posts_df = sync_posts(posts_df, all_df)
    reposts_df = sync_reposts(reposts_df, all_df)
    comments_df = sync_comments(comments_df, all_df)

    posts_df.to_csv(POSTS_PATH, index=False, encoding="utf-8-sig")
    reposts_df.to_csv(REPOSTS_PATH, index=False, encoding="utf-8-sig")
    comments_df.to_csv(COMMENTS_PATH, index=False, encoding="utf-8-sig")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"stance_model": stance_model, "frame_model": frame_model}, f)

    print("review_rows", len(review_df))
    print("stance_train_rows", len(stance_train))
    print("frame_train_rows", len(frame_train))
    print("reviewed_rows_applied", int(reviewed_mask.sum()))
    print("stance_filled_rows", int(stance_missing.sum()))
    print("frame_filled_rows", int(frame_missing.sum()))
    print("saved", ALL_PATH)
    print("saved", POSTS_PATH)
    print("saved", REPOSTS_PATH)
    print("saved", COMMENTS_PATH)
    print("saved", MODEL_PATH)


if __name__ == "__main__":
    main()