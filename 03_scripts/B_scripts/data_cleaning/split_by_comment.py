import csv
import sys

sys.stdout.reconfigure(encoding='utf-8')

INPUT = "weibo_posts_cleaned.csv"

with open(INPUT, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Sort by comment_count descending (treat empty as 0)
def parse_count(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

rows.sort(key=lambda r: parse_count(r['comment_count']), reverse=True)

total = len(rows)
part_size = total // 5
parts = []
start = 0
for i in range(5):
    end = start + part_size + (1 if i < total % 5 else 0)
    parts.append(rows[start:end])
    start = end

fieldnames = reader.fieldnames
for i, part in enumerate(parts, 1):
    out = f"weibo_posts_part{i}.csv"
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(part)
    cmin = parse_count(part[-1]['comment_count'])
    cmax = parse_count(part[0]['comment_count'])
    print(f"{out}: {len(part):>5} rows, comment_count range {cmin:>6} ~ {cmax:>6}")

print(f"\nDone. Total: {total} rows split into 5 files.")
