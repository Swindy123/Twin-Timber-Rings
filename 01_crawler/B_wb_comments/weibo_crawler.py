import requests
import pandas as pd
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ============ 配置区 ============
# Cookie 优先从文件或环境变量加载，避免使用过期的硬编码值
COOKIES = {}

# 方式1：从环境变量读取单独的 SUB 值
sub_cookie = os.getenv('WEIBO_SUB', '').strip()
if sub_cookie:
    COOKIES['SUB'] = sub_cookie

# 方式2：从 weibo_cookies.json 文件加载（如果存在）
COOKIES_FILE = Path(__file__).parent / 'weibo_cookies.json'
if COOKIES_FILE.exists():
    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            loaded_cookies = json.load(f)
            if isinstance(loaded_cookies, dict):
                COOKIES.update({k: v for k, v in loaded_cookies.items() if k != 'timestamp' and v is not None})
            print(f"✓ 已加载 Cookie 文件: {COOKIES_FILE}")
    except Exception as e:
        print(f"⚠️  加载 Cookie 文件失败: {e}")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://weibo.com',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

TARGET_POSTS_SOURCE_FILE = Path(__file__).parent / 'weibo_posts_filtered.csv'


def load_target_posts(source_file):
    """从筛选后的微博列表加载目标帖子。"""
    url_to_mid = {
        'https://weibo.com/2378564111/PCHIMeFYl?refer_flag=1001030103_': '5192245323497937',
        'https://weibo.com/5661606921/PCEq9jMwg?refer_flag=1001030103_': '5192118454714744',
        'https://weibo.com/6275217849/PDx46tDEA?refer_flag=1001030103_': '5194218987063944',
        'https://weibo.com/1642591402/PCKZUqOol?refer_flag=1001030103_': '5192371266390237',
        'https://weibo.com/5660519061/PCHoqEwgU?refer_flag=1001030103_': '5192232709657176',
        'https://weibo.com/5663510996/PD2GmrH36?refer_flag=1001030103_': '5193051066600340',
        'https://weibo.com/2318910945/PCTeog9vm?refer_flag=1001030103_': '5192687763849788',
        'https://weibo.com/6004281123/PCG2YsT1r?refer_flag=1001030103_': '5192180966884693',
        'https://weibo.com/2318910945/PCJvL2e09?refer_flag=1001030103_': '5192314130530481',
        'https://weibo.com/1700720163/PCLqQy1uw?refer_flag=1001030103_': '5192387968108888',
        'https://weibo.com/6004281123/PCGasen3b?refer_flag=1001030103_': '5192185603425201',
        'https://weibo.com/1428471193/PCLX0wRe9?refer_flag=1001030103_': '5192407907831105',
        'https://weibo.com/5523180767/QyoyUhpqx?refer_flag=1001030103_': '5281975724149321',
        'https://weibo.com/7307411548/PDvTJbrYr?refer_flag=1001030103_': '5194174112729143',
        'https://weibo.com/6301725233/PCPXJCW65?refer_flag=1001030103_': '5192562119279793',
        'https://weibo.com/5523180767/PDDB4bPSD?refer_flag=1001030103_': '5194470062821039',
        'https://weibo.com/1682207150/PDnx6fL1X?refer_flag=1001030103_': '5193852563755709',
        'https://weibo.com/5856917412/PCH7d417Y?refer_flag=1001030103_': '5192222030957650',
        'https://weibo.com/1642591402/PCSQXmgQa?refer_flag=1001030103_': '5192673235307954',
        'https://weibo.com/7825912715/PCJgoFUax?refer_flag=1001030103_': '5192304609987365',
        'https://weibo.com/1656737654/PCGT3jsjI?refer_flag=1001030103_': '5192213254637086',
        'https://weibo.com/7647806002/PDm2kxM3D?refer_flag=1001030103_': '5193795048049561',
        'https://weibo.com/6134393125/PCGXIqDXj?refer_flag=1001030103_': '5192216146350121',
        'https://weibo.com/7487705272/PCjAsk7S8?refer_flag=1001030103_': '5191317604796824',
        'https://weibo.com/2816167560/PCHtrm8im?refer_flag=1001030103_': '5192235815275106',
        'https://weibo.com/1501563482/PD2C57QbW?refer_flag=1001030103_': '5193048411868924',
        'https://weibo.com/2522098777/PCM2Vc1hW?refer_flag=1001030103_': '5192411572864892',
        'https://weibo.com/6694120511/PCLrWfllV?refer_flag=1001030103_': '5192388643657003',
        'https://weibo.com/6258043573/PD2J6l6lU?refer_flag=1001030103_': '5193052765029310',
        'https://weibo.com/8003149388/PCDzdyupE?refer_flag=1001030103_': '5192085638220062',
        'https://weibo.com/6004281123/PCHzpCcG5?refer_flag=1001030103_': '5192239519105201',
        'https://weibo.com/1619056353/PCH10rKIl?refer_flag=1001030103_': '5192218186614429',
        'https://weibo.com/6592462760/PCIb9yZNH?refer_flag=1001030103_': '5192262918340717',
        'https://weibo.com/5951921607/PCGOMvuRn?refer_flag=1001030103_': '5192210607506797',
        'https://weibo.com/6179161260/PCI6loSFT?refer_flag=1001030103_': '5192259935930045',
        'https://weibo.com/6134393125/PCIxHyu7Y?refer_flag=1001030103_': '5192276898218966',
        'https://weibo.com/7745058738/PCIjC7koJ?refer_flag=1001030103_': '5192268161746709',
        'https://weibo.com/6275217849/PCKOP9bDp?refer_flag=1001030103_': '5192364392189679',
        'https://weibo.com/7874002693/PCGGdf2GU?refer_flag=1001030103_': '5192205293585268',
        'https://weibo.com/2099868183/PCp1De86N?refer_flag=1001030103_': '5191526653367765',
        'https://weibo.com/7883519618/PDk6FiNGG?refer_flag=1001030103_': '5193720854480906',
        'https://weibo.com/6867350206/PCQzNcHaF?refer_flag=1001030103_': '5192585713025889',
        'https://weibo.com/7647806002/PDsfrlnDp?refer_flag=1001030103_': '5194033815095743',
        'https://weibo.com/6275217849/PDxr7iVHX?refer_flag=1001030103_': '5194233254511737',
    }

    encoding_candidates = ('utf-8-sig', 'utf-8', 'gb18030', 'gbk')
    last_error = None
    for encoding in encoding_candidates:
        try:
            with open(source_file, 'r', encoding=encoding, newline='') as f:
                reader = pd.read_csv(f)
            if reader.empty:
                return []
            reader.columns = [column.strip().lstrip('\ufeff') for column in reader.columns]
            target_posts = []
            for _, row in reader.iterrows():
                url = str(row.get('url', '')).strip()
                if not url:
                    continue
                mid = url_to_mid.get(url)
                if not mid:
                    print(f"⚠️  未找到对应 mid，已跳过: {url}")
                    continue
                keyword = str(row.get('keyword', '')).strip() or '筛选后目标'
                target_posts.append((mid, keyword, url))
            return target_posts
        except Exception as exc:
            last_error = exc
    print(f"⚠️  加载筛选目标失败，将使用空目标列表: {last_error}")
    return []


