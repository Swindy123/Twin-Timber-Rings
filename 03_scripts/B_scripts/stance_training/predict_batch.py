import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

GOLDEN_FILE = r'D:\1ZJUSstudy\study_3_down\数据可视化\Homework3\可视化2\b22\B2_Songw\data_copilot_cleaned.csv'
COMMENTS_FILE = 'data/filtered/weibo_comments_filtered5.csv'
REPOSTS_FILE = 'data/filtered/weibo_reposts_api_clean_multihop_filtered.csv'
OUTPUT_COMMENTS = 'data/filtered/weibo_comments_filtered5_predicted.csv'
OUTPUT_REPOSTS = 'data/filtered/weibo_reposts_api_clean_multihop_filtered_predicted.csv'

RATIO_THRESHOLD = 10.0
MAX_OTHER_COUNT = 2
TOP_N_PHRASES = 50

print('=' * 60)
print('读取训练数据...')
df_golden = pd.read_csv(GOLDEN_FILE, encoding='utf-8')

text_col_golden = 'text_clean' if 'text_clean' in df_golden.columns else 'text'
stance_col = next((c for c in ['stance_llm', 'stance'] if c in df_golden.columns), None)

df_golden = df_golden.dropna(subset=[text_col_golden, stance_col])
df_golden = df_golden[df_golden[text_col_golden].str.strip() != '']

print(f'训练数据: {df_golden.shape[0]} 条')
print(f'立场标签列: "{stance_col}"')
print(f'标签分布:\n{df_golden[stance_col].value_counts().to_string()}')

# 只保留 support_wang 和 support_zhang 用于训练
df_train = df_golden[df_golden[stance_col].isin(['support_wang', 'support_zhang'])].copy()
print(f'\n筛选后训练数据 (support_wang + support_zhang): {df_train.shape[0]} 条')

print('=' * 60)
print('划分训练集 / 测试集 (8:2)...')

label_encoder = LabelEncoder()
y_all = label_encoder.fit_transform(df_train[stance_col].values)

X_train_df, X_test_df, y_train, y_test = train_test_split(
    df_train, y_all, test_size=0.2, random_state=42, stratify=y_all
)
print(f'训练集: {len(X_train_df)} 条, 测试集: {len(X_test_df)} 条')

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

print('=' * 60)
print('在测试集上评估...')

test_preds = []
for text in tqdm(X_test_df[text_col_golden], desc='评估测试集'):
    pred_label, _ = hybrid_predict(
        text, wang_rules_phrases, zhang_rules_phrases,
        ml_classifier, tfidf, label_encoder
    )
    test_preds.append(pred_label)

print(f'\n混合模型分类报告:')
print(classification_report(X_test_df[stance_col].values, test_preds, digits=4))

# ==================== 预测两个文件 ====================
def predict_file(filepath, text_column, output_path, label):
    print('=' * 60)
    print(f'预测 {label}: {filepath}')
    df = pd.read_csv(filepath, encoding='utf-8')
    print(f'原始数据: {df.shape[0]} 条')

    if text_column not in df.columns:
        print(f'错误: 找不到 "{text_column}" 列')
        return

    df = df.dropna(subset=[text_column])
    df = df[df[text_column].str.strip() != '']
    print(f'有效数据: {df.shape[0]} 条')

    preds = []
    sources = []
    for text in tqdm(df[text_column], desc=f'预测 {label}'):
        pred_label, source = hybrid_predict(
            text, wang_rules_phrases, zhang_rules_phrases,
            ml_classifier, tfidf, label_encoder
        )
        preds.append(pred_label)
        sources.append(source)

    df['predicted_stance'] = preds
    df['prediction_source'] = sources

    print(f'\n预测来源分布:')
    for src, cnt in df['prediction_source'].value_counts().items():
        pct = cnt / len(df) * 100
        print(f'  {src:<15}: {cnt:>5} 条 ({pct:.1f}%)')

    print(f'\n预测立场分布:')
    print(df['predicted_stance'].value_counts().to_string())

    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f'保存完成: {output_path}')

predict_file(COMMENTS_FILE, 'comment_text', OUTPUT_COMMENTS, '评论')
predict_file(REPOSTS_FILE, 'repost_text', OUTPUT_REPOSTS, '转发')

print('=' * 60)
print('全部预测完成！')
