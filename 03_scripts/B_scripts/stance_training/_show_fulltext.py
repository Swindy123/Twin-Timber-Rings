# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split

df = pd.read_csv('data_copilot_cleaned.csv', encoding='utf-8')
df = df.dropna(subset=['text_clean', 'stance_llm'])

train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['stance_llm'])

train_wang = train_df[train_df['stance_llm'] == 'support_wang']
train_zhang = train_df[train_df['stance_llm'] == 'support_zhang']

# 找到命中规则"方法"的文本
rule = '方法'
hit_wang = train_wang[train_wang['text_clean'].str.contains(rule, regex=False)]
hit_zhang = train_zhang[train_zhang['text_clean'].str.contains(rule, regex=False)]

with open('_rules_output.txt', 'w', encoding='utf-8') as f:
    f.write(f'========== 规则短语: "{rule}" ==========\n')
    f.write(f'support_wang 命中: {len(hit_wang)} 条\n')
    f.write(f'support_zhang 命中: {len(hit_zhang)} 条\n\n')

    f.write('【support_wang 命中原文 - 前 20 条】\n')
    f.write('=' * 60 + '\n')
    for i, row in enumerate(hit_wang.head(20).itertuples(), 1):
        f.write(f'{i}. {row.text_clean}\n\n')

    f.write('【support_zhang 命中原文 - 全部】\n')
    f.write('=' * 60 + '\n')
    for i, row in enumerate(hit_zhang.itertuples(), 1):
        f.write(f'{i}. {row.text_clean}\n\n')

print('结果已保存到 _rules_output.txt')