# 目标帖子列表 (mid, source_keyword, source_url)
TARGET_POSTS = load_target_posts(TARGET_POSTS_SOURCE_FILE)

COMMENT_FLOWS = (0, 1)
MAX_COMMENTS_PER_POST = 3000
OUTPUT_FILE = Path(__file__).parent / 'weibo_comments_raw.csv'
STATE_FILE = Path(__file__).parent / 'weibo_crawl_state.json'


def load_existing_comments(output_path):
    """加载已存在的 CSV，便于断点续爬时去重。"""
    if not output_path.exists():
        return []
    try:
        df = pd.read_csv(output_path)
        if df.empty:
            return []
        return df.to_dict('records')
    except Exception as e:
        print(f"⚠️  读取已有CSV失败，将从头保存: {e}")
        return []


def save_comments_to_csv(records, output_path):
    """将当前已采集记录写入 CSV 快照。"""
    if not records:
        return
    try:
        existing_records = load_existing_comments(output_path)
        combined_records = existing_records + list(records)
        df = pd.DataFrame(combined_records)
        output_columns = [
            'comment_id',
            'source_post_id',
            'source_post_url',
            'comment_time',
            'user_name',
            'comment_text',
            'like_count',
            'reply_count',
            'crawl_time',
        ]
        for column in output_columns:
            if column not in df.columns:
                df[column] = ''
        df = df[output_columns]
        if 'comment_id' in df.columns:
            df = df.drop_duplicates(subset=['comment_id'], keep='first')
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
    except Exception as e:
        print(f"⚠️  保存CSV失败: {e}")


