import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ==================== 配置 ====================
GOLDEN_FILE = 'data_copilot_cleaned.csv'
REMAINING_FILE = 'remaining_data.csv'
OUTPUT_FILE = 'predicted_results.csv'

RATIO_THRESHOLD = 10.0       # 排他性比值阈值（一方出现次数 / 另一方出现次数）
MAX_OTHER_COUNT = 2          # 允许在对方阵营出现的最大文档数
TOP_N_PHRASES = 50           # 每类提取的前 N 个高频短语

# ==================== 1. 读取数据 ====================
print('=' * 60)
print('读取 CSV 文件...')

df_golden = pd.read_csv(GOLDEN_FILE, encoding='utf-8')
df_remaining = pd.read_csv(REMAINING_FILE, encoding='utf-8')

# 自动检测列名
text_col_golden = 'text_clean' if 'text_clean' in df_golden.columns else 'text'
text_col_remaining = 'text_clean' if 'text_clean' in df_remaining.columns else 'text'
stance_col = next((c for c in ['stance_llm', 'stance'] if c in df_golden.columns), None)

# 去除空文本
df_golden = df_golden.dropna(subset=[text_col_golden, stance_col])
df_golden = df_golden[df_golden[text_col_golden].str.strip() != '']
df_remaining = df_remaining.dropna(subset=[text_col_remaining])
df_remaining = df_remaining[df_remaining[text_col_remaining].str.strip() != '']

print(f'黄金数据: {df_golden.shape[0]} 条, 剩余数据: {df_remaining.shape[0]} 条')
print(f'立场标签列: "{stance_col}"')

# ==================== 2. 划分训练集 & 测试集 (8:2) ====================
print('=' * 60)
print('划分训练集 / 测试集 (8:2, 按标签分层抽样)...')

label_encoder = LabelEncoder()
y_all = label_encoder.fit_transform(df_golden[stance_col].values)

X_train_df, X_test_df, y_train, y_test = train_test_split(
    df_golden, y_all, test_size=0.2, random_state=42, stratify=y_all
)
print(f'训练集: {len(X_train_df)} 条, 测试集: {len(X_test_df)} 条')

# ==================== 3. 自动提取排他性硬规则 ====================
print('=' * 60)
print('【步骤 A】自动提取排他性硬规则...')
print(f'提取参数: 每类前 {TOP_N_PHRASES} 个短语, 排他比值 >= {RATIO_THRESHOLD}, 对方出现次数 <= {MAX_OTHER_COUNT}')

# 从训练集中筛选 support_wang 和 support_zhang 的数据
train_wang = X_train_df[X_train_df[stance_col] == 'support_wang']['text_clean']
train_zhang = X_train_df[X_train_df[stance_col] == 'support_zhang']['text_clean']

print(f'  训练集中 support_wang: {len(train_wang)} 条')
print(f'  训练集中 support_zhang: {len(train_zhang)} 条')

# 使用字符级别 2-gram 和 3-gram 提取短语（对中文效果好）
phrase_vectorizer = CountVectorizer(
    analyzer='char',
    ngram_range=(2, 3),
    min_df=2
)

# 分别对两家做短语频率统计
wang_phrase_matrix = phrase_vectorizer.fit_transform(train_wang)
zhang_phrase_matrix = phrase_vectorizer.transform(train_zhang)

# 获取短语列表和每类中的文档频次（有多少条文本包含该短语）
feature_names = phrase_vectorizer.get_feature_names_out()
wang_doc_freq = np.array((wang_phrase_matrix > 0).sum(axis=0)).flatten()
zhang_doc_freq = np.array((zhang_phrase_matrix > 0).sum(axis=0)).flatten()

# 提取 wang 阵营的前 TOP_N_PHRASES 个高频短语索引
wang_top_indices = np.argsort(wang_doc_freq)[::-1][:TOP_N_PHRASES]
zhang_top_indices = np.argsort(zhang_doc_freq)[::-1][:TOP_N_PHRASES]

# ---------- 自动提取 Wang 的硬规则 ----------
wang_auto_rules = []
for idx in wang_top_indices:
    phrase = feature_names[idx]
    w_count = int(wang_doc_freq[idx])
    z_count = int(zhang_doc_freq[idx])
    ratio = w_count / max(z_count, 1)
    if ratio >= RATIO_THRESHOLD and z_count <= MAX_OTHER_COUNT:
        wang_auto_rules.append((phrase, w_count, z_count, round(ratio, 2)))

# ---------- 自动提取 Zhang 的硬规则 ----------
zhang_auto_rules = []
for idx in zhang_top_indices:
    phrase = feature_names[idx]
    z_count = int(zhang_doc_freq[idx])
    w_count = int(wang_doc_freq[idx])
    ratio = z_count / max(w_count, 1)
    if ratio >= RATIO_THRESHOLD and w_count <= MAX_OTHER_COUNT:
        zhang_auto_rules.append((phrase, z_count, w_count, round(ratio, 2)))

# 打印提取结果
print(f'\n自动提取到 {len(wang_auto_rules)} 条 support_wang 排他性规则:')
if wang_auto_rules:
    print(f'  {"短语":<20} {"Wang中出现":<12} {"Zhang中出现":<12} {"比值":<8}')
    print(f'  {"-"*52}')
    for phrase, wc, zc, r in wang_auto_rules:
        print(f'  {phrase:<20} {wc:<12} {zc:<12} {r:<8}')
else:
    print('  （未提取到符合条件的规则，可尝试降低 RATIO_THRESHOLD）')

