# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split

df = pd.read_csv('data_copilot_cleaned.csv', encoding='utf-8')
df = df.dropna(subset=['text_clean', 'stance_llm'])

train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['stance_llm'])

train_wang = train_df[train_df['stance_llm'] == 'support_wang']['text_clean']
train_zhang = train_df[train_df['stance_llm'] == 'support_zhang']['text_clean']

vec = CountVectorizer(analyzer='char', ngram_range=(2, 3), min_df=2)
wm = vec.fit_transform(train_wang)
zm = vec.transform(train_zhang)

names = vec.get_feature_names_out()
wf = np.array((wm > 0).sum(axis=0)).flatten()
zf = np.array((zm > 0).sum(axis=0)).flatten()

top_w = np.argsort(wf)[::-1][:50]

with open('_rules_detail.txt', 'w', encoding='utf-8') as f:
    f.write('=== support_wang top 50 高频短语 ===\n')
    for idx in top_w[:20]:
        p = names[idx]; wc = int(wf[idx]); zc = int(zf[idx])
        r = wc / max(zc, 1)
        f.write(f'  phrase=[{p}]  Wang={wc}  Zhang={zc}  ratio={r:.1f}\n')

    f.write('\n\n=== 排他性规则 (比值>=10, 对方<=2) ===\n')
    for idx in top_w:
        p = names[idx]; wc = int(wf[idx]); zc = int(zf[idx])
        r = wc / max(zc, 1)
        if r >= 10 and zc <= 2:
            f.write(f'  [{p}] Wang={wc} Zhang={zc} ratio={r:.1f}\n')
            # show full text
            hit = train_df[(train_df['stance_llm'] == 'support_wang') & (train_df['text_clean'].str.contains(p, regex=False))]
            for i, row in enumerate(hit.head(3).itertuples(), 1):
                f.write(f'    Wang例{i}: {row.text_clean[:120]}\n')
            hit2 = train_df[(train_df['stance_llm'] == 'support_zhang') & (train_df['text_clean'].str.contains(p, regex=False))]
            for i, row in enumerate(hit2.head(2).itertuples(), 1):
                f.write(f'    Zhang例{i}: {row.text_clean[:120]}\n')
            f.write('\n')

    f.write('\n=== support_zhang top 50 高频短语 ===\n')
    top_z = np.argsort(zf)[::-1][:50]
    for idx in top_z[:20]:
        p = names[idx]; zc = int(zf[idx]); wc = int(wf[idx])
        r = zc / max(wc, 1)
        f.write(f'  phrase=[{p}]  Zhang={zc}  Wang={wc}  ratio={r:.1f}\n')

    f.write('\n\n=== Zhang 排他性规则 ===\n')
    found = False
    for idx in top_z:
        p = names[idx]; zc = int(zf[idx]); wc = int(wf[idx])
        r = zc / max(wc, 1)
        if r >= 10 and wc <= 2:
            found = True
            f.write(f'  [{p}] Zhang={zc} Wang={wc} ratio={r:.1f}\n')
    if not found:
        f.write('  （无符合条件的规则）\n')

print('结果已写入 _rules_detail.txt')
