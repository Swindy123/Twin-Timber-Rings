#!/usr/bin/env python3
"""Apply b2-style weak stance/frame/emotion rules to C-group repost data.

This script does not modify the original recrawl CSV. It creates a labelled
copy for downstream network analysis and GitHub submission.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(r"D:\nl")
INPUT_PATH = ROOT / "output_recrawl" / "weibo_reposts_api_clean_multihop.csv"
OUTPUT_PATH = ROOT / "output_recrawl" / "weibo_reposts_api_clean_multihop_labeled.csv"
GITHUB_COPY_PATH = ROOT / "data_collection" / "data" / "C-recrawl" / "weibo_reposts_api_clean_multihop_labeled.csv"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(c).lower(): c for c in df.columns}
    for name in candidates:
        if name in df.columns:
            return name
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def safe_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def has(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


ZHANG_PATTERNS = [
    r"唯一原唱",
    r"年轮唯一原唱",
    r"支持张碧晨",
    r"张碧晨.*原唱",
    r"张碧晨女士",
    r"硬气",
    r"十年陪伴",
]

WANG_PATTERNS = [
    r"支持汪苏泷",
    r"汪苏泷.*创作",
    r"词曲作者",
    r"尊重创作者",
    r"收回.*授权",
    r"版权费",
    r"双原唱",
]

ANTI_FANWAR_PATTERNS = [
    r"别吵",
    r"别撕",
    r"饭圈",
    r"引战",
    r"双输",
    r"体面",
    r"乌烟瘴气",
]

LEGAL_PATTERNS = [r"版权", r"授权", r"著作权", r"合约", r"法律", r"权利", r"免责"]
MEMORY_PATTERNS = [r"回忆", r"青春", r"十年", r"陪伴", r"告别", r"遗憾"]

ANGER_PATTERNS = [r"离谱", r"无语", r"恶心", r"背刺", r"撕破脸", r"气死", r"不要face"]
SAD_PATTERNS = [r"难过", r"遗憾", r"告别", r"可惜", r"破防"]
MOCK_PATTERNS = [r"哈哈哈+", r"笑死", r"啧啧", r"算个什么", r"急了"]
SUPPORTIVE_PATTERNS = [r"支持", r"硬气", r"尊重", r"谢谢", r"陪伴"]


def label_row(user_name: str, text: str) -> dict[str, Any]:
    blob = f"{user_name} {text}"
    zhang = has(ZHANG_PATTERNS, blob)
    wang = has(WANG_PATTERNS, blob)
    anti = has(ANTI_FANWAR_PATTERNS, blob)
    legal = has(LEGAL_PATTERNS, blob)
    memory = has(MEMORY_PATTERNS, blob)

    if anti and not zhang and not wang:
        stance = "anti_fanwar"
        confidence = 0.82
    elif zhang and not wang:
        stance = "support_zhang"
        confidence = 0.78
    elif wang and not zhang:
        stance = "support_wang"
        confidence = 0.78
    elif legal and not zhang and not wang:
        stance = "neutral"
        confidence = 0.72
    elif zhang and wang:
        stance = "unclear"
        confidence = 0.55
    else:
        stance = "unclear"
        confidence = 0.35

    if legal:
        frame = "legal_discussion"
    elif anti:
        frame = "fan_conflict"
    elif zhang or wang:
        frame = "original_singer" if re.search(r"原唱", blob) else "creator_identity"
    elif memory:
        frame = "memory_emotion"
    else:
        frame = "platform_meta"

    if has(ANGER_PATTERNS, blob):
        emotion = "angry"
    elif has(SAD_PATTERNS, blob):
        emotion = "sad"
    elif has(MOCK_PATTERNS, blob):
        emotion = "mocking"
    elif has(SUPPORTIVE_PATTERNS, blob):
        emotion = "supportive"
    elif stance == "unclear":
        emotion = "unclear"
    else:
        emotion = "neutral"

    hits = []
    for label, patterns in {
        "zhang": ZHANG_PATTERNS,
        "wang": WANG_PATTERNS,
        "anti_fanwar": ANTI_FANWAR_PATTERNS,
        "legal": LEGAL_PATTERNS,
        "emotion_angry": ANGER_PATTERNS,
        "emotion_sad": SAD_PATTERNS,
        "emotion_mocking": MOCK_PATTERNS,
    }.items():
        if has(patterns, blob):
            hits.append(label)

    return {
        "stance_b2_rule": stance,
        "frame_b2_rule": frame,
        "emotion_weak_rule": emotion,
        "rule_confidence": confidence,
        "matched_rule_groups": "|".join(hits),
        "label_note": "b2-style weak rules; stance/frame are more reliable than emotion",
    }


def main() -> int:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    user_col = pick_col(df, ["repost_user_name", "target_user", "user_name", "author_name"])
    text_col = pick_col(df, ["repost_text", "repost_text_clean", "text_clean", "text"])

    if not text_col:
        raise ValueError("No repost text column found; expected repost_text/repost_text_clean/text_clean/text")

    labels = [
        label_row(safe_text(row.get(user_col)) if user_col else "", safe_text(row.get(text_col)))
        for _, row in df.iterrows()
    ]
    out = pd.concat([df.copy(), pd.DataFrame(labels)], axis=1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GITHUB_COPY_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    out.to_csv(GITHUB_COPY_PATH, index=False, encoding="utf-8-sig")

    print("Labelled repost data written:")
    print(OUTPUT_PATH)
    print(GITHUB_COPY_PATH)
    print(out[["stance_b2_rule", "frame_b2_rule", "emotion_weak_rule"]].value_counts().head(12).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
