"""
微博用户身份分类器 v3
====================
基于 final_predicted_data(1).csv，将 author_type 细化为五类群体。

五类群体：张碧晨粉丝, 张方水军, 汪苏泷粉丝, 汪方水军, 路人

用法：
  python weibo_user_identity.py                  # 一键全跑（无Cookie则只跑Phase 1）
  python weibo_user_identity.py phase1           # 只跑 Phase 1: 文本+行为分类
  python weibo_user_identity.py phase2           # 只跑 Phase 2: 主页精细化
  python weibo_user_identity.py phase2 --water   # Phase 2: 低置信度 + 水军全验
  python weibo_user_identity.py <csv路径>        # 指定输入文件

设好 COOKIE 后直接跑就是全流程，无需额外参数。

输入：final_predicted_data(1).csv (需含 userid, predicted_stance, text, author_type)
Phase 1 依赖：仅 Python 标准库
Phase 2 依赖：pip install requests + 微博 Cookie
"""

import csv
import json
import os
import re
import sys
import time
import random
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

# ============================================================
# 配置
# ============================================================

# 微博 Cookie（Phase 2 需要，从浏览器 F12 → Network → 任意请求 → Cookie 复制整行）
# 注意：Cookie 几小时就过期，跑之前重新获取
COOKIE = "SCF=AnxgqmVkfaPzZi6iCJny25txl5fQwOWwHkyDl2wWDr5FL7UMpu5sP7fpD4CtigBKFuqJOFFdnqpKokuJ5CD1MK0.; XSRF-TOKEN=Kn-RdJ43nVZBq7rZ64N_2F9J; ariaDefaultTheme=default; ariaFixed=true; ariaReadtype=1; ariaMouseten=null; ariaStatus=false; SUB=_2A25HIDeaDeRhGeFH6lsZ-S7Pwz6IHXVkXDVSrDV8PUNbmtAYLUHekW9Ne9Dzp5rOqU126lR-YXfUCqSp58gmiy08; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WF.-6C5Z2OlSWDNxv3amvVi5JpX5KzhUgL.FoM4eK.R1K501hz2dJLoI0YLxKqLB-eLBK2LxK-L1h-L1heLxKMLB.zL1KeLxKMLBKBLB.-LxK-LB--L1KnLxKqL1KqLBo.LxK-L12LqBoMt; ALF=02_1783354570; WBPSESS=S5KnxENDUbmf6mSXSHVQQtr2t0N1bdLbD21Po7Bs9frkVer17DQQbvXwTtqIsO0fZGSP_dLQd2y472hNo23iGXJnFT6M4KYXhBx4KDEefjGR1iaM7r_8vAH0scd7Xtotb_I0DnmXY4K2Z6W322g--A=="

# 爬虫设置
MIN_DELAY = 3.0
MAX_DELAY = 8.0
MAX_RETRIES = 3
BATCH_SIZE = 50
BATCH_REST = 120

# ============================================================
# 工具函数
# ============================================================

