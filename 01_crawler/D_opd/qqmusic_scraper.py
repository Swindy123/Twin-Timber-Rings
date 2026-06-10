"""
QQ音乐评论区抓取
数据来源: QQ音乐JSONP接口
歌曲: 年轮（张碧晨版 + 汪苏泷版）
"""

import requests
import csv
import time
import re
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://y.qq.com/',
}

# 年轮 - 张碧晨版 和 汪苏泷版 的歌曲ID
SONG_IDS = {
    '张碧晨版': '102433352',   # 张碧晨 - 年轮
    '汪苏泷版': '107762076',   # 汪苏泷 - 年轮
}

OUTPUT_FILE = 'D_data/qqmusic_comments.csv'
CRAWL_TIME = '2026-05-29 17:59:37'


def get_comments(song_id, page=1, page_size=25):
    """通过QQ音乐JSONP接口获取评论"""
    url = 'https://c.y.qq.com/base/fcgi-bin/fcg_global_comment_h5.fcg'
    params = {
        'g_tk': '5381',
        'loginUin': '0',
        'hostUin': '0',
        'format': 'json',
        'inCharset': 'utf-8',
        'outCharset': 'utf-8',
        'notice': '0',
        'platform': 'yqq.json',
        'needNewCode': '0',
        'cid': '205360772',
        'reqtype': '2',
        'biztype': '1',
        'topid': song_id,
        'cmd': '8',
        'pagenum': page,
        'pagesize': page_size,
        'lasthotcommentid': '',
        'domain': 'qq.com',
        'ct': '24',
        'cv': '10101010',
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    data = resp.json()
    if data.get('code') != 0:
        return [], 0
    comments = data.get('comment', {}).get('commentlist', [])
    total = data.get('comment', {}).get('total', 0)
    return comments, total


def clean_comment(text):
    """清洗评论文本"""
    if not text:
        return ''
    text = re.sub(r'\[em\](.*?)\[/em\]', r'\1', text)
    text = text.replace('\n', ' | ').strip()
    return text


def main():
    all_comments = []

    for version, song_id in SONG_IDS.items():
        print(f"抓取: {version} (ID: {song_id})")
        page = 0
        while True:
            try:
                comments, total = get_comments(song_id, page=page)
                if not comments:
                    break

                for c in comments:
                    text = clean_comment(c.get('rootcommentcontent', ''))
                    if not text:
                        continue

                    all_comments.append({
                        'platform': 'QQ音乐',
                        'song_version': version,
                        'comment_user': c.get('nick', '匿名'),
                        'comment_text': text,
                        'comment_likes': c.get('praisenum', 0),
                        'comment_time': c.get('time', ''),
                        'crawl_time': CRAWL_TIME,
                    })

                print(f"  已获取 {len(all_comments)} 条评论")
                page += 1
                time.sleep(0.8)

                # API限制，最多获取约250条/版本
                if page >= 10:
                    break
            except Exception as e:
                print(f"  错误: {e}")
                break

    # 写入CSV
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'platform', 'song_version', 'comment_user', 'comment_text',
            'comment_likes', 'comment_time', 'crawl_time'
        ])
        writer.writeheader()
        writer.writerows(all_comments)

    print(f"\n完成: {len(all_comments)} 条QQ音乐评论 → {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
