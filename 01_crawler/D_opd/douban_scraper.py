"""
豆瓣帖子 + 评论抓取
数据来源: 豆瓣小组API
目标小组: 鹅组/踩组等娱乐小组
"""

import requests
import csv
import time
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.douban.com/',
    'Cookie': '',  # 需填入豆瓣登录Cookie
}

# 11个相关帖子的URL（从最终数据中提取）
TARGET_POSTS = [
    'https://www.douban.com/group/topic/332429416/',  # 鹅组er如何看待年轮事件
    'https://www.douban.com/group/topic/332012723/',  # 年轮这事本身双方没沟通好
    'https://www.douban.com/group/topic/332025012/',  # 我好像有点捋清楚了年轮整个事的始末
    'https://www.douban.com/group/topic/332007512/',  # 关于汪苏泷张碧晨年轮原唱之争时间线
    'https://www.douban.com/group/topic/482528824/',  # 张碧晨和汪苏泷谁是年轮原唱
    'https://www.douban.com/group/topic/332196065/',  # 张碧晨唱年轮的时候多次感谢过汪苏泷
    'https://www.douban.com/group/topic/331994809/',  # 为了防止岁月史书
    'https://www.douban.com/group/topic/332045242/',  # 张碧晨演唱会邀请原唱薛凯琪
    'https://www.douban.com/group/topic/331999725/',  # 请大家看看汪苏泷回收年轮版权
    'https://www.douban.com/group/topic/331995081/',  # 为什么不能两个人都是原唱
    'https://www.douban.com/group/topic/332391295/',  # 盘了盘张碧晨汪苏泷这件事
]

OUTPUT_FILE = 'D_data/douban_all_comments.csv'
CRAWL_TIME = '2026-05-29 15:46:48'


def get_topic_detail(topic_id):
    """获取帖子详情"""
    url = f'https://m.douban.com/rexxar/api/v2/group/topic/{topic_id}'
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return {}
    data = resp.json()
    return {
        'title': data.get('title', ''),
        'author': data.get('author', {}).get('name', ''),
        'create_time': data.get('create_time', ''),
        'like_count': data.get('likes_count', 0),
        'collect_count': data.get('collections_count', 0),
    }


def get_topic_comments(topic_id, start=0, count=20):
    """获取帖子评论列表"""
    url = f'https://m.douban.com/rexxar/api/v2/group/topic/{topic_id}/comments'
    params = {'start': start, 'count': count, 'sort': 'hot'}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    if resp.status_code != 200:
        return [], 0
    data = resp.json()
    comments = data.get('comments', [])
    total = data.get('total', 0)
    return comments, total


def clean_comment_text(text):
    """清洗评论文本"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return text.strip()


def extract_post_id(url):
    """从URL提取帖子ID"""
    match = re.search(r'topic/(\d+)', url)
    return match.group(1) if match else ''


def main():
    all_comments = []

    for post_url in TARGET_POSTS:
        post_id = extract_post_id(post_url)
        print(f"处理帖子: {post_id}")

        # 获取帖子详情
        detail = get_topic_detail(post_id)
        post_title = detail.get('title', '')
        post_author = detail.get('author', '')
        post_time = detail.get('create_time', '')
        post_likes = detail.get('like_count', 0)
        post_collects = detail.get('collect_count', 0)

        if not post_title:
            print(f"  跳过: 无法获取帖子信息")
            continue

        # 获取所有评论
        start = 0
        while True:
            try:
                comments, total = get_topic_comments(post_id, start=start, count=50)
                if not comments:
                    break

                for c in comments:
                    all_comments.append({
                        'platform': '豆瓣',
                        'source_post_id': post_id,
                        'source_post_url': post_url,
                        'post_title': post_title,
                        'post_author': post_author,
                        'post_time': post_time,
                        'post_content_summary': '',  # 帖子摘要
                        'post_like_count': post_likes,
                        'post_collect_count': post_collects,
                        'comment_user': c.get('author', {}).get('name', '匿名'),
                        'comment_time': c.get('create_time', ''),
                        'comment_text': clean_comment_text(c.get('text', '')),
                        'crawl_time': CRAWL_TIME,
                    })

                print(f"  已获取 {len(all_comments)} 条评论 (本页{len(comments)}条)")
                start += len(comments)
                time.sleep(1)

                if start >= total:
                    break
            except Exception as e:
                print(f"  错误: {e}")
                break

        time.sleep(2)

    # 写入CSV
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'platform', 'source_post_id', 'source_post_url', 'post_title',
            'post_author', 'post_time', 'post_content_summary',
            'post_like_count', 'post_collect_count', 'comment_user',
            'comment_time', 'comment_text', 'crawl_time'
        ])
        writer.writeheader()
        writer.writerows(all_comments)

    print(f"\n完成: {len(all_comments)} 条豆瓣评论 → {OUTPUT_FILE}")


if __name__ == '__main__':
    print("注意: 豆瓣API需要有效的登录Cookie")
    main()
