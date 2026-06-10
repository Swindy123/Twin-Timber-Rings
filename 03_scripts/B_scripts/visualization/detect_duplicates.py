"""
《年轮》舆论争议项目 —— 双方阵营高频话术提取脚本
================================================
利用 stance（立场）标签划分阵营，提取各自最典型的高频话术。

运行方式：
  python extract_phrases.py

输出：
  - zhang_fans_phrases.txt  —— 女方阵营（support_zhang）10 条典型原句
  - wang_fans_phrases.txt   —— 男方阵营（support_wang）10 条典型原句
  - 终端打印双方 Top-30 高频词组
"""

import re
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

# ============================================================
# 1. 加载数据
# ============================================================

df = pd.read_csv("all_weibo_comments_annotated.csv", encoding="utf-8-sig")
print(f"[OK] 已加载数据：all_weibo_comments_annotated.csv（{len(df)} 行）")
print(f"    stance 分布：\n{df['stance'].value_counts().to_string()}")

# ============================================================
# 2. 阵营划分：按 stance 立场标签分类
# ============================================================

# 只保留明确支持某一方的立场
zhang_mask = df["stance"] == "support_zhang"
wang_mask = df["stance"] == "support_wang"

df_zhang = df[zhang_mask].copy()
df_wang = df[wang_mask].copy()

print(f"\n  女方阵营（support_zhang）：{len(df_zhang)} 条")
print(f"  男方阵营（support_wang）：{len(df_wang)} 条")

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
    t = re.sub(r"\[.*?\]", "", t)        # 去掉微博表情 [笑哭] [doge] 等（连内容删除）
    t = re.sub(r"[【】「」]", "", t)      # 去掉中文书名号/引号（仅符号本身，保留内容）
    t = re.sub(r"\s+", " ", t).strip()   # 合并多余空白
    return t

text_col = "text_clean"
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

def extract_typical_phrases(df_camp, phrases, n=10, min_len=15):
    """
    取 Top-1 最高频词组，用其第一个 token 匹配原文（token 在句中出现即算）。
    按长度倒序取前 n 条去重原句。
    返回 (author_name, text) 元组列表。
    """
    top_token = phrases[0][0].split()[0]  # 最高频词组中的第一个 token
    mask = df_camp["text_clean"].str.contains(top_token, na=False)
    hits = df_camp.loc[mask].copy()
    hits = hits[hits["text_clean"].str.len() > min_len]
    hits = hits.drop_duplicates(subset="text_clean", keep="first")
    hits = hits.sort_values("text_clean", key=lambda x: x.str.len(), ascending=False)
    result = list(zip(hits["author_name"], hits["text_clean"]))
    return result[:n]

zhang_samples = extract_typical_phrases(df_zhang, zhang_phrases)
wang_samples = extract_typical_phrases(df_wang, wang_phrases)

# ============================================================
# 6. 结果导出
# ============================================================

def save_phrases(filepath, camp_name, phrases, samples, top_k=30):
    """将词组统计 + 典型原句写入文本文件。"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"【{camp_name}】阵营高频话术与典型洗脑包原句\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"▎Top-{top_k} 高频词组（用于匹配）：\n")
        for rank, (phrase, count) in enumerate(phrases, 1):
            f.write(f"  {rank:2d}. 「{phrase}」—— 出现 {count} 次\n")

        f.write(f"\n▎典型洗脑包原句（共 {len(samples)} 条）：\n")
        f.write("-" * 55 + "\n")
        for i, (author, sentence) in enumerate(samples, 1):
            f.write(f"\n【{i}】@{author}\n    {sentence}\n")
    print(f"[OK] 已导出：{filepath}")

save_phrases(
    "zhang_fans_phrases.txt",
    "女方（stance=support_zhang）",
    zhang_phrases,
    zhang_samples,
)
save_phrases(
    "wang_fans_phrases.txt",
    "男方（stance=support_wang）",
    wang_phrases,
    wang_samples,
)

print(f"\n全部完成！请在项目根目录查看 zhang_fans_phrases.txt 和 wang_fans_phrases.txt。")