def load_crawl_state():
    """读取断点状态文件。"""
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            return state if isinstance(state, dict) else {}
    except Exception as e:
        print(f"⚠️  读取断点状态失败，将从头续爬: {e}")
        return {}


def save_crawl_state(state):
    """保存断点状态文件。"""
    try:
        payload = dict(state)
        payload['updated_at'] = datetime.now().isoformat()
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  保存断点状态失败: {e}")


def extract_post_uid(source_url):
    """从微博链接中提取发博用户UID"""
    try:
        parsed = urlparse(source_url)
        path_parts = [part for part in parsed.path.split('/') if part]
        if len(path_parts) >= 2:
            return path_parts[0]
    except Exception:
        pass
    return ''

def fetch_comments_api(mid, max_id=None, flow=0):
    """
    获取评论数据 - 使用游标分页而非page参数
    """
    url = 'https://weibo.com/ajax/statuses/buildComments'
    params = {
        'is_reload': 1,
        'id': mid,
        'is_show_bulletin': 2,
        'flow': flow,
        'count': 20,  # 单次拉20条
        'uid': '',
        'fetch_level': 0,
        'locale': 'zh-CN'
    }
    if max_id:
        params['max_id'] = max_id
    
    last_error = None
    for attempt in range(3):
        try:
            res = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=15)

            # 检查HTTP状态码
            if res.status_code == 401 or res.status_code == 403:
                print(f"❌ 认证失败 (HTTP {res.status_code})，请更新SUB值")
                print(f"   获取方式：打开 https://weibo.com -> F12 -> Application -> Cookies -> 复制SUB值")
                return None

            # 尝试解析JSON
            try:
                data = res.json()
            except json.JSONDecodeError:
                print(f"❌ 响应格式错误，可能需要重新登录。响应内容: {res.text[:100]}")
                return None

            if data.get('ok') == 1:
                return data
            else:
                if data.get('ok') == -100:
                    login_url = data.get('url', 'https://weibo.com/login.php')
                    print("❌ Cookie 已失效或未登录，微博返回登录跳转")
                    print(f"   登录地址: {login_url}")
                else:
                    msg = data.get('msg')
                    if msg:
                        print(f"❌ API返回异常: {msg}")
                    else:
                        print(f"❌ API返回异常: {data}")
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionResetError) as e:
            last_error = e
            if attempt < 2:
                print(f"⚠️  请求失败，正在重试({attempt + 1}/3): {e}")
                time.sleep(2)
                continue
            break
        except Exception as e:
            last_error = e
            break
        
    if isinstance(last_error, requests.exceptions.Timeout):
        print(f"⚠️  请求超时，跳过此请求")
        return None
    if last_error is not None:
        print(f"❌ 请求出错: {last_error}")
    return None

SUB_COMMENT_FLOWS = (1, 0)


def fetch_sub_comments_api(comment_id, source_uid, max_id=0, flow=1):
    """获取单条主评论下被折叠的子评论"""
    url = 'https://weibo.com/ajax/statuses/buildComments'
    params = {
        'is_reload': 1,
        'id': comment_id,
        'is_show_bulletin': 2, 
        'is_mix': 1,
        'fetch_level': 1,
        'flow': flow,
        'count': 20,
        'uid': source_uid,
        'max_id': max_id,
        'locale': 'zh-CN'
    }

    last_error = None
    for attempt in range(3):
        try:
            res = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=15)

            if res.status_code == 401 or res.status_code == 403:
                print(f"❌ 认证失败 (HTTP {res.status_code})，请更新SUB值")
                print(f"   获取方式：打开 https://weibo.com -> F12 -> Application -> Cookies -> 复制SUB值")
                return None

            try:
                data = res.json()
            except json.JSONDecodeError:
                print(f"❌ 子评论响应格式错误。响应内容: {res.text[:100]}")
                return None

            if data.get('ok') == 1:
                return data

            if data.get('ok') == -100:
                login_url = data.get('url', 'https://weibo.com/login.php')
                print("❌ Cookie 已失效或未登录，微博返回登录跳转")
                print(f"   登录地址: {login_url}")
            else:
                msg = data.get('msg')
                if msg:
                    print(f"❌ 子评论API返回异常: {msg}")
                else:
                    print(f"❌ 子评论API返回异常: {data}")
            return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionResetError) as e:
            last_error = e
            if attempt < 2:
                print(f"⚠️  子评论请求失败，正在重试({attempt + 1}/3): {e}")
                time.sleep(2)
                continue
            break
        except Exception as e:
            last_error = e
            break

    if isinstance(last_error, requests.exceptions.Timeout):
        print(f"⚠️  子评论请求超时，跳过此请求")
        return None
    if last_error is not None:
        print(f"❌ 子评论请求出错: {last_error}")
    return None

