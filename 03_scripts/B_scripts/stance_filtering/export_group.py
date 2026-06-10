import csv
import glob
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

URL_PATTERN = re.compile(r'https?://t\.cn/\S+', re.IGNORECASE)
EMOJI_PATTERN = re.compile(
    '[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
    '\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251'
    '\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
    '\U00002600-\U000026FF\U0000FE00-\U0000FE0F\U0000200D]', flags=re.UNICODE)

def clean(text):
    text = URL_PATTERN.sub('', text)
    text = EMOJI_PATTERN.sub('', text)
    text = re.sub(r'[@#]\S+', '', text)
    text = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text

SIMILARITY_THRESHOLD = 0.75

all_comments = []
all_metas = []

files = sorted(glob.glob('filtered/weibo_comments_filtered*.csv'))
for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) >= 7:
                text = row[6].strip()
                if text:
                    all_comments.append(text)
                    all_metas.append((fpath, row, header))

print(f'Total: {len(all_comments)} comments', file=sys.stderr)

texts_clean = [clean(t) for t in all_comments]
valid_idx = [i for i, t in enumerate(texts_clean) if len(t) >= 3]
texts_clean = [texts_clean[i] for i in valid_idx]
all_comments = [all_comments[i] for i in valid_idx]
all_metas = [all_metas[i] for i in valid_idx]

vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), max_features=5000)
tfidf = vectorizer.fit_transform(texts_clean)

sim = cosine_similarity(tfidf)

visited = set()
groups = []
for i in range(tfidf.shape[0]):
    if i in visited:
        continue
    group = [i]
    visited.add(i)
    for j in range(i + 1, tfidf.shape[0]):
        if j in visited:
            continue
        if sim[i, j] >= SIMILARITY_THRESHOLD:
            group.append(j)
            visited.add(j)
    if len(group) >= 2:
        groups.append(group)

groups.sort(key=lambda g: len(g), reverse=True)

# Find the EXO group
target_group = None
for g in groups:
    sample_text = all_comments[g[0]]
    if 'exo' in sample_text.lower() or '私生' in sample_text:
        target_group = g
        break

# Output CSV
output_path = 'filtered/group15_exo.csv'
header = ['group_id'] + all_metas[0][2]

with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for i, gi in enumerate(target_group):
        meta = all_metas[gi]
        row = meta[1]
        writer.writerow([i + 1] + row)

print(f'Exported {len(target_group)} rows to {output_path}', file=sys.stderr)
