import csv
import sys

sys.stdout.reconfigure(encoding='utf-8')

INPUT = "weibo_posts_part1.csv"

with open(INPUT, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

def parse_count(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

# Sort by comment_count descending
rows.sort(key=lambda r: parse_count(r['comment_count']), reverse=True)

# Greedy: assign each row to the group with the smallest total so far
groups = [[] for _ in range(5)]
totals = [0] * 5

for row in rows:
    c = parse_count(row['comment_count'])
    idx = min(range(5), key=lambda i: totals[i])
    groups[idx].append(row)
    totals[idx] += c

fieldnames = reader.fieldnames
for i, group in enumerate(groups, 1):
    out = f"weibo_posts_part1_{i}.csv"
    total_c = sum(parse_count(r['comment_count']) for r in group)
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(group, key=lambda r: parse_count(r['comment_count']), reverse=True))
    print(f"{out}: {len(group):>4} rows, total comments: {total_c:>6}")

print(f"\nDone.")