def get_author_type(user_info):
    """判断作者类型"""
    if user_info.get('verified'):
        return 'verified_user'  # 认证用户
    elif user_info.get('followers_count', 0) > 10000:
        return 'big_v'  # 大V
    else:
        return 'user'

def flatten_comment_item(item, source_post_id, source_url, collector_name, parent_comment=None, comment_level=1):
    """将单条评论或回复转换为标准记录"""
    user = item.get('user', {})
    reply_comment = item.get('reply_comment') or {}

    parent_id = ''
    parent_author = ''
    if reply_comment:
        parent_id = str(reply_comment.get('idstr') or reply_comment.get('id') or '')
        parent_author = (reply_comment.get('user') or {}).get('screen_name', '')
    elif parent_comment:
        parent_id = parent_comment.get('comment_id', '')
        parent_author = parent_comment.get('author', '')

    comment_id = item.get('idstr') or str(item.get('id', ''))
    root_comment_id = item.get('rootidstr') or item.get('rootid') or (parent_comment.get('root_comment_id') if parent_comment else '') or comment_id

    return {
        "comment_id": comment_id,
        "source_post_id": source_post_id,
        "source_post_url": source_url,
        "comment_time": item.get('created_at', ''),
        "user_name": user.get('screen_name', '').strip(),
        "comment_text": item.get('text_raw', '').replace('\n', ' ').strip(),
        "like_count": item.get('like_count', item.get('like_counts', 0)),
        "reply_count": item.get('total_number', 0),
        "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "parent_comment_id": parent_id,
        "parent_author": parent_author,
        "root_comment_id": str(root_comment_id),
        "floor_comment_id": str(root_comment_id),
        "comment_level": comment_level,
        "reply_total_number": item.get('total_number', 0),
        "author_type": get_author_type(user),
    }

def fetch_all_sub_comments(parent_comment_record, source_uid, source_post_id, source_url, collector_name):
    """抓取某条主评论下所有折叠回复"""
    parent_comment_id = parent_comment_record.get('comment_id')
    if not parent_comment_id:
        return []

    all_sub_comments = []
    seen_comment_ids = set()

    for flow in SUB_COMMENT_FLOWS:
        seen_max_ids = set()
        max_id = 0

        while True:
            print(f"  → 正在抓取子评论 parent={parent_comment_id} flow={flow} max_id={max_id}", flush=True)
            if max_id in seen_max_ids:
                break
            seen_max_ids.add(max_id)

            try:
                data = fetch_sub_comments_api(parent_comment_id, source_uid, max_id=max_id, flow=flow)
            except KeyboardInterrupt:
                print("\n⚠️  收到中断信号，停止当前子评论抓取并返回已采集内容")
                return all_sub_comments
            if not data:
                break

            comments, next_max_id = process_comment_data(
                data,
                source_post_id,
                source_url,
                collector_name,
                parent_comment=parent_comment_record,
                comment_level=2,
                allow_nested_fetch=True,
            )

            for comment in comments:
                comment_id = comment.get('comment_id')
                if comment_id and comment_id in seen_comment_ids:
                    continue
                if comment_id:
                    seen_comment_ids.add(comment_id)
                all_sub_comments.append(comment)

            if not next_max_id:
                break

            if next_max_id == max_id:
                break

            max_id = next_max_id
            time.sleep(1)

    return all_sub_comments

