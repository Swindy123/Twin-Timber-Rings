import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split

df = pd.read_csv('data_copilot_cleaned.csv', encoding='utf-8')
df = df.dropna(subset=['text_clean', 'stance_llm'])
train_df, _ = train_test_split(df, test_size=0.2, random_state=42, stratify=df['stance_llm'])

train_wang = train_df[train_df['stance_llm'] == 'support_wang']['text_clean']
train_zhang = train_df[train_df['stance_llm'] == 'support_zhang']['text_clean']

vec = CountVectorizer(analyzer='char', ngram_range=(2, 3), min_df=2)
wm = vec.fit_transform(train_wang)
zm = vec.transform(train_zhang)

names = vec.get_feature_names_out()
wf = np.array((wm > 0).sum(axis=0)).flatten()
zf = np.array((zm > 0).sum(axis=0)).flatten()

top_w = np.argsort(wf)[::-1][:50]
print('=== support_wang 排他性规则 (比值>=10, Zhang端<=2) ===')
for idx in top_w:
    p = names[idx]; wc = int(wf[idx]); zc = int(zf[idx])
    r = wc / max(zc, 1)
    if r >= 10 and zc <= 2:
        print(f'  短语="{p}"  Wang={wc}条  Zhang={zc}条  比值={r:.1f}')
        kwang = train_wang[train_wang.str.contains(p, regex=False)].head(2)
        kzhang = train_zhang[train_zhang.str.contains(p, regex=False)].head(2)
        for txt in kwang:
            print(f'    [Wang原文] {txt[:80]}')
        for txt in kzhang:
            print(f'    [Zhang原文] {txt[:80]}')
        print()

print('=== support_zhang 排他性规则 ===')
top_z = np.argsort(zf)[::-1][:50]
found = False
for idx in top_z:
    p = names[idx]; zc = int(zf[idx]); wc = int(wf[idx])
    r = zc / max(wc, 1)
    if r >= 10 and wc <= 2:
        found = True
        print(f'  短语="{p}"  Zhang={zc}条  Wang={wc}条  比值={r:.1f}')
        kzhang = train_zhang[train_zhang.str.contains(p, regex=False)].head(2)
        kwang = train_wang[train_wang.str.contains(p, regex=False)].head(2)
        for txt in kzhang:
            print(f'    [Zhang原文] {txt[:80]}')
        for txt in kwang:
            print(f'    [Wang原文] {txt[:80]}')
        print()
if not found:
    print('  （无符合条件规则）')