print(f'\n自动提取到 {len(zhang_auto_rules)} 条 support_zhang 排他性规则:')
if zhang_auto_rules:
    print(f'  {"短语":<20} {"Zhang中出现":<12} {"Wang中出现":<12} {"比值":<8}')
    print(f'  {"-"*52}')
    for phrase, zc, wc, r in zhang_auto_rules:
        print(f'  {phrase:<20} {zc:<12} {wc:<12} {r:<8}')
else:
    print('  （未提取到符合条件的规则，可尝试降低 RATIO_THRESHOLD）')

# 合并规则列表（仅保留短语文本）
wang_rules_phrases = [item[0] for item in wang_auto_rules]
zhang_rules_phrases = [item[0] for item in zhang_auto_rules]

# ==================== 4. 混合预测函数 ====================
def hybrid_predict(text, wang_rules, zhang_rules, ml_model, tfidf_vectorizer, le):
    """
    混合预测：先检查硬规则，未命中则走 ML 模型兜底。
    返回 (预测标签, 预测来源) 其中来源为 'rule_wang'/'rule_zhang'/'ml'
    """
    if not isinstance(text, str) or text.strip() == '':
        return 'unclear', 'fallback'

    # 先检查 Wang 规则（优先级高）
    for rule in wang_rules:
        if rule in text:
            return 'support_wang', 'rule_wang'

    # 再检查 Zhang 规则
    for rule in zhang_rules:
        if rule in text:
            return 'support_zhang', 'rule_zhang'

    # 未命中任何规则，走 ML 模型
    vec = tfidf_vectorizer.transform([text])
    pred_id = ml_model.predict(vec)[0]
    label = le.inverse_transform([pred_id])[0]
    return label, 'ml'

# ==================== 5. 训练 ML 兜底模型 ====================
print('=' * 60)
print('训练 TF-IDF + LinearSVC 兜底模型...')

# jieba 分词器
import jieba
def jieba_tokenizer(text):
    return list(jieba.cut(text))

# TF-IDF 向量化（只对训练集 fit）
tfidf = TfidfVectorizer(
    tokenizer=jieba_tokenizer,
    max_features=10000,
    ngram_range=(1, 3),
    min_df=2,
    max_df=0.9,
)

X_train_vec = tfidf.fit_transform(X_train_df[text_col_golden])
y_train_labels = label_encoder.transform(X_train_df[stance_col].values)

# LinearSVC 做多分类兜底
ml_classifier = LinearSVC(max_iter=2000, C=1.0, random_state=42)
ml_classifier.fit(X_train_vec, y_train_labels)
print('ML 兜底模型训练完成！')

# ==================== 6. 在测试集上评估混合模型 ====================
print('=' * 60)
print('在测试集上评估混合模型 (硬规则 + ML 兜底)...')

test_preds = []
test_sources = []

for text in tqdm(X_test_df[text_col_golden], desc='评估测试集'):
    pred_label, source = hybrid_predict(
        text, wang_rules_phrases, zhang_rules_phrases,
        ml_classifier, tfidf, label_encoder
    )
    test_preds.append(pred_label)
    test_sources.append(source)

y_test_true = X_test_df[stance_col].values
test_pred_encoded = label_encoder.transform(test_preds)

# 打印统计：规则命中情况
source_counts = pd.Series(test_sources).value_counts()
print(f'\n测试集预测来源分布:')
for src, cnt in source_counts.items():
    pct = cnt / len(test_sources) * 100
    print(f'  {src:<15}: {cnt:>4} 条 ({pct:.1f}%)')

print(f'\n混合模型分类报告:')
print(classification_report(y_test_true, test_preds, digits=4))

# 单独打印纯 ML 的对比
print('=' * 60)
print('纯 ML 模型（无规则）在测试集上的对比:')
y_pred_ml_only = ml_classifier.predict(tfidf.transform(X_test_df[text_col_golden]))
y_pred_ml_labels = label_encoder.inverse_transform(y_pred_ml_only)
print(classification_report(y_test_true, y_pred_ml_labels, digits=4))

# ==================== 7. 全自动预测剩余数据 ====================
print('=' * 60)
print(f'开始全自动预测剩余数据 ({len(df_remaining)} 条)...')

remaining_preds = []
remaining_sources = []

for text in tqdm(df_remaining[text_col_remaining], desc='预测进度'):
    pred_label, source = hybrid_predict(
        text, wang_rules_phrases, zhang_rules_phrases,
        ml_classifier, tfidf, label_encoder
    )
    remaining_preds.append(pred_label)
    remaining_sources.append(source)

df_remaining['predicted_stance'] = remaining_preds
df_remaining['prediction_source'] = remaining_sources

# 打印预测分布和命中率
print(f'\n预测完成！')
source_dist = df_remaining['prediction_source'].value_counts()
print(f'\n预测来源分布:')
for src, cnt in source_dist.items():
    pct = cnt / len(df_remaining) * 100
    print(f'  {src:<15}: {cnt:>5} 条 ({pct:.1f}%)')

print(f'\n预测标签分布:')
print(df_remaining['predicted_stance'].value_counts().to_string())

# ==================== 8. 保存结果 ====================
print('=' * 60)
print(f'保存结果到 {OUTPUT_FILE} ...')
df_remaining.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
print('保存完成！')

# ==================== 总结 ====================
print('=' * 60)
print('全部流程执行完毕！')
print(f'  - 训练数据: {len(X_train_df)} 条')
print(f'  - 测试数据: {len(X_test_df)} 条')
rule_hit = (pd.Series(test_sources) != 'ml').sum()
print(f'  - 测试集规则命中: {rule_hit}/{len(test_sources)} ({rule_hit/len(test_sources)*100:.1f}%)')
print(f'  - 剩余数据预测: {len(df_remaining)} 条')
print(f'  - 输出文件: {OUTPUT_FILE}')
print('=' * 60)
