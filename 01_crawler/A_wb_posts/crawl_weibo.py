import os
import random
import re
import time
from datetime import datetime
from urllib.parse import quote, unquote

import pandas as pd
import requests
from bs4 import BeautifulSoup

# 请求头
headers = {
    "User-Agent": "Mozilla/5.0",
    "Cookie": "SCF=ApM6m8JVnRPBk4HBak7OWVuVpEqb-dPzz9qn07ObTv0wISny_uUKr5rKxHokbdtUKd8NTZ40KJ1GqEN_-W2gHwA.; PC_TOKEN=6c39765add; ALF=1783267099; SUB=_2A25HJoJLDeRhGeFG71QT-SfEyj6IHXVkXZuDrDV8PUJbkNAbLRTfkW1NeWWrrzuTelOOOE8fnGmD7FaDRSxhTKg2; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WWuceBxZYDKXA_16lD_TAJ15JpX5KMhUgL.FoMRShqE1K.ReKz2dJLoIXWki--ciKL8iKLhi--RiKyhi-zci--fi-z7iK.pi--fiKnci-z7i--Xi-iWiK.Xi--fiKnRiKnci--Ni-z0iK.c; XSRF-TOKEN=cYGLsiTRtNverYDUdQpBiOAb; WBPSESS=5YbI5mYNhPWsX1nuUxy76hsJqLD9PURNlEHhLkeXZFjFRcg99V6w6pyCLEKVwTEPfgTzGq6kvu7VkthD0yWalUUilXMXVT45YjorcJdfJ0LZiND8XQXa3j6c3_pznN7NF7t_mLLTDHa8T_FOrZK4rw==; _s_tentry=weibo.com; Apache=2913157626377.407.1780675120372; SINAGLOBAL=2913157626377.407.1780675120372; ULV=1780675120374:1:1:1:2913157626377.407.1780675120372:"
}

# 关键词及爬取页数（核心词拉满至 50 页，贴近微博搜索上限）
KEYWORD_PAGES = {
    # 核心事件
    "年轮 原唱": 50,
    "年轮原唱之争": 50,
    "年轮 版权": 50,
    "年轮 授权": 50,
    "年轮 翻唱": 50,
    "年轮 双原唱": 50,
    "年轮 唯一原唱": 50,
    "年轮 争议": 50,
    "唯一原唱": 40,
    "双原唱": 40,
    "年轮 演唱权": 40,
    "年轮 回应": 40,
    "年轮 声明": 40,
    "年轮 律师": 35,
    "年轮 起诉": 35,
    "年轮 抄袭": 35,
    "年轮 盗用": 35,
    "年轮 蹭热度": 35,

    # 人物相关
    "张碧晨 年轮": 50,
    "汪苏泷 年轮": 50,
    "张碧晨 原唱": 40,
    "汪苏泷 原唱": 40,
    "张碧晨 汪苏泷": 40,
    "张碧晨 汪苏泷 年轮": 40,
    "张碧晨 回应": 35,
    "汪苏泷 回应": 35,
    "张碧晨 汪苏泷 版权": 35,
    "张碧晨告别年轮": 40,
    "汪苏泷收回年轮授权": 40,
    "张碧晨工作室": 30,
    "汪苏泷工作室": 30,
    "张碧晨 粉丝": 25,
    "汪苏泷 粉丝": 25,

    # 作品关联
    "花千骨 年轮": 40,
    "盗墓笔记 年轮": 40,
    "汪苏泷 花千骨": 30,
    "张碧晨 花千骨": 30,
    "花千骨 原唱": 30,

    # 旺仔小乔
    "旺仔小乔": 40,
    "旺仔小乔 年轮": 30,
    "旺仔小乔 原唱": 30,
    "旺仔小乔 张碧晨": 30,
    "旺仔小乔 汪苏泷": 30,
    "旺仔小乔 翻唱": 30,

    # 舆论讨论
    "谁才是年轮原唱": 40,
    "谁唱的年轮": 35,
    "年轮 到底是谁": 35,
    "支持张碧晨": 35,
    "支持汪苏泷": 35,
    "年轮版权争议": 40,
    "年轮事件": 40,
    "年轮热搜": 40,
    "年轮 粉丝": 30,
    "内娱 原唱": 25,
}

# 时间分片：按月爬取，同一关键词在不同时间段结果不同
# 格式 (timescope, 显示标签)，timescope 为微博 custom 参数值
TIMESCOPE_RANGES = [
    ("2025-07-01-0:2025-07-31-23", "2025-07"),
    ("2025-08-01-0:2025-08-31-23", "2025-08"),
    ("2025-09-01-0:2025-09-30-23", "2025-09")
]

MEDIA_KEYWORDS = (
    "娱乐", "新闻", "日报", "晚报", "视频", "热点", "传媒",
    "周刊", "观察", "资讯", "电视", "广播", "门户", "财经",
)
OFFICIAL_KEYWORDS = ("studio", "工作室", "官微", "官方")
MAX_RETRIES = 2
OUTPUT_FILE = "weibo_posts.csv"