def find_input_csv():
    """自动查找输入文件：当前目录 → 脚本上级目录 → 脚本同级"""
    candidates = [
        Path.cwd() / "final_predicted_data(1).csv",
        Path(__file__).parent.parent / "final_predicted_data(1).csv",
        Path(__file__).parent / "final_predicted_data(1).csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


OUTPUT_DIR = Path(__file__).parent / "crawler_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_str(s, max_len=50):
    """过滤表情/emoji/特殊符号，只留中英文数字标点"""
    if s is None:
        return '(空)'
    s = str(s)
    # 只保留: 中文(一-鿿), ASCII可打印, 中文标点, 空格
    result = []
    for ch in s:
        cp = ord(ch)
        if (0x4e00 <= cp <= 0x9fff or     # 中文
            0x20 <= cp <= 0x7e or          # ASCII可打印
            cp in (0x3001, 0x3002, 0xff0c, 0xff0e, 0xff01, 0xff1f, 0xff1a, 0xff1b, 0x2018, 0x2019, 0x201c, 0x201d, 0x300a, 0x300b, 0x3010, 0x3011, 0xff08, 0xff09, 0x2014, 0x2026, 0x00b7)):
            result.append(ch)
    cleaned = ''.join(result).strip()
    if not cleaned:
        return '(空)'
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + '...'
    return cleaned


def load_csv(filepath):
    """加载CSV，自动检测分隔符"""
    rows = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        first_line = f.readline()
        f.seek(0)
        delimiter = '\t' if '\t' in first_line else ','
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(filepath, rows, fieldnames):
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(text, max_len=150):
    """去URL、@、话题干扰，用于模板匹配"""
    t = text.strip()
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'@\S+', '', t)
    t = re.sub(r'#\S+#', ' # ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:max_len]


# ============================================================
# Phase 1: 用户聚合
# ============================================================

def aggregate_users(rows):
    """按 userid 聚合，每用户汇总其所有帖子"""
    users = defaultdict(lambda: {
        'userid': '', 'author_name': '', 'author_type_orig': '',
        'texts': [], 'stances': [], 'timestamps': [],
        'repost_counts': [], 'comment_counts': [], 'like_counts': [],
        'rows': [],
    })

    for row in rows:
        uid = row.get('userid', '').strip()
        if not uid:
            continue
        u = users[uid]
        u['userid'] = uid
        u['author_name'] = row.get('author_name', '').strip()
        u['author_type_orig'] = row.get('author_type', '').strip()

        text = row.get('text', '').strip()
        if text:
            u['texts'].append(text)

        stance = row.get('predicted_stance', '').strip()
        if stance:
            u['stances'].append(stance)

        ts = row.get('publish_time', '').strip()
        if ts:
            u['timestamps'].append(ts)

        try:
            u['repost_counts'].append(int(row.get('repost_count', 0) or 0))
            u['comment_counts'].append(int(row.get('comment_count', 0) or 0))
            u['like_counts'].append(int(row.get('like_count', 0) or 0))
        except ValueError:
            pass

        u['rows'].append(row)

    return dict(users)


def get_dominant_stance(stances):
    if not stances:
        return 'unclear'
    return Counter(stances).most_common(1)[0][0]


# ============================================================
# Phase 1: 跨用户模板检测
# ============================================================

def detect_templates(all_users, max_compare=300):
    """≥3人复制同一文本 → 模板簇。O(n log n)"""
    user_texts = []
    for uid, u in all_users.items():
        if u['texts']:
            raw = max(u['texts'], key=len)
            norm = normalize_text(raw)
            if len(norm) >= 15:
                user_texts.append((uid, norm, len(norm)))

    if len(user_texts) < 3:
        return set()

    user_texts.sort(key=lambda x: x[2])
    n = len(user_texts)
    parent = {item[0]: item[0] for item in user_texts}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    half = max_compare // 2
    compared = 0
    for i in range(n):
        uid_i, text_i, len_i = user_texts[i]
        j_end = min(n, i + half + 1)
        for j in range(i + 1, j_end):
            uid_j, text_j, len_j = user_texts[j]
            if len_i > 0 and len_j / len_i > 2.0:
                break
            sim = SequenceMatcher(None, text_i, text_j).ratio()
            compared += 1
            if sim >= 0.8:
                union(uid_i, uid_j)

    print(f"  模板检测: {n}文本, {compared}次比较")

    clusters = defaultdict(list)
    for item in user_texts:
        clusters[find(item[0])].append(item[0])

    template_users = set()
    for members in clusters.values():
        if len(members) >= 3:
            template_users.update(members)

    return template_users


# ============================================================
# Phase 1: 五类身份判断（核心逻辑）
# ============================================================

def classify_user(uid, user_data, template_users):
    """
    根据 predicted_stance + 昵称 + 文本 + 行为 + 模板 → 五类身份。
    返回: (author_type, confidence, evidence_list)
    """
    stance = get_dominant_stance(user_data['stances'])
    name = user_data['author_name']
    texts = user_data['texts']
    orig_type = user_data['author_type_orig']
    n_texts = len(texts)
    evidence = []

    # 媒体 / 官方/工作室 → 保留
    if orig_type in ['媒体', '官方/工作室']:
        return orig_type, 1.0, ['原始标注']

    # ================================================================
    # 信号1: 昵称粉丝检测
    # ================================================================
    name_zhang = 0
    name_wang = 0
    name_lower = name.lower()

    zhang_name_kw = ['晨曦', '钻石', '碧晨', '张碧晨', 'bichen', 'diamond']
    wang_name_kw = ['苏泷', '汪苏泷', 'silence', '小泷包', '泷包']

    for kw in zhang_name_kw:
        if kw.lower() in name_lower:
            name_zhang += 1
    for kw in wang_name_kw:
        if kw.lower() in name_lower:
            name_wang += 1

    if name_zhang > 0:
        evidence.append(f'昵称含张碧晨粉丝词({name_zhang}个)')
    if name_wang > 0:
        evidence.append(f'昵称含汪苏泷粉丝词({name_wang}个)')

    # ================================================================
    # 信号2: 文本粉丝语言（强信号+2分, 弱信号+1分）
    # ================================================================
    combined = ' '.join(texts)

    zhang_strong = [
        r'@张碧晨', r'#张碧晨[^#]*#', r'晨曦', r'钻石',
        r'张碧晨[^，。]{0,10}唯一原唱', r'唯一原唱.*张碧晨',
        r'张碧晨[^，。]{0,10}合法权益', r'张碧晨[^，。]{0,5}女士',
    ]
    zhang_weak = [
        r'十年.*年轮|年轮.*十年',
        r'张碧晨.*唱|唱.*张碧晨',
        r'(守护|心疼|永远|一直|青春).*张碧晨',
        r'张碧晨.*(守护|心疼|永远|一直|青春)',
        r'(凭什么|为什么.*张碧晨|这样对她)',
        r'(我们家|我家).*张碧晨|张碧晨.*(我们家|我家)',
        r'支持张碧晨',
        r'(原唱|演唱).*(赋予|生命力|情感|共鸣|意义)',
        r'(只听|一直听|从小听).*张碧晨.*年轮',
        r'(花千骨|OST).*张碧晨|张碧晨.*(花千骨|OST)',
    ]
    wang_strong = [
        r'@汪苏泷', r'#汪苏泷[^#]*#', r'小泷包',
        r'汪苏泷[^，。]{0,10}原创', r'汪苏泷[^，。]{0,10}词曲',
        r'汪苏泷[^，。]{0,10}作曲', r'版权[^，。]{0,10}汪苏泷',
        r'原创作者', r'词曲[^，。]{0,10}原创',
    ]
    wang_weak = [
        r'(创作|写出|写了).*(年轮|这首歌)',
        r'汪苏泷.*(写|创作|作曲|作词)',
        r'(守护|心疼|永远|一直).*汪苏泷',
        r'汪苏泷.*(守护|心疼|永远|一直)',
        r'支持汪苏泷',
        r'(收回|拿回).*(版权|授权|演唱权)',
        r'(版权|原创).*(重要|第一|优先)',
        r'(我们家|我家).*汪苏泷|汪苏泷.*(我们家|我家)',
    ]

    zhang_strong_hits = sum(1 for p in zhang_strong if re.search(p, combined))
    zhang_weak_hits = sum(1 for p in zhang_weak if re.search(p, combined))
    wang_strong_hits = sum(1 for p in wang_strong if re.search(p, combined))
    wang_weak_hits = sum(1 for p in wang_weak if re.search(p, combined))

    zhang_fan_score = name_zhang * 2 + zhang_strong_hits * 2 + zhang_weak_hits
    wang_fan_score = name_wang * 2 + wang_strong_hits * 2 + wang_weak_hits

    if n_texts >= 3 and stance == 'support_zhang':
        zhang_fan_score += 2
        evidence.append(f'{n_texts}条帖均支持张(+2粉丝分)')
    if n_texts >= 3 and stance == 'support_wang':
        wang_fan_score += 2
        evidence.append(f'{n_texts}条帖均支持汪(+2粉丝分)')

    if zhang_strong_hits > 0:
        evidence.append(f'张方强信号{zhang_strong_hits}个')
    if zhang_weak_hits > 0:
        evidence.append(f'张方弱信号{zhang_weak_hits}个')
    if wang_strong_hits > 0:
        evidence.append(f'汪方强信号{wang_strong_hits}个')
    if wang_weak_hits > 0:
        evidence.append(f'汪方弱信号{wang_weak_hits}个')

    # ================================================================
    # 信号3: 模板复制
    # ================================================================
    is_template = uid in template_users
    if is_template:
        evidence.append('跨用户模板复制(≥80%相似,≥3人)')

    # ================================================================
    # 信号4: 水军行为信号
    # ================================================================
    water_signals = 0

    if re.match(r'^用户\d+$', name):
        water_signals += 1
        evidence.append('默认昵称(用户+数字)')
    if re.search(r'[a-zA-Z]{2,}\d{6,}$', name):
        water_signals += 1
        evidence.append('低质随机昵称')
    if n_texts >= 5:
        water_signals += 1
        evidence.append(f'事件发帖{n_texts}条')
    total_engagement = (sum(user_data['repost_counts']) +
                       sum(user_data['comment_counts']) +
                       sum(user_data['like_counts']))
    if total_engagement == 0 and n_texts >= 2:
        water_signals += 1
        evidence.append(f'{n_texts}条帖零互动')
    if is_template:
        water_signals += 1

    # ================================================================
    # 决策：五类分群
    # 立场明确 → 默认粉丝，只有"1条帖+零粉丝信号"才降为路人
    # ================================================================

    is_water = is_template or (water_signals >= 2)

    if stance == 'support_zhang':
        if is_water:
            return '张方水军', 0.7, evidence
        elif zhang_fan_score == 0 and n_texts == 1:
            return '路人', 0.5, evidence + ['仅1条帖,无粉丝信号→路人(偏张)']
        else:
            conf = 0.8 if zhang_fan_score >= 3 else 0.6
            return '张碧晨粉丝', conf, evidence

    elif stance == 'support_wang':
        if is_water:
            return '汪方水军', 0.7, evidence
        elif wang_fan_score == 0 and n_texts == 1:
            return '路人', 0.5, evidence + ['仅1条帖,无粉丝信号→路人(偏汪)']
        else:
            conf = 0.8 if wang_fan_score >= 3 else 0.6
            return '汪苏泷粉丝', conf, evidence

    else:  # neutral, anti_fanwar, unclear → 默认路人
        if is_water and n_texts >= 2:
            if zhang_fan_score > wang_fan_score:
                return '张方水军', 0.4, evidence + ['无明确立场但张方信号+水军特征']
            elif wang_fan_score > zhang_fan_score:
                return '汪方水军', 0.4, evidence + ['无明确立场但汪方信号+水军特征']
            else:
                return '路人', 0.5, evidence + ['水军特征但无立场偏向→归为路人']

        if zhang_fan_score >= 3 and zhang_fan_score > wang_fan_score:
            return '张碧晨粉丝', 0.5, evidence + ['粉丝痕迹明显但立场为中立']
        if wang_fan_score >= 3 and wang_fan_score > zhang_fan_score:
            return '汪苏泷粉丝', 0.5, evidence + ['粉丝痕迹明显但立场为中立']

        return '路人', 0.6, evidence + ['无立场无粉丝痕迹']


# ============================================================
# Phase 2: 主页爬取 + 精细化
# ============================================================

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Cookie': COOKIE,
        'Referer': 'https://weibo.com/',
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest',
    }


