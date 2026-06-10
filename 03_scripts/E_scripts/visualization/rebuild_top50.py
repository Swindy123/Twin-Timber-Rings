from __future__ import annotations

from collections import Counter
from pathlib import Path

import jieba
import pandas as pd

BASE = Path(r"e:/大学/大二/大二下/数据可视化/大作业_传播学")
OUT = BASE / "output"
ALL_PATH = OUT / "all_weibo_texts_clean.csv"
RULES_PATH = OUT / "label_rules.xlsx"

CUSTOM_WORDS = [
    "旺仔小乔",
    "张碧晨",
    "汪苏泷",
    "年轮",
    "唯一原唱",
    "双原唱",
    "收回授权",
    "永久演唱权",
    "原唱之争",
    "花千骨",
    "OST",
    "版权",
    "著作权",
    "演唱权",
]

STOPWORDS = {
    "的", "了", "和", "是", "在", "就", "都", "而", "及", "与", "还", "也", "很", "这", "那", "一个",
    "你", "我", "他", "她", "它", "们", "吧", "啊", "呢", "嘛", "呀", "吗", "被", "把", "对", "着",
    "有", "没", "无", "从", "到", "给", "让", "又", "再", "去", "来", "说", "看", "听", "做",
    "真的", "还是", "就是", "但是", "因为", "所以", "如果", "这个", "那个", "什么", "怎么", "非常",
    "来自", "回复", "微博", "视频", "自己", "歌手", "广东", "不是",
    "年轮", "张碧晨", "汪苏泷", "唯一原唱", "双原唱", "收回授权", "永久演唱权", "原唱之争", "花千骨", "版权", "著作权", "演唱权",
}

for word in CUSTOM_WORDS:
    jieba.add_word(word)


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    words = []
    for token in jieba.lcut(text):
        token = token.strip()
        if not token:
            continue
        if token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        if len(token) < 2 and token not in {"A", "B", "C", "D", "E", "OST"}:
            continue
        # normalize the known split artifact
        if token == "仔小乔":
            token = "旺仔小乔"
        words.append(token)
    return words


df = pd.read_csv(ALL_PATH, encoding="utf-8-sig")
texts = df.get("text_clean", pd.Series(dtype=str)).fillna("").astype(str)

counter = Counter()
for text in texts:
    counter.update(tokenize(text))

# Merge any residual split forms into the desired token
for alias in ["仔小乔", "旺仔", "小乔"]:
    if alias in counter:
        counter["旺仔小乔"] += counter.pop(alias)

# Build Top 50
rows = [(word, count) for word, count in counter.most_common()]
# Ensure the corrected term appears and the wrong term does not
rows = [(word, count) for word, count in rows if word != "仔小乔"]
if any(word == "旺仔小乔" for word, _ in rows):
    pass
else:
    rows.append(("旺仔小乔", counter.get("旺仔小乔", 0)))
rows = sorted(rows, key=lambda x: (-x[1], x[0]))

top50 = pd.DataFrame(rows[:50], columns=["词语", "频次"])

# Force output sheet replacement
with pd.ExcelWriter(RULES_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    # preserve the rest of the workbook by rewriting only the target sheet
    top50.to_excel(writer, sheet_name="高频词Top50", index=False)

print("Done rebuild_top50")
print(top50.head(10).to_string(index=False))
print("contains 仔小乔:", int((top50["词语"] == "仔小乔").sum()))
print("contains 旺仔小乔:", int((top50["词语"] == "旺仔小乔").sum()))