OUTPUT_COLUMNS = [
    "post_id", "url", "keyword", "publish_time", "author_name",
    "userid", "author_type", "text", "repost_count", "comment_count",
    "like_count", "topic_tag", "crawl_time",
]


def userid_from_url(url):
    if url is None or (isinstance(url, float) and pd.isna(url)):
        return ""
    url = str(url)
    match = re.search(r"weibo\.com/u/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"weibo\.com/(\d+)", url)
    return match.group(1) if match else ""


def backfill_userid(df):
    if df is None or df.empty:
        return df

    df = df.copy()
    if "userid" not in df.columns:
        df["userid"] = ""

    missing = df["userid"].isna() | (
        df["userid"].astype(str).str.strip().isin(["", "nan"])
    )
    if missing.any() and "url" in df.columns:
        df.loc[missing, "userid"] = df.loc[missing, "url"].map(userid_from_url)

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    extra_cols = [col for col in df.columns if col not in OUTPUT_COLUMNS]
    return df[OUTPUT_COLUMNS + extra_cols]


def extract_userid(name_link, card):
    hrefs = []
    if name_link and name_link.get("href"):
        hrefs.append(name_link["href"])

    avator_div = card.find("div", class_="avator")
    if avator_div:
        av_link = avator_div.find("a", href=True)
        if av_link and av_link.get("href"):
            hrefs.append(av_link["href"])

    for href in hrefs:
        match = re.search(r"weibo\.com/u/(\d+)", href)
        if match:
            return match.group(1)
        match = re.search(r"weibo\.com/(\d+)", href)
        if match:
            return match.group(1)
    return ""


def parse_count(node):
    if not node:
        return 0
    text = node.get_text(" ", strip=True).replace(",", "")
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def guess_author_type(author_name):
    name_lower = author_name.lower()
    if any(keyword in name_lower for keyword in OFFICIAL_KEYWORDS):
        return "官方/工作室"
    if any(keyword in author_name for keyword in MEDIA_KEYWORDS):
        return "媒体"
    return "普通用户"


def extract_topic_tags(content):
    tags = []
    if not content:
        return tags

    for link in content.find_all("a", href=True):
        href = link["href"]
        if href.startswith("/weibo?q=%23") or "q=%23" in href:
            tag = unquote(href.split("q=")[-1]).strip("#")
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def parse_card(card, keyword, crawl_time):
    if card.get("action-type") != "feed_list_item":
        return None

    post_id = card.get("mid")
    if not post_id:
        return None

    name_link = card.find("a", class_="name")
    author_name = ""
    userid = ""
    if name_link:
        author_name = name_link.get("nick-name") or name_link.get_text(strip=True)
        userid = extract_userid(name_link, card)

    from_div = card.find("div", class_="from")
    time_link = from_div.find("a", target="_blank") if from_div else None
    publish_time = time_link.get_text(strip=True) if time_link else ""

    url = time_link.get("href", "") if time_link else ""
    if url.startswith("//"):
        url = "https:" + url
    if not userid:
        userid = userid_from_url(url)

    content = (
        card.find("p", attrs={"node-type": "feed_list_content_full"})
        or card.find("p", attrs={"node-type": "feed_list_content"})
    )
    text = content.get_text(" ", strip=True) if content else ""
    if len(text) < 5:
        return None

    # 互动数据必须取自 card-act，避免转发帖误抓嵌套原帖的转评赞
    card_act = card.find("div", class_="card-act")

    return {
        "post_id": post_id,
        "url": url,
        "keyword": keyword,
        "publish_time": publish_time,
        "author_name": author_name,
        "userid": userid,
        "author_type": guess_author_type(author_name),
        "text": text,
        "repost_count": parse_count(
            card_act.find("a", attrs={"action-type": "feed_list_forward"})
            if card_act else None
        ),
        "comment_count": parse_count(
            card_act.find("a", attrs={"action-type": "feed_list_comment"})
            if card_act else None
        ),
        "like_count": parse_count(
            card_act.find("span", class_="woo-like-count") if card_act else None
        ),
        "topic_tag": ";".join(extract_topic_tags(content)),
        "crawl_time": crawl_time,
    }


def fetch_page(url):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = random.uniform(1, 3)
                print(f"  请求失败，{wait:.1f} 秒后重试（{attempt + 1}/{MAX_RETRIES}）：{e}")
                time.sleep(wait)
    raise last_error


def build_search_url(keyword, page, timescope=None):
    url = f"https://s.weibo.com/weibo?q={quote(keyword)}&page={page}"
    if timescope:
        url += f"&timescope=custom:{timescope}"
    return url


def crawl_keyword(
    keyword, max_pages, seen_post_ids, data,
    timescope=None, timescope_label="", persist=None, get_total=None,
):
    keyword_new_count = 0
    scope_hint = f" [{timescope_label}]" if timescope_label else ""
    print(f"\n正在搜索：{keyword}{scope_hint}（共 {max_pages} 页）")

    for page in range(1, max_pages + 1):
        url = build_search_url(keyword, page, timescope)
        crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            response = fetch_page(url)
            soup = BeautifulSoup(response.text, "lxml")
            cards = soup.find_all("div", class_="card-wrap")
            page_count = 0

            print(f"  第 {page} 页找到 {len(cards)} 个卡片")

            for card in cards:
                post = parse_card(card, keyword, crawl_time)
                if not post:
                    continue
                post_id = str(post["post_id"])
                if post_id in seen_post_ids:
                    continue

                seen_post_ids.add(post_id)
                post["post_id"] = post_id
                data.append(post)
                page_count += 1
                keyword_new_count += 1

            total_hint = f"，累计 {get_total()} 条" if get_total else ""
            print(f"  第 {page} 页新增 {page_count} 条主帖{total_hint}")
            time.sleep(random.uniform(1, 3))

        except KeyboardInterrupt:
            if persist:
                persist()
            raise
        except Exception as e:
            print(f"  第 {page} 页最终失败：{e}")
        finally:
            if persist:
                persist()

    print(f"关键词「{keyword}」{scope_hint}完成：新增 {keyword_new_count} 条")
    return keyword_new_count


def save_results(data, old_df, history_count, reason="", quiet=False):
    new_df = pd.DataFrame(data, columns=OUTPUT_COLUMNS)
    session_new = len(new_df)

    if old_df is not None and not old_df.empty:
        final_df = pd.concat([old_df, new_df], ignore_index=True)
        before_dedup = len(final_df)
        final_df.drop_duplicates(subset=["post_id"], inplace=True)
        dup_count = before_dedup - len(final_df)
    elif session_new:
        final_df = new_df
        dup_count = 0
    else:
        final_df = old_df.copy() if old_df is not None else pd.DataFrame(columns=OUTPUT_COLUMNS)
        dup_count = 0

    final_df = backfill_userid(final_df)
    final_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    if not quiet:
        title = reason or "完成"
        print(f"\n{title}！已保存至 {OUTPUT_FILE}")
        print(f"历史数据：{history_count}")
        print(f"本次新增：{session_new}")
        print(f"重复过滤：{dup_count}")
        print(f"最终总数：{len(final_df)}")

    return final_df, session_new, dup_count


def main():
    data = []
    seen_post_ids = set()
    old_df = None
    history_count = 0

    if os.path.exists(OUTPUT_FILE):
        old_df = pd.read_csv(OUTPUT_FILE)
        old_df = backfill_userid(old_df)

        if "post_id" in old_df.columns:
            seen_post_ids.update(
                old_df["post_id"].astype(str)
            )

        history_count = len(old_df)
        print(
            f"发现历史数据 {history_count} 条，已加载用于断点续爬"
        )

    session_start_count = history_count

    total_pages = sum(KEYWORD_PAGES.values()) * len(TIMESCOPE_RANGES)
    print(
        f"计划爬取：{len(KEYWORD_PAGES)} 个关键词 × "
        f"{len(TIMESCOPE_RANGES)} 个时间段 × 共约 {total_pages} 页"
    )
    print("提示：每爬完一页自动保存；随时 Ctrl+C 中断，进度不丢失")

    state = {"old_df": old_df, "data": data}

    def get_total():
        base = len(state["old_df"]) if state["old_df"] is not None else 0
        return base + len(state["data"])

    def persist_progress(quiet=True):
        if not state["data"]:
            return
        state["old_df"], _, _ = save_results(
            state["data"], state["old_df"], session_start_count, quiet=quiet
        )
        state["data"].clear()

    try:
        for timescope, timescope_label in TIMESCOPE_RANGES:
            print(f"\n========== 时间段：{timescope_label} ==========")
            for keyword, max_pages in KEYWORD_PAGES.items():
                crawl_keyword(
                    keyword, max_pages, seen_post_ids, state["data"],
                    timescope=timescope, timescope_label=timescope_label,
                    persist=persist_progress, get_total=get_total,
                )

        old_df = state["old_df"]
        print(f"\n完成！数据已全部保存至 {OUTPUT_FILE}")
        print(f"启动时历史：{session_start_count}")
        print(f"本次共新增：{len(old_df) - session_start_count}")
        print(f"最终总数：{len(old_df)}")

    except KeyboardInterrupt:
        print("\n\n检测到 Ctrl+C，正在保存剩余数据...")
        if state["data"]:
            state["old_df"], _, _ = save_results(
                state["data"], state["old_df"], session_start_count,
                reason="中断保存",
            )
            state["data"].clear()
        else:
            total = len(state["old_df"]) if state["old_df"] is not None else session_start_count
            print(f"\n中断保存！已保存至 {OUTPUT_FILE}")
            print(f"最终总数：{total}")
        print("下次运行将从 weibo_posts.csv 继续。")


if __name__ == "__main__":
    main()
