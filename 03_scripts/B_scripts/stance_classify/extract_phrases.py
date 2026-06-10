"""
《年轮》舆论争议项目 —— 粉丝/水军阵营高频话术提取脚本
=====================================================
利用 author_type 标签过滤路人，直接从双方死忠粉和水军言论中
捞取最纯正的对线话术原句。

运行方式：
  python scripts/extract_phrases.py

输出：
  - zhang_fans_phrases.txt  —— 女方阵营（张方水军+张碧晨粉丝）10 条典型原句
  - wang_fans_phrases.txt   —— 男方阵营（汪方水军+汪苏泷粉丝）10 条典型原句
  - 终端打印双方 Top-30 高频词组
"""

import re
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

# ============================================================
# 1. 加载数据
# ============================================================

df = pd.read_csv("final_predicted_data.csv", encoding="utf-8-sig")
print(f"[OK] 已加载数据：final_predicted_data.csv（{len(df)} 行）")
print(f"    author_type 分布：\n{df['author_type'].value_counts().to_string()}")

# ============================================================
# 2. 阵营划分：过滤路人，合并粉丝/水军
# ============================================================

# 直接过滤掉路人
df = df[df["author_type"] != "路人"].copy()
print(f"\n[Info] 过滤路人后剩余 {len(df)} 条")

# 女方阵营：张方水军 + 张碧晨粉丝
zhang_mask = df["author_type"].isin(["张方水军", "张碧晨粉丝"])
df_zhang = df[zhang_mask].copy()
print(f"  女方阵营（张方水军+张碧晨粉丝）：{len(df_zhang)} 条")

# 男方阵营：汪方水军 + 汪苏泷粉丝
wang_mask = df["author_type"].isin(["汪方水军", "汪苏泷粉丝"])
df_wang = df[wang_mask].copy()
print(f"  男方阵营（汪方水军+汪苏泷粉丝）：{len(df_wang)} 条")

# ============================================================
# 3. 文本清洗：去掉 @用户 和 http/https 链接
# ============================================================

def clean_text(raw: str) -> str:
    """去除 @用户、URL、微博表情标签，防止干扰词组统计。"""
    if pd.isna(raw):
        return ""
    t = str(raw)
    t = re.sub(r"@\S+", "", t)           # 去掉 @用户名
    t = re.sub(r"https?://\S+", "", t)   # 去掉 http/https 链接
    t = re.sub(r"\[.*?\]", "", t)        # 去掉微博表情 [笑哭] [doge] 等
    t = re.sub(r"\s+", " ", t).strip()   # 合并多余空白
    return t

# 兼容 text_clean / comment_text 两种列名
text_col = "text_clean" if "text_clean" in df.columns else "comment_text"
df_zhang["text_clean"] = df_zhang[text_col].apply(clean_text)
df_wang["text_clean"] = df_wang[text_col].apply(clean_text)

# ============================================================
# 4. 自动统计粉丝/水军专属强特征词组（N-gram）
# ============================================================

def top_ngrams(texts, ngram_range=(2, 3), max_features=30):
    """用 CountVectorizer 统计最高频的 N-gram 词组。"""
    vec = CountVectorizer(
        ngram_range=ngram_range,
        max_features=max_features,
        token_pattern=r"(?u)\b\w+\b",
    )
    X = vec.fit_transform(texts)
    sums = X.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    idx = sums.argsort()[::-1]
    return [(terms[i], int(sums[i])) for i in idx]

def top_keywords(texts, max_features=10):
    """统计高频单字/双字词，用于辅助筛选典型原句。"""
    vec = CountVectorizer(
        ngram_range=(1, 1),
        max_features=max_features * 3,
        token_pattern=r"(?u)\b\w+\b",
    )
    X = vec.fit_transform(texts)
    sums = X.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    idx = sums.argsort()[::-1]
    skip_words = {"回复", "转发", "评论", "收起"}
    result = []
    for i in idx:
        if len(result) >= max_features:
            break
        w = terms[i]
        if w in skip_words or len(w) > 6:
            continue
        result.append(w)
    return result

# ---------- 女方阵营 ----------
zhang_texts = df_zhang["text_clean"]
zhang_texts = zhang_texts[zhang_texts.str.len() > 3]
print(f"\n{'='*60}")
print(f"【女方阵营】共 {len(zhang_texts)} 条有效文本")
print(f"{'='*60}")
zhang_phrases = top_ngrams(zhang_texts)
for rank, (phrase, count) in enumerate(zhang_phrases, 1):
    print(f"  {rank:2d}. 「{phrase}」—— 出现 {count} 次")

# ---------- 男方阵营 ----------
wang_texts = df_wang["text_clean"]
wang_texts = wang_texts[wang_texts.str.len() > 3]
print(f"\n{'='*60}")
print(f"【男方阵营】共 {len(wang_texts)} 条有效文本")
print(f"{'='*60}")
wang_phrases = top_ngrams(wang_texts)
for rank, (phrase, count) in enumerate(wang_phrases, 1):
    print(f"  {rank:2d}. 「{phrase}」—— 出现 {count} 次")

# ============================================================
# 5. 深度捞取典型洗脑包原句
# ============================================================

def extract_typical_phrases(texts, phrases, n=10, min_len=20):
    """
    筛选包含前 3 个高频特征词组、且长度 > min_len 的前 n 条去重原句。
    """
    top3 = [p for p, _ in phrases[:3]]
    hits = texts[
        texts.apply(lambda t: all(phrase in t for phrase in top3))
    ]
    hits = hits[hits.str.len() > min_len]
    unique = list(dict.fromkeys(hits.tolist()))
    sorted_hits = sorted(unique, key=len, reverse=True)
    return sorted_hits[:n]

# 取双方阵营的前 3 高频词组（用于原文匹配）
zhang_top3 = [p for p, _ in zhang_phrases[:3]]
wang_top3 = [p for p, _ in wang_phrases[:3]]

zhang_samples = extract_typical_phrases(zhang_texts, zhang_phrases)
wang_samples = extract_typical_phrases(wang_texts, wang_phrases)

# ============================================================
# 6. 结果导出
# ============================================================

def save_phrases(filepath, camp_name, phrases, samples, top3_phrases, top_k=30):
    """将词组统计 + 典型原句写入文本文件。"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"【{camp_name}】阵营高频话术与典型洗脑包原句\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"▎Top-{top_k} 高频词组：\n")
        for rank, (phrase, count) in enumerate(phrases, 1):
            f.write(f"  {rank:2d}. 「{phrase}」—— 出现 {count} 次\n")

        f.write(f"\n▎用于筛选的前 3 高频词组：{' / '.join(top3_phrases)}\n")
        f.write(f"\n▎典型洗脑包原句（共 {len(samples)} 条）：\n")
        f.write("-" * 55 + "\n")
        for i, sentence in enumerate(samples, 1):
            f.write(f"\n【{i}】{sentence}\n")
    print(f"[OK] 已导出：{filepath}")

save_phrases(
    "zhang_fans_phrases.txt",
    "女方（张方水军+张碧晨粉丝）",
    zhang_phrases,
    zhang_samples,
    zhang_top3,
)
save_phrases(
    "wang_fans_phrases.txt",
    "男方（汪方水军+汪苏泷粉丝）",
    wang_phrases,
    wang_samples,
    wang_top3,
)

print(f"\n全部完成！请在项目根目录查看 zhang_fans_phrases.txt 和 wang_fans_phrases.txt。")