def process_comment_data(data, source_post_id, source_url, collector_name, parent_comment=None, comment_level=1, allow_nested_fetch=True):
    """处理返回的评论数据"""
    comments_list = []
    if not data or 'data' not in data:
        return comments_list, None

    def append_item_and_replies(item, parent_comment=None, comment_level=1):
        try:
            record = flatten_comment_item(item, source_post_id, source_url, collector_name, parent_comment, comment_level)
            comments_list.append(record)

            if allow_nested_fetch:
                child_comments = item.get('comments') or []
                for child in child_comments:
                    append_item_and_replies(child, parent_comment=record, comment_level=comment_level + 1)
        except Exception as e:
            print(f"处理单条评论出错: {e}")

    if parent_comment is not None:
        for item in data['data']:
            append_item_and_replies(item, parent_comment=parent_comment, comment_level=comment_level)
    else:
        for item in data['data']:
            append_item_and_replies(item)
    
    # 返回下一页游标
    next_max_id = data.get('max_id')
    return comments_list, next_max_id

def fetch_all_comments(mid, source_keyword, source_url, collector_name, target_count=None, resume_state=None, progress_callback=None):
    """
    批量获取某条微博的所有评论
    """
    all_comments = []
    seen_comment_ids = set()
    request_count = 0
    source_uid = extract_post_uid(source_url)

    flow_state = (resume_state or {}).get('flow_state', {})

    for flow in COMMENT_FLOWS:
        max_id = flow_state.get(str(flow), {}).get('max_id')
        seen_max_ids = set()
        if max_id is not None:
            print(f"↪ 从断点继续 flow={flow} max_id={max_id}", flush=True)

        while target_count is None or len(all_comments) < target_count:
            print(f"→ 正在抓取一级评论 mid={mid} flow={flow} max_id={max_id or 0}", flush=True)
            if max_id in seen_max_ids:
                break
            seen_max_ids.add(max_id)

            try:
                data = fetch_comments_api(mid, max_id, flow=flow)
            except KeyboardInterrupt:
                print("\n⚠️  收到中断信号，停止当前微博抓取并返回已采集内容")
                return all_comments if target_count is None else all_comments[:target_count]
            if not data:
                break

            comments, next_max_id = process_comment_data(data, mid, source_url, collector_name)

            new_comments = []
            for comment in comments:
                comment_id = comment.get('comment_id')
                if comment_id and comment_id in seen_comment_ids:
                    continue
                if comment_id:
                    seen_comment_ids.add(comment_id)
                new_comments.append(comment)

            all_comments.extend(new_comments)

            hidden_replies = []
            for comment in new_comments:
                if comment.get('comment_level') != 1:
                    continue
                reply_total_number = int(comment.get('reply_total_number') or 0)
                if reply_total_number <= len([item for item in comments if item.get('parent_comment_id') == comment.get('comment_id')]):
                    continue
                print(f"→ 展开楼层回复 comment_id={comment.get('comment_id')} total={reply_total_number}", flush=True)
                hidden_replies.extend(fetch_all_sub_comments(comment, source_uid, mid, source_url, collector_name))

            for reply in hidden_replies:
                comment_id = reply.get('comment_id')
                if comment_id and comment_id in seen_comment_ids:
                    continue
                if comment_id:
                    seen_comment_ids.add(comment_id)
                all_comments.append(reply)

            if target_count is not None and len(all_comments) >= target_count:
                all_comments = all_comments[:target_count]
                if progress_callback:
                    progress_callback(all_comments)
                flow_state[str(flow)] = {
                    'max_id': next_max_id,
                    'done': False,
                }
                save_crawl_state({
                    'mid': mid,
                    'flow_state': flow_state,
                })
                print(f"✓ 已达到单微博上限 {target_count} 条，停止当前微博采集", flush=True)
                return all_comments

            request_count += 1
            print(f"✓ 已采集 {len(all_comments)} 条评论/回复 (flow={flow}, 第{request_count}次请求)")

            if progress_callback:
                progress_callback(all_comments)

            flow_state[str(flow)] = {
                'max_id': next_max_id,
                'done': False,
            }
            save_crawl_state({
                'mid': mid,
                'flow_state': flow_state,
            })

            if not next_max_id:
                flow_state[str(flow)] = {
                    'max_id': None,
                    'done': True,
                }
                save_crawl_state({
                    'mid': mid,
                    'flow_state': flow_state,
                })
                break  # 没有更多评论了

            if next_max_id == max_id:
                break

            max_id = next_max_id
            time.sleep(2)  # 防止被限流

    return all_comments if target_count is None else all_comments[:target_count]

