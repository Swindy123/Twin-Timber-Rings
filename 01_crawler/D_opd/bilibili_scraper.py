"""
B站视频 + 热门评论抓取
数据来源: B站搜索API + 评论区API
搜索关键词: 年轮 原唱 版权 汪苏泷 张碧晨
"""

import requests
import csv
import time
import re
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com/',
}

SEARCH_KEYWORDS = [
    '年轮 汪苏泷 张碧晨',
    '年轮 原唱之争',
    '年轮 版权',
    '汪苏泷 年轮',
    '张碧晨 年轮',
]

OUTPUT_FILE = 'D_data/bilibili_cases.csv'
CRAWL_TIME = '2026-05-29 17:06:47'

def search_videos(keyword, page=1, page_size=20):
    """通过B站搜索API获取视频列表"""
    url = 'https://api.bilibili.com/x/web-interface/search/type'
    params = {
        'keyword': keyword,
        'search_type': 'video',
        'page': page,
        'page_size': page_size,
        'order': 'click',  # 按播放量排序
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    data = resp.json()
    if data['code'] != 0:
        return []
    return data['data']['result']


def get_video_detail(aid, bvid):
    """获取视频详细信息（播放量/弹幕/评论）"""
    url = 'https://api.bilibili.com/x/web-interface/view'
    params = {'aid': aid, 'bvid': bvid}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    data = resp.json()
    if data['code'] != 0:
        return {}
    stat = data['data']['stat']
    return {
        'play_count': stat.get('view', 0),
        'danmu_count': stat.get('danmaku', 0),
        'reply_count': stat.get('reply', 0),
    }


def get_hot_comments(oid, count=5):
    """获取视频热门评论"""
    url = 'https://api.bilibili.com/x/v2/reply/main'
    params = {'oid': oid, 'type': 1, 'mode': 3, 'ps': count}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    data = resp.json()
    if data['code'] != 0:
        return []
    comments = []
    for reply in data['data'].get('replies', [])[:count]:
        username = reply['member']['uname']
        content = reply['content']['message'].replace('\n', ' ')
        likes = reply.get('like', 0)
        comments.append(f"{username}: {content} ({likes}赞)")
    return comments


def main():
    all_videos = []
    seen_aids = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"搜索: {keyword}")
        for page in range(1, 6):  # 每个关键词搜5页
            try:
                results = search_videos(keyword, page=page)
                for item in results:
                    aid = item.get('aid')
                    if aid in seen_aids:
                        continue
                    seen_aids.add(aid)

                    bvid = item.get('bvid', '')
                    title = item.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
                    author = item.get('author', '')
                    pubdate = datetime.fromtimestamp(item.get('pubdate', 0)).strftime('%Y-%m-%d')

                    # 过滤无关视频
                    if not any(kw in title for kw in ['年轮', '原唱', '版权', '汪苏泷', '张碧晨']):
                        continue

                    print(f"  获取: {title[:50]}...")
                    detail = get_video_detail(aid, bvid)
                    hot_comments = get_hot_comments(aid)

                    video = {
                        'platform': 'B站',
                        'video_title': title,
                        'up_author': author,
                        'play_count': detail.get('play_count', ''),
                        'danmu_count': detail.get('danmu_count', ''),
                        'reply_count': detail.get('reply_count', ''),
                        'publish_time': pubdate,
                        'hot_comment_1': hot_comments[0] if len(hot_comments) > 0 else '',
                        'hot_comment_2': hot_comments[1] if len(hot_comments) > 1 else '',
                        'hot_comment_3': hot_comments[2] if len(hot_comments) > 2 else '',
                        'hot_comment_4': hot_comments[3] if len(hot_comments) > 3 else '',
                        'hot_comment_5': hot_comments[4] if len(hot_comments) > 4 else '',
                        'crawl_time': CRAWL_TIME,
                    }
                    all_videos.append(video)
                    time.sleep(0.5)  # 请求间隔
            except Exception as e:
                print(f"  错误: {e}")
                continue
        time.sleep(1)

    # 写入CSV
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'platform', 'video_title', 'up_author', 'play_count',
            'danmu_count', 'reply_count', 'publish_time',
            'hot_comment_1', 'hot_comment_2', 'hot_comment_3',
            'hot_comment_4', 'hot_comment_5', 'crawl_time'
        ])
        writer.writeheader()
        writer.writerows(all_videos)

    print(f"\n完成: {len(all_videos)} 条B站视频数据 → {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
