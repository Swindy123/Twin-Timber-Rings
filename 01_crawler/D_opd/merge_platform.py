"""
跨平台数据合并脚本
将 B站/抖音/豆瓣/知乎 的原始数据合并为统一的 platform_cases.csv
"""

import csv
import re
from datetime import datetime

INPUT_FILES = {
    'B站': 'D_data/bilibili_cases.csv',
    '抖音': 'D_data/douyin_cases.csv',
    '豆瓣': 'D_data/douban_all_comments.csv',
    '知乎': 'D_data/zhihu_cases.csv',
}

OUTPUT_FILE = 'D_data/platform_cases.csv'
CRAWL_TIME = '2026-05-29 17:43:43'


def read_csv(filepath):
    """安全读取CSV（处理BOM）"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def clean(val):
    return str(val).strip() if val else ''


def merge_bilibili(rows):
    """B站数据 → 统一格式"""
    result = []
    for r in rows:
        result.append({
            'platform': 'B站',
            'video_title': clean(r.get('video_title', '')),
            'author': clean(r.get('up_author', '')),
            'play_count': clean(r.get('play_count', '')),
            'like_count': '',  # B站API未提供点赞数
            'reply_count': clean(r.get('reply_count', '')),
            'danmu_count': clean(r.get('danmu_count', '')),
            'publish_date': clean(r.get('publish_time', '')),
            'video_type': '',    # 待标注
            'stance': '',        # 待标注
            'main_viewpoint': '', # 待标注
            'hot_comment_1': clean(r.get('hot_comment_1', '')),
            'hot_comment_2': clean(r.get('hot_comment_2', '')),
            'hot_comment_3': clean(r.get('hot_comment_3', '')),
            'hot_comment_4': clean(r.get('hot_comment_4', '')),
            'hot_comment_5': clean(r.get('hot_comment_5', '')),
            'crawl_time': CRAWL_TIME,
        })
    return result


def merge_douyin(rows):
    """抖音数据 → 统一格式"""
    result = []
    for r in rows:
        result.append({
            'platform': '抖音',
            'video_title': clean(r.get('video_title', '')),
            'author': clean(r.get('author', '')),
            'play_count': '',    # 抖音未提供播放量
            'like_count': clean(r.get('estimated_like', '')),
            'reply_count': '',   # 抖音未提供评论数
            'danmu_count': '',   # 抖音无弹幕
            'publish_date': clean(r.get('publish_date', '')),
            'video_type': '',
            'stance': '',
            'main_viewpoint': '',
            'hot_comment_1': clean(r.get('hot_comment_1', '')),
            'hot_comment_2': clean(r.get('hot_comment_2', '')),
            'hot_comment_3': clean(r.get('hot_comment_3', '')),
            'hot_comment_4': clean(r.get('hot_comment_4', '')),
            'hot_comment_5': clean(r.get('hot_comment_5', '')),
            'crawl_time': CRAWL_TIME,
        })
    return result


def merge_douban(rows):
    """豆瓣评论 → 按帖子聚合为统一格式（每帖一行，取前5条热评）"""
    posts = {}
    for r in rows:
        pid = clean(r.get('source_post_id', ''))
        if pid not in posts:
            posts[pid] = {
                'platform': '豆瓣',
                'video_title': clean(r.get('post_title', '')),
                'author': clean(r.get('post_author', '')),
                'play_count': '',
                'like_count': clean(r.get('post_like_count', '')),
                'reply_count': clean(r.get('post_collect_count', '')),
                'danmu_count': '',
                'publish_date': clean(r.get('post_time', '')),
                'video_type': '',
                'stance': '',
                'main_viewpoint': '',
                'hot_comments': [],
                'crawl_time': CRAWL_TIME,
            }
        comment_text = f"{clean(r.get('comment_user', ''))}: {clean(r.get('comment_text', ''))}"
        posts[pid]['hot_comments'].append(comment_text)

    result = []
    for pid, post in posts.items():
        row = dict(post)
        for i in range(5):
            row[f'hot_comment_{i+1}'] = post['hot_comments'][i] if i < len(post['hot_comments']) else ''
        del row['hot_comments']
        result.append(row)
    return result


def merge_zhihu(rows):
    """知乎回答 → 统一格式"""
    result = []
    for r in rows:
        result.append({
            'platform': '知乎',
            'video_title': clean(r.get('question_title', '')),
            'author': clean(r.get('answer_author', '')),
            'play_count': '',     # 知乎无播放量
            'like_count': clean(r.get('upvote_count', '')),
            'reply_count': clean(r.get('comment_count', '')),
            'danmu_count': '',    # 知乎无弹幕
            'publish_date': clean(r.get('publish_date', '')),
            'video_type': '',
            'stance': '',
            'main_viewpoint': clean(r.get('answer_summary', '')),
            'hot_comment_1': '',  # 知乎无热评字段
            'hot_comment_2': '',
            'hot_comment_3': '',
            'hot_comment_4': '',
            'hot_comment_5': '',
            'crawl_time': CRAWL_TIME,
        })
    return result


def main():
    all_rows = []

    # B站
    print("合并B站数据...")
    bili = read_csv(INPUT_FILES['B站'])
    all_rows.extend(merge_bilibili(bili))
    print(f"  B站: {len(bili)} 条")

    # 抖音
    print("合并抖音数据...")
    douyin = read_csv(INPUT_FILES['抖音'])
    all_rows.extend(merge_douyin(douyin))
    print(f"  抖音: {len(douyin)} 条")

    # 豆瓣（按帖子聚合）
    print("合并豆瓣数据...")
    douban = read_csv(INPUT_FILES['豆瓣'])
    douban_rows = merge_douban(douban)
    all_rows.extend(douban_rows)
    print(f"  豆瓣: {len(douban)} 条评论 → {len(douban_rows)} 个帖子")

    # 知乎
    print("合并知乎数据...")
    zhihu = read_csv(INPUT_FILES['知乎'])
    all_rows.extend(merge_zhihu(zhihu))
    print(f"  知乎: {len(zhihu)} 条")

    # 写入统一格式
    fieldnames = [
        'platform', 'video_title', 'author', 'play_count', 'like_count',
        'reply_count', 'danmu_count', 'publish_date', 'video_type',
        'stance', 'main_viewpoint', 'hot_comment_1', 'hot_comment_2',
        'hot_comment_3', 'hot_comment_4', 'hot_comment_5', 'crawl_time'
    ]

    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n完成: {len(all_rows)} 条跨平台数据 → {OUTPUT_FILE}")

    # 统计
    from collections import Counter
    platform_counts = Counter(r['platform'] for r in all_rows)
    for platform, count in platform_counts.items():
        print(f"  {platform}: {count}")


if __name__ == '__main__':
    main()