def main():
    """主函数"""
    print("\n" + "="*60)
    print("微博评论爬虫 v1.0")
    print("="*60)
    
    # 检查Cookie配置
    if not COOKIES.get('SUB'):
        print("\n❌ 错误：未检测到有效的 SUB Cookie")
        print("\n请按照以下步骤获取 Cookie：")
        print("  1. 打开浏览器访问 https://weibo.com 并登录")
        print("  2. 按 F12 打开开发者工具")
        print("  3. 切换到 Application 标签")
        print("  4. 左侧选择 Cookies -> weibo.com")
        print("  5. 找到名为 'SUB' 的条目，复制其 Value 值")
        print("  6. 粘贴到脚本中的 COOKIES['SUB'] 中")
        print("\n也可以先运行 get_cookies.py 或 setup_cookies.py 生成 weibo_cookies.json")
        print("   然后重新运行 weibo_crawler.py")
        return
    
    print(f"✓ 已检测到 Cookie，准备开始采集")
    print(f"✓ 目标微博数: {len(TARGET_POSTS)}\n")
    
    all_results = load_existing_comments(OUTPUT_FILE)
    existing_ids = {row.get('comment_id') for row in all_results if row.get('comment_id')}
    if all_results:
        print(f"↪ 检测到已有CSV，已加载 {len(all_results)} 条历史数据，准备续爬")

    resume_state = load_crawl_state()

    resume_mid = str(resume_state.get('mid') or '') if resume_state else ''
    start_index = 0
    if resume_mid:
        for index, (mid, _, _) in enumerate(TARGET_POSTS):
            if str(mid) == resume_mid:
                start_index = index
                break

    if resume_mid and start_index > 0:
        print(f"↪ 断点对应微博 mid={resume_mid}，将从目标列表第 {start_index + 1} 条继续采集")
    elif resume_mid and start_index == 0 and TARGET_POSTS and str(TARGET_POSTS[0][0]) != resume_mid:
        print(f"↪ 断点微博 mid={resume_mid} 不在当前目标列表中，将从头开始采集")

    for mid, keyword, url in TARGET_POSTS[start_index:]:
        if resume_mid and str(mid) == resume_mid:
            local_resume = resume_state or {}
        else:
            local_resume = {}
        print(f"\n{'='*60}")
        print(f"开始采集: {keyword}")
        print(f"微博ID: {mid}")
        print(f"{'='*60}")
        base_results = list(all_results)

        def save_current_snapshot(current_comments):
            save_comments_to_csv(base_results + current_comments, OUTPUT_FILE)

        comments = fetch_all_comments(
            mid,
            keyword,
            url,
            collector_name="数据爬虫",
            target_count=MAX_COMMENTS_PER_POST,
            resume_state=local_resume,
            progress_callback=save_current_snapshot,
        )
        new_comments = []
        for row in comments:
            comment_id = row.get('comment_id')
            if comment_id and comment_id in existing_ids:
                continue
            if comment_id:
                existing_ids.add(comment_id)
            new_comments.append(row)
        all_results.extend(new_comments)
        print(f"✓ 本批采集完成，新增 {len(new_comments)} 条，累计 {len(all_results)} 条")
        time.sleep(3)  # 不同帖子间隔
    
    # 保存到CSV
    if all_results:
        save_comments_to_csv(all_results, OUTPUT_FILE)
        if STATE_FILE.exists():
            try:
                STATE_FILE.unlink()
            except Exception:
                pass
        print(f"\n{'='*60}")
        print(f"✓ 完成！共采集 {len(all_results)} 条评论")
        print(f"✓ 文件已保存: {OUTPUT_FILE}")
        print(f"{'='*60}\n")
    else:
        print("\n❌ 没有采集到数据，请检查以下几点：")
        print("  1. SUB Cookie 是否有效和最新")
        print("  2. 微博ID (mid) 是否正确")
        print("  3. 网络连接是否正常")

if __name__ == '__main__':
    main()