def api_request(url, params=None, max_retries=MAX_RETRIES):
    """带重试和延迟的 API 请求"""
    import requests as req
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            resp = req.get(url, headers=get_headers(), params=params, timeout=15)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"  限流，等待 {wait}s...")
                time.sleep(wait)
            elif resp.status_code == 403:
                print(f"  403 Forbidden — Cookie 可能已过期")
                return None
            else:
                print(f"  HTTP {resp.status_code}, 重试 {attempt+1}/{max_retries}")
        except Exception as e:
            print(f"  请求异常: {e}, 重试 {attempt+1}/{max_retries}")
            time.sleep(5 * (attempt + 1))
    return None


def crawl_profile_info(uid):
    """爬取用户主页资料。API: /ajax/profile/info"""
    url = 'https://weibo.com/ajax/profile/info'
    resp = api_request(url, params={'uid': uid})
    if not resp:
        return None
    try:
        data = resp.json()
        user = data.get('data', {}).get('user', {})
        return {
            'screen_name': user.get('screen_name', ''),
            'description': user.get('description', '').strip(),
            'verified': user.get('verified', False),
            'verified_reason': user.get('verified_reason', ''),
            'gender': user.get('gender', ''),
            'location': user.get('location', ''),
            'followers_count': user.get('followers_count', 0),
            'friends_count': user.get('friends_count', 0),
            'statuses_count': user.get('statuses_count', 0),
            'created_at': user.get('created_at', ''),
            'mbrank': user.get('mbrank', 0),
            'mbtype': user.get('mbtype', 0),
            'profile_url': f'https://weibo.com/u/{uid}',
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  解析资料失败: {e}")
        return None


def crawl_recent_posts(uid, max_pages=3):
    """爬取用户最近帖子。API: /ajax/statuses/mymblog"""
    all_posts = []
    for page in range(1, max_pages + 1):
        url = 'https://weibo.com/ajax/statuses/mymblog'
        params = {'uid': uid, 'page': page, 'feature': 0, 'since_id': 0}
        resp = api_request(url, params=params)
        if not resp:
            break
        try:
            data = resp.json()
            posts = data.get('data', {}).get('list', [])
            if not posts:
                break
            for post in posts:
                all_posts.append({
                    'text': (post.get('text_raw') or post.get('text', '')).strip(),
                    'created_at': post.get('created_at', ''),
                    'reposts_count': post.get('reposts_count', 0),
                    'comments_count': post.get('comments_count', 0),
                    'attitudes_count': post.get('attitudes_count', 0),
                    'source': post.get('source', ''),
                })
            if len(posts) < 20:
                break
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  解析帖子失败(page={page}): {e}")
            break
    return all_posts


def refine_with_homepage(current_type, current_conf, current_evidence, profile, posts):
    """
    用主页数据修正 Phase 1 的分类。
    主要作用：区分"真人粉丝"和"组织号"；确认"路人"是否有隐藏粉丝身份。
    """
    if not profile:
        return current_type, current_conf, current_evidence

    evidence = list(current_evidence)
    bio = profile.get('description', '')
    followers = profile.get('followers_count', 0)
    friends = profile.get('friends_count', 0)
    statuses = profile.get('statuses_count', 0)
    verified = profile.get('verified', False)

    # --- 主页水军信号 ---
    hp_water = 0
    if followers < 50:
        hp_water += 1
    if followers > 0 and friends / followers > 10:
        hp_water += 1
    if 0 < statuses < 30:
        hp_water += 1
        evidence.append(f'主页总发帖仅{statuses}条(疑似小号)')
    if not verified:
        hp_water += 0.5

    # 帖子零互动
    if posts:
        total_eng = sum(p['reposts_count'] + p['comments_count'] + p['attitudes_count']
                       for p in posts[:10])
        if total_eng == 0 and len(posts) >= 5:
            hp_water += 1
            evidence.append('历史帖子零互动')

    # --- 主页粉丝信号 ---
    hp_zhang = 0
    hp_wang = 0
    if bio:
        # 最长匹配优先去重：短关键词如果是某个已命中长关键词的子串，不算分
        def dedup_bio_hits(kw_list, text):
            matched = [kw for kw in kw_list if kw in text]
            # 按长度降序排，后面短的如果是前面某个长的子串 → 剔除
            matched.sort(key=len, reverse=True)
            keep = []
            for kw in matched:
                if not any(kw in longer for longer in keep):
                    keep.append(kw)
            return len(keep)

        hp_zhang = dedup_bio_hits(['张碧晨', '晨曦', 'Bichen', '钻石', '碧晨'], bio)
        hp_wang = dedup_bio_hits(['汪苏泷', '苏泷', 'Silence', '小泷包'], bio)
        if hp_zhang > 0:
            evidence.append(f'Bio含张碧晨相关词({hp_zhang}个)')
        if hp_wang > 0:
            evidence.append(f'Bio含汪苏泷相关词({hp_wang}个)')

    if posts:
        all_post_text = ' '.join(p['text'] for p in posts[:50])
        # count() 会重复计子串，改用去重：先算各关键词出现次数，再减去"张碧晨→碧晨"的重叠
        zhang_counts = {kw: all_post_text.count(kw) for kw in ['张碧晨', '碧晨', '晨曦']}
        wang_counts = {kw: all_post_text.count(kw) for kw in ['汪苏泷', '苏泷']}
        # "张碧晨"每出现一次，"碧晨"就被多计一次 → 减去
        zhang_dedup = sum(zhang_counts.values()) - zhang_counts.get('张碧晨', 0)
        wang_dedup = sum(wang_counts.values()) - wang_counts.get('汪苏泷', 0)
        hp_zhang += zhang_dedup
        hp_wang += wang_dedup
        if hp_zhang > 0:
            evidence.append(f'历史帖子含张碧晨({hp_zhang}处,去重)')
        if hp_wang > 0:
            evidence.append(f'历史帖子含汪苏泷({hp_wang}处,去重)')

    # --- 修正决策 ---
    is_water = hp_water >= 2.0
    has_zhang_trace = hp_zhang > 0
    has_wang_trace = hp_wang > 0

    # 水军覆盖
    if is_water:
        if current_type in ['张碧晨粉丝', '路人'] and has_zhang_trace:
            return '张方水军', 0.7, evidence + [f'主页水军信号{hp_water}个 → 张方水军']
        elif current_type in ['汪苏泷粉丝', '路人'] and has_wang_trace:
            return '汪方水军', 0.7, evidence + [f'主页水军信号{hp_water}个 → 汪方水军']
        elif current_type == '张碧晨粉丝':
            return '张方水军', 0.6, evidence + [f'主页水军信号{hp_water}个']
        elif current_type == '汪苏泷粉丝':
            return '汪方水军', 0.6, evidence + [f'主页水军信号{hp_water}个']
        elif current_type == '路人':
            return current_type, current_conf, evidence + [f'主页水军信号{hp_water}个,但无立场偏向']

    # 路人 → 粉丝（主页发现粉丝痕迹）
    if current_type == '路人' and has_zhang_trace and not has_wang_trace:
        return '张碧晨粉丝', 0.6, evidence + ['主页发现张碧晨粉丝痕迹→修正为粉丝']
    if current_type == '路人' and has_wang_trace and not has_zhang_trace:
        return '汪苏泷粉丝', 0.6, evidence + ['主页发现汪苏泷粉丝痕迹→修正为粉丝']

    # 粉丝 → 路人（主页无粉丝痕迹 + 无水军特征）
    if current_type == '张碧晨粉丝' and not has_zhang_trace and not is_water:
        return '路人', 0.5, evidence + ['主页无张碧晨痕迹→修正为路人(偏张)']
    if current_type == '汪苏泷粉丝' and not has_wang_trace and not is_water:
        return '路人', 0.5, evidence + ['主页无汪苏泷痕迹→修正为路人(偏汪)']

    # 水军 → 粉丝（主页有明显粉丝身份 + 无水军特征）
    if current_type == '张方水军' and has_zhang_trace and not is_water:
        return '张碧晨粉丝', 0.6, evidence + ['主页有真实粉丝痕迹→修正为粉丝']
    if current_type == '汪方水军' and has_wang_trace and not is_water:
        return '汪苏泷粉丝', 0.6, evidence + ['主页有真实粉丝痕迹→修正为粉丝']

    # --- 主页证据推翻 Phase 1 错误标签 ---
    # 张方水军 + 主页只有汪痕迹(无张痕迹) → 汪苏泷粉丝
    if current_type == '张方水军' and has_wang_trace and not has_zhang_trace and not is_water:
        return '汪苏泷粉丝', 0.7, evidence + ['主页无张痕迹,有汪粉丝痕迹→Phase1标签被推翻']
    # 汪方水军 + 主页只有张痕迹(无汪痕迹) → 张碧晨粉丝
    if current_type == '汪方水军' and has_zhang_trace and not has_wang_trace and not is_water:
        return '张碧晨粉丝', 0.7, evidence + ['主页无汪痕迹,有张粉丝痕迹→Phase1标签被推翻']
    # 张方水军 + 汪痕迹(有水军特征) → 汪方水军
    if current_type == '张方水军' and has_wang_trace and not has_zhang_trace and is_water:
        return '汪方水军', 0.6, evidence + ['主页汪痕迹+水军特征→修正为汪方水军']
    # 汪方水军 + 张痕迹(有水军特征) → 张方水军
    if current_type == '汪方水军' and has_zhang_trace and not has_wang_trace and is_water:
        return '张方水军', 0.6, evidence + ['主页张痕迹+水军特征→修正为张方水军']

    return current_type, current_conf, evidence


# ============================================================
# Phase 1 主流程
# ============================================================

def run_phase1(input_csv):
    print("=" * 60)
    print("Phase 1: 文本+行为分类（无需Cookie）")
    print("=" * 60)

    # 1. 加载
    print(f"\n[1/5] 加载: {input_csv}")
    rows = load_csv(str(input_csv))
    print(f"  总行数: {len(rows)}")

    # 2. 聚合
    print("\n[2/5] 按 userid 聚合...")
    users = aggregate_users(rows)
    print(f"  唯一用户: {len(users)}")
    print(f"  发帖≥2条: {sum(1 for u in users.values() if len(u['texts']) >= 2)}")
    print(f"  媒体: {sum(1 for u in users.values() if u['author_type_orig'] == '媒体')}")
    print(f"  官方/工作室: {sum(1 for u in users.values() if u['author_type_orig'] == '官方/工作室')}")

    # 3. 模板检测
    print("\n[3/5] 跨用户模板检测...")
    template_users = detect_templates(users)
    print(f"  模板用户: {len(template_users)}")

    # 4. 分类
    print("\n[4/5] 五类身份分类...")
    results = {}
    for uid, u in users.items():
        atype, conf, ev = classify_user(uid, u, template_users)
        results[uid] = {'author_type': atype, 'confidence': conf, 'evidence': ev}

    # 5. 输出
    print("\n[5/5] 输出...")

    # 统计
    type_counts = Counter(r['author_type'] for r in results.values())
    print("\n  === 五类群体分布 ===")
    for t, c in type_counts.most_common():
        print(f"    {t}: {c} ({c/len(results)*100:.1f}%)")

    # 交叉统计
    print("\n  === stance × identity 交叉 ===")
    cross = defaultdict(Counter)
    for uid, r in results.items():
        stance = get_dominant_stance(users[uid]['stances'])
        cross[stance][r['author_type']] += 1
    for stance in ['support_zhang', 'support_wang', 'neutral', 'anti_fanwar']:
        idents = cross[stance]
        if idents:
            total = sum(idents.values())
            parts = ', '.join(f'{k}:{v}({v/total*100:.0f}%)' for k, v in idents.most_common())
            print(f"    {stance}({total}人) → {parts}")

    # 输出1: 每用户详情
    detail_file = OUTPUT_DIR / 'user_identity_v3.csv'
    with open(detail_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'userid', 'author_name', 'author_type', 'dominant_stance',
            'n_posts', 'confidence', 'evidence', 'needs_homepage'
        ])
        writer.writeheader()
        for uid, r in results.items():
            u = users[uid]
            needs_hp = 'Y' if r['confidence'] < 0.6 and r['author_type'] not in ['媒体', '官方/工作室'] else 'N'
            writer.writerow({
                'userid': uid, 'author_name': u['author_name'],
                'author_type': r['author_type'],
                'dominant_stance': get_dominant_stance(u['stances']),
                'n_posts': len(u['texts']), 'confidence': r['confidence'],
                'evidence': '; '.join(r['evidence']),
                'needs_homepage': needs_hp,
            })
    print(f"\n  用户详情 → {detail_file}")

    # 输出2: 原始格式 + author_type 细化
    enriched_file = input_csv.parent / 'final_predicted_data_enriched.csv'
    identity_map = {uid: r['author_type'] for uid, r in results.items()}
    enriched_rows = []
    for row in rows:
        new_row = dict(row)
        uid = row.get('userid', '').strip()
        new_row['author_type'] = identity_map.get(uid, row.get('author_type', ''))
        enriched_rows.append(new_row)
    write_csv(enriched_file, enriched_rows, list(rows[0].keys()) if rows else [])
    print(f"  原始格式(已细化) → {enriched_file}")

    # 输出3: 低置信度名单（供 Phase 2 爬主页）
    low_conf = [(uid, r) for uid, r in results.items()
                if r['confidence'] < 0.6 and r['author_type'] not in ['媒体', '官方/工作室']]
    low_conf.sort(key=lambda x: len(users[x[0]]['texts']), reverse=True)

    # 水军用户单独名单（默认不进 Phase 2，如需主页验证可手动合并）
    water_users = [(uid, r) for uid, r in results.items()
                   if '水军' in r['author_type']]
    water_users.sort(key=lambda x: len(users[x[0]]['texts']), reverse=True)

    if low_conf:
        check_file = OUTPUT_DIR / 'low_confidence_check.csv'
        with open(check_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['userid', 'author_name', 'author_type', 'dominant_stance',
                           'n_posts', 'confidence', 'evidence'])
            for uid, r in low_conf:
                u = users[uid]
                writer.writerow([uid, u['author_name'], r['author_type'],
                               get_dominant_stance(u['stances']), len(u['texts']),
                               r['confidence'], '; '.join(r['evidence'])])
        print(f"  低置信度名单 → {check_file} ({len(low_conf)} 人)")
        print(f"  提示: 运行 'python {Path(__file__).name} phase2' 可爬主页修正 {len(low_conf)} 人")
    else:
        check_file = OUTPUT_DIR / 'low_confidence_check.csv'
        check_file.write_text('userid,author_name,author_type,dominant_stance,n_posts,confidence,evidence\n', encoding='utf-8-sig')

    # 水军验证名单
    if water_users:
        water_file = OUTPUT_DIR / 'water_army_verify.csv'
        with open(water_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['userid', 'author_name', 'author_type', 'dominant_stance',
                           'n_posts', 'confidence', 'evidence'])
            for uid, r in water_users:
                u = users[uid]
                writer.writerow([uid, u['author_name'], r['author_type'],
                               get_dominant_stance(u['stances']), len(u['texts']),
                               r['confidence'], '; '.join(r['evidence'])])
        print(f"  水军验证名单 → {water_file} ({len(water_users)} 人, 跑 'python {Path(__file__).name} phase2 --water' 可爬主页复核)")
    else:
        water_file = OUTPUT_DIR / 'water_army_verify.csv'
        water_file.write_text('userid,author_name,author_type,dominant_stance,n_posts,confidence,evidence\n', encoding='utf-8-sig')

    print("\nPhase 1 完成！")
    return users, results


