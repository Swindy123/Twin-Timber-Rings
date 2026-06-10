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
PREDICT_FILE = 'weibo_posts_cleaned.csv'
OUTPUT_FILE = 'weibo_posts_predicted.csv'

RATIO_THRESHOLD = 10.0
MAX_OTHER_COUNT = 2
TOP_N_PHRASES = 50

# ==================== 1. 读取数据 ====================
print('=' * 60)
print('读取 CSV 文件...')

df_golden = pd.read_csv(GOLDEN_FILE, encoding='utf-8')
df_predict = pd.read_csv(PREDICT_FILE, encoding='utf-8')

text_col_golden = 'text_clean' if 'text_clean' in df_golden.columns else 'text'
text_col_predict = 'text_clean' if 'text_clean' in df_predict.columns else 'text'
stance_col = next((c for c in ['stance_llm', 'stance'] if c in df_golden.columns), None)

df_golden = df_golden.dropna(subset=[text_col_golden, stance_col])
df_golden = df_golden[df_golden[text_col_golden].str.strip() != '']
df_predict = df_predict.dropna(subset=[text_col_predict])
df_predict = df_predict[df_predict[text_col_predict].str.strip() != '']

print(f'训练数据: {df_golden.shape[0]} 条')
print(f'待预测数据: {df_predict.shape[0]} 条')
print(f'立场标签列: "{stance_col}"')
print(f'预测文本列: "{text_col_predict}"')

# ==================== 2. 划分训练集 & 测试集 (8:2) ====================
print('=' * 60)
print('划分训练集 / 测试集 (8:2)...')

label_encoder = LabelEncoder()
y_all = label_encoder.fit_transform(df_golden[stance_col].values)

X_train_df, X_test_df, y_train, y_test = train_test_split(
    df_golden, y_all, test_size=0.2, random_state=42, stratify=y_all
)
print(f'训练集: {len(X_train_df)} 条, 测试集: {len(X_test_df)} 条')

# ==================== 3. 提取排他性硬规则 ====================
print('=' * 60)
print('自动提取排他性硬规则...')

train_wang = X_train_df[X_train_df[stance_col] == 'support_wang'][text_col_golden]
train_zhang = X_train_df[X_train_df[stance_col] == 'support_zhang'][text_col_golden]

print(f'  support_wang: {len(train_wang)} 条, support_zhang: {len(train_zhang)} 条')

phrase_vectorizer = CountVectorizer(analyzer='char', ngram_range=(2, 3), min_df=2)

wang_phrase_matrix = phrase_vectorizer.fit_transform(train_wang)
zhang_phrase_matrix = phrase_vectorizer.transform(train_zhang)

feature_names = phrase_vectorizer.get_feature_names_out()
wang_doc_freq = np.array((wang_phrase_matrix > 0).sum(axis=0)).flatten()
zhang_doc_freq = np.array((zhang_phrase_matrix > 0).sum(axis=0)).flatten()

wang_top_indices = np.argsort(wang_doc_freq)[::-1][:TOP_N_PHRASES]
zhang_top_indices = np.argsort(zhang_doc_freq)[::-1][:TOP_N_PHRASES]

wang_auto_rules = []
for idx in wang_top_indices:
    phrase = feature_names[idx]
    w_count = int(wang_doc_freq[idx])
    z_count = int(zhang_doc_freq[idx])
    ratio = w_count / max(z_count, 1)
    if ratio >= RATIO_THRESHOLD and z_count <= MAX_OTHER_COUNT:
        wang_auto_rules.append((phrase, w_count, z_count, round(ratio, 2)))

zhang_auto_rules = []
for idx in zhang_top_indices:
    phrase = feature_names[idx]
    z_count = int(zhang_doc_freq[idx])
    w_count = int(wang_doc_freq[idx])
    ratio = z_count / max(w_count, 1)
    if ratio >= RATIO_THRESHOLD and w_count <= MAX_OTHER_COUNT:
        zhang_auto_rules.append((phrase, z_count, w_count, round(ratio, 2)))

print(f'自动提取到 {len(wang_auto_rules)} 条 support_wang 规则, {len(zhang_auto_rules)} 条 support_zhang 规则')

wang_rules_phrases = [item[0] for item in wang_auto_rules]
zhang_rules_phrases = [item[0] for item in zhang_auto_rules]

# ==================== 4. 混合预测函数 ====================
def hybrid_predict(text, wang_rules, zhang_rules, ml_model, tfidf_vectorizer, le):
    if not isinstance(text, str) or text.strip() == '':
        return 'unclear', 'fallback'
    for rule in wang_rules:
        if rule in text:
            return 'support_wang', 'rule_wang'
    for rule in zhang_rules:
        if rule in text:
            return 'support_zhang', 'rule_zhang'
    vec = tfidf_vectorizer.transform([text])
    pred_id = ml_model.predict(vec)[0]
    label = le.inverse_transform([pred_id])[0]
    return label, 'ml'

# ==================== 5. 训练 ML 兜底模型 ====================
print('=' * 60)
print('训练 TF-IDF + LinearSVC 兜底模型...')

import jieba
def jieba_tokenizer(text):
    return list(jieba.cut(text))

tfidf = TfidfVectorizer(
    tokenizer=jieba_tokenizer,
    max_features=10000,
    ngram_range=(1, 3),
    min_df=2,
    max_df=0.9,
)

X_train_vec = tfidf.fit_transform(X_train_df[text_col_golden])
y_train_labels = label_encoder.transform(X_train_df[stance_col].values)

ml_classifier = LinearSVC(max_iter=2000, C=1.0, random_state=42)
ml_classifier.fit(X_train_vec, y_train_labels)
print('ML 模型训练完成！')

# ==================== 6. 测试集评估 ====================
print('=' * 60)
print('在测试集上评估混合模型...')

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
print(f'\n混合模型分类报告:')
print(classification_report(y_test_true, test_preds, digits=4))

# ==================== 7. 预测 Posts ====================
print('=' * 60)
print(f'预测 Posts ({len(df_predict)} 条)...')

predict_preds = []
predict_sources = []

for text in tqdm(df_predict[text_col_predict], desc='预测 Posts'):
    pred_label, source = hybrid_predict(
        text, wang_rules_phrases, zhang_rules_phrases,
        ml_classifier, tfidf, label_encoder
    )
    predict_preds.append(pred_label)
    predict_sources.append(source)

df_predict['predicted_stance'] = predict_preds
df_predict['prediction_source'] = predict_sources

print(f'\n预测来源分布:')
for src, cnt in df_predict['prediction_source'].value_counts().items():
    pct = cnt / len(df_predict) * 100
    print(f'  {src:<15}: {cnt:>5} 条 ({pct:.1f}%)')

print(f'\n预测立场分布:')
print(df_predict['predicted_stance'].value_counts().to_string())

# ==================== 8. 保存结果 ====================
print('=' * 60)
print(f'保存结果到 {OUTPUT_FILE} ...')
df_predict.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
print('保存完成！')
print('=' * 60)
