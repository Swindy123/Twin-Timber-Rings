import pandas as pd, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

df = pd.read_csv('all_weibo_comments_annotated.csv', encoding='utf-8-sig')
df = df[df['author_type'] != '路人'].copy()

def norm(t):
    if pd.isna(t): return ''
    t = str(t)
    t = re.sub(r'@\S+', '', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'[【】「」]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

df['text'] = df['text_clean'].apply(norm)
df = df[df['text'].str.len() > 10].copy()

lines = []
total_dup = 0
total_rows = 0

for stance, label in [('support_zhang', '支持张碧晨'), ('support_wang', '支持汪苏泷')]:
    lines.append(f"{'='*70}")
    lines.append(f"【{label}】")
    lines.append(f"{'='*70}\n")
    sub = df[df['stance'] == stance]
    vc = sub['text'].value_counts()
    dup = vc[vc > 1].sort_values(ascending=False)
    total_dup += len(dup)
    total_rows += dup.sum()

    for txt, cnt in dup.items():
        rows = sub[sub['text'] == txt]
        at_counts = rows['author_type'].value_counts()
        by_author = rows.groupby('author_name')['text'].count().sort_values(ascending=False)
        lines.append(f"━━━ 重复 {cnt} 次 ━━━")
        lines.append(f"  作者类型分布：{' | '.join(f'{k} {v}人' if v>1 else k for k,v in sorted(at_counts.items(), key=lambda x:-x[1]))}")
        lines.append(f"  发布用户 TOP5：{' | '.join([f'{k}({v}次)' for k,v in by_author.head(5).items()])}")
        lines.append(f"  {txt}")
        lines.append("")

with open('duplicated_texts.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'共 {total_dup} 组重复文本，{total_rows} 条重复评论')
print(f'输出文件：duplicated_texts.txt')