# ============================================================
# Phase 2 主流程
# ============================================================

def _autosave_results(results, refined_detail):
    """每批次自动保存 Phase 2 结果，防止中途崩溃丢数据"""
    if not results:
        return
    # 1. 保存 Phase 2 爬取详情
    tmp_file = OUTPUT_DIR / 'user_identity_homepage_refined.csv'
    write_csv(tmp_file, results, list(results[0].keys()))
    # 2. 更新 v3 用户详情
    v3_file = OUTPUT_DIR / 'user_identity_v3.csv'
    if v3_file.exists():
        v3_rows = load_csv(str(v3_file))
        for row in v3_rows:
            uid = row.get('userid', '').strip()
            if uid in refined_detail:
                row['author_type'] = refined_detail[uid]['author_type']
                row['confidence'] = refined_detail[uid]['confidence']
                row['evidence'] = refined_detail[uid]['evidence']
                row['needs_homepage'] = 'N'
        write_csv(v3_file, v3_rows, list(v3_rows[0].keys()))
    # 3. 更新 enriched CSV
    enriched_file = Path(find_input_csv()).parent / 'final_predicted_data_enriched.csv'
    if enriched_file.exists():
        enr_rows = load_csv(str(enriched_file))
        for row in enr_rows:
            uid = row.get('userid', '').strip()
            if uid in refined_detail:
                row['author_type'] = refined_detail[uid]['author_type']
        write_csv(enriched_file, enr_rows, list(enr_rows[0].keys()))


