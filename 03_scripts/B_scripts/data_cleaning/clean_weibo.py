import csv
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

INPUT = "weibo_posts.csv"
OUTPUT = "weibo_posts_cleaned.csv"

# Keywords that strongly indicate relevance to the 汪苏泷张碧晨年轮争吵
RELEVANT_KW = [
    r'汪苏泷.*张碧晨', r'张碧晨.*汪苏泷',
    r'年轮.*(?:原唱|版权|收回|争议|风波|撕|授权|演唱权|唯一|双原唱)',
    r'(?:原唱|版权|收回|争议|风波|撕|授权|演唱权|唯一|双原唱).*年轮',
    r'告别年轮', r'年轮回家', r'年轮纠纷', r'年轮事件',
    r'年轮.*商标', r'年轮.*抄袭',
    r'不再演唱年轮', r'年轮.*不再唱',
    r'张碧晨.*(?:原唱|版权|回应|声明)',
    r'汪苏泷.*(?:原唱|版权|收回|授权|声明)',
    r'花千骨.*年轮',
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in RELEVANT_KW]

def is_relevant(text: str) -> bool:
    for pat in COMPILED:
        if pat.search(text):
            return True
    return False

def is_clearly_irrelevant(text: str) -> bool:
    text_lower = text.lower()
    # Pure song sharing (only links, no discussion)
    if re.match(r'^[《（\[].*[）》\]].*[唱歌听].*[网页链接@]', text):
        return True
    # Pure karaoke cover sharing
    if '这是我在' in text and ('唱的' in text or '合唱' in text):
        return True
    # Main topic is other celebrities' gossip (孟子义, 王鹤棣, etc.)
    if re.search(r'(?:孟子义|王鹤棣|沈月|白鹿|李小冉|张昊玥|虞书欣|李荣浩|单依纯)', text):
        # Only exclude if the text doesn't strongly center on 汪苏泷/张碧晨
        ws_count = len(re.findall(r'汪苏泷|张碧晨', text))
        other_count = len(re.findall(r'孟子义|王鹤棣|沈月|白鹿|李小冉|张昊玥|虞书欣|李荣浩|单依纯', text))
        if other_count > ws_count:
            return True
    return False

kept = 0
removed = 0

with open(INPUT, 'r', encoding='utf-8-sig') as fin, \
     open(OUTPUT, 'w', newline='', encoding='utf-8-sig') as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
    writer.writeheader()

    for row in reader:
        text = row['text']
        if is_clearly_irrelevant(text):
            removed += 1
            print(f"[REMOVED] {row['post_id']} | {text[:60]}...")
            continue
        if is_relevant(text):
            kept += 1
            writer.writerow(row)
        else:
            removed += 1
            print(f"[REMOVED] {row['post_id']} | {text[:60]}...")

print(f"\nDone. Kept: {kept}, Removed: {removed}. Output: {OUTPUT}")
