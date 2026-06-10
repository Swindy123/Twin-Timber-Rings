"""
知乎回答 + 评论抓取
数据来源: 知乎搜索API + 回答评论API
搜索关键词: 年轮 原唱 版权 汪苏泷 张碧晨
"""

import requests
import csv
import time
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.zhihu.com/',
    'Authorization': '',  # 需填入知乎登录Token
}

SEARCH_KEYWORDS = [
    '年轮 原唱 汪苏泷 张碧晨',
    '年轮 版权之争',
    '汪苏泷 年轮 收回',
    '张碧晨 年轮 原唱',
]

OUTPUT_CASES = 'D_data/zhihu_cases.csv'
OUTPUT_COMMENTS = 'D_data/zhihu_all_comments.csv'
CRAWL_TIME = '2026-05-29 17:43:30'


def search_answers(keyword, offset=0, limit=20):
    """通过知乎搜索API获取回答列表"""
    url = 'https://www.zhihu.com/api/v4/search_v3'
    params = {
        'q': keyword,
        'type': 'answer',
        'offset': offset,
        'limit': limit,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    data = resp.json()
    return data.get('data', [])


def get_answer_detail(answer_id):
    """获取回答详细信息"""
    url = f'https://www.zhihu.com/api/v4/answers/{answer_id}'
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return {}
    data = resp.json()
    return {
        'question_title': data.get('question', {}).get('title', ''),
        'author': data.get('author', {}).get('name', '匿名'),
        'upvote_count': data.get('voteup_count', 0),
        'comment_count': data.get('comment_count', 0),
        'created_time': data.get('created_time', 0),
        'excerpt': data.get('excerpt', ''),
    }


def get_answer_comments(answer_id, page=1):
    """获取回答的评论"""
    url = f'https://www.zhihu.com/api/v4/answers/{answer_id}/comments'
    params = {
        'page': page,
        'limit': 20,
        'order': 'score',  # 按热度排序
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    if resp.status_code != 200:
        return [], {}
    data = resp.json()
    comments = data.get('data', [])
    paging = data.get('paging', {})
    return comments, paging


def clean_text(text):
    """清洗文本"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()


def main():
    all_answers = []
    all_comments = []
    seen_answer_ids = set()
    answer_id_counter = {}  # answer_id -> auto-generated question_title mapping

    for keyword in SEARCH_KEYWORDS:
        print(f"搜索: {keyword}")
        for offset in range(0, 100, 20):  # 最多100条结果
            try:
                results = search_answers(keyword, offset=offset)
                for item in results:
                    obj = item.get('object', {})
                    answer_id = str(obj.get('id', ''))
                    if not answer_id or answer_id in seen_answer_ids:
                        continue
                    seen_answer_ids.add(answer_id)

                    # 获取回答详情
                    detail = get_answer_detail(answer_id)
                    question_title = detail.get('question_title', '')
                    author = detail.get('author', '')
                    upvote = detail.get('upvote_count', 0)
                    comment_count = detail.get('comment_count', 0)
                    excerpt = detail.get('excerpt', '')

                    if not question_title:
                        continue

                    # 过滤无关回答
                    if not any(kw in question_title for kw in ['年轮', '原唱', '版权', '汪苏泷', '张碧晨']):
                        continue

                    print(f"  回答: {question_title[:50]}... by {author}")
                    timestamp = detail.get('created_time', 0)
                    pub_date = time.strftime('%Y-%m-%d', time.localtime(timestamp)) if timestamp else ''

                    all_answers.append({
                        'platform': '知乎',
                        'question_title': question_title,
                        'answer_author': author,
                        'upvote_count': upvote,
                        'comment_count': comment_count,
                        'publish_date': pub_date,
                        'answer_summary': clean_text(excerpt)[:300],
                        'stance': '',
                        'crawl_time': CRAWL_TIME,
                    })

                    # 获取评论
                    page = 1
                    while True:
                        comments, paging = get_answer_comments(answer_id, page=page)
                        if not comments:
                            break
                        for c in comments:
                            all_comments.append({
                                'platform': '知乎',
                                'answer_id': answer_id,
                                'question_title': question_title,
                                'comment_user': c.get('author', {}).get('name', '匿名'),
                                'comment_text': clean_text(c.get('content', '')),
                                'comment_likes': c.get('vote_count', 0),
                                'comment_time': time.strftime('%Y-%m-%d', time.localtime(c.get('created_time', 0))),
                                'crawl_time': CRAWL_TIME,
                            })
                        if paging.get('is_end', True):
                            break
                        page += 1
                        time.sleep(0.5)

                    time.sleep(1)
            except Exception as e:
                print(f"  错误: {e}")
                continue
        time.sleep(2)

    # 写入回答CSV
    with open(OUTPUT_CASES, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'platform', 'question_title', 'answer_author', 'upvote_count',
            'comment_count', 'publish_date', 'answer_summary', 'stance', 'crawl_time'
        ])
        writer.writeheader()
        writer.writerows(all_answers)

    # 写入评论CSV
    with open(OUTPUT_COMMENTS, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'platform', 'answer_id', 'question_title', 'comment_user',
            'comment_text', 'comment_likes', 'comment_time', 'crawl_time'
        ])
        writer.writeheader()
        writer.writerows(all_comments)

    print(f"\n完成: {len(all_answers)} 条知乎回答 → {OUTPUT_CASES}")
    print(f"完成: {len(all_comments)} 条知乎评论 → {OUTPUT_COMMENTS}")


if __name__ == '__main__':
    print("注意: 知乎API需要有效的Authorization Token")
    main()