def run_phase2(input_csv, include_water=False):
    global COOKIE
    if not COOKIE or not COOKIE.strip():
        COOKIE = os.environ.get('WEIBO_COOKIE', '')

    if not COOKIE or COOKIE.strip() == "":
        print("\n" + "=" * 60)
        print("错误：请先设置 COOKIE")
        print("=" * 60)
        print("\n获取方式：")
        print("  1. 浏览器打开 https://weibo.com 并登录")
        print("  2. F12 → Network → 任意请求 → Request Headers")
        print("  3. 复制完整的 Cookie 值")
        print("  4. 打开本脚本，粘贴到顶部的 COOKIE = \"...\"")
        print("\n然后重新运行:")
        print("  python weibo_user_identity.py phase2            # 低置信度用户")
        print("  python weibo_user_identity.py phase2 --water    # 低置信度 + 水军全部")
        return

    # 加载 Phase 1 结果
    detail_file = OUTPUT_DIR / 'user_identity_v3.csv'
    if not detail_file.exists():
        print("请先运行 Phase 1")
        return

    # 选择爬取名单
    if include_water:
        # 合并低置信度 + 水军
        check_file = OUTPUT_DIR / 'low_confidence_check.csv'
        water_file = OUTPUT_DIR / 'water_army_verify.csv'
        seen_uids = set()
        crawl_users = []
        for f in [check_file, water_file]:
            if f.exists() and f.stat().st_size > 50:
                with open(f, 'r', encoding='utf-8-sig') as fh:
                    for row in csv.DictReader(fh):
                        uid = row['userid']
                        if uid not in seen_uids:
                            seen_uids.add(uid)
                            crawl_users.append(row)
        if not crawl_users:
            print("没有需要爬取的用户")
            return
    else:
        check_file = OUTPUT_DIR / 'low_confidence_check.csv'
        if not check_file.exists() or check_file.stat().st_size < 50:
            print("没有需要爬取的用户（所有用户置信度 ≥ 0.6）")
            print("提示: 运行 'python weibo_user_identity.py phase2 --water' 可一并验证水军")
            return
        crawl_users = []
        with open(check_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                crawl_users.append(row)

    print("=" * 60)
    print("Phase 2: 主页爬取 + 精细化分类")
    if include_water:
        print("模式: 低置信度 + 水军验证")
    print("=" * 60)

    print(f"\n待爬取: {len(crawl_users)} 人")
    print(f"延迟: {MIN_DELAY}-{MAX_DELAY}s/请求, 每{BATCH_SIZE}人休息{BATCH_REST}s\n")

    # 加载 Phase 1 分类结果
    prev_results = {}
    with open(detail_file, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            prev_results[row['userid']] = {
                'author_type': row['author_type'],
                'confidence': float(row['confidence']),
                'evidence': row['evidence'].split('; ') if row['evidence'] else [],
            }

    results = []
    errors = []
    refined_count = 0
    refined_detail = {}  # uid → {author_type, confidence, evidence} 供回写用

    for i, user in enumerate(crawl_users):
        uid = user['userid']
        uname = user['author_name']
        old_type = user['author_type']
        pct = (i + 1) / len(crawl_users) * 100
        print(f"[{i+1}/{len(crawl_users)} ({pct:.0f}%)] {uname} (当前: {old_type})")

        # 爬资料
        profile = crawl_profile_info(uid)
        if profile:
            print(f"  [OK] 资料: {profile['followers_count']}粉丝, "
                  f"bio={safe_str(profile['description'])}")
        else:
            print(f"  [FAIL] 资料获取失败")

        # 爬帖子
        posts = crawl_recent_posts(uid, max_pages=3)
        print(f"  [OK] 帖子: {len(posts)}条")

        # 修正
        prev = prev_results.get(uid, {'author_type': old_type, 'confidence': 0.5, 'evidence': []})
        new_type, new_conf, new_ev = refine_with_homepage(
            prev['author_type'], prev['confidence'], prev['evidence'], profile, posts
        )

        if new_type != old_type:
            refined_count += 1
            print(f"  → {old_type} → {new_type} (修正)")
        else:
            print(f"  → {new_type} (维持, 置信度: {new_conf})")

        if new_ev:
            for e in new_ev[-3:]:
                print(f"     └ {e}")

        results.append({
            'userid': uid, 'author_name': uname,
            'author_type_before': old_type,
            'author_type_after': new_type,
            'was_refined': 'Y' if new_type != old_type else 'N',
            'confidence': new_conf,
            'evidence': '; '.join(new_ev),
            'profile_bio': (profile or {}).get('description', ''),
            'profile_followers': (profile or {}).get('followers_count', 0),
            'profile_friends': (profile or {}).get('friends_count', 0),
            'profile_statuses': (profile or {}).get('statuses_count', 0),
            'profile_verified': (profile or {}).get('verified', False),
            'recent_posts_count': len(posts),
        })
        refined_detail[uid] = {
            'author_type': new_type,
            'confidence': str(new_conf),
            'evidence': '; '.join(new_ev),
        }

        if not profile:
            errors.append(uid)

        if (i + 1) % BATCH_SIZE == 0:
            print(f"\n  --- 批次完成 ({i+1}/{len(crawl_users)})，休息 {BATCH_REST}s，自动保存中... ---")
            _autosave_results(results, refined_detail)
            time.sleep(BATCH_REST)

    # 最终保存
    _autosave_results(results, refined_detail)

    # 输出
    print(f"\n{'='*60}")
    print(f"Phase 2 完成！成功: {len(results) - len(errors)}, 失败: {len(errors)}, 修正: {refined_count}")

    if not results:
        print("  无有效爬取结果，跳过输出")
        return

    result_file = OUTPUT_DIR / 'user_identity_homepage_refined.csv'
    with open(result_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"  主页修正结果 → {result_file}")

    final_counts = Counter(r['author_type_after'] for r in results)
    print(f"\n  修正后分布:")
    for t, c in final_counts.most_common():
        print(f"    {t}: {c}")

    # 将修正结果合并回 enriched CSV
    enriched_file = input_csv.parent / 'final_predicted_data_enriched.csv'
    if enriched_file.exists():
        rows = load_csv(str(enriched_file))
        for row in rows:
            uid = row.get('userid', '').strip()
            if uid in refined_detail:
                row['author_type'] = refined_detail[uid]['author_type']
        write_csv(enriched_file, rows, list(rows[0].keys()) if rows else [])
        print(f"  已更新 enriched CSV → {enriched_file}")

    # 回写 user_identity_v3.csv：同步 author_type + confidence + evidence
    v3_file = OUTPUT_DIR / 'user_identity_v3.csv'
    if v3_file.exists():
        v3_rows = load_csv(str(v3_file))
        for row in v3_rows:
            uid = row.get('userid', '').strip()
            if uid in refined_detail:
                d = refined_detail[uid]
                row['author_type'] = d['author_type']
                row['confidence'] = d['confidence']
                row['evidence'] = d['evidence']
                row['needs_homepage'] = 'N'
        write_csv(v3_file, v3_rows, list(v3_rows[0].keys()) if v3_rows else [])
        print(f"  已更新 v3 CSV(含evidence) → {v3_file}")


# ============================================================
# Main
# ============================================================

def main():
    global COOKIE
    # 解析参数
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = [a for a in sys.argv[1:] if a.startswith('-')]

    if '--help' in flags or '-h' in flags:
        print(__doc__)
        return

    # 找输入文件
    csv_path = None
    for a in args:
        if a not in ('phase2', 'all') and Path(a).exists():
            csv_path = Path(a)
            break
    if csv_path is None:
        csv_path = find_input_csv()

    include_water = '--water' in flags
    phase1_only = 'phase1' in args
    phase2_only = 'phase2' in args

    if phase2_only:
        # 只跑 Phase 2
        run_phase2(csv_path, include_water=include_water)
    elif phase1_only:
        # 只跑 Phase 1
        run_phase1(csv_path)
    else:
        # 默认：Phase 1 → 自动接 Phase 2（无Cookie则跳过）
        run_phase1(csv_path)
        cookie = COOKIE or os.environ.get('WEIBO_COOKIE', '')
        if cookie and cookie.strip():
            COOKIE = cookie
            run_phase2(csv_path, include_water=include_water)
        else:
            print("\n" + "=" * 60)
            print("提示: 设置 COOKIE 后重新运行可自动爬主页验证")
            print("  1. 浏览器登录 weibo.com → F12 → Network → 复制 Cookie")
            print("  2. 粘贴到脚本顶部 COOKIE = \"...\"")
            print("  3. 再次运行: python weibo_user_identity.py")
            print("=" * 60)


if __name__ == '__main__':
    main()
