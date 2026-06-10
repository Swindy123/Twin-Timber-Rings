"""
抖音视频 + 热门评论抓取
数据来源: 抖音搜索页面滚动提取 + 评论接口
搜索关键词: 年轮 原唱 版权 汪苏泷 张碧晨
"""

import requests
import csv
import time
import re
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.douyin.com/',
    'Cookie': '',  # 需填入抖音登录Cookie
}

SEARCH_KEYWORDS = [
    '年轮 原唱',
    '汪苏泷 年轮',
    '张碧晨 年轮',
    '年轮 版权之争',
]

OUTPUT_FILE = 'D_data/douyin_cases.csv'
CRAWL_TIME = '2026-05-29 17:06:47'


def search_aweme(keyword, cursor=0, count=20):
    """通过抖音搜索接口获取视频列表（需Cookie）"""
    url = 'https://www.douyin.com/aweme/v1/web/search/item/'
    params = {
        'keyword': keyword,
        'cursor': cursor,
        'count': count,
        'search_source': 'normal_search',
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    data = resp.json()
    if data.get('status_code') != 0:
        return [], 0
    aweme_list = data.get('aweme_list', [])
    has_more = data.get('has_more', 0)
    next_cursor = data.get('cursor', 0)
    return aweme_list, next_cursor


def get_video_comments(aweme_id, count=5):
    """获取抖音视频热门评论"""
    url = 'https://www.douyin.com/aweme/v1/web/comment/list/'
    params = {'aweme_id': aweme_id, 'cursor': 0, 'count': count}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    data = resp.json()
    comments = []
    for item in data.get('comments', [])[:count]:
        user = item['user']['nickname']
        text = item['text'].replace('\n', ' ')
        likes = item.get('digg_count', 0)
        likes_str = f"{likes/10000:.1f}万赞" if likes >= 10000 else f"{likes}赞"
        comments.append(f"{user}: {text} ({likes_str})")
    return comments


def extract_like_count(aweme):
    """提取点赞数（抖音页面为估计值）"""
    stat = aweme.get('statistics', {})
    return stat.get('digg_count', stat.get('admire_count', 0))


def main():
    all_videos = []
    seen_ids = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"搜索: {keyword}")
        cursor = 0
        for _ in range(10):  # 最多翻10页
            try:
                items, cursor = search_aweme(keyword, cursor=cursor)
                if not items:
                    break

                for aweme in items:
                    aweme_id = aweme.get('aweme_id')
                    if aweme_id in seen_ids:
                        continue
                    seen_ids.add(aweme_id)

                    desc = aweme.get('desc', '')[:200]
                    author = aweme.get('author', {}).get('nickname', '')
                    create_time = aweme.get('create_time', 0)
                    pub_date = time.strftime('%Y-%m-%d', time.localtime(create_time))

                    # 过滤无关内容
                    if not any(kw in desc for kw in ['年轮', '原唱', '版权', '汪苏泷', '张碧晨']):
                        continue

                    print(f"  获取: {desc[:50]}...")
                    like_count = extract_like_count(aweme)
                    hot_comments = get_video_comments(aweme_id)

                    video = {
                        'platform': '抖音',
                        'video_title': desc,
                        'author': author,
                        'estimated_like': like_count,
                        'publish_date': pub_date,
                        'hot_comment_1': hot_comments[0] if len(hot_comments) > 0 else '',
                        'hot_comment_2': hot_comments[1] if len(hot_comments) > 1 else '',
                        'hot_comment_3': hot_comments[2] if len(hot_comments) > 2 else '',
                        'hot_comment_4': hot_comments[3] if len(hot_comments) > 3 else '',
                        'hot_comment_5': hot_comments[4] if len(hot_comments) > 4 else '',
                        'crawl_time': CRAWL_TIME,
                    }
                    all_videos.append(video)
                    time.sleep(1)
            except Exception as e:
                print(f"  错误: {e}")
                continue
            if cursor == 0:
                break
        time.sleep(2)

    # 写入CSV
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'platform', 'video_title', 'author', 'estimated_like',
            'publish_date', 'hot_comment_1', 'hot_comment_2',
            'hot_comment_3', 'hot_comment_4', 'hot_comment_5', 'crawl_time'
        ])
        writer.writeheader()
        writer.writerows(all_videos)

    print(f"\n完成: {len(all_videos)} 条抖音视频数据 → {OUTPUT_FILE}")


if __name__ == '__main__':
    print("注意: 抖音接口需要有效的Cookie才能运行")
    print("Cookie获取方式: 浏览器登录抖音后，F12 → Application → Cookies 复制")
    main()
